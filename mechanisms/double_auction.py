"""Multi-round call double auction.

Each round, every remaining buyer submits a bid and every remaining seller an
ask. Bids are sorted descending, asks ascending, and the k-th bid is matched
with the k-th ask while bid_k >= ask_k. Each matched pair trades at the
midpoint (bid_k + ask_k) / 2. Traders who transact leave the market (one unit
each). The market runs for N_ROUNDS rounds or until nobody is left on one side.

The class is a step-based state machine so an async runner can query LLM
agents concurrently between steps. `run_double_auction` is a synchronous
convenience wrapper for scripted bots and tests.
"""
from dataclasses import dataclass, field
from typing import Callable, Dict, List

from .types import Buyer, Seller, Trade


@dataclass
class RoundRecord:
    round: int
    bids: Dict[str, float]
    asks: Dict[str, float]
    trades: List[Trade]


@dataclass
class DoubleAuction:
    buyers: List[Buyer]
    sellers: List[Seller]
    n_rounds: int = 5
    history: List[RoundRecord] = field(default_factory=list)
    _active_buyers: List[str] = field(default_factory=list)
    _active_sellers: List[str] = field(default_factory=list)

    def __post_init__(self):
        self._active_buyers = [b.id for b in self.buyers]
        self._active_sellers = [s.id for s in self.sellers]

    # --- state accessors ---------------------------------------------------
    @property
    def round(self) -> int:
        """1-indexed index of the NEXT round to be played."""
        return len(self.history) + 1

    @property
    def done(self) -> bool:
        return (self.round > self.n_rounds
                or not self._active_buyers or not self._active_sellers)

    @property
    def active_buyers(self) -> List[Buyer]:
        return [b for b in self.buyers if b.id in self._active_buyers]

    @property
    def active_sellers(self) -> List[Seller]:
        return [s for s in self.sellers if s.id in self._active_sellers]

    @property
    def trades(self) -> List[Trade]:
        return [t for r in self.history for t in r.trades]

    def public_state(self) -> dict:
        """What an agent may see before choosing a bid/ask: no private values."""
        return {
            "round": self.round,
            "n_rounds": self.n_rounds,
            "n_active_buyers": len(self._active_buyers),
            "n_active_sellers": len(self._active_sellers),
            "past_rounds": [
                {
                    "round": r.round,
                    "bids": sorted(r.bids.values(), reverse=True),
                    "asks": sorted(r.asks.values()),
                    "prices": [t.price for t in r.trades],
                }
                for r in self.history
            ],
        }

    # --- transition ---------------------------------------------------------
    def step(self, bids: Dict[str, float], asks: Dict[str, float]) -> List[Trade]:
        """Clear one round. bids: active buyer_id -> bid; asks: active seller_id -> ask."""
        if self.done:
            raise RuntimeError("auction is finished")
        missing = [i for i in self._active_buyers if i not in bids] + \
                  [j for j in self._active_sellers if j not in asks]
        if missing:
            raise ValueError(f"missing bids/asks for active agents: {missing}")
        bids = {i: bids[i] for i in self._active_buyers}
        asks = {j: asks[j] for j in self._active_sellers}

        sb = sorted(bids.items(), key=lambda kv: kv[1], reverse=True)
        sa = sorted(asks.items(), key=lambda kv: kv[1])
        trades = []
        for (bid_id, bid), (ask_id, ask) in zip(sb, sa):
            if bid >= ask:
                trades.append(Trade(buyer_id=bid_id, seller_id=ask_id,
                                    price=(bid + ask) / 2.0, bid=bid, ask=ask,
                                    round=self.round))
            else:
                break
        for t in trades:
            self._active_buyers.remove(t.buyer_id)
            self._active_sellers.remove(t.seller_id)
        self.history.append(RoundRecord(self.round, bids, asks, trades))
        return trades


BidFn = Callable[[Buyer, dict], float]   # (buyer, public_state) -> bid
AskFn = Callable[[Seller, dict], float]  # (seller, public_state) -> ask


def run_double_auction(buyers: List[Buyer], sellers: List[Seller],
                       bid_fn: BidFn, ask_fn: AskFn, n_rounds: int = 5) -> DoubleAuction:
    """Synchronous wrapper: run all rounds with scripted bid/ask functions."""
    da = DoubleAuction(buyers, sellers, n_rounds=n_rounds)
    while not da.done:
        st = da.public_state()
        bids = {b.id: bid_fn(b, st) for b in da.active_buyers}
        asks = {s.id: ask_fn(s, st) for s in da.active_sellers}
        da.step(bids, asks)
    return da
