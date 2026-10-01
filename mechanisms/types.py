from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Buyer:
    id: str
    value: float  # true private value v_i


@dataclass(frozen=True)
class Seller:
    id: str
    cost: float  # true private cost c_j


@dataclass(frozen=True)
class Trade:
    buyer_id: str
    seller_id: str
    price: float
    bid: float          # buyer's report (bid or reported value)
    ask: float          # seller's report (ask or reported cost)
    round: Optional[int] = None  # 1-indexed round for the double auction; None for planner
