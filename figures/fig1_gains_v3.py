"""FIG1 v3 (PAPER v2.2+, 2026-11-07; from v2) — one-glance gains: stock vs slipguard on the registered public results (dumbbell rows, 95% CIs where the
producer stores them). Every value is read from the cited JSONs (see figure_data.json); nothing is typed in.

    python fig1_gains_v3.py         # writes fig1_gains_v3.png + fig1_gains_v3.svg; values -> figure_data_v3.json
    (env_agentpaper has no matplotlib: run with /opt/envs/env_g3/bin/python -B -s, matplotlib 3.11)

v3.1 changes (PAPER v2.3, 2026-11-07; R4 methodologist M1, area chair Change 3): the refusal panel is dropped (Table 1
keeps it), so the figure has seven panels and panel 5 is the pooled quarantine panel, whose subtitle names the three runs
and their removals; panel 3 is titled "Tasks solved (non-inferior at -3 pp)", zoomed, with the -3 pp margin dashed and
the 95% CI of the difference drawn around slipguard; the audit-pick TranscriptLab panel uses the matched-dtype run
(PREREG_v2.7 D1: AWQ served bf16, as end to end); the audit-pick end-to-end panel uses PREREG_E_awq2 (QAT 1.91 ->
AWQ 0.50 stock, six fresh replicates -> AWQ + proxy 0.29), change "0.26x (stock); proxy 0.59x [CI]" (the stale
"n.s." of the two-replicate S-a test is gone); one unit per panel (stated in each subtitle), arrows coloured by step
(orange = checkpoint swap, blue = slipguard), "change" text in ink, legend splits "other method" from "audit pick".

v3 changes: panels 1-2 use PREREG_E_ext's eight fresh replicates (registered; the first two replicates are named in the
subtitles); new panel 3 = tasks solved (non-inferiority, PREREG_E_ext primary); new last panel = the audit pick end to
end (PREREG_E_awq: QAT stock -> AWQ stock -> AWQ + proxy).

v2 changes: exact-intent panel compares IPD with the best non-slipguard method (greedy decoding), not the lenient
parser's 0%; the quarantine panel uses the registered pooled estimate over three runs (v27_pooled_retest.json);
the thinking-off panel is dropped (moved to RESULTS); 'delivered' malformed calls; T = 0.2 stated.

Needs matplotlib >= 3.8.
"""
from __future__ import annotations

import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

import _figdata  # noqa: E402
from _figdata import GUARD, HERE, MID, REF, STOCK, Sources  # noqa: E402

_figdata.DATA_JSON = HERE / "figure_data_v3.json"   # never touch the v1/v2 figure data

E2E = "experiments/endtoend/analysis/prereg_pop31.json"
CP = "release/lib/results/conformance_pnc/RESULTS.json"
V24 = "experiments/intent_decoding/v24/battery_run_analysis.json"
V25 = "experiments/intent_decoding/v25/out/analysis_v25.json"
V26 = "experiments/contagion/out/confirmatory/v26_audit_analysis.json"
CF = "experiments/contagion/out/confirmatory/confirm_v2_all_full.json"
POOL = "experiments/contagion/out/confirmatory/v27_pooled_retest.json"
EXT = "experiments/endtoend/analysis/prereg_E_ext.json"
AWQE = "experiments/endtoend/analysis/prereg_E_awq.json"
AWQ2 = "experiments/endtoend/analysis/prereg_E_awq2.json"
V27 = "experiments/contagion/out/confirmatory/v27_robustness_analysis.json"

S = Sources("FIG1_v3", "paper/protocol/draft/figures/fig1_gains_v3.py")
pct = lambda x: 100.0 * x  # noqa: E731


def rate3(label, rel, key):
    """[rate, lo, hi, n] stored by the producer -> percent triple."""
    r = S.get(label, rel, key)
    return pct(r[0]), pct(r[1]), pct(r[2]), r[3]


# ---- 1. end to end: malformed calls per episode (31B, ADK harness); first two replicates for the subtitle ----
y_base = S.get("E2E malformed calls/episode, stock", E2E, "co_primary/Y1/base_mean")
y_full = S.get("E2E malformed calls/episode, slipguard proxy", E2E, "co_primary/Y1/fullp_mean")
ratio = S.get("E2E ratio slipguard/stock", E2E, "co_primary/Y1/ratio_fullp_over_base/ratio")
n_tasks = S.get("E2E tasks", E2E, "co_primary/Y1/diff_fullp_minus_base/n")
reps = S.get("E2E tasks per replicate count (base arm)", E2E, "replicates/base")
n_rep = int(max(reps, key=int))

