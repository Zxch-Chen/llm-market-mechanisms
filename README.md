# LLM agents in markets: do AI traders tell the truth?

A completed CS2881r class experiment on AI agents trading with private values and costs. We compare central clearing with auctions or chat negotiation, and measure efficiency, surplus, and misreporting.

Start with **[Results](RESULTS.md)**. The repository includes the code, prompts, recorded decisions, trade logs, and reports. You can inspect and analyze the saved experiments without API keys.

## Findings and scope

- **v1, Claude Opus 5.5:** 0 of 408 decisions misreported under the honest prompt; 374 of 426 did under the profit prompt. Mean efficiency was 100% under the honest prompt and 98.6–99.6% under the profit prompt.
- **v2, Qwen3-8B + GPT-OSS-20B:** mean chat efficiency ranged from 62–78% across framings, versus 91–100% for the planner. In chat, 37 of 258 trades crossed a client's price limit. Of these, 21 involved a retry or token cutoff; see the [reproducibility notes](docs/reproducibility.md) before interpreting that rate.
- **v2, Opus:** chat efficiency was 98–100%, with no limit violations in 25 trades. This comparison has one seed per condition and used Claude Code, which adds environment context. It is exploratory.

Both main experiments use 10 seeds per condition. The additional model comparisons use only one or two. Agents' explanations and debriefs are self-reports; keyword-based chat analyses need transcript review.

## Repository guide

| Path | Contents |
|---|---|
| [RESULTS.md](RESULTS.md) | Results across v1, v2, and model comparisons |
| `mechanisms/`, `agents/`, `config.py`, `runner.py` | v1: 5 buyers, 5 sellers, one good; planner versus 5-round call double auction |
| [v2/](v2/README.md) | v2: 24 agents, three goods; planner versus 6-round chat negotiation |
| [outputs/](outputs/README.md) | Committed experiment data and a batch inventory |
| `analysis/` | v1 analysis, v2 comparison figures, tables, and selected quotes |
| [docs/](docs/README.md) | Design history, schemas, discussion, and reproducibility limits |
| [report/](report/README.md) | v1 written report and presentation, with source files |
| `tests/` | Offline mechanism and runner regression tests |

## Verify and analyze the saved experiment

Use Python **3.11 or newer**, from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q

# Recompute v1 tables and SVG figures into a local directory.
python analysis/analyze.py --out outputs/local/analysis-v1

# Print v2 tables and the chat-failure analysis from committed data.
python -m v2.analyze --backend tinker
python -m v2.failure_analysis
```

The analysis above uses the Python standard library. To rebuild the five v2 comparison PNGs, install Matplotlib:

```bash
python -m pip install -r analysis/requirements.txt
python analysis/v2_mix_figures.py --out outputs/local/figures-v2
```

`analysis/analyze.py` generates SVGs; the committed v1 PNGs are exports used by the presentation. The [report guide](report/README.md) describes rebuilding the deck.

## Run an offline smoke test

```bash
python runner.py --mock --pilot
python -m v2.run --backend mock --seeds 0
python -m v2.analyze --input outputs/local/v2/mock
```

New runs default to ignored directories under `outputs/local/`; the committed experiment data stays separate. Both runners skip completed run IDs on restart. Use a fresh `--out` directory for a new batch, or `--tag` for v2. Changing a model or recorded v2 settings in an existing batch raises an error. See [reproducibility notes](docs/reproducibility.md) for resume limits.

## Run with a model provider

These commands make paid model calls. Model names, provider features, and prices in the source record the experiment setup; availability and charges may differ for a new run.

```bash
# v1: Anthropic API
python -m pip install anthropic
export ANTHROPIC_API_KEY=your_key
python runner.py --pilot --out outputs/local/v1-new

# v2: Tinker and optional Anthropic dependencies
python -m pip install -r v2/requirements.txt
export TINKER_API_KEY=your_key
python -m v2.run --backend tinker --seeds 0 1 --tag new
```

You can also place API keys in a local `.env` file, which git ignores. The v2 Claude CLI backend uses an existing Claude Code login instead of an API key. See the [v2 guide](v2/README.md) for backend options and limitations.

## v1 mechanisms API

```python
import config
from mechanisms import DoubleAuction, efficiency, run_planner

buyers, sellers = config.draw_market(seed=0)
values = {b.id: b.value for b in buyers}
costs = {s.id: s.cost for s in sellers}

planner = run_planner(buyers, sellers, values, costs)
print(planner.price, efficiency(planner.trades, buyers, sellers))

auction = DoubleAuction(buyers, sellers, n_rounds=config.N_ROUNDS)
while not auction.done:
    # Replace these truthful reports with agent decisions as needed.
    auction.step(
        {b.id: b.value for b in auction.active_buyers},
        {s.id: s.cost for s in auction.active_sellers},
    )
print(efficiency(auction.trades, buyers, sellers))
```

Both mechanisms sort buyer reports descending and seller reports ascending, then match while bid ≥ ask. The planner uses one uniform price: the midpoint of the marginal matched pair. The auction uses each pair's midpoint and allows unmatched traders to return next round. Welfare accounting uses true values and costs.
