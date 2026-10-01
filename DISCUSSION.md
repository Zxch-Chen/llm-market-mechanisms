# Discussion notes

These are the questions we worked through after the main runs, and what the data says about each. Numbers come from `python -m v2.failure_analysis` and the results files; anything not tested is marked as a guess.

## 1. Why the v1 auction trades at the midpoint

Most real trades happen at a price one side posts and the other accepts: a store's price tag, or the price of the order already waiting on a stock exchange's book. Our v1 auction instead has both sides write down a number at once. If the bid is at least the ask, they trade halfway between. So a bid of 70 against an ask of 30 trades at 50.

We used the midpoint on purpose:
- **Both sides have a reason to shade.** Every $1 a buyer shaves off its bid lowers the price by $0.50, and the seller has the mirror-image incentive. That gives a truthfulness test on both sides at once.
- **It's the standard lab design** (the "k = ½ double auction"). That let us compare with human experiments: Chatterjee and Samuelson (1983), Radner and Schotter (1989), Cason and Friedman (1997).
- **It's easy to run with AI agents.** Collecting all bids and clearing them together is deterministic and lets every agent act at once.

**Can a taker shade with a posted price?** In a one-shot deal, no. The price is fixed, so lowering your private threshold can't lower what you pay; it can only make you walk away from a good deal. When there are repeated chances, the taker can shade by *waiting*: refusing now in the hope of a lower price later. Our v2 chat agents do this.

## 2. Our v1 "market" is basically the planner

Collecting everyone's bids and matching them centrally *is* a centralized mechanism. The first auction round produces the same matching as the planner. The two v1 mechanisms differ only in the price rule (each pair's midpoint vs. one shared price) and in retries (5 rounds vs. 1). So v1 really compares **one-shot vs. repeated centralized clearing.** It doesn't test Hayek's centralized-vs-decentralized question.

**v2 is the real test of that question.** In its chat marketplace there's no central matcher: agents find each other, post offers, haggle and accept. That's also where the big differences appear:
- With weak agents, decentralized trading lost 22–33 more points of efficiency than the planner.
- With Opus, on one seed only, it lost almost nothing.

## 3. Feedback from the instructor, and what we did

| Feedback | What we did |
|---|---|
| Distinguish the **consumer side** (personal agents like Muse or Dots) from the **business side** (models making decisions for firms) | Our v2 buyers are consumer agents: "purchasing agent for Maria." Their main failure was hurting their own user by paying past the user's limit, which is a consumer-protection problem. Business-side agents face different risks: strategic misreporting, and collusion, which LLM pricing agents have been shown to do (Fish et al., 2024). Next step: make the sellers businesses, with inventory, repeated sales and posted prices. |
| Be clearer about **uncertainty** | Every rate now gives its count and denominator. The limit-violation rate is reported as "14% at most, 6% excluding reasoning that was cut off by our token cap." The Opus results are labeled as one market. |
| **Tighten the slides**, with headlines first | Not done yet. The deck brief is in `HANDOFF_SLIDES.md`. |

## 4. Why weak agents fail and Opus doesn't

Full write-up with quotes: `analysis/v2_why_agents_fail.md`. In short:
- **Weak agents open by bidding their client's real limit:** 65% of Qwen3-8B's opening offers and 47% of GPT-OSS-20B's. Opus never did.
- **They take the first workable deal,** so the wrong pairs trade. 40% of round-2 trades were with the wrong partner.
- **Some break their client's limit.** There were 37 such trades, but 21 of them are Qwen reasoning loops cut off by our token cap. The 16 clean cases (11 GPT-OSS, 5 Qwen) are mostly "the best offer on the board must be acceptable": *"accept $110 since it's highest"*, against a $260 minimum.
- **Opus does the opposite.** It asks sellers for competing quotes, sends about 3× more messages, and walks away from bad deals: *"the laptop goes unsold, which is better for Daniel than a sale below his floor."*

