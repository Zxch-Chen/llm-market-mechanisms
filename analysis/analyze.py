"""Stage 3 analysis: recompute every number in the writeup and draw the figures.

Standard library only. Run from the repo root:

    python3 analysis/analyze.py

Reads outputs/logs.jsonl and outputs/summary.jsonl. Writes
analysis/results.json, analysis/tables.md and analysis/figures/*.svg.

Confidence intervals are 95% t-intervals over the 10 seeds (t_9 = 2.262).
Every condition uses the same 10 markets, so comparisons between conditions
are paired by seed.
"""
import argparse
import json
import math
import os
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import config  # noqa: E402
from mechanisms.welfare import efficient_matching  # noqa: E402

OUT = os.path.join(ROOT, "analysis")
FIG = os.path.join(OUT, "figures")
T9 = 2.262  # two-sided 95% t critical value, 9 degrees of freedom

MECHS = ["planner", "double_auction"]
PROMPTS = ["truthful", "strategic"]
MECH_LABEL = {"planner": "Planner", "double_auction": "Double auction"}
PROMPT_LABEL = {"truthful": "honest", "strategic": "profit"}


def load(name):
    with open(os.path.join(ROOT, "outputs", name)) as f:
        return [json.loads(line) for line in f if line.strip()]


def tci(xs):
    """Mean and 95% t half-width over seeds."""
    m = st.mean(xs)
    if len(xs) < 2:
        return m, 0.0
    return m, T9 * st.stdev(xs) / math.sqrt(len(xs))


def abs_shade(r):
    return abs(r["action"] - r["true_value"])


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------

def compute(logs, summ):
    S = {s["run_id"]: s for s in summ}
    res = {"conditions": {}, "shade": {}, "da_rounds": {}, "paired": {},
           "lossy_runs": [], "counts": {}}

    for m in MECHS:
        for p in PROMPTS:
            runs = [S[f"{m}_{p}_seed{k}"] for k in config.SEEDS]
            rows = [r for r in logs if r["mechanism"] == m and r["prompt"] == p]
            per_run_mis = [st.mean(r["misreport"] for r in rows if r["seed"] == k)
                           for k in config.SEEDS]
            c = {
                "efficiency": tci([s["efficiency"] for s in runs]),
                "efficiency_min": min(s["efficiency"] for s in runs),
                "n_rows": len(rows),
                "n_misreport": sum(r["misreport"] for r in rows),
                "misreport_rate_rows": st.mean(r["misreport"] for r in rows),
                "misreport_rate_runs": tci(per_run_mis),
                "n_knows_but_defects": sum(r["knows_but_defects"] for r in rows),
                "buyer_surplus": tci([s["buyer_surplus"] for s in runs]),
                "seller_surplus": tci([s["seller_surplus"] for s in runs]),
                "buyer_share": tci([s["buyer_share"] for s in runs]),
                "n_trades": sum(s["n_trades"] for s in runs),
            }
            res["conditions"][f"{m}/{p}"] = c

    res["counts"] = {
        "rows": len(logs),
        "runs": len(summ),
        "parse_errors": sum(r["parse_error"] for r in logs),
        "wmr_equals_truth": sum(r["welfare_maximizing_report"] is not None and
                                abs(r["welfare_maximizing_report"] - r["true_value"]) <= 0.5
                                for r in logs),
        "wrong_direction_misreports": sum(
            r["misreport"] and ((r["role"] == "buyer") == (r["action"] > r["true_value"]))
            for r in logs),
        "efficient_trades_total": sum(len(efficient_matching(*config.draw_market(k)))
                                      for k in config.SEEDS),
    }
    strat = [r for r in logs if r["prompt"] == "strategic"]
    res["counts"]["strategic_rows"] = len(strat)
    res["counts"]["strategic_misreports"] = sum(r["misreport"] for r in strat)

    # How much they shade (strategic prompt only; truthful never misreports).
    for m in MECHS:
        for role in ["buyer", "seller"]:
            rows = [r for r in strat if r["mechanism"] == m and r["role"] == role]
            res["shade"][f"{m}/{role}"] = {
                "n": len(rows),
                "median_relative": st.median(r["shade"] for r in rows),
                "median_absolute": st.median(abs_shade(r) for r in rows),
                "max_relative": max(abs(r["shade"]) for r in rows),
            }

    # Double auction round by round.
    for p in PROMPTS:
        out = []
        for k in range(1, config.N_ROUNDS + 1):
            rows = [r for r in logs if r["mechanism"] == "double_auction"
                    and r["prompt"] == p and r["round"] == k]
            if not rows:
                continue
            out.append({
                "round": k,
                "rows": len(rows),
                "misreport_rate": st.mean(r["misreport"] for r in rows),
                "median_abs_shade": st.median(abs_shade(r) for r in rows),
                "trades": sum(r["traded"] for r in rows) // 2,
            })
        res["da_rounds"][p] = out

    # Paired comparisons across seeds.
    def diff(f):
        return tci([f(k) for k in config.SEEDS])
    for m in MECHS:
        res["paired"][f"{m}/strategic seller minus buyer surplus"] = diff(
            lambda k: S[f"{m}_strategic_seed{k}"]["seller_surplus"]
            - S[f"{m}_strategic_seed{k}"]["buyer_surplus"])
        res["paired"][f"{m} efficiency, profit minus honest"] = diff(
            lambda k: S[f"{m}_strategic_seed{k}"]["efficiency"]
            - S[f"{m}_truthful_seed{k}"]["efficiency"])
    res["paired"]["strategic efficiency, double auction minus planner"] = diff(
        lambda k: S[f"double_auction_strategic_seed{k}"]["efficiency"]
        - S[f"planner_strategic_seed{k}"]["efficiency"])

    # Why each inefficient run lost welfare: a missed efficient trade, or an
    # extra-marginal trader getting in.
    for s in summ:
        if s["efficiency"] >= 1 - 1e-9:
            continue
        buyers, sellers = config.draw_market(s["seed"])
        eff = efficient_matching(buyers, sellers)
        eff_ids = {b.id for b, _ in eff} | {x.id for _, x in eff}
        traded = {r["agent_id"] for r in logs if r["run_id"] == s["run_id"] and r["traded"]}
        res["lossy_runs"].append({
            "run_id": s["run_id"],
            "efficiency": s["efficiency"],
            "efficient_trades": len(eff),
            "actual_trades": s["n_trades"],
            "efficient_traders_left_out": sorted(eff_ids - traded),
            "extra_marginal_traders_in": sorted(traded - eff_ids),
        })
    return res


# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------

def fmt_ci(t, d=3):
    return f"{t[0]:.{d}f} ± {t[1]:.{d}f}"


def tables(res):
    L = ["# Stage 3 tables", "",
         "Generated by `analysis/analyze.py`. ± is a 95% t-interval over 10 seeds.", "",
         "## Main results", "",
         "| condition | efficiency | min | misreports | knows-but-defects | buyer surplus | seller surplus | buyer share | trades |",
         "|---|---|---|---|---|---|---|---|---|"]
    for m in MECHS:
        for p in PROMPTS:
            c = res["conditions"][f"{m}/{p}"]
            L.append(
                f"| {MECH_LABEL[m]}, {PROMPT_LABEL[p]} prompt | {fmt_ci(c['efficiency'])} | "
                f"{c['efficiency_min']:.3f} | {c['n_misreport']}/{c['n_rows']} "
                f"({100 * c['misreport_rate_rows']:.0f}%) | {c['n_knows_but_defects']} | "
                f"{fmt_ci(c['buyer_surplus'], 1)} | {fmt_ci(c['seller_surplus'], 1)} | "
                f"{fmt_ci(c['buyer_share'], 2)} | {c['n_trades']} |")
    L += ["", "## Shading under the profit prompt", "",
          "| mechanism | role | rows | median relative shade | median absolute shade |",
          "|---|---|---|---|---|"]
    for k, v in res["shade"].items():
        m, role = k.split("/")
        L.append(f"| {MECH_LABEL[m]} | {role} | {v['n']} | {v['median_relative']:+.3f} | "
                 f"{v['median_absolute']:.2f} |")
    for p in PROMPTS:
        L += ["", f"## Double auction by round, {PROMPT_LABEL[p]} prompt", "",
              "| round | agent rows | misreport rate | median absolute shade | trades |",
              "|---|---|---|---|---|"]
        for r in res["da_rounds"][p]:
            L.append(f"| {r['round']} | {r['rows']} | {r['misreport_rate']:.2f} | "
                     f"{r['median_abs_shade']:.2f} | {r['trades']} |")
    L += ["", "## Paired differences across seeds", "", "| comparison | mean ± 95% CI |", "|---|---|"]
    for k, v in res["paired"].items():
        L.append(f"| {k} | {fmt_ci(v, 3 if 'efficiency' in k else 1)} |")
    L += ["", "## Runs that lost efficiency", "",
          "| run | efficiency | efficient trades | actual trades | efficient traders left out | extra-marginal traders in |",
          "|---|---|---|---|---|---|"]
    for r in res["lossy_runs"]:
        L.append(f"| {r['run_id']} | {r['efficiency']:.3f} | {r['efficient_trades']} | "
                 f"{r['actual_trades']} | {', '.join(r['efficient_traders_left_out']) or '-'} | "
                 f"{', '.join(r['extra_marginal_traders_in']) or '-'} |")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------
