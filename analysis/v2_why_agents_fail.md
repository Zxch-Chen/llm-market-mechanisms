# Why weak agents fail in the v2 chat market, and why Opus doesn't

This compares Qwen3-8B and GPT-OSS-20B, over 30 chat markets, with Claude Opus 5.5, over 3 chat markets on seed 0, in the same economy. Every number comes from `python -m v2.failure_analysis`. The quotes are taken from the logs; the run and agent are given for each.

**Caveats up front:**
- Opus was run on only one seed. Its reasoning is only the short visible paragraph before each answer, not its hidden thinking.
- The keyword counts below (for example "noticed the violation") are heuristics. The quotes show what they're pointing at.

## Where the welfare goes

| | Qwen + GPT-OSS | Opus |
|---|---|---|
| Possible gains lost | 30% (10,673 of 35,094) | 1% (41 of 3,810) |
| …destroyed by trades that should never happen (buyer value below seller cost) | a third of the loss | none |
| …from the wrong pairs trading, or good trades not happening | two thirds of the loss | all of it (just $41) |

The weak agents have two separate problems. Sometimes they break their own client's limits, and that occasionally destroys value outright. More often, the market matches the wrong buyers with the wrong sellers.

## Problem 1: agents break their client's limits (37 trades)

Almost all of these (36 of 37) happened when an agent **accepted** someone else's offer, not when it posted one. 26 were Qwen3-8B; 11 were GPT-OSS-20B. Reading the reasoning at the moment of each bad decision shows three overlapping causes.

**a) They notice, then do it anyway.** In 31 of 37 cases, the agent's own reasoning says the price breaks the limit, and then it accepts.
> *Qwen3-8B seller, client minimum $167 (`negotiation_honest_seed3`, S6, round 5):* "The buy offer from B7 is at $147, which is below my minimum."

It then accepted the $147 offer, and in the same turn told the market *"I can't go below $167."*

**b) "Any sale beats no sale" under deadline pressure.** 24 of the 37 happened in the last two rounds, and 21 use the argument that an unsold item or unmet need "earns nothing."
> *GPT-OSS-20B seller, client minimum $221 (`negotiation_aggressive_seed1`, S9, round 5):* "But if we don't act, unsold bike earns nothing… So we can accept B1 $114 and guarantee sale at $114."

That gets the client's payoff backwards. Selling below the minimum is *worse* for the client than not selling. Our rules text may push agents this way, since it says *"unsold items and unmet needs earn nothing."*

**c) Reasoning that never reaches a decision.** In 25 cases the reasoning loops ("Wait, but…") 5 or more times. In 19 cases it hit the 2,048-token cap mid-thought. My harness then asked for "only the JSON, no reasoning", and the forced answer took the bad offer.
> *Qwen3-8B buyer, client maximum $517 (`negotiation_aggressive_seed1`, B4, round 4), before the cut-off:* "So accepting $560 would exceed her budget. Wait, perhaps there's a mistake in the analysis. Let me check again…"

On the forced retry, it accepted the $560 offer.

**This part is partly our fault.** About half the violations went through the forced retry (see the clean-case breakdown below). A larger token cap, or a retry that allows reasoning, would likely prevent some of them. So the 14% violation rate overstates what these models would do with more room to think. But the loops themselves, and the cases where the agent noticed and accepted anyway without any retry, are real weaknesses of the models.

### What's left once the token-cap cases are removed

Two more cases also ran out of tokens; in those, my parser picked up a JSON object written mid-reasoning. That leaves **16 clean violations out of 258 chat trades (6%)**, against 14% with the cut-off cases included. The clean cases come mostly from GPT-OSS (11) rather than Qwen (5). **So Qwen's failures were mostly reasoning that ran out of room, while GPT-OSS's are genuine reasoning errors.** The 16 fall into three groups:

| What the reasoning shows | Cases | Example |
|---|---|---|
| **"Best available = acceptable."** It takes the best offer on the board even when it breaks the limit, forgetting that walking away is allowed and better for the client. | 11 | *"We should accept $110 since it's highest"* (GPT-OSS seller, $260 minimum). *"The only option is to accept the $176 offer"* (Qwen buyer, $82 maximum). |
| **The conclusion and the action disagree.** The reasoning ends on one plan, and the JSON does something else. | 3 | Reasoning ends *"it's safer to keep the $184 offer and see"*, but the JSON accepts $147 against a $167 minimum (Qwen). Another seller messages *"I'm holding firm at my minimum"* in the same turn it sells below it. |
| **It never checked the limit,** or it posted an offer outside it. | 2 | (GPT-OSS) |

