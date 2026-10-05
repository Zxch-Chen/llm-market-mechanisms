"""Figures for docs/discussion.md section 7b: mixed vs single-model markets.

Run from the project root (needs matplotlib in .venv):
    .venv/bin/python analysis/v2_mix_figures.py

Writes analysis/figures/v2_size_vs_mixing.png and analysis/figures/v2_cross_model_share.png.
"""
import argparse
import glob
import json
import os
import random
import statistics as st
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from v2.economy import draw_economy  # noqa: E402
from v2.run import assign_models  # noqa: E402

OUT = os.path.join(ROOT, "analysis", "figures")
SINGLE, MIXED = "#2a78d6", "#eb6834"
INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0", "#ffffff"
MIX_TAGS = ["tinker-mix-120b-qwen38", "tinker-mix-qwen38-120b-swapped"]

plt.rcParams.update({"font.family": "Arial", "font.size": 15, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2})


def chat_efficiencies(tags, seeds=(0, 1)):
    out = []
    for tag in tags:
        for line in open(os.path.join(ROOT, "outputs", "v2", tag, "summary.jsonl")):
            r = json.loads(line)
            if r["mechanism"] == "negotiation" and r["seed"] in seeds:
                out.append(r["efficiency"])
    return out


def cross_model_shares(tag, focus="Qwen/Qwen3.8-27B"):
    """`focus` model's share of the gains in each value-creating trade between the two models in a run."""
    base = os.path.join(ROOT, "outputs", "v2", tag)
    models = json.loads(open(os.path.join(base, "summary.jsonl")).readline())["models"]
    shares = []
    for rd in sorted(glob.glob(os.path.join(base, "runs", "negotiation_*"))):
        bs, ss = draw_economy(int(rd.rsplit("seed", 1)[1]))
        mo = assign_models(bs, ss, models)
        B = {b.id: b for b in bs}
        S = {s.id: s for s in ss}
        for line in open(os.path.join(rd, "events.jsonl")):
            e = json.loads(line)
            if e["type"] != "trade":
                continue
            v, c, p = B[e["buyer"]].values[e["good"]], S[e["seller"]].cost, e["price"]
            mb, ms = mo[e["buyer"]], mo[e["seller"]]
            if mb != ms and v > c:
                shares.append((v - p) / (v - c) if mb == focus else (p - c) / (v - c))
    return shares


def style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)


def fig_size_vs_mixing(with_opus=False):
    groups = [
        ("Qwen3-8B\nalone", ["tinker-qwen3-8b-solo"], SINGLE),
        ("GPT-OSS-20B\nalone", ["tinker-gptoss20b-solo"], SINGLE),
        ("Both,\nmixed", ["tinker"], MIXED),
        ("GPT-OSS-120B\nalone", ["tinker-gptoss120b"], SINGLE),
        ("Qwen3.8-27B\nalone", ["tinker-qwen38-27b"], SINGLE),
        ("Both,\nmixed", MIX_TAGS, MIXED),
    ]
    xs = [0, 1, 2, 3.6, 4.6, 5.6]
    tiers = [(1, "Small models"), (4.6, "Middle-tier models")]
    if with_opus:
        groups.append(("Opus 5.5\nalone", ["claude-cli"], SINGLE))
        xs.append(7.2)
        tiers.append((7.2, "Frontier"))
    fig, ax = plt.subplots(figsize=(13.6, 7.4), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    style(ax)
    rng = random.Random(0)
    for x, (label, tags, color) in zip(xs, groups):
        eff = [100 * e for e in chat_efficiencies(tags)]
        m = st.mean(eff)
        ax.bar(x, m, width=0.62, color=color, alpha=0.9, zorder=2)
        ax.scatter([x + rng.uniform(-0.16, 0.16) for _ in eff], eff, s=46, color=INK, alpha=0.55,
                   edgecolor=SURFACE, linewidth=1.2, zorder=3)
        ax.text(x, max(m, max(eff)) + 3, f"{m:.0f}%", ha="center", va="bottom", fontsize=17,
                fontweight="bold", color=INK)
    ax.set_xticks(xs, [f"{g[0]}\nn = {len(chat_efficiencies(g[1]))}" for g in groups], fontsize=13)
    ax.axhline(0, color=MUTED, linewidth=1, zorder=1)
    ax.set_ylim(-12, 110)
    ax.set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    ax.yaxis.grid(True, color=GRID, linewidth=1, zorder=0)
    ax.set_ylabel("Chat-market efficiency")
    for x, text in tiers:
        ax.annotate(text, xy=(x, 0), xycoords=("data", "axes fraction"), xytext=(0, -92),
                    textcoords="offset points", ha="center", fontsize=15, fontweight="bold", color=INK)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=SINGLE), plt.Rectangle((0, 0), 1, 1, color=MIXED),
                       plt.Line2D([], [], marker="o", linestyle="", color=INK, alpha=0.55, markersize=7)],
              labels=["One model in every seat", "Two models mixed", "One market"],
              loc="lower left", frameon=False, fontsize=13, ncol=3, bbox_to_anchor=(0, 1.0))
    title = ("Stronger models close the gap; mixing models doesn't matter" if with_opus
             else "Model size, not mixing, explains the chat-market failures")
    fig.suptitle(title, x=0.06, ha="left", fontsize=22, fontweight="bold", color=INK, y=0.98)
    note = ("Opus is one seed (3 markets). " if with_opus else "")
    fig.text(0.06, 0.905, "Seeds 0–1, all three framings. Bars are means; dots are individual markets. "
             f"{note}Read directions, not effect sizes.", fontsize=13, color=INK2)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.8, bottom=0.22)
    name = "v2_model_ladder_with_opus.png" if with_opus else "v2_size_vs_mixing.png"
    fig.savefig(os.path.join(OUT, name), dpi=150, facecolor=SURFACE)


