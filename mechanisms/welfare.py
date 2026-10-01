"""Welfare accounting. All functions use TRUE values/costs, never reports."""
from typing import Dict, List, Tuple

from .types import Buyer, Seller, Trade


def efficient_matching(buyers: List[Buyer], sellers: List[Seller]) -> List[Tuple[Buyer, Seller]]:
    """Welfare-maximizing set of trades: match highest values to lowest costs while v >= c."""
    bs = sorted(buyers, key=lambda b: b.value, reverse=True)
    ss = sorted(sellers, key=lambda s: s.cost)
    pairs = []
    for b, s in zip(bs, ss):
        if b.value >= s.cost:
            pairs.append((b, s))
        else:
            break
    return pairs


def optimal_welfare(buyers: List[Buyer], sellers: List[Seller]) -> float:
    """W* = sum of (v - c) over the efficient matching."""
    return sum(b.value - s.cost for b, s in efficient_matching(buyers, sellers))


def realized_welfare(trades: List[Trade], buyers: List[Buyer], sellers: List[Seller]) -> float:
    """W_realized = sum of (v_i - c_j) over executed trades. Price cancels out."""
    v = {b.id: b.value for b in buyers}
    c = {s.id: s.cost for s in sellers}
    return sum(v[t.buyer_id] - c[t.seller_id] for t in trades)


def efficiency(trades: List[Trade], buyers: List[Buyer], sellers: List[Seller]) -> float:
    """E = W_realized / W*. Returns 1.0 if W* == 0 and nothing traded (nothing to gain)."""
    w_star = optimal_welfare(buyers, sellers)
    w_real = realized_welfare(trades, buyers, sellers)
    if w_star == 0:
        return 1.0 if w_real == 0 else float("-inf")
    return w_real / w_star


def payoffs(trades: List[Trade], buyers: List[Buyer], sellers: List[Seller]) -> Dict[str, float]:
    """Per-agent payoff using true values: buyer v - p, seller p - c, non-traders 0."""
    v = {b.id: b.value for b in buyers}
    c = {s.id: s.cost for s in sellers}
    out = {b.id: 0.0 for b in buyers}
    out.update({s.id: 0.0 for s in sellers})
    for t in trades:
        out[t.buyer_id] += v[t.buyer_id] - t.price
        out[t.seller_id] += t.price - c[t.seller_id]
    return out


def surplus_split(trades: List[Trade], buyers: List[Buyer], sellers: List[Seller]) -> Dict[str, float]:
    """Total buyer surplus vs total seller surplus (and buyer share of the total)."""
    p = payoffs(trades, buyers, sellers)
    buyer_ids = {b.id for b in buyers}
    bs = sum(x for k, x in p.items() if k in buyer_ids)
    ss = sum(x for k, x in p.items() if k not in buyer_ids)
    total = bs + ss
    return {
        "buyer_surplus": bs,
        "seller_surplus": ss,
        "buyer_share": (bs / total) if total > 0 else float("nan"),
    }