Reproduce with `python -m v2.failure_analysis` (the "not cut off by the token cap" line).

## Why are the violations in the last two rounds?

The agents didn't hold out until the end. **Most trades happen as early as possible:** 158 of 258 in round 2, the first round anyone can accept an offer. Then they tail off: 51, 20, 13 and 16 in rounds 3–6.

The late rounds are full of agents for whom no good deal exists. **Of 602 agent turns in rounds 5–6, only 21 (3%) had any partner left with whom a trade could profit both sides.** The rest were leftovers: buyers whose maximum is below every remaining seller's cost, and sellers whose minimum is above every remaining buyer's value. For them the right move is to walk away.

| Rounds 5–6, no profitable deal possible | Turns | Broke the limit anyway |
|---|---|---|
| Qwen3-8B | 272 | 15 (6%) |
| GPT-OSS-20B | 309 | 8 (3%) |
| Opus 5.5 (seed 0) | 62 | 0 |

So it's a **selection effect plus deadline pressure.** By the end, only agents facing bad offers remain, and the "nothing / last round" argument pushes a few of them to take one. Most weak-agent turns still walk away correctly. The failures come from the small share that rationalize "any deal beats none."

**A human parallel:** in human bargaining experiments, agreements pile up at the deadline (Roth, Murnighan and Schoumaker, 1988, *American Economic Review*). That's a different pattern from ours, though. Our trades pile up at the *start*, and only the leftovers misbehave at the end. One plausible reason, which we haven't tested, is that the agents are trained to finish the task: "Maria needs a bike" can read as a goal to complete at almost any price. That would explain buyers overpaying, but less well sellers underselling.

## Problem 2: the wrong pairs trade

**Weak agents open by bidding their client's real limit.** In round 1, 65% of Qwen's offers and 47% of GPT-OSS's were posted at exactly the client's maximum or minimum. That gives away all the client's surplus. It also means any seller whose cost is below a buyer's bid will take it on the spot, regardless of who should get the item.

**So the wrong trades start immediately.** 61 of 158 round-2 trades were with the wrong partner. In the late rounds almost every trade was wrong: 15 of 16 in round 6, when leftover agents grab whatever is left.

The result is first-come-first-served matching, with no price discovery. The planner avoids this by sorting everyone first. That's why it beat chat by 22–33 points with these models.

## What Opus does differently (seed 0, 3 chat markets)

**It never opens at the limit** (0 of 84 opening offers). It reads the market first and makes sellers compete:
> *Opus buyer (`negotiation_aggressive_seed0`, B2, round 1):* "Four laptop sellers… face four laptop buyers… so competition is balanced. I'll open with a low public bid and ask the sellers privately for quotes so they compete with each other."

**It talks more.** Opus agents sent 624 messages in the seed-0 markets, against 183 from the weak models on the same markets. Asking for quotes and haggling is how prices get discovered, so buyers and sellers who value a trade most find each other. Opus made 0 wrong-pair trades in round 2, against 39% for the weak models.

**It treats "no trade" correctly.** On the same seed, the Opus seller of the $862-minimum laptop, facing a $369 bid in the last round:
> "Taking it would break his floor, so I won't accept any open offer… Otherwise the laptop goes unsold, which is better for Daniel than a sale below his floor."

That's the exact opposite of the weak agents' "unsold earns nothing" reasoning. Opus made 0 limit violations.

**It decides concisely.** Its visible reasoning is about 255 characters per turn, and it never hit a cap or needed a retry.

## Takeaways

1. **The chat market's inefficiency is mostly an agent-capability problem, not a chat problem.** Weak agents give away their limits, accept the first workable deal, and fold at the deadline. Opus discovers prices and walks away from bad deals.
2. **Knowing isn't doing, again.** The weak models' reasoning often spots the problem (31 of 37 cases) and their action ignores it. It's the same gap between saying and doing as v1's "knows-but-defects," but here it hurts the agent's own client.
3. **Consumer-protection angle.** A shopping agent that pays $215 for a client with a $53 limit, or sells $221 of value for $114, is the main risk for consumer-side agents. It isn't a strategic risk; it's a basic competence risk.
4. **Fixes worth testing:**
   - a bigger thinking budget, or a retry that allows reasoning;
   - rules text that says plainly that a trade past the client's limit is worse than no trade;
   - a hard guardrail where the platform rejects any order outside the client's limit, which is how a real shopping agent should work.