def fig_cross_model_share():
    rows = [("Original\nassignment", cross_model_shares(MIX_TAGS[0])),
            ("Positions\nswapped", cross_model_shares(MIX_TAGS[1]))]
    fig, ax = plt.subplots(figsize=(13.6, 5.6), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    style(ax)
    ax.spines["bottom"].set_visible(True)
    ax.axvspan(50, 100, color=SINGLE, alpha=0.06, zorder=0)
    ax.axvline(50, color=MUTED, linestyle=(0, (4, 4)), linewidth=1.5, zorder=1)
    ax.text(50, -0.62, "even split", ha="center", va="bottom", fontsize=13, color=INK2)
    ax.text(100, -0.62, "Qwen3.8 got more →", ha="right", va="bottom", fontsize=13, color=INK2)
    ax.text(0, -0.62, "← GPT-OSS-120B got more", ha="left", va="bottom", fontsize=13, color=INK2)
    rng = random.Random(1)
    for y, (label, shares) in enumerate(rows):
        pct = [100 * s for s in shares]
        ax.scatter(pct, [y + rng.uniform(-0.17, 0.17) for _ in pct], s=110, color=SINGLE,
                   edgecolor=SURFACE, linewidth=2, zorder=3, clip_on=False)
        m = st.mean(pct)
        ax.plot([m, m], [y - 0.32, y + 0.32], color=INK, linewidth=3, zorder=4)
    labels = [f"{label.replace(chr(10), ' ')}\nmean {100 * st.mean(sh):.0f}%,\nmore than half in {sum(s > 0.5 for s in sh)} of {len(sh)}"
              for label, sh in rows]
    ax.set_yticks([0, 1], labels, fontsize=13)
    ax.set_ylim(1.5, -0.75)
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    ax.set_xlabel("Qwen3.8-27B's share of the gains from the trade")
    all_s = rows[0][1] + rows[1][1]
    fig.suptitle(f"Trading with each other, Qwen3.8-27B took most of the gains in {sum(s > 0.5 for s in all_s)} "
                 f"of {len(all_s)} trades", x=0.06, ha="left", fontsize=21, fontweight="bold", color=INK, y=0.97)
    fig.text(0.06, 0.86, "Each dot is one chat trade between a GPT-OSS-120B agent and a Qwen3.8-27B agent "
             "(seeds 0–1, 12 markets). Black tick = mean.", fontsize=13, color=INK2)
    fig.subplots_adjust(left=0.2, right=0.97, top=0.76, bottom=0.17)
    fig.savefig(os.path.join(OUT, "v2_cross_model_share.png"), dpi=150, facecolor=SURFACE)


def fig_cross_model_share_all():
    rows = [("Small models (10 seeds)\nGPT-OSS-20B vs Qwen3-8B", cross_model_shares("tinker", "openai/gpt-oss-20b")),
            ("Middle tier, original seats\nQwen3.8-27B vs GPT-OSS-120B", cross_model_shares(MIX_TAGS[0])),
            ("Middle tier, seats swapped\nQwen3.8-27B vs GPT-OSS-120B", cross_model_shares(MIX_TAGS[1]))]
    fig, ax = plt.subplots(figsize=(13.6, 7.0), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    style(ax)
    ax.spines["bottom"].set_visible(True)
    ax.axvline(50, color=MUTED, linestyle=(0, (4, 4)), linewidth=1.5, zorder=1)
    ax.text(50, -0.62, "even split", ha="center", va="bottom", fontsize=13, color=INK2)
    ax.text(100, -0.62, "first-named model got more →", ha="right", va="bottom", fontsize=13, color=INK2)
    ax.text(0, -0.62, "← second model got more", ha="left", va="bottom", fontsize=13, color=INK2)
    rng = random.Random(2)
    labels = []
    for y, (label, shares) in enumerate(rows):
        pct = [100 * x for x in shares]
        small = len(pct) > 50
        ax.scatter(pct, [y + rng.uniform(-0.22, 0.22) for _ in pct], s=60 if small else 110,
                   color=MUTED if small else SINGLE, alpha=0.7 if small else 1, edgecolor=SURFACE,
                   linewidth=1.5, zorder=3, clip_on=False)
        m = st.mean(pct)
        ax.plot([m, m], [y - 0.34, y + 0.34], color=INK, linewidth=3, zorder=4)
        won = sum(x > 0.5 for x in shares)
        labels.append(f"{label}\nmean {m:.0f}%, more than half in {won} of {len(shares)}")
    ax.set_yticks(range(len(rows)), labels, fontsize=12.5)
    ax.set_ylim(len(rows) - 0.5, -0.75)
    ax.set_xlim(-3, 103)
    ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    ax.set_xlabel("First-named model's share of the gains from the trade")
    fig.suptitle("Two weak agents split the gains; a strategic agent beats a transparent one", x=0.03,
                 ha="left", fontsize=21, fontweight="bold", color=INK, y=0.975)
    fig.text(0.03, 0.885, "Each dot is one chat trade between two different models. Black tick = mean. "
             "Middle tier is 2 seeds (12 markets), so read it as a direction.", fontsize=13, color=INK2)
    fig.subplots_adjust(left=0.27, right=0.97, top=0.78, bottom=0.12)
    fig.savefig(os.path.join(OUT, "v2_cross_model_share_all.png"), dpi=150, facecolor=SURFACE)


CHAT_TAGS = ["tinker", "tinker-qwen3-8b-solo", "tinker-gptoss20b-solo", "tinker-gptoss120b", "tinker-qwen38-27b",
             "tinker-mix-120b-qwen38", "tinker-mix-qwen38-120b-swapped", "claude-cli"]


def limit_slots():
    """One row per agent and good with a round-1 offer in any chat market:
    (model, opened at the client's exact limit, client's share of the gains if it traded)."""
    rows = []
    for tag in CHAT_TAGS:
        for f in glob.glob(os.path.join(ROOT, "outputs", "v2", tag, "runs", "negotiation_*", "events.jsonl")):
            bs, ss = draw_economy(int(f.split("seed")[1].split(os.sep)[0]))
            B = {b.id: b for b in bs}
            S = {s.id: s for s in ss}
            model = {}
            for line in open(f.replace("events.jsonl", "calls.jsonl")):
                c = json.loads(line)
                model[c["agent_id"]] = c["model"].split("/")[-1]
            ev = [json.loads(line) for line in open(f)]
            opened = {}
            for e in ev:
                if e["type"] == "offer" and e["round"] == 1:
                    a = e["agent"]
                    lim = B[a].values[e["good"]] if a in B else S[a].cost
                    opened[(a, e["good"])] = opened.get((a, e["good"]), False) or abs(e["price"] - lim) <= 0.5
            share = {}
            for e in ev:
                if e["type"] == "trade":
                    v, c, p = B[e["buyer"]].values[e["good"]], S[e["seller"]].cost, e["price"]
                    if v > c:
                        share[(e["buyer"], e["good"])] = (v - p) / (v - c)
                        share[(e["seller"], e["good"])] = (p - c) / (v - c)
            rows += [(model[a], at, share.get((a, g))) for (a, g), at in opened.items()]
    return rows


def fig_limit_reveal():
    names = [("Qwen3-8B", "Qwen3-8B"), ("gpt-oss-20b", "GPT-OSS-20B"), ("gpt-oss-120b", "GPT-OSS-120B"),
             ("Qwen3.8-27B", "Qwen3.8-27B"), ("claude-opus-5-5", "Opus 5.5")]
    rows = limit_slots()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13.6, 6.8), dpi=150, gridspec_kw={"width_ratios": [1, 1.35]})
    fig.patch.set_facecolor(SURFACE)
    for ax in (a1, a2):
        style(ax)
        ax.yaxis.grid(True, color=GRID, linewidth=1, zorder=0)
        ax.set_ylim(0, 100)
        ax.set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    ticks = ["Qwen3-8B", "GPT-OSS-\n20B", "GPT-OSS-\n120B", "Qwen3.8-\n27B", "Opus 5.5"]
    xs = range(len(names))
    for x, (key, label) in zip(xs, names):
        mine = [r for r in rows if r[0] == key]
        rate = 100 * sum(r[1] for r in mine) / len(mine)
        a1.bar(x, max(rate, 0.6), width=0.62, color=MIXED, zorder=2)
        a1.text(x, rate + 2, f"{rate:.0f}%", ha="center", va="bottom", fontsize=15, fontweight="bold", color=INK)
    a1.set_xticks(list(xs), ticks, fontsize=12)
    a1.set_title("How often agents open at their\nclient's exact limit", loc="left", fontsize=15,
                 fontweight="bold", color=INK, pad=12)
    w = 0.38
    for x, (key, label) in zip(xs, names):
        for dx, at, color in ((-w / 2 - 0.01, True, MIXED), (w / 2 + 0.01, False, SINGLE)):
            sh = [100 * r[2] for r in rows if r[0] == key and r[1] == at and r[2] is not None]
            if len(sh) < 5:
                a2.text(x + dx, 3, "never", ha="center", va="bottom", fontsize=11, color=MUTED, rotation=90)
                continue
            m = st.mean(sh)
            a2.bar(x + dx, m, width=w, color=color, zorder=2)
            a2.text(x + dx, m + 2, f"{m:.0f}%", ha="center", va="bottom", fontsize=13, fontweight="bold", color=INK)
    a2.axhline(50, color=MUTED, linestyle=(0, (4, 4)), linewidth=1.5, zorder=1)
    a2.set_xticks(list(xs), ticks, fontsize=12)
    a2.set_title("Client's average share of the gains\nfrom its trades", loc="left", fontsize=15,
                 fontweight="bold", color=INK, pad=12)
    a2.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=MIXED), plt.Rectangle((0, 0), 1, 1, color=SINGLE),
                       plt.Line2D([], [], color=MUTED, linestyle=(0, (4, 4)), linewidth=1.5)],
              labels=["Opened at the client's limit", "Didn't", "Even split of the gains"], loc="upper right", frameon=False, fontsize=12,
              ncol=1, bbox_to_anchor=(1.0, 1.0))
    fig.suptitle("Opening at your client's limit gives the gains away, and stronger models stop doing it",
                 x=0.03, ha="left", fontsize=19, fontweight="bold", color=INK, y=0.975)
    fig.text(0.03, 0.895, "All chat markets we ran (small models: 10 seeds; middle tier: 2; Opus: 1). "
             "Within each model, opening at the limit cut the client's share by 11–28 points.", fontsize=12.5,
             color=INK2)
    fig.subplots_adjust(left=0.06, right=0.98, top=0.76, bottom=0.13, wspace=0.18)
    fig.savefig(os.path.join(OUT, "v2_limit_reveal.png"), dpi=150, facecolor=SURFACE)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=OUT, help="directory for the five PNG figures")
    OUT = ap.parse_args().out
    os.makedirs(OUT, exist_ok=True)
    fig_size_vs_mixing()
    fig_size_vs_mixing(with_opus=True)
    fig_cross_model_share()
    fig_cross_model_share_all()
    fig_limit_reveal()
    print(f"wrote five figures to {OUT}")
