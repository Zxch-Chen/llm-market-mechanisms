"""A multi-good economy where every AI agent works for a named person.

Each seller agent sells one item for one person, who won't accept less than a
private minimum. Each buyer agent shops for one person, who wants one or two of
the goods and will pay at most a private maximum for each. Values are additive
across goods and each buyer wants at most one unit of each good, so the
efficient allocation can be computed good by good.
"""
import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

GOODS = {
    "bike": {"label": "used road bike", "lo": 60, "hi": 300},
    "laptop": {"label": "refurbished laptop", "lo": 150, "hi": 900},
    "ticket": {"label": "concert ticket", "lo": 40, "hi": 240},
}

N_BUYERS = 12
N_SELLERS = 12  # split evenly across goods

FIRST = ["Maria", "James", "Aisha", "Wei", "Sofia", "Daniel", "Priya", "Lucas", "Fatima", "Noah",
         "Grace", "Mateo", "Hana", "Omar", "Elena", "Kwame", "Chloe", "Ravi", "Zoe", "Diego",
         "Amara", "Ethan", "Leila", "Tomas"]
LAST = ["Lopez", "Carter", "Khan", "Zhang", "Rossi", "Kim", "Patel", "Silva", "Haddad", "Brooks",
        "Nguyen", "Garcia", "Sato", "Farouk", "Novak", "Mensah", "Dubois", "Iyer", "Park", "Reyes",
        "Okafor", "Walsh", "Amini", "Costa"]
BUY_REASON = {
    "bike": ["needs a bike to commute to campus", "wants to start riding on weekends", "just moved and sold their old bike"],
    "laptop": ["needs a laptop for a new job", "had their old laptop die before finals", "wants a second machine for school"],
    "ticket": ["wants to see the show with their sister", "promised a friend a birthday concert", "has wanted to see this band for years"],
}
SELL_REASON = {
    "bike": ["is moving abroad and can't take the bike", "upgraded to a new bike", "rarely rides anymore"],
    "laptop": ["got a new laptop from work", "is clearing out old electronics", "needs cash before rent is due"],
    "ticket": ["can no longer make the concert date", "bought an extra ticket by mistake", "has a work trip that night"],
}


@dataclass
class BuyerAgent:
    id: str
    principal: str
    values: Dict[str, float]          # good -> principal's max price (only goods they want)
    reasons: Dict[str, str] = field(default_factory=dict)


@dataclass
class SellerAgent:
    id: str
    principal: str
    good: str
    cost: float                       # principal's minimum acceptable price
    reason: str = ""


def draw_economy(seed: int) -> Tuple[List[BuyerAgent], List[SellerAgent]]:
    """Deterministically draw one economy from its seed."""
    rng = random.Random(1000 + seed)
    names = [f"{f} {l}" for f, l in zip(rng.sample(FIRST, len(FIRST)), rng.sample(LAST, len(LAST)))]
    goods = list(GOODS)

    sellers = []
    for j in range(N_SELLERS):
        g = goods[j % len(goods)]
        lo, hi = GOODS[g]["lo"], GOODS[g]["hi"]
        sellers.append(SellerAgent(id=f"S{j}", principal=names[j], good=g,
                                   cost=float(round(rng.uniform(lo, hi))),
                                   reason=rng.choice(SELL_REASON[g])))
    buyers = []
    for i in range(N_BUYERS):
        k = 1 if rng.random() < 0.6 else 2
        wanted = rng.sample(goods, k)
        values = {g: float(round(rng.uniform(GOODS[g]["lo"], GOODS[g]["hi"]))) for g in wanted}
        reasons = {g: rng.choice(BUY_REASON[g]) for g in wanted}
        buyers.append(BuyerAgent(id=f"B{i}", principal=names[N_SELLERS + i], values=values, reasons=reasons))
    return buyers, sellers


def efficient_trades(buyers: List[BuyerAgent], sellers: List[SellerAgent]) -> List[Tuple[str, str, str, float]]:
    """Welfare-maximizing trades as (good, buyer_id, seller_id, gain), good by good."""
    out = []
    for g in GOODS:
        bs = sorted(((b.values[g], b.id) for b in buyers if g in b.values), reverse=True)
        ss = sorted((s.cost, s.id) for s in sellers if s.good == g)
        for (v, bid), (c, sid) in zip(bs, ss):
            if v < c:
                break
            out.append((g, bid, sid, v - c))
    return out


def optimal_welfare(buyers, sellers) -> float:
    return sum(t[3] for t in efficient_trades(buyers, sellers))


def welfare_report(trades: List[dict], buyers, sellers) -> dict:
    """Score a list of trades {good, buyer, seller, price} with true values."""
    B = {b.id: b for b in buyers}
    S = {s.id: s for s in sellers}
    w_star = optimal_welfare(buyers, sellers)
    buyer_surplus = sum(B[t["buyer"]].values[t["good"]] - t["price"] for t in trades)
    seller_surplus = sum(t["price"] - S[t["seller"]].cost for t in trades)
    w = buyer_surplus + seller_surplus
    eff = efficient_trades(buyers, sellers)
    eff_pairs = {(g, b) for g, b, _, _ in eff} | {(g, s) for g, _, s, _ in eff}
    return {
        "W_star": w_star,
        "W_realized": w,
        "efficiency": w / w_star if w_star > 0 else float("nan"),
        "n_trades": len(trades),
        "n_efficient_trades": len(eff),
        "buyer_surplus": buyer_surplus,
        "seller_surplus": seller_surplus,
        "losing_trades": sum(1 for t in trades if B[t["buyer"]].values[t["good"]] < t["price"]
                             or t["price"] < S[t["seller"]].cost),
        "extra_marginal_trades": sum(1 for t in trades if (t["good"], t["buyer"]) not in eff_pairs
                                     or (t["good"], t["seller"]) not in eff_pairs),
    }