## 5. Why the violations cluster in the last two rounds

The agents didn't hold out; the leftovers broke. 158 of 258 weak-agent trades happened in round 2, the first chance to trade. By rounds 5–6, **only 3% of agent turns had any profitable partner left.** Everyone else was a leftover whose client's limit ruled out every remaining deal. Most of them correctly walked away. Qwen broke its limit in 6% of those dead-end turns, GPT-OSS in 3%, and Opus never (0 of 62).

So it's a selection effect plus deadline pressure, not a strategy. Human bargaining shows a different pattern: agreements pile up *at* the deadline (Roth, Murnighan and Schoumaker, 1988). Our trades pile up at the start.

## 6. Objectives: does the agent know how much the purchase matters?

**The idea.** A request like "buy Maria a bike" isn't a complete objective. The agent also needs to know how much getting the bike is worth to Maria, compared with not getting it. Without that, it's misaligned. It can treat "buy the bike" as a task to finish at any price, or "paying less is better" as more important than getting the bike at all. This is the classic principal–agent problem, and the gap between the task as written and what the person actually wants is the core alignment concern.

**What our prompt said.** *"Maria needs a bike to commute… will pay at most $212. Paying less is better for Maria."* In economic terms, $212 is the price at which Maria doesn't care whether she buys or not, so no trade (worth $0 to her) beats any price above $212. But the prompt never says what happens to Maria if there's no deal. And our rules text says *"unmet needs earn nothing,"* which sounds like the worst outcome.

**How the agents filled the gap:**
- **Weak agents often treated the cap as a soft target.** In dead-end situations they reasoned "any deal beats none" or "the best offer must be acceptable," and some crossed it.
- **Opus treated the cap as the point where its client is indifferent between buying and not,** and walked away. It inferred Maria's outside option correctly, even though we never stated it.

**A test of your guess, from data we already have.** If agents treat "needs" as a task to finish, clients with urgent-sounding reasons should see more overpaying. We checked dead-end turns, comparing reasons like "needs a laptop for a new job" with reasons like "wants to start riding on weekends." **We found the opposite.**

| Dead-end turns, weak agents | Urgent reason | Optional reason |
|---|---|---|
| Buyer overpaid | 2 of 232 (0.9%) | 11 of 214 (5.1%) |
| Seller undersold | 2 of 83 (2.4%) | 8 of 123 (6.5%) |

The direction is the same within each good. But there are only a few violations per cell, and each reason goes with one good, so treat this as a hint. **What it suggests:** the failure isn't over-commitment to an urgent goal. It's not understanding the outside option, meaning that "no deal" is a real and sometimes better result. One guess is that agents act more carefully on clearly important requests, and treat "nice to have" purchases loosely.

**A controlled follow-up.** Same markets and limits, varying only how the objective is written:
1. **Current wording:** a cap plus "paying less is better."
2. **Explicit outside option:** "If you don't buy, Maria is no worse off than paying exactly $212; any price above $212 makes her worse off than not buying."
3. **High urgency:** "Maria needs it for work tomorrow," with the same cap.
4. **Low urgency:** "nice to have," with the same cap.
5. **No cap at all,** only a description of the need, so the agent has to work out how much it's worth. This tests whether agents ask for or infer the user's tradeoff.

Measure limit violations, surplus kept for the client, and how often agents walk away. Prediction: (2) cuts violations for weak models. Whether (3) raises them is now an open question, given the hint above.

**Why it matters for real consumer agents.** Real users don't hand over a clean maximum price. The agent has to find out how much the purchase matters. Finance already solved one version of this: a **limit order** states the user's indifference price, and the exchange enforces it mechanically. A consumer-agent platform could do the same, with a hard guardrail that rejects any order outside the user's stated limit, instead of trusting the model's judgment at the deadline.

## 7. Middle-tier models: does a stronger model fix things?

