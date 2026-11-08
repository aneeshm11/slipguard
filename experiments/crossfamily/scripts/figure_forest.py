"""Forest plot of the history-injection contrasts on the same 300 gate contexts: unconditional RD vs P0 (pp) with 95%
attempt-cluster bootstrap CIs, for Gemma-4-31B (workstream A, reference) and the three Qwen models (X, registered judge).
Rows = arms (A's P1 ~ X's P1L; A's P3 ~ X's hermes P1N). One axis; categorical slots 1-4 of the dataviz reference palette
in fixed order. Also writes the plotted numbers as JSON (table view).
usage (matplotlib lives in env_kg): /opt/envs/env_kg/bin/python figure_forest.py out_prefix"""
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

X = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A_REF = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion/out/ana_31b_old_gate_k1_random_sample.json')
SERIES = [('Gemma-4-31B (A, reference)', '#2a78d6'), ('Qwen3-8B (hermes JSON)', '#eb6834'),
          ('Qwen3-32B-FP8 (hermes JSON)', '#1baf7a'), ('Qwen3.5-9B (qwen3_coder XML)', '#eda100')]
ROWS = [('laundered exemplar + error', 'P1k1', 'P1L'), ('native slip via own parser', 'P3k1', 'P1N'),
        ('laundered exemplar + success', 'P6k1', 'P6'), ('removed + note', 'P5k1', 'P5'), ('shipped quarantine', 'P8ak1', 'P8a')]
TEXT, MUTED, GRID = '#0b0b0b', '#52514e', '#e4e3df'


def get(p):
    p = p if os.path.isabs(p) else os.path.join(X, p)
    return json.load(open(p)) if os.path.exists(p) else None


ref = get(A_REF)
qw = {'Qwen3-8B (hermes JSON)': get('out/ana_qwen3-8b.json'), 'Qwen3-32B-FP8 (hermes JSON)': get('out/ana_qwen3-32b.json'),
      'Qwen3.5-9B (qwen3_coder XML)': get('out/ana_qwen3.5-9b.json')}
pts = []
for ri, (lab, aarm, xarm) in enumerate(ROWS):
    for si, (sname, col) in enumerate(SERIES):
        if sname.startswith('Gemma'):
            u = ((ref or {}).get('paired_vs_P0', {}).get(aarm) or {}).get('uncond')
            if u:
                pts.append({'row': lab, 'series': sname, 'arm': aarm, 'RD_pp': 100 * u['diff'], 'CI_pp': [100 * u['diff_CI'][0], 100 * u['diff_CI'][1]]})
        else:
            an = qw[sname]
            u = ((an or {}).get('paired_vs_P0', {}).get(xarm) or {}).get('uncond')
            if u:
                pts.append({'row': lab, 'series': sname, 'arm': xarm, 'RD_pp': 100 * u['RD'], 'CI_pp': [100 * float(u['RD_CI'][0]), 100 * float(u['RD_CI'][1])]})
fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=200)
fig.patch.set_facecolor('#fcfcfb'); ax.set_facecolor('#fcfcfb')
nrow = len(ROWS); off = [-0.27, -0.09, 0.09, 0.27]
for p in pts:
    ri = [r[0] for r in ROWS].index(p['row']); si = [s[0] for s in SERIES].index(p['series']); col = SERIES[si][1]
    y = nrow - 1 - ri - off[si]
    ax.plot(p['CI_pp'], [y, y], color=col, lw=2, solid_capstyle='round', zorder=2)
    ax.plot([p['RD_pp']], [y], 'o', ms=6, color=col, mec='#fcfcfb', mew=1.5, zorder=3)
    if p['series'].startswith('Gemma') or abs(p['RD_pp']) >= 3:
        ax.annotate(f"{p['RD_pp']:+.1f}", (p['CI_pp'][1], y), xytext=(4, 0), textcoords='offset points', va='center',
                    fontsize=7, color=MUTED)
ax.axvline(0, color=MUTED, lw=1, zorder=1)
ax.set_yticks(range(nrow)); ax.set_yticklabels([r[0] for r in ROWS][::-1], fontsize=8, color=TEXT)
ax.set_xlabel('change in P(next call is a malformed edit), pp vs original history (95% CI)', fontsize=8, color=TEXT)
ax.tick_params(axis='x', labelsize=7, colors=MUTED); ax.tick_params(axis='y', length=0)
ax.grid(axis='x', color=GRID, lw=0.8); ax.set_axisbelow(True)
for s in ('top', 'right', 'left'):
    ax.spines[s].set_visible(False)
ax.spines['bottom'].set_color(GRID)
handles = [plt.Line2D([0], [0], marker='o', color=c, lw=2, ms=6, label=n) for n, c in SERIES]
ax.legend(handles=handles, fontsize=7, frameon=False, loc='lower right')
ax.set_title('One corrupted exemplar in history: Gemma-4 vs Qwen (same 300 agent states)', fontsize=9, color=TEXT, loc='left')
fig.tight_layout()
pre = sys.argv[1] if len(sys.argv) > 1 else os.path.join(X, 'out', 'fig_forest_rd')
fig.savefig(pre + '.png'); fig.savefig(pre + '.svg')
json.dump(pts, open(pre + '.json', 'w'), indent=1)
print('wrote', pre + '.{png,svg,json}', len(pts), 'points')
