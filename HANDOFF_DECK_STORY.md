# Handoff: build the results deck (story version)

You're building the main part of a class presentation on AI agents trading in markets. Read this whole file before you start. It sets the story, the figures and the rules for stating uncertainty.

`HANDOFF_SLIDES.md` (same folder) is the **fact sheet**: every number, the design details, the common mistakes and the rebuild/render commands. This file says what goes on the slides and in what order. If the two conflict on structure or style, this file wins. If they conflict on a number, recheck the source data and use what the data says.

**Project root:** `~/Downloads/llm-market-mechanisms/` (all paths below are relative to it)

---

## 1. What the user wants

- **Simple slides, a strong narrative.** One idea per slide, and the slide title states the finding. Little text on the slide; numbers, reasons and likely Q&A go in the speaker notes.
- **Clear results, built on figures.** Most result slides should be a figure you generate (section 4) plus a one-line takeaway.
- **Honest uncertainty.** Every result slide says how much evidence is behind it (section 5).
- **Tie back to Hayek and the central question.** The talk opens with a question and has to end by answering it.
- **Output:** a `.pptx` the user can import into Google Slides, plus each figure as its own PNG they can drop in by hand. No native PowerPoint charts; they break on import. Use PNGs and plain shapes.

---

## 2. The deck already has two opening slides. Continue from them.

The user made these in Google Slides. Images: `report/deck/existing/`. Look at them before designing anything.

1. **"What constitutes transactions in a market?"** Subtitle: "Buyers + sellers + private information," over three flat icons: a shopper with a cart, a seller at a stall, a laptop with a lock.
2. **"Will this economy benefit us?"** Below it, the central question: *"When an AI agent has private information about a buyer's value or a seller's cost, does it report that information truthfully, strategically, or in a way that harms its own user and overall welfare?"*

**Match their style, not the navy style in `HANDOFF_SLIDES.md`:**
- White background, big centered bold black sans-serif titles (Arial), plain black body text.
- Simple flat icons, used sparingly.
- Charts: buyers blue `2A78D6`, sellers orange `EB6834`, everything else grays. For model-tier charts use one blue ramp from light (small models) to dark (Opus), so "stronger" reads as "darker."
- Don't make slides 1–2 again. Your deck starts at slide 3.

---

## 3. The story

The central question offers three answers: **truthfully, strategically, or harmfully.** The talk's finding is that **all three happen**, and which one you get depends on the instructions and the model. That decides whether a planner or a market works better, which is Hayek's question.

**The Hayek setup (say it early, return to it at the end).** Hayek argued that markets beat central planners because the knowledge that matters (what each person values, what each good costs) is spread across people. A planner only knows what people *report*; a market uses that knowledge through trading, without anyone handing it over. So the two systems fail in different ways:
- **A planner needs honest reports.**
- **A market needs traders who search for good prices.**

When AI agents trade for us, neither condition is guaranteed. That gives our experiment its question: **with AI agents holding the private information, does the planner or the market work better?**

**The answer, in four beats:**
1. **Strategically, when told to.** Strong models treat honesty like a switch set by the prompt, and they know what lying costs (v1).
2. **Harmfully, when the model is weak.** In open negotiation, small models hurt their own clients and waste welfare, so the planner beats the market by 22–33 points (v2).
3. **Stronger models fix competence, not honesty.** As models get stronger, the market catches up (69% → 99% efficiency), but honesty doesn't come along with it.
4. **Back to Hayek.** The planner fails when agents lie; the market fails when agents can't find prices. Which one to use depends on what your agents are bad at.

**Closing line, answering slide 2:** *"Will this economy benefit us? Only if the agents can find prices for us, honesty is enforced by the rules, not assumed, and the agents know when to walk away."*

---

## 4. Figures to generate

Write one script, `analysis/v2_figures.py`, that reads the data files and writes `analysis/figures/v2_*.png` at 2040 px wide with a white background. Don't type numbers into the script by hand; compute them from the files listed. The `.venv` doesn't have matplotlib. `.venv/bin/pip install matplotlib` is fine (no API calls, no cost). Or reuse the SVG helper in `analysis/analyze.py`, which made the v1 figures.

**Chart rules:** one message per chart; a title that states the finding; large labels (readable from the back of a room); no gridline clutter; n on or under every bar or group.

