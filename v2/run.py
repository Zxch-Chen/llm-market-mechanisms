"""Run the v2 economy: {planner, negotiation} x {neutral, honest, aggressive} x seeds.

  python -m v2.run --backend mock                       # plumbing test, free
  python -m v2.run --backend tinker                     # the pilot: seeds 0 and 1 (needs TINKER_API_KEY + billing)
  python -m v2.run --backend tinker --seeds 0 1 2 3 4 5 --deadline-min 90

All runs play at the same time and share one pool of in-flight model calls, so wall-clock
time is set by the slowest market, not the number of markets. Each call is capped at
--call-timeout seconds. Past --deadline-min, negotiations stop starting new rounds and
every market closes cleanly with what it has.

Writes outputs/v2/<backend>/runs/<run_id>/{calls,events}.jsonl, appends one row per run to
outputs/v2/<backend>/summary.jsonl, and writes outputs/v2/<backend>/results.md at the end.
Finished run_ids are skipped on restart.
"""
import argparse
import asyncio
import contextlib
import io
import json
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from v2 import markets, prompts  # noqa: E402
from v2.backends import PRICES, AnthropicBackend, ClaudeCLIBackend, MockBackend, TinkerBackend  # noqa: E402
from v2.economy import draw_economy, welfare_report  # noqa: E402

DEFAULT_MODELS = ["Qwen/Qwen3-8B", "openai/gpt-oss-20b"]
T0 = time.time()


def say(msg):
    print(f"[{(time.time() - T0) / 60:5.1f} min] {msg}", flush=True)


def load_env():
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        for line in open(path):
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v)


def assign_models(buyers, sellers, models):
    """Alternate models within each role so each model gets half the buyers and half the sellers."""
    out = {}
    for group in (buyers, sellers):
        for i, a in enumerate(group):
            out[a.id] = models[i % len(models)]
    return out


def cost_of(usage):
    total = 0.0
    for m, u in usage.items():
        if u.get("cost_usd"):  # the backend reported its own cost (claude -p)
            total += u["cost_usd"]
            continue
        p_in, p_out = PRICES.get(m, (0.0, 0.0))
        total += u["prompt_tokens"] / 1e6 * p_in + u["output_tokens"] / 1e6 * p_out
    return total


