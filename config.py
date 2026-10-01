"""Experiment configuration (Stage 1 contract).

Everything downstream (agents, runner, analysis) should import constants from
here rather than hard-coding them.
"""
import random
from typing import List, Tuple

from mechanisms.types import Buyer, Seller

# --- Market size ------------------------------------------------------------
N_BUYERS = 5
N_SELLERS = 5

# Private values (buyers) and costs (sellers) are drawn i.i.d. from U[LOW, HIGH].
VALUE_LOW = 0.0
VALUE_HIGH = 100.0

# --- Double auction ---------------------------------------------------------
N_ROUNDS = 5  # trading rounds per double-auction run

# --- Seeds ------------------------------------------------------------------
SEEDS = list(range(10))  # 0..9 -> 10 markets per condition

# --- LLM agent --------------------------------------------------------------
MODEL_NAME = "claude-opus-5-5"  # override with runner.py --model
TEMPERATURE = 1.0

# --- Conditions (2 mechanisms x 2 prompts) -----------------------------------
MECHANISMS = ["double_auction", "planner"]
PROMPTS = ["truthful", "strategic"]
CONDITIONS = [(m, p) for m in MECHANISMS for p in PROMPTS]

# --- Scripted-bot parameters (used by tests, handy as baselines) -----------
SHADE_FRACTION = 0.20  # bots shade reports by 20%


def draw_market(seed: int) -> Tuple[List[Buyer], List[Seller]]:
    """Deterministically draw one market (buyers' values, sellers' costs).

    Buyers are drawn first, then sellers, so the same seed always yields the
    same market regardless of mechanism or prompt condition.
    """
    rng = random.Random(seed)
    buyers = [
        Buyer(id=f"B{i}", value=round(rng.uniform(VALUE_LOW, VALUE_HIGH), 2))
        for i in range(N_BUYERS)
    ]
    sellers = [
        Seller(id=f"S{j}", cost=round(rng.uniform(VALUE_LOW, VALUE_HIGH), 2))
        for j in range(N_SELLERS)
    ]
    return buyers, sellers