| # | File | What it shows | Data | Uncertainty shown |
|---|---|---|---|---|
| F1 | `v2_planner_vs_chat.png` | Efficiency, planner vs chat, for each framing (neutral, honest, aggressive). Small models. | `outputs/v2/tinker/summary.jsonl`, all 10 seeds | Mean bar, 95% t-interval (t₉ = 2.262), plus each market as a faint dot. The dots show how spread out chat is: one market ends below 0%. |
| F2 | `v2_model_ladder.png` | **The key figure.** X axis: small mix → GPT-OSS-120B → Qwen3.8-27B → Opus. Two series: chat efficiency (filled) and planner efficiency (hollow). The planner stays flat near the top while chat climbs to meet it. | `summary.jsonl` in `tinker/`, `tinker-gptoss120b/`, `tinker-qwen38-27b/`, `claude-cli/`. **Seeds 0–1 only** for every tier, so all tiers face the same markets. | Each market as a dot, the mean as a short bar. Under each tier, write "n = 6 markets" (Opus: "n = 3, one seed"). **No error bars** here: 2 seeds is too few. |
| F3 | `v2_client_harm.png` | Chat trades that broke the client's price limit, by tier: 7 of 46, 1 of 44, 0 of 41, 0 of 25. | `python -m v2.failure_analysis tinker tinker-gptoss120b tinker-qwen38-27b claude-cli` (check that it accepts these folders; `DISCUSSION.md` §7 has the table to check against). | Label each bar with the raw count ("7 of 46"), not just a percentage. |
| F4 | `v2_honesty_by_tier.png` | Planner misreport rate by tier, grouped by framing (neutral / honest / aggressive). The story is the **honest** bars: 7%, 4%, **31%**, 0%. Highlight that group and gray out the others. | Per-tier `results.md` honesty tables, or the planner reports in `runs/*/events.jsonl`. Check against `DISCUSSION.md` §7. | Show counts in the notes. Label tiers with their market count. |
| F5 | `hayek_two_failures.png` | A diagram, not data. A 2×2 grid: honest vs dishonest agents × good vs bad at finding prices. Each cell says which mechanism works: honest + good → "both work"; dishonest + good → "market"; honest + bad → "planner"; dishonest + bad → "planner + guardrails." Mark where each model landed: small models bottom row, Qwen3.8-27B top-right (competent, not honest), GPT-OSS-120B and Opus top-left. | — | Label model placements "from 1–2 markets each." |
| v1 | reuse `analysis/figures/fig2_shade_vs_private_number.png` | v1: honest prompt → reports match the truth; profit prompt → systematic shading. | already made | Already in the figure. |

**Check figure values against these** (seeds 0–1 mean efficiency; minimum in parentheses):

| | Planner | Chat |
|---|---|---|
| Small mix | 96.0% (87.2%) | 69.4% (34.8%) |
| GPT-OSS-120B | 99.6% (97.5%) | 92.2% (77.8%) |
| Qwen3.8-27B | 95.4% (84.3%) | 96.0% (93.1%) |
| Opus 5.5 (seed 0 only) | 99.3% (97.8%) | 98.9% (98.3%) |

If your script gets something different, find out why before you plot it.

---

## 5. How to state uncertainty (put it on every result slide)

Use a small **evidence tag** in the bottom corner of every result slide, always in the same spot and style:

| Tag | When | Applies to |
|---|---|---|
| **Solid · 10 markets** | 95% interval excludes zero | v1 honest vs profit misreports; v2 small-model planner vs chat (all three framings); planner honest vs aggressive; chat honest vs neutral |
| **Exploratory · 2 markets** | direction only | GPT-OSS-120B and Qwen3.8-27B |
| **Single market** | an anecdote, not a result | Opus in v2 (also ran via `claude -p`, so it saw some environment context; no reasoning logged) |

Rules:
- Never call something "significant" unless the 95% interval excludes zero. Say plainly what's *not* significant (e.g. the v1 seller advantage, 16 ± 21).
- State the limit-violation rate as "**14% at most, 6% excluding reasoning cut off by our token cap.**"
- **Don't use the "false claims" column** for GPT-OSS-120B or any tier. The keyword detector matched the wrong price to the wrong item (e.g. it flagged "bike (max $244) and ticket (max $72)" as a $72 bike claim, but the sentence is true).
- Debrief self-reports undercount: the GPT-OSS-20B aggressive planner made 60 misreports out of 141 reports, but only 7 of 120 debriefs admitted it. You can use that as a point, but don't use debriefs to *measure* honesty.

---

## 6. Slide outline (about 10 main slides)

Slides 1–2 are the user's. Each entry: **title (the finding)** — what's on the slide — what goes in the notes.

3. **Hayek: a planner needs honest reports; a market needs good shoppers.** Two simple diagrams side by side: agents → one box (planner), and agents trading with each other (market). One line under each: "fails if agents lie" / "fails if agents can't find prices." *Notes:* the knowledge problem in two sentences; why AI agents make this an open question; this is the lens for every result.

4. **What we built.** Two columns. v1: 10 agents, one abstract good, Claude Opus. v2: 24 agents, bikes/laptops/tickets, each working for a named person ("buy Maria a bike, at most $212"), with chat and an offer board. Under them, the model ladder as four dots from light to dark. *Notes:* the three framings (neutral / honest / aggressive); efficiency = share of the best possible gains from trade; the warrant for each choice (why the midpoint price: both sides gain from shading, so it's a two-sided honesty test; why named clients: that's how consumer agents will actually be used; why weaker open models: cheap, full reasoning logs).

5. **Told to profit, a strong model shades on purpose.** v1 figure (fig2). Big numbers: **0 of 408** misreports when told to be honest, **374 of 426** when told to profit. One line: "In all 834 decisions, the agent said the truth was best for everyone." Tag: Solid. *Notes:* this is "strategically" from the central question; it's following instructions, not breaking them, so don't say "the AI lies"; efficiency barely moved (98.6–99.6%) because the market rules absorbed it.