# Figures (hand-written SVG, light theme for print)
# --------------------------------------------------------------------------

INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURF = "#e1e0d9", "#c3c2b7", "#fcfcfb"
BUYER, SELLER = "#2a78d6", "#eb6834"
FONT = 'font-family="system-ui, -apple-system, Segoe UI, sans-serif"'


class Svg:
    def __init__(self, w, h):
        self.w, self.h, self.parts = w, h, []

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, size=12, fill=INK2, anchor="start", weight="400"):
        s = str(s).replace("&", "&amp;").replace("<", "&lt;")
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
                 f'text-anchor="{anchor}" font-weight="{weight}" {FONT}>{s}</text>')

    def line(self, x1, y1, x2, y2, stroke=GRID, width=1):
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                 f'stroke="{stroke}" stroke-width="{width}"/>')

    def column(self, x, y0, y1, w, fill):
        """Column from baseline y0 up to y1 with a 4px rounded top."""
        h = y0 - y1
        if h <= 0:
            return
        r = min(4, h, w / 2)
        self.add(f'<path d="M{x:.1f},{y0:.1f} V{y1 + r:.1f} Q{x:.1f},{y1:.1f} {x + r:.1f},{y1:.1f} '
                 f'H{x + w - r:.1f} Q{x + w:.1f},{y1:.1f} {x + w:.1f},{y1 + r:.1f} V{y0:.1f} Z" '
                 f'fill="{fill}"/>')

    def dot(self, x, y, fill, r=4):
        self.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" '
                 f'fill-opacity="0.8" stroke="{SURF}" stroke-width="1.5"/>')

    def legend(self, x, y, items):
        for label, color in items:
            self.add(f'<rect x="{x}" y="{y - 9}" width="10" height="10" rx="2" fill="{color}"/>')
            self.text(x + 15, y, label, 12, INK2)
            x += 15 + 7.2 * len(label) + 18

    def save(self, path):
        body = "\n".join(self.parts)
        with open(path, "w") as f:
            f.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
                    f'width="{self.w}" height="{self.h}">\n'
                    f'<rect width="{self.w}" height="{self.h}" fill="{SURF}"/>\n{body}\n</svg>\n')


def y_axis(svg, x0, x1, top, bot, lo, hi, ticks, fmt=lambda v: f"{v:g}"):
    def sy(v):
        return bot - (v - lo) / (hi - lo) * (bot - top)
    for t in ticks:
        svg.line(x0, sy(t), x1, sy(t), GRID if t != 0 or lo == 0 else AXIS)
        svg.text(x0 - 6, sy(t) + 4, fmt(t), 11, MUTED, "end")
    return sy