# ---- 2. stuck episodes in the first two replicates (subtitle) ----
st = {}
for rep in ("replicate1", "replicate2"):
    for arm in ("base", "fullp"):
        st[(rep, arm)] = S.get(f"stuck episodes {rep} {arm} [k, n, CI]", E2E, f"secondary/stuck/{rep}/{arm}")
k_b = S.derived("stuck episodes, stock, pooled k", st[("replicate1", "base")][0] + st[("replicate2", "base")][0],
                "sum of replicate k", ["stuck episodes replicate1 base [k, n, CI]", "stuck episodes replicate2 base [k, n, CI]"])
k_f = S.derived("stuck episodes, slipguard, pooled k", st[("replicate1", "fullp")][0] + st[("replicate2", "fullp")][0],
                "sum of replicate k", ["stuck episodes replicate1 fullp [k, n, CI]", "stuck episodes replicate2 fullp [k, n, CI]"])
n_st = S.derived("stuck episodes, pooled n", st[("replicate1", "base")][1] + st[("replicate2", "base")][1],
                 "sum of replicate n", ["stuck episodes replicate1 base [k, n, CI]", "stuck episodes replicate2 base [k, n, CI]"])

# ---- 1-3. eight fresh replicates (PREREG_E_ext): the plotted end-to-end values ----
fy_base = S.get("E_ext malformed calls/episode, stock", EXT, "secondary/Y1/base_mean")
fy_full = S.get("E_ext malformed calls/episode, slipguard proxy", EXT, "secondary/Y1/fullp_mean")
f_ratio = S.get("E_ext ratio slipguard/stock", EXT, "secondary/Y1/ratio_fullp_over_base/ratio")
f_ratio_ci = S.get("E_ext ratio CI", EXT, "secondary/Y1/ratio_fullp_over_base/ci95")
f_st_b = S.get("E_ext stuck, stock [k, n]", EXT, "secondary/stuck/base")
f_st_f = S.get("E_ext stuck, slipguard [k, n]", EXT, "secondary/stuck/fullp")
f_res = S.get("E_ext resolved [base, fullp, n]", EXT, "primary_resolve/resolved_base_fullp_of")
f_res_d = S.get("E_ext resolve diff (fullp - base)", EXT, "primary_resolve/mean_diff")
f_res_ci = S.get("E_ext resolve diff CI", EXT, "primary_resolve/ci95")
f_verdict = S.get("E_ext primary verdict", EXT, "primary_verdict")
assert f_verdict == "RESOLVE NON-INFERIOR"
_ni_key = [k for k in S.get("E_ext primary_resolve block", EXT, "primary_resolve") if k.startswith("non_inferior_at_")]
assert len(_ni_key) == 1 and S.get("E_ext non-inferior at the registered margin", EXT, f"primary_resolve/{_ni_key[0]}") is True
ni_margin = S.derived("non-inferiority margin (pp), parsed from the result key", float(re.fullmatch(r"non_inferior_at_(-?[\d.]+)pp", _ni_key[0]).group(1)),
                      "number in the key name primary_resolve/non_inferior_at_<margin>pp", ["E_ext non-inferior at the registered margin"])

# ---- 4. exact intent and silent corruption on injected slips (393 detectable states, reweighted) ----
ex, sil = {}, {}
for arm in ("lenient", "greedy", "IPD"):
    r = S.get(f"exact intent {arm}", V24, f"outcomes_detectable/{arm}/exact/reweighted/rate")
    ci = S.get(f"exact intent {arm} CI (Kish-Wilson)", V24, f"outcomes_detectable/{arm}/exact/reweighted/wilson95_kish")
    ex[arm] = (pct(r), pct(ci[0]), pct(ci[1]))
for arm in ("greedy", "IPD"):
    sil[arm] = pct(S.get(f"silently wrong {arm}", V24, f"outcomes_detectable/{arm}/silent/reweighted/rate"))
n_inj = S.get("injected-slip states (detectable)", V24, "n_detectable")

