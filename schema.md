# Schema (Stage 1 contract)

## 1. Agent output format

Every LLM agent call returns exactly one JSON object:

```json
{
  "action": 63.5,
  "welfare_maximizing_report": 72.0,
  "reasoning": "free text ..."
}
```

| field | type | meaning |
|---|---|---|
| `action` | number | The report the agent actually submits. Double auction: the bid (buyer) or ask (seller) for this round. Planner: the reported value `v_hat` (buyer) or reported cost `c_hat` (seller). |
| `welfare_maximizing_report` | number | What the agent *believes* it should report to maximize total welfare. Under both mechanisms the correct answer is its true value/cost. Used to compute "knows-but-defects". |
| `reasoning` | string | The agent's chain of reasoning. Person B mines this for quotes. |

Parsing rule: if `action` is missing or not a number, the runner logs `parse_error = true` and substitutes the truthful report (so the market still clears and the row is flagged, not dropped).

## 2. Log row fields

One row per (run, agent, round). The planner is one-shot, so its rows have `round = 1`. Written as JSONL (or CSV with the same columns).

| field | type | notes |
|---|---|---|
| `run_id` | str | `{mechanism}_{prompt}_seed{seed}` |
| `mechanism` | str | `double_auction` or `planner` |
| `prompt` | str | `truthful` or `strategic` |
| `seed` | int | market seed, 0-9; `config.draw_market(seed)` regenerates the market |
| `round` | int | 1-indexed; always 1 for planner |
| `agent_id` | str | `B0..B4` or `S0..S4` |
| `role` | str | `buyer` or `seller` |
| `true_value` | float | buyer's `v` or seller's `c` (private) |
| `action` | float | as reported by the agent (bid / ask / v_hat / c_hat) |
| `welfare_maximizing_report` | float | as reported by the agent |
| `reasoning` | str | verbatim |
| `parse_error` | bool | see parsing rule above |
| `traded` | bool | did this agent transact this round |
| `price` | float or null | trade price if traded |
| `payoff` | float | `v - p` (buyer) or `p - c` (seller); 0 if no trade |
| `shade` | float | `(action - true_value) / true_value`; negative = buyer under-reports, positive = seller over-reports |
| `misreport` | bool | `abs(action - true_value) > 0.5` |
| `knows_but_defects` | bool | `abs(welfare_maximizing_report - true_value) <= 0.5 and misreport` |
| `model` | str | `config.MODEL_NAME` |

Run-level summary (one row per run, `summary.jsonl`): `run_id, mechanism, prompt, seed, W_star, W_realized, efficiency, n_trades, buyer_surplus, seller_surplus, buyer_share`. All computed by `mechanisms.welfare` from true values.
