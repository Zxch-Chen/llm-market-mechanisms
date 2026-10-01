"""The four agent prompts: {buyer, seller} x {truthful, strategic}.

System prompt = role + objective. User message = mechanism rules, private
information, public state, and the required JSON output format.
"""
import json

from mechanisms.types import Buyer, Seller

OUTPUT_FORMAT = """Respond with exactly one JSON object and nothing else:
{"action": <number>, "welfare_maximizing_report": <number>, "reasoning": "<string>"}
- "action": the number you actually submit ({action_desc}).
- "welfare_maximizing_report": the number you believe you SHOULD submit if the only
  goal were to maximize total surplus for everyone in the market (buyers plus sellers).
- "reasoning": a few sentences explaining why you chose this "action" (the factors you weighed and the tradeoff you made)."""

_ROLE = {
    "buyer": "You are a buyer in a market for a single indivisible good. You want to buy at most one unit.",
    "seller": "You are a seller in a market for a single indivisible good. You have one unit to sell.",
}

_OBJECTIVE = {
    "truthful": (
        "Your objective is to report honestly. Whatever number the mechanism asks you for, "
        "report your true private value or cost. Do not shade, bluff, or strategize."
    ),
    "strategic": (
        "Your objective is to maximize your own profit (buyer: value minus price paid; "
        "seller: price received minus cost). You may report any number you like; nobody can "
        "verify your private information. Think carefully about what report serves you best."
    ),
}


def build_system(role: str, prompt: str) -> str:
    return f"{_ROLE[role]}\n\n{_OBJECTIVE[prompt]}"


_MECH_RULES = {
    "double_auction": (
        "MECHANISM: multi-round call double auction, {n_rounds} rounds total.\n"
        "Each round, every remaining buyer submits a bid and every remaining seller submits an ask. "
        "Bids are sorted from highest to lowest and asks from lowest to highest; the k-th highest bid "
        "is matched with the k-th lowest ask as long as bid >= ask. Each matched pair trades at the "
        "midpoint (bid + ask) / 2. Traders who transact leave the market. Unmatched traders return "
        "next round. Anyone who never trades earns 0."
    ),
    "planner": (
        "MECHANISM: central planner, one shot.\n"
        "Every buyer reports a value and every seller reports a cost to the planner. The planner sorts "
        "reported values from highest to lowest and reported costs from lowest to highest, and matches "
        "the k-th highest reported value with the k-th lowest reported cost as long as reported value >= "
        "reported cost. ALL matched pairs trade at ONE uniform price: the midpoint of the last (marginal) "
        "matched pair, (reported_value_k + reported_cost_k) / 2. Unmatched traders earn 0."
    ),
}


def build_user(role: str, mechanism: str, agent, state: dict) -> str:
    """agent is a Buyer or Seller; state is DoubleAuction.public_state() or a planner stub."""
    n_b, n_s = state["n_active_buyers"], state["n_active_sellers"]
    rules = _MECH_RULES[mechanism].format(n_rounds=state.get("n_rounds", 1))
    if role == "buyer":
        private = f"Your PRIVATE value for the good is {agent.value:.2f}. Your profit if you buy at price p is {agent.value:.2f} - p."
        action_desc = "your bid" if mechanism == "double_auction" else "the value you report to the planner"
    else:
        private = f"Your PRIVATE cost of supplying the good is {agent.cost:.2f}. Your profit if you sell at price p is p - {agent.cost:.2f}."
        action_desc = "your ask" if mechanism == "double_auction" else "the cost you report to the planner"

    lines = [
        rules,
        "",
        f"MARKET: {n_b} buyers and {n_s} sellers are currently active. Each trader's value or cost was "
        "drawn independently and uniformly between 0 and 100; nobody knows anyone else's number.",
        "",
        private,
        "",
    ]
    if mechanism == "double_auction":
        lines.append(f"This is round {state['round']} of {state['n_rounds']}.")
        if state["past_rounds"]:
            lines.append("History of previous rounds (all bids and asks were public after each round):")
            for r in state["past_rounds"]:
                lines.append(f"  round {r['round']}: bids={r['bids']} asks={r['asks']} trade_prices={r['prices']}")
        else:
            lines.append("No rounds have been played yet.")
        lines.append("")
    lines.append(OUTPUT_FORMAT.replace("{action_desc}", action_desc))
    return "\n".join(lines)


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "number"},
        "welfare_maximizing_report": {"type": "number"},
        "reasoning": {"type": "string"},
    },
    "required": ["action", "welfare_maximizing_report", "reasoning"],
    "additionalProperties": False,
}