# ---- 5. quarantine (31B 4-bit QAT, 300 public states, three runs pooled) ----
q_p0 = rate3("malformed next edit, clean history (QAT P0, run 1)", V26, "rates/QAT/P0")
q_p1 = rate3("malformed next edit, laundered call + error (QAT P1, run 1)", V26, "rates/QAT/P1")
assert abs(S.get("C1 arm (cross-check)", CF, "31B/full/C1/uncond/arm") * 100 - q_p1[0]) < 1e-9
assert abs(S.get("C1 base (cross-check)", CF, "31B/full/C1/uncond/base") * 100 - q_p0[0]) < 1e-9
pool_runs = S.get("pooled runs", POOL, "runs")
assert pool_runs == ["C1", "RSA", "RSB"]
qp_p0 = rate3("pooled 3 runs: clean history P0", POOL, "pooled/P0")
qp_p1 = rate3("pooled 3 runs: laundered call + error P1", POOL, "pooled/P1")
qp_p8 = rate3("pooled 3 runs: quarantined P8a", POOL, "pooled/P8a")
rem = S.get("pooled quarantine removal (pre-specified descriptive pool)", POOL, "pooled_removal/point")
rem_ci = S.get("pooled quarantine removal CI", POOL, "pooled_removal/CI")
run_rem = [S.get(f"quarantine removal, run {i} ({k})", V27, f"removal/{k}/point") for i, k in ((1, "QAT"), (2, "RSA"), (3, "RSB"))]
assert abs(S.get("C1 removal (cross-check of run 1)", CF, "31B/full/C5/uncond/removal") - run_rem[0]) < 1e-3

# ---- 6. checkpoint audit pick, matched dtype (PREREG_v2.7 D1: AWQ served bf16, as in the end-to-end runs) ----
m_qat = rate3("matched dtype: QAT P1", V27, "rates/QAT/P1")
m_awq = rate3("matched dtype: AWQ (audit pick, bf16) P1", V27, "rates/RD16/P1")
m_awq8 = rate3("matched dtype: AWQ + quarantine P8a", V27, "rates/RD16/P8a")
d1_rd = S.get("audit pick RD at matched dtype (AWQ - QAT, P1)", V27, "contrasts/D1/RD")
d1_ci = S.get("audit pick RD CI at matched dtype", V27, "contrasts/D1/RD_CI")
assert S.get("D1 verdict", V27, "verdicts/D1") == "AUDIT PICK REPLICATES AT MATCHED DTYPE"
q_rd = S.derived("quarantine on the pick (pp): P8a - P1, matched dtype", m_awq8[0] - m_awq[0], "difference of the two plotted rates",
                 ["matched dtype: AWQ + quarantine P8a", "matched dtype: AWQ (audit pick, bf16) P1"])

# ---- 7. audit pick end to end (PREREG_E_awq2: six fresh AWQ replicates; QAT comparator r1..r10) ----
w_qat = S.get("E_awq2 QAT base Y1 (r1..r10)", AWQ2, "secondary/S4_awq_base_vs_qat_base_fresh/B_mean")
w_awq = S.get("E_awq2 AWQ base Y1 (fresh)", AWQ2, "secondary/S4_awq_base_vs_qat_base_fresh/A_mean")
w_ratio = S.get("E_awq2 S4 ratio AWQ/QAT (fresh)", AWQ2, "secondary/S4_awq_base_vs_qat_base_fresh/ratio_A_over_B/ratio")
assert S.get("E_awq2 S4 verdict", AWQ2, "secondary/S4_awq_base_vs_qat_base_fresh/verdict") == "REPLICATES"
assert abs(S.get("E_awq2 P2 AWQ base (cross-check)", AWQ2, "primary_P2_awq_fullp_vs_awq_base/B_mean") - w_awq) < 1e-9
w_awqp = S.get("E_awq2 AWQ + proxy Y1 (fresh)", AWQ2, "primary_P2_awq_fullp_vs_awq_base/A_mean")
w_p2 = S.get("E_awq2 P2 ratio proxy/stock on AWQ", AWQ2, "primary_P2_awq_fullp_vs_awq_base/ratio_A_over_B/ratio")
w_p2_ci = S.get("E_awq2 P2 ratio CI", AWQ2, "primary_P2_awq_fullp_vs_awq_base/ratio_A_over_B/ci95")
assert S.get("E_awq2 P2 verdict", AWQ2, "primary_P2_awq_fullp_vs_awq_base/verdict").startswith("SLIPGUARD STILL REDUCES")
n_awq2 = len(S.get("E_awq2 analysis set (replicates)", AWQ2, "analysis_set"))
w1_awq = S.get("E_awq AWQ base Y1, first 2 replicates", AWQE, "primary_awq_base_vs_qat_base/A_mean")
w1_ratio = S.get("E_awq ratio AWQ/QAT, first 2 replicates", AWQE, "primary_awq_base_vs_qat_base/ratio_A_over_B/ratio")
n_qat = len(S.get("E_awq QAT comparator replicates", AWQE, "qat_replicates"))