def fig_surplus(res, path):
    """Buyer vs seller surplus per condition, with 95% CI whiskers."""
    svg = Svg(680, 330)
    svg.legend(56, 22, [("Buyers", BUYER), ("Sellers", SELLER)])
    top, bot, x0, x1 = 44, 262, 56, 664
    sy = y_axis(svg, x0, x1, top, bot, 0, 90, [0, 15, 30, 45, 60, 75, 90])
    svg.text(14, (top + bot) / 2, "Mean surplus per market", 11, MUTED, "middle")
    svg.parts[-1] = svg.parts[-1].replace("<text ", f'<text transform="rotate(-90 14 {(top + bot) / 2})" ', 1)
    groups = [(m, p) for m in MECHS for p in PROMPTS]
    gw = (x1 - x0) / len(groups)
    bw = 24
    for i, (m, p) in enumerate(groups):
        c = res["conditions"][f"{m}/{p}"]
        cx = x0 + gw * (i + 0.5)
        for j, (key, color) in enumerate([("buyer_surplus", BUYER), ("seller_surplus", SELLER)]):
            mean, hw = c[key]
            bx = cx - bw - 1 + j * (bw + 2)
            svg.column(bx, sy(0), sy(mean), bw, color)
            mx = bx + bw / 2
            svg.line(mx, sy(mean - hw), mx, sy(mean + hw), INK2, 1)
            svg.line(mx - 4, sy(mean + hw), mx + 4, sy(mean + hw), INK2, 1)
            svg.line(mx - 4, sy(mean - hw), mx + 4, sy(mean - hw), INK2, 1)
            svg.text(mx, sy(mean + hw) - 5, f"{mean:.0f}", 11, INK2, "middle")
        svg.text(cx, bot + 18, MECH_LABEL[m], 12, INK, "middle", "600")
        svg.text(cx, bot + 34, f"{PROMPT_LABEL[p]} prompt", 12, INK2, "middle")
        e = c["efficiency"][0]
        svg.text(cx, bot + 52, f"efficiency {e:.3f}", 11, MUTED, "middle")
    svg.save(path)


def fig_shade_scatter(logs, path):
    """Signed shade vs private number, profit prompt, first report only."""
    svg = Svg(680, 340)
    svg.legend(56, 22, [("Buyers (value)", BUYER), ("Sellers (cost)", SELLER)])
    panels = [("planner", "Planner (one report)"), ("double_auction", "Double auction, round 1")]
    pw, gap, x_start = 280, 44, 56
    top, bot = 62, 290
    for i, (m, title) in enumerate(panels):
        x0 = x_start + i * (pw + gap)
        x1 = x0 + pw
        rows = [r for r in logs if r["mechanism"] == m and r["prompt"] == "strategic" and r["round"] == 1]
        svg.text(x0, top - 10, title, 12, INK, "start", "600")
        sy = y_axis(svg, x0, x1, top, bot, -50, 50, [-50, -25, 0, 25, 50],
                    lambda v: f"{v:+g}" if v else "0")
        for t in [0, 25, 50, 75, 100]:
            sx = x0 + t / 100 * pw
            svg.text(sx, bot + 16, t, 11, MUTED, "middle")
        svg.text((x0 + x1) / 2, bot + 34, "True value or cost", 11, MUTED, "middle")
        for r in rows:
            d = max(-50, min(50, r["action"] - r["true_value"]))
            svg.dot(x0 + r["true_value"] / 100 * pw, sy(d), BUYER if r["role"] == "buyer" else SELLER)
    svg.text(8, 176, "Report minus truth", 11, MUTED, "middle")
    svg.parts[-1] = svg.parts[-1].replace("<text ", '<text transform="rotate(-90 8 176)" ', 1)
    svg.save(path)


