"""Model backends. Each returns the visible reply AND the model's thinking text.

  TinkerBackend     open-weight models on Tinker (needs TINKER_API_KEY and billing)
  AnthropicBackend  Claude via the Anthropic API (needs ANTHROPIC_API_KEY or an `ant auth login` profile)
  ClaudeCLIBackend  Claude via headless Claude Code (`claude -p`) on the user's own login; no API key
  MockBackend    scripted agents for plumbing tests; no network, no cost
"""
import asyncio
import json
import random

# Tinker list prices, dollars per million tokens (prefill, sample).
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "Qwen/Qwen3-8B": (0.195, 0.60),
    "openai/gpt-oss-20b": (0.18, 0.45),
}
RENDERER = {
    "Qwen/Qwen3-8B": "qwen3",                       # thinking on; <think> is returned
    "openai/gpt-oss-20b": "gpt_oss_medium_reasoning",  # analysis channel is returned
}


class TinkerBackend:
    def __init__(self, model: str, max_tokens: int = 4096, temperature: float = 1.0):
        import tinker
        from tinker_cookbook import renderers
        self.tinker = tinker
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.client = tinker.ServiceClient().create_sampling_client(base_model=model)
        self.renderer = renderers.get_renderer(RENDERER[model], self.client.get_tokenizer())
        self._get_text = renderers.get_text_content

    def check_access(self):
        """One tiny call so billing or auth problems fail fast, before any market starts."""
        mi = self.renderer.build_generation_prompt([{"role": "user", "content": "Say OK."}])
        self.client.sample(mi, num_samples=1,
                           sampling_params=self.tinker.SamplingParams(max_tokens=1, temperature=0.0)).result()

    async def generate(self, messages, ctx=None) -> dict:
        model_input = self.renderer.build_generation_prompt(messages)
        resp = await self.client.sample_async(
            model_input, num_samples=1,
            sampling_params=self.tinker.SamplingParams(
                max_tokens=self.max_tokens, temperature=self.temperature,
                stop=self.renderer.get_stop_sequences()))
        seq = resp.sequences[0]
        msg, _ = self.renderer.parse_response(seq.tokens)
        content = msg["content"]
        thinking = ""
        if isinstance(content, list):
            thinking = "\n".join(p["thinking"] for p in content if p.get("type") == "thinking")
        return {
            "model": self.model,
            "text": self._get_text(msg),
            "thinking": thinking,
            "prompt_tokens": model_input.length,
            "output_tokens": len(seq.tokens),
            "stop_reason": str(seq.stop_reason),
        }


class AnthropicBackend:
    """Claude Opus 5.5, matching the v1 setup: medium effort and server-side refusal fallback.

    Claude never returns its raw chain of thought; with display "summarized" the thinking we log
    is a readable summary. That is less than the open models give, and worth saying in any
    comparison.
    """

    def __init__(self, model: str = "claude-opus-5-5", max_tokens: int = 8000, effort: str = "medium"):
        import anthropic
        self.anthropic = anthropic
        self.model = model
        self.max_tokens = max_tokens
        self.effort = effort
        self.client = anthropic.AsyncAnthropic()

    def check_access(self):
        self.anthropic.Anthropic().messages.create(
            model=self.model, max_tokens=64, output_config={"effort": "low"},
            messages=[{"role": "user", "content": "Say OK."}])

    async def generate(self, messages, ctx=None) -> dict:
        system = messages[0]["content"] if messages and messages[0]["role"] == "system" else None
        rest = messages[1:] if system is not None else messages
        resp = await self.client.beta.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=rest,
            thinking={"type": "adaptive", "display": "summarized"},
            output_config={"effort": self.effort},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        stop = str(resp.stop_reason)
        if resp.stop_reason == "refusal" and getattr(resp, "stop_details", None):
            stop = f"refusal:{resp.stop_details.category}"
        return {
            "model": self.model,
            "served_by": resp.model,  # differs from model only if the fallback ran
            "text": "".join(b.text for b in resp.content if b.type == "text"),
            "thinking": "\n".join(b.thinking for b in resp.content if b.type == "thinking"),
            "prompt_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
            "stop_reason": stop,
        }


