"""Print candidate quotes from logs: rows where the agent said the truthful report
was welfare-maximizing and misreported anyway (knows_but_defects)."""
import json
from pathlib import Path
import sys

path = sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "outputs/logs.jsonl"
n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
rows = [json.loads(l) for l in open(path) if l.strip()]
kbd = [r for r in rows if r["knows_but_defects"]]
kbd.sort(key=lambda r: (-abs(r["shade"] or 0), -len(r["reasoning"])))
print(f"# Candidate quotes ({len(kbd)} knows-but-defects rows of {len(rows)})\n")
for r in kbd[:n]:
    print(f"## {r['run_id']} / {r['agent_id']} ({r['role']}, round {r['round']})")
    print(f"true={r['true_value']:.2f}  action={r['action']:.2f}  shade={r['shade']:+.2f}  "
          f"wmr={r['welfare_maximizing_report']}  traded={r['traded']}  payoff={r['payoff']:.2f}\n")
    print(f"> {r['reasoning']}\n")
