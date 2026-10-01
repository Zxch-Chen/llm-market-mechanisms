"""Why weak agents fail in the v2 chat market, and what Opus does differently.

  python -m v2.failure_analysis                      # tinker and claude-cli
  python -m v2.failure_analysis tinker-gptoss120b    # any folder under outputs/v2/

Reads outputs/v2/tinker (Qwen3-8B + GPT-OSS-20B) and outputs/v2/claude-cli (Opus 5.5, seed 0)
and prints the numbers quoted in analysis/v2_why_agents_fail.md. Keyword checks are heuristics;
the write-up quotes the transcripts they point to.
"""
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from v2.economy import draw_economy, efficient_trades  # noqa: E402

NOTICED = re.compile(r"over (the |my |her |his |their )?(budget|max|limit)|exceed|too high|above (the |her |his |their )?"
                     r"(max|budget|limit)|below (the |her |his |their )?(min|minimum|cost)|less than (the |her |his |their )?"
                     r"(min|minimum)|can'?t (afford|accept|go below)|not acceptable|way over", re.I)
DEADLINE = re.compile(r"earns? nothing|get nothing|better than nothing|unsold|guarantee|last round|final round|"
                      r"no more rounds|run out of", re.I)


def runs(backend):
    for f in sorted(glob.glob(os.path.join(ROOT, "outputs", "v2", backend, "runs", "negotiation_*", "events.jsonl"))):
        run = f.split(os.sep)[-2]
        seed = int(run.split("seed")[1])
        ev = [json.loads(l) for l in open(f)]
        calls = [json.loads(l) for l in open(f.replace("events.jsonl", "calls.jsonl"))]
        yield run, seed, ev, calls


def welfare_loss(backend):
    """Per market: (best possible welfare, welfare destroyed by value-losing trades, best minus positive gains)."""
    for _, seed, ev, _ in runs(backend):
        bs, ss = draw_economy(seed)
        B, S = {b.id: b for b in bs}, {s.id: s for s in ss}
        wstar = sum(t[3] for t in efficient_trades(bs, ss))
        gains = [B[e["buyer"]].values[e["good"]] - S[e["seller"]].cost for e in ev if e["type"] == "trade"]
        yield wstar, -sum(g for g in gains if g < 0), wstar - sum(g for g in gains if g > 0)


def limit_violations(backend):
    out = []
    for run, seed, ev, calls in runs(backend):
        bs, ss = draw_economy(seed)
        B, S = {b.id: b for b in bs}, {s.id: s for s in ss}
        offers = {e["id"]: e for e in ev if e["type"] == "offer"}
        for t in (e for e in ev if e["type"] == "trade"):
            v, c, p = B[t["buyer"]].values[t["good"]], S[t["seller"]].cost, t["price"]
            for side, agent, bad in (("buyer", t["buyer"], p > v + 0.5), ("seller", t["seller"], p < c - 0.5)):
                if not bad:
                    continue
                how = "accepted" if t["accepted_by"] == agent else "posted"
                rnd = t["round"] if how == "accepted" else offers[t["offer"]]["round"]
                call = next(x for x in calls if x["agent_id"] == agent and x["kind"] == "negotiation" and x["round"] == rnd)
                reasoning = (call["thinking"] or "") + " " + (call["text"] or "")  # truncated thinking lands in text
                out.append({"run": run, "agent": agent, "model": call["model"].split("/")[-1], "how": how, "round": rnd,
                            "retried": call["retried"],
                            # cut off by the token cap: either retried, or the parser found JSON inside unfinished reasoning
                            "truncated": call["retried"] or "length" in str(call["stop_reason"]), "noticed": bool(NOTICED.search(reasoning)),
                            "deadline_logic": bool(DEADLINE.search(reasoning)), "wait_loop": reasoning.count("Wait") >= 5})
    return out


def opening_at_limit(backend):
    res = defaultdict(lambda: [0, 0])
    for _, seed, ev, calls in runs(backend):
        bs, ss = draw_economy(seed)
        B, S = {b.id: b for b in bs}, {s.id: s for s in ss}
        model = {c["agent_id"]: c["model"].split("/")[-1] for c in calls}
        for e in ev:
            if e["type"] == "offer" and e["round"] == 1:
                a = e["agent"]
                lim = B[a].values[e["good"]] if a in B else S[a].cost
                res[model[a]][0] += 1
                res[model[a]][1] += abs(e["price"] - lim) <= 0.5
    return dict(res)


