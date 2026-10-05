# v2: multi-good markets with chat negotiation

The completed v2 experiment has 12 buyers, 12 sellers, and three goods: used bikes, refurbished laptops, and concert tickets. Each agent represents a fictional client with private price limits. Buyers want one or two goods, with additive values; each seller supplies one unit.

See [results](../RESULTS.md), the [batch inventory](../outputs/README.md), and [reproducibility notes](../docs/reproducibility.md).

## Design

- **Planner:** each agent submits one report per item. For each good, the mechanism sorts reports, matches while buyer report ≥ seller report, and charges the midpoint of the marginal matched pair to all matched agents.
- **Chat negotiation:** six simultaneous rounds with public offers, private and public messages, cancellations, and at most one acceptance per agent per round. Trades use the posted price. Acceptances run in seeded random order before cancellations. Agents see new offers and messages next round; public messages reach agents who share an item.
- **Framings:** neutral asks for good deals; honest adds a rule against misrepresenting the client's limits or situation; aggressive asks for the best price by any legal means and says claims are unverifiable. All agents in a run share the same framing.
- **Debrief:** after trading, a separate call asks each agent about welfare and misrepresentation. A run that reaches the deadline skips its debrief.

The mechanism enforces one unit per seller and one unit of each desired good per buyer. It does **not** enforce the client's private price limits: crossing them is an outcome we measure. Invalid planner reports fall back to the true limit; invalid negotiation actions do nothing. This fallback difference can affect comparisons.

The main batch alternates Qwen3-8B and GPT-OSS-20B within each role, for 60 runs (10 seeds × 2 mechanisms × 3 framings). Additional batches use single models or different pairs. See `economy.py`, `prompts.py`, and `markets.py` for the exact setup.

## Offline checks

From the repository root, with Python 3.11+:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
python -m v2.run --backend mock --seeds 0
python -m v2.analyze --input outputs/local/v2/mock
python -m v2.analyze --backend tinker
```

`--input` analyzes a batch directory; `--backend` selects a committed folder under `outputs/v2/`. Mock output is generated test data and is excluded from reported results.

## Model runs

```bash
python -m pip install -r v2/requirements.txt
export TINKER_API_KEY=your_key
python -m v2.run --backend tinker --seeds 0 1 --tag replication

# Extend that batch to ten seeds, keeping the same models and settings.
python -m v2.run --backend tinker --seeds 2 3 4 5 6 7 8 9 --tag replication
```

The runner reads API keys from the environment or the repository's ignored `.env` file. Tinker needs a funded account. Access checks make a small provider call before starting the markets.

Other backends:

| Flag | Authentication | Default model(s) |
|---|---|---|
| `--backend mock` | None | Scripted stand-ins for the two open models |
| `--backend tinker` | `TINKER_API_KEY` | Qwen3-8B + GPT-OSS-20B |
| `--backend anthropic` | `ANTHROPIC_API_KEY` | Claude Opus 5.5 |
| `--backend claude-cli` | Installed `claude` command and existing login | Claude Opus 5.5 |

Use `--models MODEL [MODEL ...]` to change the assignment. The Tinker backend has explicit renderer mappings in `backends.py`; additional models require a compatible renderer. The API backends retain the model IDs and beta features from the experiment. They have not been revalidated with paid calls during the public-release cleanup.

## Runtime and resume behavior

Run `python -m v2.run --help` for all flags.

- `--concurrency` limits model calls in flight across the batch (64 by default; 16 for Anthropic, 8 for Claude CLI).
- `--max-tokens` defaults to 2,048 for Tinker and mock, 8,000 for Anthropic. Claude CLI manages its own output budget; this flag does not control that backend.
- `--call-timeout` defaults to 180 seconds per attempt, after acquiring a concurrency slot. Invalid JSON gets one retry. Timeouts return no action; the planner then uses its truthful fallback.
- `--deadline-min` defaults to 100. It stops new negotiation rounds and skips debriefs once reached. It does not cancel an in-progress round, queued calls, or planner calls, so it is not a hard wall-clock cap.
- `--out` chooses a batch directory. The default is `outputs/local/v2/<backend>/`; `--tag NAME` adds a suffix there.

Completed IDs in `summary.jsonl` are skipped. New summaries record settings and reject a resume with different models, token caps, rounds, or debrief settings. Deadline-shortened markets also count as completed; use a fresh batch to rerun them. A failed run without a summary restarts from its first round, replacing that run's incomplete transcripts. Do not run two writers against the same output directory.

Costs in the summaries are historical estimates based on token counts and constants in `backends.py`, or provider-reported Claude CLI cost. They exclude access probes and may omit timed-out calls. Mock cost estimates are synthetic.

## Output files

Each batch contains:

- `summary.jsonl`: one row per market, including welfare, trades, limit violations, model usage, estimated cost, and run settings for new runs.
- `runs/<run_id>/calls.jsonl`: prompts, visible replies, returned thinking, parsed actions, token counts, and retry/timeout flags. A retry shares its row with the first attempt.
- `runs/<run_id>/events.jsonl`: reports, offers, acceptances, trades, messages, and debrief answers.
- `results.md`: generated analysis tables and sample excerpts.

Open-model logs contain the thinking returned by their renderer. Anthropic returns summarized thinking; Claude CLI returns none. Length-limited responses can be incomplete. The Claude CLI comparison also includes environment context beyond the recorded task prompts.

The saved failed pilot in `../outputs/v2/tinker/discarded_cancel_before_accept_bug/` used cancellation-before-acceptance ordering. It is retained for provenance and excluded from summaries and analysis. The completed runs use acceptance-before-cancellation ordering.