# =============================== drawing ===============================
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.spines.left": False, "svg.fonttype": "none",
                     "svg.hashsalt": "slipguard-figures"})   # deterministic SVG ids
ARR, EN, TIMES, MINUS = "→", "–", "×", "−"
INK, INK2 = "#222222", "#444444"
fmt_pp = lambda v: f"{v:+.1f}".replace("-", MINUS)  # noqa: E731
fmt_m = f"{ni_margin:+g}".replace("-", MINUS)   # the registered margin as printed in the registration (-3 pp)
f_pct = lambda k, n: pct(k / n)  # noqa: E731
rows = [
    dict(title="Delivered malformed tool calls per episode",
         sub=f"ADK harness, Gemma-4-31B 4-bit, T 0.2, {n_tasks} tasks {TIMES} 8 fresh replicates; change: ratio "
             f"(first {n_rep} replicates: {y_base:.2f} {ARR} {y_full:.2f}, {ratio:.2f}{TIMES})",
         better="lower", xlim=(0, 3.0), fmt=None,
         pts=[(fy_base, None, None, "stock"), (fy_full, None, None, "guard")],
         labels=[f"{fy_base:.2f}", f"{fy_full:.2f}"],
         right=f"{f_ratio:.2f}{TIMES}\n[{f_ratio_ci[0]:.2f}, {f_ratio_ci[1]:.2f}]"),
    dict(title="Stuck episodes (5+ malformed calls in a row)",
         sub=f"same 8 fresh replicates, episodes of {f_st_b[1]} per arm; change: episodes (first {n_rep}: {k_b} {ARR} {k_f} of {n_st})",
         better="lower", xlim=(0, 60), fmt=None,
         pts=[(f_st_b[0], None, None, "stock"), (f_st_f[0], None, None, "guard")],
         labels=[f"{f_st_b[0]}", f"{f_st_f[0]}"], right=f"{f_st_b[0]} {ARR} {f_st_f[0]}\nof {f_st_b[1]}"),
    dict(title=f"Tasks solved (non-inferior at {fmt_m} pp)",
         sub=f"same 8 fresh replicates, {f_res[0]} vs {f_res[1]} of {f_res[2]}; bar: 95% CI of the difference; "
             f"dashed: stock {fmt_m} pp; change: pp",
         better="higher", xlim=(36, 48), fmt="%",
         margin=f_pct(f_res[0], f_res[2]) + ni_margin,
         pts=[(f_pct(f_res[0], f_res[2]), None, None, "stock"),
              (f_pct(f_res[0], f_res[2]) + pct(f_res_d), f_pct(f_res[0], f_res[2]) + pct(f_res_ci[0]),
               f_pct(f_res[0], f_res[2]) + pct(f_res_ci[1]), "guard")],
         labels=[f"{f_pct(f_res[0], f_res[2]):.1f}% vs {f_pct(f_res[1], f_res[2]):.1f}%", ""],
         right=f"{fmt_pp(pct(f_res_d))} pp\n[{fmt_pp(pct(f_res_ci[0]))}, {fmt_pp(pct(f_res_ci[1]))}]"),
    dict(title="Intended call recovered exactly (detectable injected slips)",
         sub=f"{n_inj} slips; greedy re-decoding (best other) vs IPD; stock parser {ex['lenient'][0]:.0f}%; "
             f"silently wrong: greedy {sil['greedy']:.1f}%, IPD {sil['IPD']:.1f}%",
         better="higher", xlim=(0, 100), fmt="%",
         pts=[(*ex["greedy"], "mid_hollow"), (*ex["IPD"], "guard")],
         labels=[f"greedy {ex['greedy'][0]:.1f}%", f"IPD {ex['IPD'][0]:.1f}%"],
         right=f"{ex['greedy'][0]:.1f}% {ARR} {ex['IPD'][0]:.1f}%"),
    dict(title="Malformed next edit after one laundered call in history",
         sub=f"runs 1{EN}3 pooled ({qp_p1[3]} state-runs; {run_rem[0] * 100:.0f}%, {run_rem[1] * 100:.0f}%, "
             f"{run_rem[2] * 100:.0f}% removed per run); tick: clean history; change: share of excess removed",
         better="lower", xlim=(0, 30), fmt="%", ref=qp_p0,
         pts=[(*qp_p1[:3], "stock"), (*qp_p8[:3], "guard")],
         labels=[f"{qp_p1[0]:.1f}%", f"quarantined {qp_p8[0]:.1f}%"],
         right=f"{rem * 100:.0f}% removed\n[{rem_ci[0] * 100:.0f}, {rem_ci[1] * 100:.0f}]"),
    dict(title="Same outcome by served checkpoint: audit pick, then quarantine",
         sub=f"300 states, one run, matched dtype (bf16): 4-bit QAT {ARR} AWQ (audit pick) {ARR} AWQ + quarantine; change: pp",
         better="lower", xlim=(0, 30), fmt="%",
         pts=[(*m_qat[:3], "stock"), (*m_awq[:3], "mid"), (*m_awq8[:3], "guard")],
         labels=["QAT", "AWQ", f"{m_awq8[0]:.0f}%"],
         right=f"{fmt_pp(pct(d1_rd))} pp\n[{fmt_pp(pct(d1_ci[0]))}, {fmt_pp(pct(d1_ci[1]))}]\nthen {fmt_pp(q_rd)} pp"),
    dict(title="Audit pick, end to end: delivered malformed calls per episode",
         sub=f"stock parser: QAT ({n_qat} replicates) {ARR} AWQ ({n_awq2} fresh; first 2: {w1_awq:.2f}, {w1_ratio:.2f}{TIMES}); "
             f"then AWQ + proxy; not seed-paired; change: ratio",
         better="lower", xlim=(0, 3.0), fmt=None,
         pts=[(w_qat, None, None, "stock"), (w_awq, None, None, "mid"), (w_awqp, None, None, "guard")],
         labels=[f"QAT {w_qat:.2f}", (f"AWQ {w_awq:.2f}", "left"), f"+ proxy {w_awqp:.2f}"],
         right=f"{w_ratio:.2f}{TIMES} (stock)\nproxy {w_p2:.2f}{TIMES}\n[{w_p2_ci[0]:.2f}, {w_p2_ci[1]:.2f}]"),
]