def wrong_pairs_by_round(backend):
    wrong, tot = Counter(), Counter()
    for _, seed, ev, _ in runs(backend):
        bs, ss = draw_economy(seed)
        eff = efficient_trades(bs, ss)
        ok = {(g, b) for g, b, _, _ in eff} | {(g, s) for g, _, s, _ in eff}
        for e in ev:
            if e["type"] == "trade":
                tot[e["round"]] += 1
                wrong[e["round"]] += not ((e["good"], e["buyer"]) in ok and (e["good"], e["seller"]) in ok)
    return {r: (wrong[r], tot[r]) for r in sorted(tot)}


def late_rounds(backend):
    """Agent turns in rounds 5-6: was any profitable partner still active, and did the agent break its limit?"""
    out = []
    for _, seed, ev, calls in runs(backend):
        bs, ss = draw_economy(seed)
        B, S = {b.id: b for b in bs}, {s.id: s for s in ss}
        model = {c["agent_id"]: c["model"].split("/")[-1] for c in calls}
        trades = [e for e in ev if e["type"] == "trade"]
        for r in (5, 6):
            active = {c["agent_id"] for c in calls if c["kind"] == "negotiation" and c["round"] == r}
            for a in active:
                feasible = viol = False
                if a in S:
                    g = S[a].good
                    buyers = [x for x in active if x in B and g in B[x].values
                              and not any(t["buyer"] == x and t["good"] == g and t["round"] < r for t in trades)]
                    feasible = any(B[x].values[g] >= S[a].cost for x in buyers)
                    viol = any(t["seller"] == a and t["round"] == r and t["price"] < S[a].cost - 0.5 for t in trades)
                else:
                    for g, v in B[a].values.items():
                        if any(t["buyer"] == a and t["good"] == g and t["round"] < r for t in trades):
                            continue
                        feasible |= any(S[x].cost <= v for x in active if x in S and S[x].good == g)
                        viol |= any(t["buyer"] == a and t["good"] == g and t["round"] == r and t["price"] > v + 0.5
                                    for t in trades)
                out.append({"model": model[a], "feasible": feasible, "viol": viol})
    return out


def main():
    dirs = sys.argv[1:] or ["tinker", "claude-cli"]  # folder names under outputs/v2/
    for backend in dirs:
        label = f"{backend} ({len(list(runs(backend)))} chat markets)"
        rows = list(welfare_loss(backend))
        if not rows:
            continue
        wstar = sum(r[0] for r in rows)
        destroyed = sum(r[1] for r in rows)
        lost = sum(r[1] + r[2] for r in rows)
        print(f"\n== {label}")
        print(f"welfare lost: {lost:.0f} of {wstar:.0f} ({lost / wstar:.0%}); destroyed by value-losing trades: "
              f"{destroyed / max(lost, 1):.0%} of the loss; wrong pairs or missed trades: {1 - destroyed / max(lost, 1):.0%}")
        print("round-1 offers at exactly the client's limit:",
              {m: f"{a}/{n} ({a / n:.0%})" for m, (n, a) in opening_at_limit(backend).items()})
        print("wrong-pair trades by round:", {r: f"{w}/{t}" for r, (w, t) in wrong_pairs_by_round(backend).items()})
        v = limit_violations(backend)
        print(f"limit violations: {len(v)}")
        if v:
            print("  by model and how:", dict(Counter((x["model"], x["how"]) for x in v)))
            print(f"  reasoning noticed the violation, then took it anyway: {sum(x['noticed'] for x in v)}")
            print(f"  thinking hit the token cap, then a JSON-only retry made the call: {sum(x['retried'] for x in v)}")
            print(f"  'Wait...' loops (5+ in the reasoning): {sum(x['wait_loop'] for x in v)}")
            print(f"  'nothing / unsold / last round' logic: {sum(x['deadline_logic'] for x in v)}")
            print(f"  in the last two rounds: {sum(x['round'] >= 5 for x in v)}")
            clean = [x for x in v if not x["truncated"]]
            print(f"  not cut off by the token cap: {len(clean)} (noticed the violation first: {sum(x['noticed'] for x in clean)}; "
                  f"'nothing / last round' logic: {sum(x['deadline_logic'] for x in clean)})")
        trades = sum(1 for _, _, ev, _ in runs(backend) for e in ev if e["type"] == "trade")
        by_round = Counter(e["round"] for _, _, ev, _ in runs(backend) for e in ev if e["type"] == "trade")
        print(f"trades by round: {dict(sorted(by_round.items()))} (total {trades})")
        late = late_rounds(backend)
        if late:
            print(f"agent turns in rounds 5-6: {len(late)}; with any profitable partner still active: "
                  f"{sum(x['feasible'] for x in late)}")
            for m in sorted({x["model"] for x in late}):
                dead = [x for x in late if x["model"] == m and not x["feasible"]]
                print(f"  {m}: dead-end turns {len(dead)}, broke the limit anyway {sum(x['viol'] for x in dead)}")


if __name__ == "__main__":
    main()
