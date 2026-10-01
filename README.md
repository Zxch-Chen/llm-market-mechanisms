# LLM agents in markets: do AI traders tell the truth?

CS2881r in-class experiment. AI agents act as buyers and sellers with private values and costs. We compare a central planner with a market, under honest and profit-seeking instructions, and measure efficiency, who gets the surplus, and whether agents misreport.

**Start with [RESULTS.md](RESULTS.md)**: v1, v2 and the Opus comparison on one page.

## What's in this repo

| Path | What it is |
|---|---|
| `mechanisms/`, `config.py`, `agents/`, `runner.py` | **v1** (Stages 1–2). A 5×5 single-good market with Claude Opus 5.5 agents. Planner vs. 5-round double auction, honest vs. profit prompt, 40 runs. |
| `outputs/logs.jsonl`, `outputs/summary.jsonl` | v1 data: 834 agent decisions and 40 run summaries. The schema is in `schema.md`. |
| `analysis/` | v1 analysis (`analyze.py`, standard library only), tables, and figures (PNG/SVG). |
| `report/STAGE3_REPORT.pdf` | The v1 writeup, with related work on human double-auction experiments. |
| `report/LLM_Markets_Presentation.pptx` | The slide deck. Rebuild it with `report/deck/build_deck.js`. |
| `v2/` | **v2**, the realistic economy. 24 agents and 3 goods (bikes, laptops, tickets). Each agent works for a named person, in a central planner or a 6-round chat marketplace with messages, under neutral, honest or aggressive framings. Full reasoning is logged. See `v2/README.md`. |
| `outputs/v2/tinker/` | v2 with Qwen3-8B + GPT-OSS-20B: 60 runs (10 markets × 6 conditions). Tables are in `results.md`; every call's prompt and thinking is in `runs/*/calls.jsonl`. |
| `outputs/v2/tinker-gptoss120b/`, `outputs/v2/tinker-qwen38-27b/` | v2 with middle-tier models, seeds 0–1 (12 runs each). |
| `outputs/v2/claude-cli/` | v2 with Claude Opus 5.5 via `claude -p`, on seed 0 only (6 runs). Exploratory: the agents also saw Claude Code's environment context, and no reasoning text is returned. |
| `DISCUSSION.md` | Mechanism design questions, the instructor's feedback, why agents fail, objectives and alignment, and middle-tier results. |
| `NOTES_stage3.md`, `HANDOFF_SLIDES.md` | Corrections to earlier notes; the full results summary and slide brief. |

## Headline results

- **v1 (Opus, simple market).** Honesty acts like a switch. There were 0 of 408 misreports under the honest prompt and 374 of 426 (88%) under the profit prompt. In every one of the 834 decisions, the agent said the truth maximizes welfare. Efficiency stayed at 98.6–99.6%.
- **v2 (Qwen3-8B / GPT-OSS-20B, realistic economy).**
  - Chat negotiation loses far more welfare than the planner: 62–78% vs 91–100% efficiency.
  - Agents broke their own client's price limits in 14% of chat trades.
  - GPT-OSS misreports far more than Qwen, even when told to be honest.
- **v2 with Opus (seed 0, exploratory).**
  - Opus kept 98–100% efficiency even in chat, and never broke a client's limit. This suggests the chat inefficiency comes mostly from weak agents, not from chat itself.
  - Under the neutral framing it still shaded half its planner reports.
  - It reported its own misrepresentations accurately in the debrief.

## Running

```bash
python3 -m venv .venv && .venv/bin/pip install -r v2/requirements.txt
.venv/bin/python -m pytest -q                  # 14 tests, no network
.venv/bin/python analysis/analyze.py           # v1 tables and figures
.venv/bin/python -m v2.run --backend mock      # v2 plumbing, free
.venv/bin/python -m v2.analyze --backend tinker
```

Real v2 runs need `TINKER_API_KEY` (Tinker backend), `ANTHROPIC_API_KEY` (`--backend anthropic`), or a Claude Code login (`--backend claude-cli`), in a local `.env` that git ignores.

---

## v1 mechanisms API

Do LLM agents report truthfully in a double auction vs. a central planner? 2 mechanisms × 2 prompts × 10 seeds = 40 runs.

## Setup

```bash
pip install -r requirements.txt
python -m pytest -q
```

Python 3.9+, no dependencies beyond `pytest`.

## Calling the mechanisms

`config.draw_market(seed)` returns `(buyers, sellers)`: 5 `Buyer(id, value)` and 5 `Seller(id, cost)` with values/costs i.i.d. U[0,100].

**Planner** is one-shot. Collect one report per agent, then

```python
from mechanisms import run_planner, efficiency
out = run_planner(buyers, sellers, reported_values={"B0": 71.0, ...}, reported_costs={"S0": 12.0, ...})
out.trades   # list[Trade(buyer_id, seller_id, price, bid, ask)]
out.price    # single uniform price = midpoint of the marginal matched pair, or None
efficiency(out.trades, buyers, sellers)
```

**Double auction** is a step-based state machine so an async runner can query agents between rounds:

```python
from mechanisms import DoubleAuction
da = DoubleAuction(buyers, sellers, n_rounds=config.N_ROUNDS)
while not da.done:
    state = da.public_state()           # round, counts, past sorted bids/asks/prices (no private info)
    bids = {b.id: ... for b in da.active_buyers}   # ask agents (await them concurrently here)
    asks = {s.id: ... for s in da.active_sellers}
    da.step(bids, asks)                 # returns this round's trades; traders exit after trading
da.trades                              # all trades across rounds
```

Each round: bids sorted descending, asks ascending, k-th bid matched with k-th ask while bid ≥ ask, price = midpoint. `run_double_auction(buyers, sellers, bid_fn, ask_fn)` is a synchronous wrapper for scripted bots (see `mechanisms/bots.py`).

**Welfare** (`mechanisms/welfare.py`, always on true values): `optimal_welfare` (W*), `realized_welfare`, `efficiency` (E = W_realized / W*), `payoffs` (per agent), `surplus_split` (buyer vs seller).

The agent output format and log row schema are in `schema.md`. Design decisions and rationale are in `DESIGN_LOG.md`.