def fig_shade_hist(logs, path):
    """Distribution of absolute shade under the profit prompt, all rows."""
    bins = [(0, 0.5, "under 0.5"), (0.5, 2, "0.5–2"), (2, 5, "2–5"), (5, 10, "5–10"),
            (10, 20, "10–20"), (20, 40, "20–40"), (40, 1e9, "40+")]
    svg = Svg(680, 320)
    svg.legend(56, 22, [("Buyers", BUYER), ("Sellers", SELLER)])
    panels = ["planner", "double_auction"]
    pw, gap, x_start = 280, 44, 56
    top, bot = 62, 262
    counts = {}
    for m in panels:
        for role in ["buyer", "seller"]:
            rows = [r for r in logs if r["mechanism"] == m and r["prompt"] == "strategic" and r["role"] == role]
            counts[(m, role)] = [sum(lo <= abs_shade(r) < hi for r in rows) / len(rows) for lo, hi, _ in bins]
    hi = 0.6
    for i, m in enumerate(panels):
        x0 = x_start + i * (pw + gap)
        x1 = x0 + pw
        n = sum(1 for r in logs if r["mechanism"] == m and r["prompt"] == "strategic")
        svg.text(x0, top - 10, f"{MECH_LABEL[m]} ({n} reports)", 12, INK, "start", "600")
        sy = y_axis(svg, x0, x1, top, bot, 0, hi, [0, 0.2, 0.4, 0.6], lambda v: f"{v * 100:.0f}%")
        bw_slot = pw / len(bins)
        bw = min(15, (bw_slot - 8) / 2)
        for b, (_, _, lab) in enumerate(bins):
            cx = x0 + bw_slot * (b + 0.5)
            for j, (role, color) in enumerate([("buyer", BUYER), ("seller", SELLER)]):
                svg.column(cx - bw - 1 + j * (bw + 2), sy(0), sy(counts[(m, role)][b]), bw, color)
            svg.text(cx, bot + 15, lab, 10, MUTED, "middle")
        svg.text((x0 + x1) / 2, bot + 32, "Distance between report and truth", 11, MUTED, "middle")
    svg.text(8, 162, "Share of reports", 11, MUTED, "middle")
    svg.parts[-1] = svg.parts[-1].replace("<text ", '<text transform="rotate(-90 8 162)" ', 1)
    svg.save(path)


def fig_da_rounds(res, path):
    """Double auction under the profit prompt: three small panels by round."""
    rounds = res["da_rounds"]["strategic"]
    svg = Svg(680, 250)
    panels = [("misreport_rate", "Share of reports that misreport", 0, 1, [0, 0.5, 1],
               lambda v: f"{v * 100:.0f}%", "line"),
              ("median_abs_shade", "Median distance from truth", 0, 12, [0, 4, 8, 12],
               lambda v: f"{v:g}", "line"),
              ("trades", "Trades that round (all 10 markets)", 0, 16, [0, 8, 16],
               lambda v: f"{v:g}", "col")]
    pw, gap, x_start = 180, 48, 46
    top, bot = 40, 196
    for i, (key, title, lo, hi, ticks, fmt, kind) in enumerate(panels):
        x0 = x_start + i * (pw + gap)
        x1 = x0 + pw
        svg.text(x0 - 30, top - 16, title, 12, INK, "start", "600")
        sy = y_axis(svg, x0, x1, top, bot, lo, hi, ticks, fmt)
        slot = pw / len(rounds)
        pts = []
        for j, r in enumerate(rounds):
            cx = x0 + slot * (j + 0.5)
            svg.text(cx, bot + 15, r["round"], 11, MUTED, "middle")
            v = r[key]
            if kind == "col":
                svg.column(cx - 10, sy(0), sy(v), 20, BUYER)
                svg.text(cx, sy(v) - 5, v, 11, INK2, "middle")
            else:
                pts.append((cx, sy(v)))
        if pts:
            d = " ".join(f"{'M' if k == 0 else 'L'}{x:.1f},{y:.1f}" for k, (x, y) in enumerate(pts))
            svg.add(f'<path d="{d}" fill="none" stroke="{BUYER}" stroke-width="2" '
                    f'stroke-linejoin="round" stroke-linecap="round"/>')
            for x, y in pts:
                svg.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{BUYER}" stroke="{SURF}" stroke-width="2"/>')
        svg.text((x0 + x1) / 2, bot + 32, "Round", 11, MUTED, "middle")
    svg.save(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=OUT, help="directory for results.json, tables.md, and figures/")
    args = ap.parse_args(argv)
    out, fig = args.out, os.path.join(args.out, "figures")
    logs, summ = load("logs.jsonl"), load("summary.jsonl")
    res = compute(logs, summ)
    os.makedirs(fig, exist_ok=True)
    with open(os.path.join(out, "results.json"), "w") as f:
        json.dump(res, f, indent=2)
    with open(os.path.join(out, "tables.md"), "w") as f:
        f.write(tables(res))
    fig_surplus(res, os.path.join(fig, "fig1_surplus_split.svg"))
    fig_shade_scatter(logs, os.path.join(fig, "fig2_shade_vs_private_number.svg"))
    fig_shade_hist(logs, os.path.join(fig, "fig3_shade_distribution.svg"))
    fig_da_rounds(res, os.path.join(fig, "fig4_da_rounds.svg"))
    print(tables(res))


if __name__ == "__main__":
    main()
