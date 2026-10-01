"""Central planner (direct-revelation mechanism).

Each buyer reports a value v_hat, each seller a cost c_hat. The planner sorts
reports, matches the k-th highest v_hat with the k-th lowest c_hat while
v_hat_k >= c_hat_k, and charges ONE uniform price equal to the midpoint of the
marginal (last matched) pair: p = (v_hat_k + c_hat_k) / 2.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .types import Buyer, Seller, Trade


@dataclass
class PlannerOutcome:
    trades: List[Trade]
    price: Optional[float]                # None if no pair was matched
    reported_values: Dict[str, float] = field(default_factory=dict)
    reported_costs: Dict[str, float] = field(default_factory=dict)


def run_planner(
    buyers: List[Buyer],
    sellers: List[Seller],
    reported_values: Dict[str, float],
    reported_costs: Dict[str, float],
) -> PlannerOutcome:
    """Run the planner on one set of reports.

    reported_values: buyer_id -> v_hat ; reported_costs: seller_id -> c_hat.
    Every buyer and seller must have a report.
    """
    missing = [b.id for b in buyers if b.id not in reported_values] + \
              [s.id for s in sellers if s.id not in reported_costs]
    if missing:
        raise ValueError(f"missing reports for: {missing}")

    bs = sorted(buyers, key=lambda b: reported_values[b.id], reverse=True)
    ss = sorted(sellers, key=lambda s: reported_costs[s.id])

    matched = []
    for b, s in zip(bs, ss):
        vh, ch = reported_values[b.id], reported_costs[s.id]
        if vh >= ch:
            matched.append((b, s, vh, ch))
        else:
            break

    if not matched:
        return PlannerOutcome(trades=[], price=None,
                              reported_values=dict(reported_values),
                              reported_costs=dict(reported_costs))

    _, _, vh_k, ch_k = matched[-1]
    price = (vh_k + ch_k) / 2.0
    trades = [Trade(buyer_id=b.id, seller_id=s.id, price=price, bid=vh, ask=ch, round=None)
              for b, s, vh, ch in matched]
    return PlannerOutcome(trades=trades, price=price,
                          reported_values=dict(reported_values),
                          reported_costs=dict(reported_costs))