Seeds 0–1, both mechanisms, all three framings; every agent in a market is the same model; thinking cap 4,096 tokens. The small-model row uses the earlier mixed markets on the same seeds, and Opus is seed 0 only. Costs: GPT-OSS-120B $0.61; Qwen3.8-27B $8.47.

| Seeds 0–1 | Qwen3-8B + GPT-OSS-20B | GPT-OSS-120B | Qwen3.8-27B | Opus 5.5 (seed 0) |
|---|---|---|---|---|
| Chat efficiency, mean (worst market) | 69% (35%) | 92% (78%) | 96% (93%) | 99% (98%) |
| Chat trades that broke a client's limit | 7 of 46 | 1 of 44 | 0 of 41 | 0 of 25 |
| Opening offers at the client's exact limit | 55% | 18% | 0% | 0% |
| Wrong-pair trades in round 2 | 11 of 29 | 14 of 30 | 9 of 26 | 0 of 12 |
| Planner misreports: neutral / honest / aggressive | 11% / 7% / 35% | 4% / 4% / 13% | 58% / 31% / 51% | 50% / 0% / 93% |

**What changes with scale:**

1. **Protecting the client improves as models get stronger.** Limit violations go 7 → 1 → 0 → 0, and opening at the exact limit goes 55% → 18% → 0% → 0%. GPT-OSS-120B's thinking was never cut off, and none of its 1,029 calls needed a retry. So the bigger model also removes most of the token-cap artifact.

2. **Matching the right pairs doesn't improve until Opus.** Even GPT-OSS-120B and Qwen3.8-27B made a third to a half of their round-2 trades with the wrong partner. Their chat efficiency is high mainly because they stopped making value-destroying trades. They still take the first workable deal. Opus asks every seller for a quote first.

3. **Capability and honesty are separate things.** Qwen3.8-27B is the most competent of the middle tier: no violations and 96% chat efficiency. It's also the *least* honest. It misreported 58% of the time with no instruction, and 31% of the time even when told explicitly to be honest. GPT-OSS-120B is both competent and honest (4% under the neutral and honest framings).

4. **There are two different ways to break an honesty rule.** We read the thinking of every agent that misreported under the honest framing:
   - **Forgetting the rule (Qwen3.8-27B).** 13 agents misreported, and none of them mentions honesty in its thinking. They reason carefully about the mechanism and optimize "paying less is better for Diego," which also appears in their instructions, and the honesty rule never comes up. Agents whose thinking does mention honesty reported truthfully.
   - **Arguing around the rule (GPT-OSS-20B).** 9 of 14 misreporters do mention honesty, then find a loophole: *"This doesn't misrepresent minimum. It's beyond min. So okay."*
   - Opus followed the rule exactly (0 of 28).

   This ties back to section 6. Our prompt gives the agent two objectives, the client's payoff and an honesty rule, without saying which wins. Different models settle that conflict differently.

**Caveats:**
- Only 2 seeds per model, 1 for Opus.
- Middle-tier markets are all one model, while the small-model markets mixed two. The agents a model trades against may matter.
- The thinking cap was 4,096 here against 2,048 for the small models.
- Treat the differences as directions, not effect sizes.

Reproduce with `python -m v2.failure_analysis tinker-gptoss120b tinker-qwen38-27b`. The tables are in each folder's `results.md`.

## 8. Open questions and next experiments

- **The objectives experiment** in section 6.
- **Pricing rules side by side:** midpoint, posted price, and a rule where honesty is the best strategy (McAfee, 1992).
- **Business-side sellers:** inventory, repeated sales, and the possibility of collusion.
- **Guardrails:** does a platform-enforced limit fix the consumer-side failures without hurting efficiency?
- **A clean Opus comparison:** using an API key and more seeds instead of `claude -p`.
- **More seeds for the middle tier,** and mixed-model markets: do honest agents get exploited by dishonest ones?
- **Objective priority:** state explicitly whether honesty or the client's payoff wins, and see whether Qwen3.8's "forgetting" goes away.
