# Reproducibility and post-experiment changes

The committed transcripts and summaries record the completed experiment. Public-release cleanup preserves those files, including the six excluded negotiation pilots. New runs go under the ignored `outputs/local/` directory by default.

## Validation of the saved results

During cleanup we recomputed the v2 welfare fields from recorded trade events across all 138 model-backed runs and checked their summary call counts and one-unit constraints. The extra-marginal classification required the tie correction below. We also regenerated the v1 numerical analysis from its 834 decisions and 40 summaries, and compared the output with the committed analysis.

The retained raw JSONL data is byte-for-byte unchanged by the cleanup. Generated mock batches, console launch logs, superseded team notes, presentation handoffs, and unused slide reference images were removed. The written report, presentation and their sources remain available in `report/`.

## Correction to extra-marginal trade counts

The original v2 metric selected one efficient set of traders using agent IDs to break ties. It then classified trades involving any other trader as extra-marginal, even when that trader had the same value or cost as a selected trader. The corrected metric treats traders tied at the marginal value or cost as eligible for an efficient allocation.

This changes three main-batch chat counts, all on seed 8: honest 3 → 2, aggressive 6 → 5, and neutral 1 → 0. The total falls from **121 to 118**. All three corrections are in round 2, changing that rate from 64/158 (40%) to 61/158 (39%). No other retained model-backed run changes. Welfare, efficiency, trade counts, and price-limit violations are unchanged.

The raw `summary.jsonl` files keep their historical fields. `v2.analyze`, `v2.failure_analysis`, the per-batch `results.md` files, and `RESULTS.md` use the corrected classification. Future runs write the corrected metric into their summaries.

## Parser defect found after the experiment

The original v2 JSON extractor counted braces without respecting quoted strings. A brace inside a message could cause it to return a nested object instead of the full action, or to reject valid JSON.

We compared the old and corrected extractors on the initial and retry replies in all retained, completed v2 runs. One extraction differs:

- Batch: `tinker-mix-120b-qwen38`
- Run: `negotiation_neutral_seed1`
- Agent: `S7`, round 5
- File: `outputs/v2/tinker-mix-120b-qwen38/runs/negotiation_neutral_seed1/calls.jsonl`, line 92

The reply contains `Fair?}` inside a message. The old extractor returned the nested public message as the action, dropping that turn's offer and messages. The saved events and resulting metrics reflect the old behavior. We have not rerun the market or estimated how a corrected turn would have changed later decisions. The mixed-model comparison therefore retains this limitation.

The new parser uses Python's JSON decoder to respect strings and nested objects. Other runtime fixes reject boolean/non-finite v1 reports, tolerate malformed negotiation list fields, preserve debrief event identity, and reap timed-out Claude CLI processes. These affect future runs; they do not retroactively alter the experiment.

## Interpretation limits

- Main batches have 10 seeds per condition; model comparisons have one or two. Reusing a seed pairs the private economy, not the model's stochastic response.
- v1 reports use a $0.50 misreport tolerance and 95% t-intervals over 10 seeds. Its analysis script targets the committed ten-seed design, rather than arbitrary new batches.
- `knows_but_defects` is an operational label for misreporting while answering the welfare question truthfully. It is not an independent measure of internal knowledge.
- Invalid planner reports fall back to true limits. Negotiation failures instead yield no action. This asymmetry can favor the planner when models return invalid responses.
- The 37 limit-violating chat trades in the main v2 batch are observed outcomes. Excluding 21 cases flagged for a retry or length cutoff leaves 16; it does not establish what would happen with a larger token budget. The historical failure analysis groups retries and length cutoffs together, and retries can occur for malformed JSON.
- The chat claim detector and reasoning keyword checks are heuristics. Review source transcripts before treating flags as evidence of deception or a particular reasoning process.
- The Claude CLI batch has one seed, includes extra environment context, and returns no thinking text. Comparisons with API backends are exploratory.
- The archived report and presentation cover v1 and predate these cleanup notes. Provider names, prices, and beta API options describe the recorded setup; paid backends were not exercised during cleanup.

## New runs and resuming

Both runners skip completed run IDs. New v2 summaries also record settings, and resumes check those settings and model assignments. Old summaries lack some settings, so model/backend checks alone cannot establish configuration compatibility with an archived batch. Use a fresh output directory for replication.

Deadline-shortened v2 runs count as completed. Incomplete v2 runs restart from the beginning and replace their partial per-run logs. The v1 runner writes decisions before its summary; interruption between those writes can leave decisions without a completed summary. Use a fresh batch after such an interruption to avoid duplicating those rows. Concurrent writers to the same output directory are unsupported.

The mock backend is for offline integration checks. Its shared pseudorandom stream depends on call order and batching, so it is not a substitute for replicating model behavior.
