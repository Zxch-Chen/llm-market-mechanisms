# Stage 2 handoff note (Person B → Person C)

**Data:** `outputs/logs.jsonl` (834 agent rows) and `outputs/summary.jsonl` (40 run rows), schema in `schema.md`. Model: `claude-opus-5-5`, effort medium, every one of the 758 launch calls was served by that model (no fallback fired). Cost: ~683k input / ~226k output tokens.

**Headline numbers (mean over 10 seeds):**

| condition | E | misreport rate | knows-but-defects | buyer share |
|---|---|---|---|---|
| planner / truthful | 1.000 | 0.00 | 0.00 | 0.50 |
| planner / strategic | 0.986 | 0.97 | 0.97 | 0.48 |
| double auction / truthful | 1.000 | 0.00 | 0.00 | 0.50 |
| double auction / strategic | 0.996 | 0.86 | 0.86 | 0.43 |

**Things to know before analysing:**

1. **Relative shade is dominated by tiny costs.** Sellers with cost ~1–3 asked 40–50, giving `shade` of +15 to +29. Mean seller shade (+0.79) is meaningless; use the median (+0.064 sellers, −0.107 buyers) or absolute shade `|action − true|` (median 4.05 sellers, 2.67 buyers). A histogram of relative shade needs clipping or a log axis.
2. **Efficiency barely moves despite near-universal misreporting.** Markets have only 1–4 efficient pairs and the gains from trade for those pairs are usually large, so shading rarely flips a match. The interesting quantity is the surplus split (buyer share drops to 0.43 in the DA), not E. The 2×2 efficiency table will look flat; say why.
3. **`welfare_maximizing_report` equals the true value in 100% of rows.** Every agent, in every condition, correctly identified the truthful report as welfare-maximizing. So `misreport` and `knows_but_defects` are identical columns in this dataset; the knows-but-defects rate is simply the misreport rate.
4. **The truthful prompt produced zero misreports** (0 of 408 rows). Instruction-following was perfect; the safety story is entirely in the strategic condition.
5. **Strategic DA rows are more numerous** (326 vs 308 truthful) because shaded bids fail to match early and the market runs all 5 rounds in every strategic seed. The misreport rate in the DA falls in late rounds as unmatched agents converge to truthful reports; consider a per-round plot.
6. **Structural note from Stage 1:** with sort-and-match clearing, one round of the DA is the same matching as the planner; they differ in price (per-pair midpoint vs uniform) and in the DA's repeated rounds with public bid/ask history. Truthful bots give E = 1 exactly in both, so all inefficiency is attributable to agent behavior.
7. **No weirdness:** 0 parse errors, 0 refusals in the final data, 0 actions outside [0, 100], 0 negative payoffs, no run with zero trades. A first pilot had 45/72 refusals (`reasoning_extraction` category) from asking for "your full reasoning"; that data was discarded, the prompt reworded, and the pilot rerun (see `DESIGN_LOG.md`).

**Reproduce:** `.venv/bin/python runner.py` (resumes; delete `outputs/*.jsonl` to rerun from scratch). Quotes: `quotes.md`, candidates via `.venv/bin/python quotes.py`.