W, row_h, head_h = 8.6, 1.08, 0.62
fig = plt.figure(figsize=(W, head_h + row_h * len(rows) + 0.1))
FH = fig.get_figheight()
left, right_col = 0.035, 0.80
style = {"stock": dict(marker="o", ms=8, mfc=STOCK, mec=STOCK, color=STOCK),
         "guard": dict(marker="D", ms=8, mfc=GUARD, mec=GUARD, color=GUARD),
         "mid": dict(marker="s", ms=7.5, mfc=MID, mec=MID, color=MID),
         "mid_hollow": dict(marker="s", ms=7.5, mfc="white", mec=MID, mew=1.6, color=MID)}
for i, r in enumerate(rows):
    y_top = 1 - (head_h + i * row_h) / FH            # top of this row (figure fraction)
    hh = row_h / FH
    fig.text(left, y_top - 0.12 * hh, f"{i + 1}. " + r["title"], fontsize=10.5, fontweight="bold", va="center", color=INK)
    fig.text(left, y_top - 0.30 * hh, r["sub"] + ("  (lower is better)" if r["better"] == "lower" else "  (higher is better)"),
             fontsize=7.6, color=INK2, va="center")
    ax = fig.add_axes([left + 0.01, y_top - 0.74 * hh, right_col - left - 0.03, 0.30 * hh])
    span = r["xlim"][1] - r["xlim"][0]
    ax.set_xlim(r["xlim"][0] - 0.015 * span, r["xlim"][1] + 0.015 * span); ax.set_ylim(-1, 1.6); ax.set_yticks([])
    ax.spines["bottom"].set_bounds(*r["xlim"])
    ax.tick_params(axis="x", labelsize=8.5, length=3, pad=2)
    if r["fmt"] == "%":
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.grid(axis="x", color="#E8E8E8", lw=0.8); ax.set_axisbelow(True)
    pts = r["pts"]
    # connectors between consecutive points, coloured by the step: orange = checkpoint swap, blue = slipguard
    for a, b in zip(pts[:-1], pts[1:]):
        col = MID if b[3] == "mid" else GUARD
        ax.annotate("", xy=(b[0], 0), xytext=(a[0], 0), zorder=1,
                    arrowprops=dict(arrowstyle="-|>", color=col, lw=1.2, alpha=0.6, shrinkA=6, shrinkB=7, mutation_scale=11))
    for p in pts:
        x, lo, hi, kind = p[:4]
        if lo is not None and hi - lo > 0:
            ax.plot([lo, hi], [0, 0], color=style[kind]["color"], lw=2.6, zorder=2, solid_capstyle="butt")
        ax.plot([x], [0], ls="none", zorder=4, clip_on=False, **{k: v for k, v in style[kind].items() if k != "color"})
    if "ref" in r:
        ax.plot([r["ref"][0]] * 2, [-0.75, 0.75], color=REF, lw=1.5, zorder=5)
    if "margin" in r:
        ax.plot([r["margin"]] * 2, [-0.9, 1.2], color=REF, lw=1.2, ls=(0, (3, 2)), zorder=5)
        ax.text(r["margin"] - 0.01 * span, 0.75, f"{fmt_m} pp", ha="right", va="bottom", fontsize=8.2, color=INK)
    for j, lab in enumerate(r.get("labels") or []):
        if not lab:
            continue
        lab, ha = lab if isinstance(lab, tuple) else (lab, None)   # (text, ha) pins the alignment where labels would collide
        xl = pts[j][0]
        if ha is None:
            ha = "left" if xl < r["xlim"][0] + 0.06 * span else ("right" if xl > r["xlim"][1] - 0.06 * span else "center")
        ax.text(xl + 0.02 * span if ha == "left" else xl, 0.75, lab, ha=ha, va="bottom", fontsize=8.2, color=INK)
    fig.text(right_col + 0.005, y_top - 0.59 * hh, r["right"], fontsize=9.5, fontweight="bold", color=INK, va="center",
             linespacing=1.15)