6. **Weak agents in a free market hurt their own clients.** F1. Takeaway: "The planner beats open negotiation by 22–33 points." Tag: Solid. *Notes:* 121 wrong-partner trades in chat vs 6 in the planner; one market went below zero welfare; 37 of 258 chat trades broke the client's limit (14% at most, 6% clean). This is "harmfully" from the central question.

7. **Its reasoning saw the problem; its action ignored it.** Just the quote, large: the Qwen3-8B buyer whose client's max was $53. Thinking: *"$215, which is way over the budget."* Action: accepted the $215 offer. Below, three small icons for the failure patterns: opens at the client's real limit · takes the first workable deal · folds at the deadline. *Notes:* the source is `analysis/v2_why_agents_fail.md`; Opus did the opposite: asked for quotes, sent 3× more messages, walked away (*"the laptop goes unsold, which is better for Daniel than a sale below his floor"*).

8. **Stronger models close the gap with the planner.** F2, the key slide. Takeaway: "Chat efficiency 69% → 92% → 96% → 99%; the planner was high all along." Optionally F3 as a small inset, or as its own slide if it's too crowded. Tag: Exploratory. *Notes:* client harm fixed first (7 → 1 → 0 → 0 limit-breaking trades); finding the right trading partner improves only with Opus (wrong-partner trades in round 2 stay at a third to a half for the middle tier); GPT-OSS-120B costs $0.61 for all 12 markets. Same seeds for every tier; middle-tier markets are all one model.

9. **Smarter isn't more honest.** F4, honest-framing bars highlighted. Takeaway: "Told to be honest, Qwen3.8-27B still misreported 31% of the time." Two short labels: "Forgets the rule" (Qwen3.8-27B: its thinking never mentions honesty) / "Argues around it" (GPT-OSS-20B: *"This doesn't misrepresent minimum. It's beyond min. So okay."*). Tag: Exploratory. *Notes:* the prompt gave two objectives (client's price and honesty) without saying which wins, and models settled it differently; GPT-OSS-120B was competent and honest (4%); Opus followed the rule exactly but shaded 50% with no instruction.

10. **Back to Hayek: which system works depends on your agents.** F5, the 2×2. Takeaway: "The planner fails when agents lie. The market fails when agents can't find prices." *Notes:* this turns Hayek around: a market only uses what people know if its traders actually search for prices, and weak agents don't, so central matching won; once agents search (Opus), the market catches up. Caveat: our economy favors the planner. Goods are fixed and known and values add up, so central matching is exactly optimal. Real markets also discover new goods and handle bundles, which we didn't test.

11. **Will this economy benefit us?** Answer the slide-2 question directly. Three short lines, each with a small icon:
    - **Consumer agents need guardrails:** a hard cap the platform enforces, like a limit order, not the model's judgment at the deadline.
    - **Spell out the objective:** "at most $212" has to mean "no deal beats $213," and say whether honesty or price wins.
    - **Match the market to the agents:** central matching for weak agents; open markets only once agents can find prices.
    *Notes:* the consumer vs business-side distinction from instructor feedback (`DISCUSSION.md` §3); business-side agents can't be assumed honest just because they're capable.

12. **How sure are we.** Three rows matching the evidence tags: what's solid, what's a direction, what's an anecdote. Then limits in one line each: few markets; agents only trade with copies of themselves; the setup looks like a test (some agents said so); the 2,048-token cap on small models; the planner and market differ in both price rule and retries. *Notes:* next experiments from `DISCUSSION.md` §8, especially the objectives experiment and mixed-model markets.

**Backup slides** (after a "Backup" divider): v1 results table; why trades happen at the midpoint (`DISCUSSION.md` §1); why v1's auction is essentially a planner and v2's chat isn't (§2); the late-round clustering explanation (§5); the urgency-vs-overpaying hint (§6); the cancel-before-accept bug and fix.

---

## 7. Building and checking

- Build with pptxgenjs. Start a **new** script at `report/deck/build_story_deck.js` that writes `report/LLM_Markets_Story.pptx`. Don't overwrite the old deck. Setup and the Keynote render-to-PDF check are in `HANDOFF_SLIDES.md` §2.
- Render every slide and look at it before handing back. Check: titles fit on one or two lines; no text overflow; every figure is readable; every result slide has its evidence tag; slides 3+ look like they belong next to the user's slides 1–2.
- Hand back: the `.pptx`, the `analysis/figures/v2_*.png` files, and a one-paragraph summary of anything you couldn't verify.

## 8. Don't

- Don't open, print or copy `.env` (it holds a live API key).
- Don't run `v2.run` with any paid backend. Every figure comes from existing outputs.
- Don't type numbers by hand. Compute them, or copy them from `results.md`, `analysis/tables.md` or `DISCUSSION.md`, and check them against section 4 above.
- Don't put error bars on 2-seed or 1-seed results.
- Don't say "the AI lies" about v1, and don't cite the false-claims detector.
