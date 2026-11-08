"""FIG2 v3 (2026-11-08: + Hermes-3-Llama-3.1-8B row, PREREG_v2.12; 31B bf16 row now PREREG_v2.14, registered). v2: (PAPER v2.0 draft; R2 review item 17) — what TranscriptLab measures. (a) Gemma-4-31B (4-bit QAT) on public PNC states: malformed next edit vs the
number of laundered calls in history. (b, c) One laundered call, by model and tool format (benchmark coverage):
risk difference vs the original history when the call is followed by the framework's error (copying) or by its
success response (induction), with the producers' episode-cluster bootstrap 95% CIs.
Every value is read from the cited JSONs (see figure_data.json).

    python fig2_transcriptlab_v2.py # writes fig2_transcriptlab_v3.png + .svg; values -> figure_data_v2.json

v2 changes: 13 configurations (adds Gemma-4-E4B bf16 and E2B 4-bit, PREREG_v2.9; read from the released CLI's analysis.json files, which
v29_coverage.json summarises);
the 300-state points (k = 0, 1) and the 216-state dose set (k = 1, 2, 4) are drawn as separate panels and never
joined; the '(per-k CIs not stored...)' note is dropped; precision in every label; 'imitation' replaces 'induction';
rows with no events in either arm are drawn hollow and labelled.

Needs matplotlib >= 3.8.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

import _figdata  # noqa: E402
from _figdata import GEMMA, HERE, OTHER, STOCK, Sources  # noqa: E402

_figdata.DATA_JSON = HERE / "figure_data_fig2_v3.json"   # own file: figure_data_v3.json belongs to FIG1 v3

CF = "experiments/contagion/out/confirmatory/confirm_v2_all_full.json"
CE = "experiments/contagion/out/confirmatory/confirm_v2_31b_e4b_full.json"
BF = "experiments/contagion/out/confirmatory/bf16_core_all.json"
V26 = "experiments/contagion/out/confirmatory/v26_audit_analysis.json"
XQ = "experiments/crossfamily/out/v2/results_v2.json"
EX = "experiments/crossfamily/out/ext/results_ext.json"
V29 = "experiments/contagion/out/confirmatory/v29_coverage.json"

S = Sources("FIG2_v3", "paper/protocol/draft/figures/fig2_transcriptlab_v3.py")
H3 = "experiments/transcriptlab_cli/run_v212_hermes3/analysis.json"   # v3: PREREG_v2.12, CLI 0.1.3
V214 = "experiments/contagion/out/confirmatory/v214_bf16_analysis.json"   # v3: registered 31B bf16 row (replaces exploratory)


def rdci(label, rel, key, rdkey):
    d = S.get(label, rel, key)
    return pct(d[rdkey]), pct(d["CI"][0]), pct(d["CI"][1])
pct = lambda x: 100.0 * x  # noqa: E731
MINUS = "−"

# ---------------- (a) dose response, Gemma-4-31B 4-bit QAT ----------------
p0 = S.get("31B QAT original history (A1) [rate, lo, hi, n]", V26, "rates/QAT/P0")
p1 = S.get("31B QAT one laundered call + error (A1)", V26, "rates/QAT/P1")
p6 = S.get("31B QAT one laundered call + success (A1)", V26, "rates/QAT/P6")
assert abs(S.get("C1 base (cross-check)", CF, "31B/full/C1/uncond/base") - p0[0]) < 1e-9
assert abs(S.get("C1 arm (cross-check)", CF, "31B/full/C1/uncond/arm") - p1[0]) < 1e-9
assert abs(S.get("C2 arm (cross-check)", CF, "31B/full/C2/uncond/arm") - p6[0]) < 1e-9
dose = {k: S.get(f"31B QAT dose set (A2) + success, k={k}", CF, f"31B/C3/uncond/rates/k={k}") for k in (1, 2, 4)}
n_dose = S.get("dose set states (A2)", CF, "31B/C3/uncond/n_contexts")
d2 = S.get("dose: delta log-odds k=2 vs k=1 [point, CI]", CF, "31B/C3/uncond/Delta_2")
d4 = S.get("dose: delta log-odds k=4 vs k=1 [point, CI]", CF, "31B/C3/uncond/Delta_4")

# ---------------- (b, c) coverage: RD by model ----------------
def frac_rd(label, rel, key):
    d = S.get(label, rel, key)
    return pct(d["RD"]), pct(d["RD_CI"][0]), pct(d["RD_CI"][1])


def triple(label, rel, key):
    d = S.get(label, rel, key)
    return pct(d[0]), pct(d[1]), pct(d[2])


def pp(label, rel, key):
    d = S.get(label, rel, key)
    return d["RD_pp"], d["CI_pp"][0], d["CI_pp"][1]


models = [
    ("Gemma-4-31B, 4-bit QAT", "Gemma 4", True, frac_rd("copy 31B QAT", CF, "31B/full/C1/uncond"),
     frac_rd("imitation 31B QAT", CF, "31B/full/C2/uncond"), None),
    ("Gemma-4-31B, bf16", "Gemma 4", True, rdci("copy 31B bf16 (PREREG_v2.14)", V214, "copying/CLI", "RD_P1_minus_P0"),
     rdci("imitation 31B bf16 (PREREG_v2.14)", V214, "induction/CLI", "RD_P6_minus_P0"), None),
    ("Gemma-4-E4B, 4-bit QAT", "Gemma 4", True, frac_rd("copy E4B", CE, "E4B/C9/uncond"),
     frac_rd("imitation E4B", CE, "E4B/C10/RD_P6_P0"), None),
    ("Gemma-4-E4B, bf16", "Gemma 4", True, triple("copy E4B bf16", "experiments/transcriptlab_cli/run_e4b16/analysis.json", "uncond/RD_P1_P0"),
     triple("imitation E4B bf16", "experiments/transcriptlab_cli/run_e4b16/analysis.json", "uncond/RD_P6_P0"), None),
    ("Gemma-4-E2B, 4-bit QAT", "Gemma 4", True, triple("copy E2B", "experiments/transcriptlab_cli/run_e2b/analysis.json", "uncond/RD_P1_P0"),
     triple("imitation E2B", "experiments/transcriptlab_cli/run_e2b/analysis.json", "uncond/RD_P6_P0"), None),
    ("Gemma-4-12B, 4-bit QAT", "Gemma 4", True, frac_rd("copy 12B", CF, "12B/C8/uncond"),
     frac_rd("imitation 12B", CF, "12B/C10/RD_P6_P0"), None),
]
for mk, name, fmt in (("qwen3-8b", "Qwen3-8B, bf16", "hermes JSON"), ("qwen3-32b", "Qwen3-32B, FP8", "hermes JSON"),
                      ("qwen3.5-9b", "Qwen3.5-9B, bf16", "qwen3_coder XML")):
    models.append((name, fmt, False, pp(f"copy {mk}", XQ, f"models/{mk}/X1"), pp(f"imitation {mk}", XQ, f"models/{mk}/X4"), None))
for mk, name, fmt in (("gpt-oss-20b", "gpt-oss-20b, MXFP4", "harmony"), ("qwen3-coder-30b", "Qwen3-Coder-30B, FP8", "qwen3_coder XML"),
                      ("devstral-24b", "Devstral-Small-2, FP8", "Mistral"), ("qwen3.8-27b", "Qwen3.8-27B, FP8", "qwen3_coder XML")):
    n = S.get(f"states {mk}", EX, f"models/{mk}/n_contexts")
    models.append((name, fmt, False, frac_rd(f"copy {mk}", EX, f"models/{mk}/P1L_vs_P0"),
                   frac_rd(f"imitation {mk}", EX, f"models/{mk}/secondary/P6"), n if n != 300 else None))
# v3 (2026-11-08): the first Llama-family row (PREREG_v2.12, released CLI 0.1.3; Table 3 footnote: retries, not copies)
models.append(("Hermes-3-Llama-3.1-8B, bf16", "hermes JSON", False, frac_rd("copy hermes3-8b", H3, "paired_vs_P0/P1L/uncond"),
               frac_rd("imitation hermes3-8b", H3, "paired_vs_P0/P6/uncond"), None))

# =============================== drawing ===============================
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "svg.fonttype": "none",
                     "svg.hashsalt": "slipguard-figures"})   # deterministic SVG ids
fig = plt.figure(figsize=(8.0, 8.4))

# (a1) one laundered call on the 300 A1 states; (a2) dose set on 216 A2 states. Separate axes: never joined.
ax = fig.add_axes([0.085, 0.735, 0.33, 0.215])
xs = [0, 1, 2]
vals = [p0, p1, p6]
cols = [STOCK, GEMMA, GEMMA]
mfcs = ["white", GEMMA, "white"]
marks = ["o", "o", "s"]
for x, v, c, mf, mk in zip(xs, vals, cols, mfcs, marks):
    ax.errorbar([x], [pct(v[0])], yerr=[[pct(v[0] - v[1])], [pct(v[2] - v[0])]], fmt=mk, ms=7.5, color=c, mfc=mf,
                mec=c, mew=1.6, capsize=0, elinewidth=2.2, zorder=4)
    ax.text(x + 0.12, pct(v[0]), f"{pct(v[0]):.1f}%", va="center", fontsize=8.5, color="#222222")
ax.set_xticks(xs); ax.set_xticklabels(["original", "+ error", "+ success"], fontsize=8.8)
ax.set_xlim(-0.4, 2.6); ax.set_ylim(0, 45)
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
ax.set_ylabel("malformed next edit", fontsize=9.5)
ax.grid(axis="y", color="#E8E8E8", lw=0.8); ax.set_axisbelow(True); ax.tick_params(axis="y", labelsize=9)
ax.set_title(f"(a) one laundered call ({p1[3]} states)", loc="left", fontsize=10.2, fontweight="bold")

ax2 = fig.add_axes([0.53, 0.735, 0.33, 0.215])
ks = [1, 2, 4]
ax2.plot(ks, [pct(dose[k]) for k in ks], color=GEMMA, lw=1.6, marker="^", ms=8, mfc=GEMMA, zorder=4)
for k in ks:
    ax2.text(k + 0.12, pct(dose[k]), f"{pct(dose[k]):.1f}%", va="center", fontsize=8.5, color="#222222")
ax2.set_xticks(ks); ax2.set_xlim(0.6, 4.7); ax2.set_ylim(0, 45)
ax2.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
ax2.set_xlabel("laundered calls, each followed by success", fontsize=9)
ax2.grid(axis="y", color="#E8E8E8", lw=0.8); ax2.set_axisbelow(True); ax2.tick_params(labelsize=9)
ax2.set_title(f"(b) dose: separate set of {n_dose} states", loc="left", fontsize=10.2, fontweight="bold")
fmt_d = lambda d: (f"{d[0]:+.2f} [{d[1][0]:.2f}, {d[1][1]:.2f}]").replace("-", MINUS)  # noqa: E731
ax2.text(2.25, 2.0, f"log-odds vs 1 call\n2 calls: {fmt_d(d2)}\n4 calls: {fmt_d(d4)}", fontsize=7.8, color="#333333",
         va="bottom", ha="left", linespacing=1.3)

# (b), (c)
n = len(models)
ys = list(range(n))[::-1]
labels = [f"{m[0]}" + (f"  (n = {m[5]})" if m[5] else "") + f"\n{m[1]}" for m in models]
for col, (title, idx) in enumerate((("(c) after the error: copying", 3), ("(d) after a success: imitation", 4))):
    axb = fig.add_axes([0.37 + col * 0.315, 0.06, 0.285, 0.585])
    for y, m in zip(ys, models):
        rd, lo, hi = m[idx]
        c = GEMMA if m[2] else OTHER
        if rd == lo == hi == 0:   # no events in either arm: uninformative, drawn hollow
            axb.plot([rd], [y], marker="o" if m[2] else "D", ms=6.5, color=c, mfc="white", mew=1.4, zorder=3, ls="none")
            axb.text(1.2, y, "no events", va="center", fontsize=7.8, color="#555555")
            continue
        axb.plot([lo, hi], [y, y], color=c, lw=2.4, solid_capstyle="butt", zorder=2)
        axb.plot([rd], [y], marker="o" if m[2] else "D", ms=6.5, color=c, zorder=3, ls="none")
    axb.axvline(0, color="#555555", lw=0.9, zorder=1)
    axb.set_xlim(-6, 25); axb.set_ylim(-0.6, n - 0.4)
    axb.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}".replace("-", MINUS)))
    axb.set_xlabel("risk difference vs original (pp)", fontsize=9)
    axb.grid(axis="x", color="#E8E8E8", lw=0.8); axb.set_axisbelow(True)
    axb.set_yticks(ys)
    axb.set_yticklabels(labels if col == 0 else [], fontsize=8.0, linespacing=1.0)
    axb.tick_params(axis="x", labelsize=8.8); axb.tick_params(axis="y", length=0)
    axb.set_title(title, loc="left", fontsize=10.5, fontweight="bold")
    if col == 0:
        axb.legend(handles=[Line2D([], [], marker="o", ls="none", color=GEMMA, ms=6.5, label="Gemma 4"),
                            Line2D([], [], marker="D", ls="none", color=OTHER, ms=6.5, label="other families")],
                   loc="center right", bbox_to_anchor=(1.0, 0.45), frameon=False, fontsize=8.6,
                   handletextpad=0.3)
    if col == 0:
        for t, m in zip(axb.get_yticklabels(), models):
            t.set_color("#1A1A1A")
fig.savefig(HERE / "fig2_transcriptlab_v3.png", dpi=200, metadata={"Software": None})
fig.savefig(HERE / "fig2_transcriptlab_v3.svg", dpi=200, metadata={"Date": None})   # reproducible bytes
S.write(["fig2_transcriptlab_v3.png", "fig2_transcriptlab_v3.svg", "fig2_transcriptlab_v3.py"])
print("wrote", HERE / "fig2_transcriptlab_v3.png", HERE / "fig2_transcriptlab_v3.svg")
