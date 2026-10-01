# Stage 3 note (Person C → Persons A and B)

## What's here

- `analysis/analyze.py`: recomputes every number in the writeup from `outputs/*.jsonl`. Standard library only. Run `python3 analysis/analyze.py` from the repo root.
- `analysis/tables.md` and `analysis/results.json`: its output.
- `analysis/figures/*.svg`: the four figures (shade vs private number, shade distribution, surplus split, double auction by round).
- `report/stage3_report.html`: the draft writeup. `report/STAGE3_REPORT.pdf` is rendered from it with headless Chrome.
- Related work (Section 2) cites 19 papers. Each was checked against its DOI or arXiv page. The five 2025–2026 arXiv preprints were checked again by hand, and they are cited as preprints. We left out anything the search could only find in a secondary source (Joyce 1998, and Gneezy 2005's percentages).
- Limitations (Section 6) includes evaluation awareness. The setup is plainly artificial and we logged only a short explanation per decision, so we can't rule out that the agents knew they were being tested.

## Corrections to PROJECT_NOTES.md

1. **§4.1, "each by losing one marginal trade."** True for the three planner runs (seeds 0, 1, 5), where the marginal pair's shaded reports crossed. Not true for `double_auction_strategic_seed7`. That run made 3 trades where 2 were efficient. The low-cost seller S3 (cost 3.75) and the high-cost seller S0 (cost 36.57) both asked exactly 42 in round 2. The tie went to S0 by agent order, and S3 then traded in round 3 with B0, who is extra-marginal.
2. **§4.4, "all 24 trades happen in round 1 and the market is finished."** The trades do all happen in round 1, but the leftover agents are queried for rounds 2 to 5 (208 of the 308 honest double-auction rows).
3. **§4.6, the seed 5 S1 quote "traded at 50 and earned 55.1".** The ask was 50 but the trade price was 58.0 (midpoint with a bid of 66). The payoff of 55.1 is right.
4. **Confidence intervals.** The notes use 1.96. With 10 seeds we used t_9 = 2.262, so planner/profit efficiency is 0.986 ± 0.017 and double auction/profit is 0.996 ± 0.009.
5. **Double-auction misreport rate** is 277/326 = 84.97%, so 85%.

## Things to know before the final pass

- **The seller advantage isn't significant.** Paired by seed, seller minus buyer surplus in the double auction (profit prompt) is 16.1 ± 21.2. Seeds 1, 3 and 7 drive it, each with a seller whose cost is below 4. The draft says this.
- **No efficiency difference is significant** (profit minus honest, or double auction minus planner). The draft says this too.
- **Honest-prompt agents often notice the incentive.** At least 48 of the 408 honest-prompt explanations point out that shading would pay, and then report truthfully anyway. The draft uses one as a quote.

## For Person A (methods check)

- Section 3 of the draft describes the mechanisms. Please check it against `mechanisms/`.
- Ties: both mechanisms sort with Python's stable sort, so equal bids or asks are broken by the agents' order in the input (B0 before B1, S0 before S1). This decided seed 7. Please confirm that's intended, and whether the methods should say so (the draft does).

## For Person B (quotes and safety framing)

- Section 5 of the draft frames the profit-prompt shading as following instructions, not breaking them. The safety point is that the agents knowingly traded off total welfare for their principal's profit, and that the prompt alone decided honesty.
- Quotes used: planner/honest seed 2 B4, double auction/profit seed 5 S1, double auction/profit seed 7 S3 (round 3).