handles = [Line2D([], [], ls="none", **{k: v for k, v in style["stock"].items() if k != "color"}, label="stock"),
           Line2D([], [], ls="none", **{k: v for k, v in style["mid_hollow"].items() if k != "color"}, label="other method"),
           Line2D([], [], ls="none", **{k: v for k, v in style["mid"].items() if k != "color"}, label="audit pick (AWQ)"),
           Line2D([], [], ls="none", **{k: v for k, v in style["guard"].items() if k != "color"}, label="slipguard"),
           Line2D([], [], color=STOCK, lw=2.6, label="95% CI")]
fig.legend(handles=handles, loc="center left", bbox_to_anchor=(left - 0.01, 1 - 0.20 / FH), ncol=5, frameon=False,
           fontsize=9, handletextpad=0.4, columnspacing=1.2)
fig.text(left, 1 - 0.46 / FH, "stock = unmodified vLLM 0.19.1 parser + ADK, or the unguarded laundered history (panels 5" + EN + "6)",
         fontsize=8, color=INK2, va="center")
fig.text(right_col + 0.005, 1 - 0.20 / FH, "change", fontsize=9, color=INK2, va="center")
fig.canvas.draw()   # layout check: no text may run past the right edge of the figure
_over = [tx.get_text()[:60] for tx in fig.texts if tx.get_window_extent().x1 > fig.bbox.x1 - 2]
assert not _over, f"text overflows the figure: {_over}"
fig.savefig(HERE / "fig1_gains_v3.png", dpi=200, metadata={"Software": None})
fig.savefig(HERE / "fig1_gains_v3.svg", dpi=200, metadata={"Date": None})   # reproducible bytes
S.write(["fig1_gains_v3.png", "fig1_gains_v3.svg", "fig1_gains_v3.py"])
print("wrote", HERE / "fig1_gains_v3.png", HERE / "fig1_gains_v3.svg")
