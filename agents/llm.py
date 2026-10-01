"""LLM backends. `AnthropicBackend` calls the Claude API; `MockBackend` is for
plumbing tests and dry runs (no network)."""
import json
import os
import re
from typing import Optional

from .prompts import OUTPUT_SCHEMA


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class ParseError(Exception):
    pass


def parse_agent_output(text: str) -> dict:
    """Parse the agent's JSON. Raises ParseError if action is missing/non-numeric."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise ParseError(f"no JSON object in: {text[:200]!r}")
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            raise ParseError(str(e))
    if not isinstance(data, dict) or not isinstance(data.get("action"), (int, float)):
        raise ParseError(f"bad or missing action in: {text[:200]!r}")
    if not isinstance(data.get("welfare_maximizing_report"), (int, float)):
        data["welfare_maximizing_report"] = float("nan")
    data["reasoning"] = str(data.get("reasoning", ""))
    return data


class AnthropicBackend:
    def __init__(self, model: str, effort: str = "medium", max_tokens: int = 4000):
        import anthropic
        _load_dotenv()
        self.client = anthropic.AsyncAnthropic()
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0, "served_by": {}}

    async def ask(self, system: str, user: str) -> str:
        """Return the raw response text (caller parses so parse errors get logged)."""
        resp = await self.client.beta.messages.create(
            model=self.model,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
            },
        )
        self.usage["calls"] += 1
        self.usage["input_tokens"] += resp.usage.input_tokens
        self.usage["output_tokens"] += resp.usage.output_tokens
        self.usage["served_by"][resp.model] = self.usage["served_by"].get(resp.model, 0) + 1
        if resp.stop_reason == "refusal":
            return f'{{"error": "refusal", "category": "{getattr(resp.stop_details, "category", None)}"}}'
        return next((b.text for b in resp.content if b.type == "text"), "")


class MockBackend:
    """Scripted stand-in. strategy: 'truthful' | 'shade' | 'garbage'."""

    def __init__(self, strategy: str = "truthful", shade: float = 0.2):
        self.strategy = strategy
        self.shade = shade
        self.usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}

    async def ask(self, system: str, user: str) -> str:
        self.usage["calls"] += 1
        m = re.search(r"PRIVATE (value|cost)[^0-9]*([0-9]+(?:\.[0-9]+)?)", user)
        kind, x = m.group(1), float(m.group(2))
        if self.strategy == "garbage":
            return "I refuse to answer in JSON."
        if self.strategy == "shade":
            act = x * (1 - self.shade) if kind == "value" else x * (1 + self.shade)
            why = f"Truthful would be {x:.1f}, but shading by 20% should raise my profit."
        else:
            act = x
            why = "Reporting honestly."
        return json.dumps({"action": round(act, 2), "welfare_maximizing_report": x, "reasoning": why})
