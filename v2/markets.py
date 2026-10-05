"""The two v2 market mechanisms and the agent-call plumbing.

planner      one sealed report per agent per item; per-item uniform midpoint price
negotiation  multi-round open marketplace: public offer board, accept-an-offer trades,
             private and public messages
"""
import asyncio
import json
import random
import time
from typing import Dict, List

from mechanisms.planner import run_planner
from mechanisms.types import Buyer, Seller

from . import prompts
from .economy import GOODS

MSG_MAX_CHARS = 500
MSG_MAX_PER_TURN = 5
INBOX_SHOWN = 30


# --------------------------------------------------------------------------- agent calls

def extract_json(text: str):
    """Return the last top-level JSON object in text, or None."""
    if not text:
        return None
    decoder = json.JSONDecoder()
    pos, last = 0, None
    while pos < len(text):
        start = text.find("{", pos)
        if start < 0:
            break
        try:
            obj, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            pos = start + 1
            continue
        if isinstance(obj, dict):
            last = obj
        # Skip nested objects and braces inside strings in a decoded object.
        pos = end
    return last


class Caller:
    """Calls an agent's backend, parses JSON (one retry), and logs every call.

    Each model call is capped at `timeout` seconds so one slow agent can't stall a round.
    A call that times out counts as "do nothing this turn" and is logged with timed_out=True.
    """

    def __init__(self, backends: Dict[str, object], sem: asyncio.Semaphore, log, base: dict,
                 timeout: float = None):
        self.backends, self.sem, self.log, self.base, self.timeout = backends, sem, log, base, timeout
        self.usage = {}

    def _count(self, res):
        u = self.usage.setdefault(res["model"], {"calls": 0, "prompt_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})
        u["cost_usd"] = u.get("cost_usd", 0.0) + res.get("cost_usd", 0.0)  # reported directly by some backends
        u["calls"] += 1
        u["prompt_tokens"] += res["prompt_tokens"]
        u["output_tokens"] += res["output_tokens"]

    async def _generate(self, backend, messages, ctx):
        async with self.sem:
            try:
                return await asyncio.wait_for(backend.generate(messages, ctx), self.timeout)
            except asyncio.TimeoutError:
                return None

    async def __call__(self, agent_model: str, messages: List[dict], ctx: dict, meta: dict):
        backend = self.backends[agent_model]
        row = dict(self.base, **meta, model=agent_model, system=messages[0]["content"],
                   user=messages[-1]["content"], retried=False, timed_out=False)
        res = await self._generate(backend, messages, ctx)
        if res is None:
            row.update(timed_out=True, text="", thinking="", prompt_tokens=0, output_tokens=0,
                       stop_reason="timeout", parsed=None, parse_error=True)
            self.log.write(json.dumps(row) + "\n")
            return None
        self._count(res)
        parsed = extract_json(res["text"])
        row.update(text=res["text"], thinking=res["thinking"], prompt_tokens=res["prompt_tokens"],
                   output_tokens=res["output_tokens"], stop_reason=res["stop_reason"],
                   served_by=res.get("served_by", agent_model))
        if parsed is None:
            retry = messages + [{"role": "assistant", "content": res["text"]},
                                {"role": "user", "content": "Your reply did not end with a valid JSON object "
                                 "in the required format. Reply with only that JSON object, no reasoning."}]
            res2 = await self._generate(backend, retry, ctx)
            row["retried"] = True
            if res2 is None:
                row["timed_out"] = True
            else:
                self._count(res2)
                parsed = extract_json(res2["text"])
                row.update(retry_text=res2["text"], retry_thinking=res2["thinking"],
                           prompt_tokens=row["prompt_tokens"] + res2["prompt_tokens"],
                           output_tokens=row["output_tokens"] + res2["output_tokens"])
        row["parsed"] = parsed
        row["parse_error"] = parsed is None
        self.log.write(json.dumps(row) + "\n")
        return parsed


def _num(x):
    if isinstance(x, bool):
        return None
    try:
        v = float(x)
        return v if v == v and abs(v) < 1e7 else None
    except (TypeError, ValueError, OverflowError):
        return None


def _list_field(action, name):
    value = action.get(name)
    return value if isinstance(value, list) else []


# --------------------------------------------------------------------------- planner

async def run_planner_market(buyers, sellers, framing, model_of, call: Caller, rng) -> dict:
    async def ask(agent, role):
        messages = [{"role": "system", "content": prompts.system_prompt(agent, role, framing)},
                    {"role": "user", "content": prompts.planner_user(agent, role)}]
        ctx = {"kind": "planner", "role": role, "framing": framing, "agent_id": agent.id,
               "values": getattr(agent, "values", None), "cost": getattr(agent, "cost", None)}
        return await call(model_of[agent.id], messages, ctx,
                          {"agent_id": agent.id, "role": role, "round": 1, "kind": "planner"})

    outs = await asyncio.gather(*[ask(b, "buyer") for b in buyers], *[ask(s, "seller") for s in sellers])
    b_out, s_out = outs[:len(buyers)], outs[len(buyers):]

    reports = []  # one row per (agent, item) report
    rep_v = {g: {} for g in GOODS}
    rep_c = {g: {} for g in GOODS}
    for b, o in zip(buyers, b_out):
        got = (o or {}).get("reports") or {}
        for g, v in b.values.items():
            r = _num(got.get(g)) if isinstance(got, dict) else None
            fallback = r is None
            r = v if fallback else r
            rep_v[g][b.id] = r
            reports.append({"agent_id": b.id, "role": "buyer", "good": g, "true": v, "report": r,
                            "fallback": fallback, "model": model_of[b.id]})
    for s, o in zip(sellers, s_out):
        r = _num((o or {}).get("report"))
        fallback = r is None
        r = s.cost if fallback else r
        rep_c[s.good][s.id] = r
        reports.append({"agent_id": s.id, "role": "seller", "good": s.good, "true": s.cost, "report": r,
                        "fallback": fallback, "model": model_of[s.id]})

    trades = []
    for g in GOODS:
        gb = [Buyer(b.id, b.values[g]) for b in buyers if g in b.values]
        gs = [Seller(s.id, s.cost) for s in sellers if s.good == g]
        if not gb or not gs:
            continue
        out = run_planner(gb, gs, rep_v[g], rep_c[g])
        trades += [{"good": g, "buyer": t.buyer_id, "seller": t.seller_id, "price": t.price, "round": 1}
                   for t in out.trades]
    for r in reports:
        r["misreport"] = abs(r["report"] - r["true"]) > 0.5
        r["shade"] = r["report"] - r["true"]
    return {"trades": trades, "reports": reports, "events": []}


# --------------------------------------------------------------------------- negotiation

async def run_negotiation_market(buyers, sellers, framing, model_of, call: Caller, rng: random.Random,
                                 n_rounds: int, events_log, deadline: float = None, progress=None) -> dict:
    B = {b.id: b for b in buyers}
    S = {s.id: s for s in sellers}
    needs = {b.id: set(b.values) for b in buyers}
    sold = {s.id: False for s in sellers}
    offers: Dict[str, dict] = {}
    trades, messages = [], []
    counter = {"offer": 0}
    # items each agent trades in; public messages only reach agents who share an item
    goods_of = {**{b.id: set(b.values) for b in buyers}, **{s.id: {s.good} for s in sellers}}

    def event(**e):
        events_log.write(json.dumps(e) + "\n")

    def unsold_goods():
        return {S[i].good for i, v in sold.items() if not v}

    def wanted_goods():
        return {g for n in needs.values() for g in n}

    def is_active(aid):
        if aid in B:
            return bool(needs[aid] & unsold_goods())
        return (not sold[aid]) and S[aid].good in wanted_goods()

    def label(aid):
        if aid in B:
            return f"{aid} (buying {', '.join(sorted(needs[aid]))})"
        return f"{aid} (selling {S[aid].good})"

    def view_for(aid, r):
        relevant = needs[aid] if aid in B else {S[aid].good}
        return {
            "round": r, "n_rounds": n_rounds,
            "needs": sorted(needs[aid]) if aid in B else [],
            "offers": [o for o in offers.values() if o["status"] == "open" and o["good"] in relevant],
            "trades": [{"good": t["good"], "price": t["price"], "round": t["round"]} for t in trades],
            "inbox": [m for m in messages if m["from"] != aid and
                      (m["to"] == aid or (m["to"] == "ALL" and goods_of[m["from"]] & goods_of[aid]))][-INBOX_SHOWN:],
            "active": [label(a) for a in list(B) + list(S) if a != aid and is_active(a)],
        }

    history = {a: [] for a in list(B) + list(S)}  # each agent's own actions, for the debrief

    r = 0
    for r in range(1, n_rounds + 1):
        active = [a for a in list(B) + list(S) if is_active(a)]
        if not active:
            r -= 1
            break
        if deadline is not None and time.time() > deadline:
            event(type="deadline", round=r)
            r -= 1
            break
        if progress:
            progress(f"round {r}: {len(active)} active, {len(trades)} trades so far")

        async def turn(aid):
            role = "buyer" if aid in B else "seller"
            agent = B.get(aid) or S.get(aid)
            view = view_for(aid, r)
            msgs = [{"role": "system", "content": prompts.system_prompt(agent, role, framing)},
                    {"role": "user", "content": prompts.negotiation_user(agent, role, view)}]
            ctx = {"kind": "negotiation", "role": role, "framing": framing, "agent_id": aid, "view": view,
                   "values": getattr(agent, "values", None), "cost": getattr(agent, "cost", None),
                   "good": getattr(agent, "good", None)}
            act = await call(model_of[aid], msgs, ctx, {"agent_id": aid, "role": role, "round": r, "kind": "negotiation"})
            return aid, act or {}

        acts = dict(await asyncio.gather(*[turn(a) for a in active]))

        # 1. accepts, in random order
        order = [a for a in active if acts[a].get("accept_offer_id")]
        rng.shuffle(order)
        for aid in order:
            oid = str(acts[aid]["accept_offer_id"])
            o = offers.get(oid)
            reason = None
            if not o or o["status"] != "open":
                reason = "offer not open"
            elif o["agent"] == aid:
                reason = "own offer"
            elif aid in B and not (o["side"] == "sell" and o["good"] in needs[aid]):
                reason = "buyer can only accept sell offers for an item it needs"
            elif aid in S and not (o["side"] == "buy" and o["good"] == S[aid].good and not sold[aid]):
                reason = "seller can only accept buy offers for its item"
            elif o["side"] == "sell" and sold[o["agent"]]:
                reason = "seller already sold"
            elif o["side"] == "buy" and o["good"] not in needs[o["agent"]]:
                reason = "buyer no longer needs item"
            if reason:
                event(type="accept_failed", round=r, agent=aid, offer=oid, reason=reason)
                history[aid].append(f"round {r}: tried to accept {oid} but failed ({reason})")
                continue
            buyer, seller = (aid, o["agent"]) if aid in B else (o["agent"], aid)
            g = o["good"]
            t = {"good": g, "buyer": buyer, "seller": seller, "price": o["price"], "round": r,
                 "offer": oid, "accepted_by": aid}
            trades.append(t)
            o["status"] = "filled"
            needs[buyer].discard(g)
            sold[seller] = True
            for x in offers.values():
                if x["status"] == "open" and ((x["agent"] == buyer and x["good"] == g) or x["agent"] == seller):
                    x["status"] = "closed"
            event(type="trade", **t)
            history[buyer].append(f"round {r}: bought the {g} from {seller} at ${o['price']:.0f}")
            history[seller].append(f"round {r}: sold the {g} to {buyer} at ${o['price']:.0f}")

        # 2. cancellations (after accepts: offers on the board at the start of a round are firm for that round)
        for aid, act in acts.items():
            for oid in _list_field(act, "cancel_offer_ids"):
                o = offers.get(str(oid))
                if o and o["agent"] == aid and o["status"] == "open":
                    o["status"] = "cancelled"
                    event(type="cancel", round=r, agent=aid, offer=o["id"])
                    history[aid].append(f"round {r}: cancelled offer {o['id']}")

        # 3. new offers (visible next round)
        for aid, act in acts.items():
            for p in _list_field(act, "post_offers")[:len(GOODS)]:
                if not isinstance(p, dict):
                    continue
                g, price = p.get("item"), _num(p.get("price"))
                ok = isinstance(g, str) and price is not None and round(price, 2) > 0 and (
                    (aid in B and g in needs[aid]) or (aid in S and not sold[aid] and g == S[aid].good))
                if not ok:
                    event(type="offer_rejected", round=r, agent=aid, item=g, price=p.get("price"))
                    continue
                for x in offers.values():
                    if x["agent"] == aid and x["good"] == g and x["status"] == "open":
                        x["status"] = "replaced"
                counter["offer"] += 1
                o = {"id": f"O{counter['offer']}", "agent": aid, "side": "buy" if aid in B else "sell",
                     "good": g, "price": round(price, 2), "round": r, "status": "open"}
                offers[o["id"]] = o
                event(type="offer", **o)
                history[aid].append(f"round {r}: posted a {o['side']} offer for the {g} at ${price:.0f}")

        # 4. messages (delivered next round)
        for aid, act in acts.items():
            for m in _list_field(act, "messages")[:MSG_MAX_PER_TURN]:
                if not isinstance(m, dict):
                    continue
                to, txt = str(m.get("to", "")), str(m.get("text", ""))[:MSG_MAX_CHARS]
                if not txt or (to != "ALL" and to not in B and to not in S) or to == aid:
                    continue
                msg = {"round": r, "from": aid, "to": to, "text": txt}
                messages.append(msg)
                event(type="message", **msg)
                history[aid].append(f"round {r}: told {to}: \"{txt}\"")

    return {"trades": trades, "events_summary": {
        "n_messages": len(messages),
        "n_public_messages": sum(m["to"] == "ALL" for m in messages),
        "n_offers": counter["offer"],
        "rounds_used": r,
    }, "history": history, "messages": messages}


# --------------------------------------------------------------------------- debrief

async def debrief(buyers, sellers, framing, model_of, call: Caller, outcome_of: Dict[str, str],
                  history: Dict[str, List[str]]):
    async def ask(agent, role):
        what = history.get(agent.id) or []
        hist = ("What you did:\n" + "\n".join(f"- {h}" for h in what) + "\n\n") if what else ""
        msgs = [{"role": "system", "content": prompts.system_prompt(agent, role, framing)},
                {"role": "user", "content": hist + prompts.DEBRIEF.replace("{outcome}", outcome_of[agent.id])}]
        ctx = {"kind": "debrief", "role": role, "framing": framing, "agent_id": agent.id}
        o = await call(model_of[agent.id], msgs, ctx, {"agent_id": agent.id, "role": role, "round": 0, "kind": "debrief"})
        return agent.id, o or {}
    return dict(await asyncio.gather(*[ask(b, "buyer") for b in buyers], *[ask(s, "seller") for s in sellers]))
