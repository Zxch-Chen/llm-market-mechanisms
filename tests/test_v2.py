"""v2 economy and market invariants, run on the mock backend (no network)."""
import asyncio
import io
import json
import random

from v2 import markets
from v2.backends import MockBackend
from v2.economy import GOODS, draw_economy, efficient_trades, welfare_report
from v2.markets import extract_json
from v2.run import assign_models

MODELS = ["Qwen/Qwen3-8B", "openai/gpt-oss-20b"]


def _caller(log):
    backends = {m: MockBackend(m, seed=1) for m in MODELS}
    return markets.Caller(backends, asyncio.Semaphore(8), log, {"run_id": "t"})


def test_economy_is_deterministic_and_balanced():
    a, b = draw_economy(3), draw_economy(3)
    assert [(x.id, x.values) for x in a[0]] == [(x.id, x.values) for x in b[0]]
    sellers = a[1]
    assert {g: sum(s.good == g for s in sellers) for g in GOODS} == {g: 4 for g in GOODS}


def test_efficient_trades_have_positive_gains_and_unique_traders():
    buyers, sellers = draw_economy(0)
    eff = efficient_trades(buyers, sellers)
    assert all(gain >= 0 for _, _, _, gain in eff)
    assert len({(g, b) for g, b, _, _ in eff}) == len(eff)
    assert len({s for _, _, s, _ in eff}) == len(eff)


def test_extract_json_takes_last_object():
    assert extract_json('thinking {"a": 1} more {"b": {"c": 2}}') == {"b": {"c": 2}}
    assert extract_json("no json here") is None


def test_truthful_planner_is_efficient():
    buyers, sellers = draw_economy(1)
    trades = []
    from mechanisms.planner import run_planner
    from mechanisms.types import Buyer, Seller
    for g in GOODS:
        gb = [Buyer(b.id, b.values[g]) for b in buyers if g in b.values]
        gs = [Seller(s.id, s.cost) for s in sellers if s.good == g]
        out = run_planner(gb, gs, {x.id: x.value for x in gb}, {x.id: x.cost for x in gs})
        trades += [{"good": g, "buyer": t.buyer_id, "seller": t.seller_id, "price": t.price} for t in out.trades]
    assert abs(welfare_report(trades, buyers, sellers)["efficiency"] - 1.0) < 1e-9


def test_negotiation_respects_one_unit_rules():
    for framing in ["neutral", "honest", "aggressive"]:
        buyers, sellers = draw_economy(2)
        model_of = assign_models(buyers, sellers, MODELS)
        res = asyncio.run(markets.run_negotiation_market(
            buyers, sellers, framing, model_of, _caller(io.StringIO()), random.Random(0), 6, io.StringIO()))
        trades = res["trades"]
        assert len({t["seller"] for t in trades}) == len(trades)              # each seller sells once
        assert len({(t["buyer"], t["good"]) for t in trades}) == len(trades)  # one unit per good per buyer
        B = {b.id: b for b in buyers}
        S = {s.id: s for s in sellers}
        for t in trades:
            assert t["good"] in B[t["buyer"]].values and S[t["seller"]].good == t["good"]


def test_calls_are_logged_with_thinking():
    log = io.StringIO()
    buyers, sellers = draw_economy(0)
    model_of = assign_models(buyers, sellers, MODELS)
    asyncio.run(markets.run_planner_market(buyers, sellers, "neutral", model_of, _caller(log), random.Random(0)))
    rows = [json.loads(l) for l in log.getvalue().splitlines()]
    assert len(rows) == len(buyers) + len(sellers)
    assert all(r["thinking"] and r["system"] and r["user"] for r in rows)
    assert {r["model"] for r in rows} == set(MODELS)


class _Scripted:
    """Round 1: seller posts. Round 2: seller cancels while the buyer accepts the same offer."""

    def __init__(self, seller, buyer, good):
        self.seller, self.buyer, self.good = seller, buyer, good

    async def generate(self, messages, ctx=None):
        a, r = ctx["agent_id"], ctx["view"]["round"]
        act = {"accept_offer_id": None, "post_offers": [], "cancel_offer_ids": [], "messages": []}
        if a == self.seller and r == 1:
            act["post_offers"] = [{"item": self.good, "price": 9999}]
        if a == self.seller and r == 2:
            act["cancel_offer_ids"] = ["O1"]
        if a == self.buyer and r == 2:
            act["accept_offer_id"] = "O1"
        return {"model": "m", "text": json.dumps(act), "thinking": "", "prompt_tokens": 0,
                "output_tokens": 0, "stop_reason": "stop"}


def test_offers_are_firm_within_a_round():
    buyers, sellers = draw_economy(0)
    s = sellers[0]
    b = next(x for x in buyers if s.good in x.values)
    backend = _Scripted(s.id, b.id, s.good)
    call = markets.Caller({"m": backend}, asyncio.Semaphore(4), io.StringIO(), {"run_id": "t"})
    model_of = {x.id: "m" for x in buyers + sellers}
    res = asyncio.run(markets.run_negotiation_market(
        buyers, sellers, "neutral", model_of, call, random.Random(0), 2, io.StringIO()))
    assert [(t["buyer"], t["seller"], t["round"]) for t in res["trades"]] == [(b.id, s.id, 2)]