async def run_one(mech, framing, seed, args, backends, out_dir, sem, deadline):
    run_id = f"{mech}_{framing}_seed{seed}"
    rdir = os.path.join(out_dir, "runs", run_id)
    os.makedirs(rdir, exist_ok=True)
    buyers, sellers = draw_economy(seed)
    model_of = assign_models(buyers, sellers, args.models)
    rng = random.Random(run_id)
    t0 = time.time()
    with open(os.path.join(rdir, "calls.jsonl"), "w") as log, open(os.path.join(rdir, "events.jsonl"), "w") as ev:
        call = markets.Caller(backends, sem, log, {"run_id": run_id, "mechanism": mech, "framing": framing, "seed": seed},
                              timeout=args.call_timeout)
        if mech == "planner":
            res = await markets.run_planner_market(buyers, sellers, framing, model_of, call, rng)
            history = {}
            for r in res["reports"]:
                history.setdefault(r["agent_id"], []).append(f"reported ${r['report']:.0f} for the {r['good']}")
                ev.write(json.dumps(dict(type="report", **r)) + "\n")
            for t in res["trades"]:
                ev.write(json.dumps(dict(type="trade", **t)) + "\n")
        else:
            res = await markets.run_negotiation_market(buyers, sellers, framing, model_of, call, rng, args.rounds, ev,
                                                       deadline=deadline, progress=lambda m: say(f"{run_id}: {m}"))
            history = res["history"]

        outcome = {}
        for b in buyers:
            got = [t for t in res["trades"] if t["buyer"] == b.id]
            outcome[b.id] = "; ".join(f"bought the {t['good']} at ${t['price']:.0f}" for t in got) or "bought nothing"
        for s in sellers:
            got = [t for t in res["trades"] if t["seller"] == s.id]
            outcome[s.id] = f"sold at ${got[0]['price']:.0f}" if got else "did not sell"
        deb = {}
        if args.debrief and time.time() < deadline:
            deb = await markets.debrief(buyers, sellers, framing, model_of, call, outcome, history)
            for aid, o in deb.items():
                ev.write(json.dumps({"type": "debrief", "agent": aid, "model": model_of[aid], **o}) + "\n")

    calls = [json.loads(l) for l in open(os.path.join(rdir, "calls.jsonl"))]
    w = welfare_report(res["trades"], buyers, sellers)
    row = {"run_id": run_id, "mechanism": mech, "framing": framing, "seed": seed,
           "models": args.models, "backend": args.backend, **w,
           "usage": call.usage, "est_cost_usd": round(cost_of(call.usage), 4),
           "n_calls": len(calls), "n_timeouts": sum(c["timed_out"] for c in calls),
           "n_parse_errors": sum(c["parse_error"] for c in calls),
           "seconds": round(time.time() - t0, 1)}
    if mech == "planner":
        reps = res["reports"]
        row["misreport_rate"] = sum(r["misreport"] for r in reps) / len(reps)
        row["n_fallback_reports"] = sum(r["fallback"] for r in reps)
    else:
        row.update(res["events_summary"])
    row["n_self_reported_misrepresentation"] = sum(1 for o in deb.values() if o.get("misrepresented") is True)
    row["n_debriefs"] = len(deb)
    return row


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["mock", "tinker", "anthropic", "claude-cli"], default="mock")
    ap.add_argument("--models", nargs="+", default=None, help="default: Qwen3-8B + GPT-OSS-20B, or Opus 5.5 for --backend anthropic")
    ap.add_argument("--mechanisms", nargs="+", default=["planner", "negotiation"])
    ap.add_argument("--framings", nargs="+", default=prompts.FRAMINGS)
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1])
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--concurrency", type=int, default=None, help="model calls in flight across all runs (default 64; 16 for anthropic)")
    ap.add_argument("--max-tokens", type=int, default=None, help="cap on thinking + answer per call (default 2048; 8000 for anthropic)")
    ap.add_argument("--call-timeout", type=float, default=180, help="seconds before a call counts as a no-op")
    ap.add_argument("--deadline-min", type=float, default=100, help="stop starting new rounds after this many minutes")
    ap.add_argument("--mock-latency", type=float, default=0.0, help="mock only: max simulated seconds per call")
    ap.add_argument("--no-debrief", dest="debrief", action="store_false")
    args = ap.parse_args()
    anth = args.backend in ("anthropic", "claude-cli")
    args.models = args.models or (["claude-opus-5-5"] if anth else DEFAULT_MODELS)
    args.concurrency = args.concurrency or (8 if args.backend == "claude-cli" else 16 if anth else 64)
    args.max_tokens = args.max_tokens or (8000 if anth else 2048)

    load_env()
    out_dir = os.path.join(ROOT, "outputs", "v2", args.backend)
    os.makedirs(out_dir, exist_ok=True)
    summary_path = os.path.join(out_dir, "summary.jsonl")
    done = set()
    if os.path.exists(summary_path):
        done = {json.loads(l)["run_id"] for l in open(summary_path) if l.strip()}
    todo = [(m, f, s) for s in args.seeds for m in args.mechanisms for f in args.framings
            if f"{m}_{f}_seed{s}" not in done]
    if not todo:
        say("nothing to do: every requested run is already in summary.jsonl")
        return

    if args.backend == "tinker":
        backends = {m: TinkerBackend(m, max_tokens=args.max_tokens) for m in args.models}
    elif args.backend == "claude-cli":
        backends = {m: ClaudeCLIBackend(m) for m in args.models}
    elif anth:
        backends = {m: AnthropicBackend(m, max_tokens=args.max_tokens) for m in args.models}
    else:
        backends = {m: MockBackend(m, latency=args.mock_latency) for m in args.models}
    for m, b in backends.items():
        try:
            b.check_access()
        except Exception as e:  # billing/auth problems should stop the run before anything starts
            say(f"cannot reach {m}: {type(e).__name__}: {str(e)[:300]}")
            sys.exit(1)
    say(f"access ok for {', '.join(args.models)}; launching {len(todo)} runs at once "
        f"(concurrency {args.concurrency}, call timeout {args.call_timeout:.0f}s, deadline {args.deadline_min:.0f} min)")

    sem = asyncio.Semaphore(args.concurrency)
    deadline = T0 + args.deadline_min * 60
    spent = {"usd": 0.0}

    async def one(m, f, s):
        row = await run_one(m, f, s, args, backends, out_dir, sem, deadline)
        spent["usd"] += row["est_cost_usd"]
        with open(summary_path, "a") as fh:
            fh.write(json.dumps(row) + "\n")
        say(f"done {row['run_id']:30s} E={row['efficiency']:.3f} trades={row['n_trades']}/{row['n_efficient_trades']} "
            f"timeouts={row['n_timeouts']} cost=${row['est_cost_usd']:.3f} (total ${spent['usd']:.2f})")

    await asyncio.gather(*[one(m, f, s) for m, f, s in todo])
    say(f"all runs finished; estimated spend ${spent['usd']:.2f}")

    from v2 import analyze
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        sys.argv = ["analyze", "--backend", args.backend, "--examples", "3"]
        analyze.main()
    with open(os.path.join(out_dir, "results.md"), "w") as fh:
        fh.write(buf.getvalue())
    say(f"wrote {os.path.join(out_dir, 'results.md')}")


if __name__ == "__main__":
    asyncio.run(main())