class ClaudeCLIBackend:
    """Claude through headless Claude Code (`claude -p`), using the person's own Claude Code login.

    Tools are off and our persona replaces Claude Code's system prompt, but Claude Code still adds
    some context it won't let us remove without an API key (--bare): the account email, the working
    directory, platform, date and a token budget. Thinking happens but no thinking text comes back.
    Treat results as exploratory and say so next to any comparison.
    """

    FLAGS = ["--output-format", "json", "--tools", "", "--exclude-dynamic-system-prompt-sections",
             "--no-session-persistence", "--strict-mcp-config", "--setting-sources", ""]

    def __init__(self, model: str = "claude-opus-5-5", effort: str = "medium", workdir: str = None):
        import tempfile
        self.model = model
        self.effort = effort
        self.workdir = workdir or tempfile.mkdtemp(prefix="market_agent_")  # empty dir: no project files

    def _cmd(self, system):
        return ["claude", "-p", "--model", self.model, "--effort", self.effort, "--system-prompt", system, *self.FLAGS]

    def check_access(self):
        import subprocess
        out = subprocess.run(self._cmd("Reply with OK."), input="Say OK.", capture_output=True, text=True,
                             cwd=self.workdir, timeout=180)
        d = json.loads(out.stdout or "{}")
        if out.returncode != 0 or d.get("is_error"):
            raise RuntimeError(f"claude -p failed: {(out.stderr or out.stdout)[:300]}")

    async def generate(self, messages, ctx=None) -> dict:
        system = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
        rest = messages[1:] if system else messages
        prompt = rest[0]["content"]
        for m in rest[1:]:  # the JSON retry: fold the earlier reply into one prompt
            prompt += ("\n\nYour previous reply was:\n" + m["content"]) if m["role"] == "assistant" else ("\n\n" + m["content"])
        proc = await asyncio.create_subprocess_exec(
            *self._cmd(system), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, cwd=self.workdir)
        try:
            out, err = await proc.communicate(prompt.encode())
        except asyncio.CancelledError:  # the per-call timeout fired: don't leave the process running
            proc.kill()
            raise
        try:
            d = json.loads(out.decode() or "{}")
        except json.JSONDecodeError:
            d = {"is_error": True, "result": err.decode()[:300]}
        u = d.get("usage") or {}
        return {
            "model": self.model,
            "served_by": ",".join(d.get("modelUsage", {}) or [self.model]),
            "text": "" if d.get("is_error") else (d.get("result") or ""),
            "thinking": "",  # Claude Code doesn't return thinking text
            "prompt_tokens": u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0),
            "output_tokens": u.get("output_tokens", 0),
            "stop_reason": "error:" + str(d.get("result", ""))[:120] if d.get("is_error") else str(d.get("subtype", "success")),
            "cost_usd": d.get("total_cost_usd", 0.0),
        }


class MockBackend:
    """Scripted stand-in that uses the structured context instead of reading the prompt."""

    def __init__(self, model: str, seed: int = 0, latency: float = 0.0):
        self.model = model
        self.rng = random.Random(f"{model}-{seed}")
        self.latency = latency  # max simulated seconds per call, to test timeouts and deadlines

    def check_access(self):
        pass

    async def generate(self, messages, ctx=None) -> dict:
        ctx = ctx or {}
        r = self.rng
        if self.latency:
            await asyncio.sleep(r.uniform(0, self.latency))
        shade = {"honest": 0.0, "neutral": 0.08, "aggressive": 0.2}.get(ctx.get("framing"), 0.1)
        kind = ctx.get("kind")
        if kind == "planner":
            if ctx["role"] == "buyer":
                out = {"reports": {g: round(v * (1 - r.uniform(0, shade))) for g, v in ctx["values"].items()},
                       "explanation": "mock"}
            else:
                out = {"report": round(ctx["cost"] * (1 + r.uniform(0, shade))), "explanation": "mock"}
        elif kind == "negotiation":
            out = self._negotiate(ctx, shade)
        elif kind == "debrief":
            out = {"welfare_maximizing_action": "report the true limit", "misrepresented": shade > 0,
                   "what_was_misrepresented": "budget" if shade > 0 else ""}
        else:
            out = {}
        text = "Mock reasoning.\n" + json.dumps(out)
        if r.random() < 0.03:
            text = "I will not answer in JSON."  # exercise the retry path
        prompt_chars = sum(len(m["content"]) for m in messages)
        return {"model": self.model, "text": text, "thinking": "mock thinking " * 20,
                "prompt_tokens": prompt_chars // 4, "output_tokens": 300, "stop_reason": "stop"}

    def _negotiate(self, ctx, shade):
        r = self.rng
        view, me = ctx["view"], ctx["agent_id"]
        act = {"accept_offer_id": None, "post_offers": [], "cancel_offer_ids": [], "messages": []}
        if ctx["role"] == "buyer":
            for g in view["needs"]:
                v = ctx["values"][g]
                asks = [o for o in view["offers"] if o["side"] == "sell" and o["good"] == g and o["price"] <= v]
                if asks and r.random() < 0.6:
                    act["accept_offer_id"] = min(asks, key=lambda o: o["price"])["id"]
                    break
                act["post_offers"].append({"item": g, "price": round(v * r.uniform(0.6, 0.95))})
                claim = round(v * (1 - shade))
                act["messages"].append({"to": "ALL", "text": f"Looking for a {g}. My client's budget is ${claim} max."})
        else:
            c = ctx["cost"]
            bids = [o for o in view["offers"] if o["side"] == "buy" and o["good"] == ctx["good"] and o["price"] >= c]
            if bids and r.random() < 0.6:
                act["accept_offer_id"] = max(bids, key=lambda o: o["price"])["id"]
            else:
                act["post_offers"].append({"item": ctx["good"], "price": round(c * r.uniform(1.05, 1.5))})
                claim = round(c * (1 + shade))
                act["messages"].append({"to": "ALL", "text": f"Selling a {ctx['good']}. I can't go below ${claim}."})
        return act
