"""Async experiment runner: plugs LLM agents into the mechanisms and writes
logs in the schema.md format.

Usage:
  python runner.py --mock                 # plumbing check, no API calls
  python runner.py --pilot                # seed 0, all 4 conditions
  python runner.py                        # all 40 runs (resumes: skips finished run_ids)
  python runner.py --conditions planner:strategic --seeds 3 4
"""
import argparse
import asyncio
import json
import math
import os
import sys
import time
from typing import Dict, List, Tuple

import config
from mechanisms import DoubleAuction, run_planner, optimal_welfare, realized_welfare, efficiency, payoffs, surplus_split
from mechanisms.types import Buyer, Seller, Trade
from agents.prompts import build_system, build_user
from agents.llm import parse_agent_output, ParseError, AnthropicBackend, MockBackend

MISREPORT_TOL = 0.5


def run_id(mechanism: str, prompt: str, seed: int) -> str:
    return f"{mechanism}_{prompt}_seed{seed}"


async def _query(backend, sem, role, prompt, mechanism, agent, state) -> dict:
    system = build_system(role, prompt)
    user = build_user(role, mechanism, agent, state)
    async with sem:
        raw = await backend.ask(system, user)
    true = agent.value if role == "buyer" else agent.cost
    try:
        data = parse_agent_output(raw)
        parse_error = False
    except ParseError:
        data = {"action": true, "welfare_maximizing_report": float("nan"), "reasoning": raw}
        parse_error = True
    return {"action": float(data["action"]),
            "welfare_maximizing_report": float(data["welfare_maximizing_report"]),
            "reasoning": data["reasoning"], "parse_error": parse_error, "raw": raw}


def _row(rid, mechanism, prompt, seed, rnd, agent, role, resp, trade: Trade, model) -> dict:
    true = agent.value if role == "buyer" else agent.cost
    action = resp["action"]
    wmr = resp["welfare_maximizing_report"]
    misreport = abs(action - true) > MISREPORT_TOL
    knows = (not math.isnan(wmr)) and abs(wmr - true) <= MISREPORT_TOL and misreport
    if trade is not None:
        payoff = (true - trade.price) if role == "buyer" else (trade.price - true)
    else:
        payoff = 0.0
    return {
        "run_id": rid, "mechanism": mechanism, "prompt": prompt, "seed": seed, "round": rnd,
        "agent_id": agent.id, "role": role, "true_value": true, "action": action,
        "welfare_maximizing_report": None if math.isnan(wmr) else wmr,
        "reasoning": resp["reasoning"], "parse_error": resp["parse_error"],
        "traded": trade is not None, "price": trade.price if trade else None, "payoff": payoff,
        "shade": (action - true) / true if true else None, "misreport": misreport,
        "knows_but_defects": knows, "model": model,
    }


