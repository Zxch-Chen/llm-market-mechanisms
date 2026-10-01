"""Scripted baseline agents (no LLM). Used for tests and as reference behavior."""
from .types import Buyer, Seller


def truthful_bid(b: Buyer, state: dict = None) -> float:
    return b.value


def truthful_ask(s: Seller, state: dict = None) -> float:
    return s.cost


def make_shaded(frac: float):
    """Buyers under-report value by frac; sellers over-report cost by frac."""
    def bid(b: Buyer, state: dict = None) -> float:
        return b.value * (1 - frac)

    def ask(s: Seller, state: dict = None) -> float:
        return s.cost * (1 + frac)
    return bid, ask