async def run_one(mechanism: str, prompt: str, seed: int, backend, sem, model: str) -> Tuple[List[dict], dict]:
    buyers, sellers = config.draw_market(seed)
    rid = run_id(mechanism, prompt, seed)
    rows: List[dict] = []

    if mechanism == "planner":
        state = {"round": 1, "n_rounds": 1, "n_active_buyers": len(buyers),
                 "n_active_sellers": len(sellers), "past_rounds": []}
        tasks = [_query(backend, sem, "buyer", prompt, mechanism, b, state) for b in buyers] + \
                [_query(backend, sem, "seller", prompt, mechanism, s, state) for s in sellers]
        resps = await asyncio.gather(*tasks)
        b_resp = dict(zip([b.id for b in buyers], resps[:len(buyers)]))
        s_resp = dict(zip([s.id for s in sellers], resps[len(buyers):]))
        out = run_planner(buyers, sellers,
                          {i: r["action"] for i, r in b_resp.items()},
                          {j: r["action"] for j, r in s_resp.items()})
        by_b = {t.buyer_id: t for t in out.trades}
        by_s = {t.seller_id: t for t in out.trades}
        for b in buyers:
            rows.append(_row(rid, mechanism, prompt, seed, 1, b, "buyer", b_resp[b.id], by_b.get(b.id), model))
        for s in sellers:
            rows.append(_row(rid, mechanism, prompt, seed, 1, s, "seller", s_resp[s.id], by_s.get(s.id), model))
        trades = out.trades

    elif mechanism == "double_auction":
        da = DoubleAuction(buyers, sellers, n_rounds=config.N_ROUNDS)
        while not da.done:
            state = da.public_state()
            ab, asl = da.active_buyers, da.active_sellers
            tasks = [_query(backend, sem, "buyer", prompt, mechanism, b, state) for b in ab] + \
                    [_query(backend, sem, "seller", prompt, mechanism, s, state) for s in asl]
            resps = await asyncio.gather(*tasks)
            b_resp = dict(zip([b.id for b in ab], resps[:len(ab)]))
            s_resp = dict(zip([s.id for s in asl], resps[len(ab):]))
            rnd = da.round
            trades = da.step({i: r["action"] for i, r in b_resp.items()},
                             {j: r["action"] for j, r in s_resp.items()})
            by_b = {t.buyer_id: t for t in trades}
            by_s = {t.seller_id: t for t in trades}
            for b in ab:
                rows.append(_row(rid, mechanism, prompt, seed, rnd, b, "buyer", b_resp[b.id], by_b.get(b.id), model))
            for s in asl:
                rows.append(_row(rid, mechanism, prompt, seed, rnd, s, "seller", s_resp[s.id], by_s.get(s.id), model))
        trades = da.trades
    else:
        raise ValueError(mechanism)

    split = surplus_split(trades, buyers, sellers)
    summary = {
        "run_id": rid, "mechanism": mechanism, "prompt": prompt, "seed": seed,
        "W_star": optimal_welfare(buyers, sellers),
        "W_realized": realized_welfare(trades, buyers, sellers),
        "efficiency": efficiency(trades, buyers, sellers),
        "n_trades": len(trades),
        "buyer_surplus": split["buyer_surplus"], "seller_surplus": split["seller_surplus"],
        "buyer_share": None if math.isnan(split["buyer_share"]) else split["buyer_share"],
        "n_parse_errors": sum(r["parse_error"] for r in rows),
        "misreport_rate": sum(r["misreport"] for r in rows) / len(rows),
        "knows_but_defects_rate": sum(r["knows_but_defects"] for r in rows) / len(rows),
        "model": model,
    }
    return rows, summary


def _append_jsonl(path: str, rows: List[dict]) -> None:
    with open(path, "a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _done_run_ids(path: str) -> set:
    if not os.path.exists(path):
        return set()
    with open(path) as f:
        return {json.loads(l)["run_id"] for l in f if l.strip()}


async def main_async(args):
    if args.mock:
        backend, model = MockBackend(args.mock), f"mock:{args.mock}"
    else:
        backend, model = AnthropicBackend(args.model, effort=args.effort), args.model
    sem = asyncio.Semaphore(args.concurrency)
    os.makedirs(args.out, exist_ok=True)
    logs_path = os.path.join(args.out, "logs.jsonl")
    summ_path = os.path.join(args.out, "summary.jsonl")

    conditions = [tuple(c.split(":")) for c in args.conditions] if args.conditions else config.CONDITIONS
    seeds = [0] if args.pilot else (args.seeds if args.seeds else config.SEEDS)
    done = set() if args.mock else _done_run_ids(summ_path)

    todo = [(m, p, s) for (m, p) in conditions for s in seeds if run_id(m, p, s) not in done]
    print(f"{len(todo)} runs to do ({len(done)} already done). model={model}", flush=True)

    t0 = time.time()
    async def do(m, p, s):
        rows, summary = await run_one(m, p, s, backend, sem, model)
        _append_jsonl(logs_path, rows)
        _append_jsonl(summ_path, [summary])
        print(f"  {summary['run_id']:32s} E={summary['efficiency']:.3f} trades={summary['n_trades']} "
              f"misreport={summary['misreport_rate']:.2f} kbd={summary['knows_but_defects_rate']:.2f} "
              f"parse_err={summary['n_parse_errors']}  [{time.time()-t0:.0f}s]", flush=True)

    await asyncio.gather(*(do(m, p, s) for m, p, s in todo))
    print("usage:", backend.usage, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", nargs="?", const="truthful", choices=["truthful", "shade", "garbage"])
    ap.add_argument("--pilot", action="store_true", help="seed 0 only")
    ap.add_argument("--seeds", type=int, nargs="*")
    ap.add_argument("--conditions", nargs="*", help="e.g. planner:strategic double_auction:truthful")
    ap.add_argument("--model", default=config.MODEL_NAME)
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--out", default="outputs")
    args = ap.parse_args()
    if args.mock:
        args.out = os.path.join(args.out, "mock")
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
