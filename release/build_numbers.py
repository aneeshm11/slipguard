#!/usr/bin/env python3
"""build_numbers.py -- the single source of truth for every number in the paper (workstream R; `make numbers`).

Reads each workstream's machine-readable results (never logs, never prose), extracts every quantity the paper
cites, and writes
  release/numbers.json        {id: value, ci, n, k, source file + sha256 + mtime, JSON path, producing script, definition}
  release/claims_ledger.md    every claim in paper/protocol/OUTLINE.md and UPGRADE_PLAN §1/§4 -> exact number, CI,
                              n, source, script, and a status: OK | MISMATCH (stale or drifted) | CONFLICT (two
                              sources disagree) | PENDING (target, no result yet) | RETRACTED | EXTERNAL.
CPU only, read-only on sources, standard library only, < 5 s.
Usage: python release/build_numbers.py [--root PROJECT_ROOT] [--out-dir release] [--strict]
  --strict exits 1 if any main-text claim is MISMATCH/CONFLICT (use as a pre-submission gate).
In a fresh Kaggle notebook pass --root to the unpacked dataset; the SOURCES map below lists the files needed.
"""
import argparse
import datetime as dt
import hashlib
import collections
import json
import re
import math
import os
import sys

# ----------------------------------------------------------------------------------------------- sources
SOURCES = {
    'A_gate': 'experiments/contagion/out/gate_gate31b_final.json',
    'A_union': 'experiments/contagion/results.json',
    'A_12b': 'experiments/contagion/out/ana_12b_old_gate_k1_random_sample.json',
    'A_e4b': 'experiments/contagion/out/ana_e4b_old_gate_k1_random_sample.json',
    'A_copy_gate': 'experiments/contagion/out/copy_check_gate.json',
    'A_copy': 'experiments/contagion/out/copy_check.json',
    'A_rules': 'experiments/contagion/out/decision_rules.json',
    'A_obs': 'experiments/contagion/out/observational.json',
    'B_gate': 'experiments/intent_decoding/out/gate_v2_r31_on.json',
    'B_qs': 'experiments/intent_decoding/out/quotestorm_free_big.json',
    'B_res': 'experiments/intent_decoding/results.json',
    'C_res': 'experiments/conformance/results.json',
    'C_stats': 'experiments/conformance/slips/release/corpus_stats.json',
    'C_hist': 'experiments/conformance/history/results_history.json',
    'D_t3': 'paper/protocol_theory/sim/out/t3_summary.json',
    'D_boot': 'paper/protocol_theory/sim/out/t3_boot_extra.json',
    'D_seqs': 'paper/protocol_theory/sim/out/t3_seqs_check.json',
    'D_replay': 'paper/protocol_theory/sim/out/t3_replay_results.json',
    'D_t1': 'paper/protocol_theory/sim/out/t1_results.json',
    'D_t2': 'paper/protocol_theory/sim/out/t2_logs_by_run.json',
    'D_t4': 'paper/protocol_theory/sim/out/t4_natural_vs_oldfirst.json',
    'D_t5': 'paper/protocol_theory/sim/out/t5_results.json',
    'F_margins': 'experiments/quant_margins/out/results_margins.json',
    'F_replay': 'experiments/quant_margins/out/results_replay.json',
    'F_t5': 'experiments/quant_margins/out/t5_quant_check.json',
    'E_res': 'experiments/endtoend/results.json',
    'CEN': 'experiments/format_census/census.json',
    'R_priv': 'release/reports/privacy/summary.json',
    'R_prov': 'release/provenance/provenance_summary.json',
    'X_res': 'experiments/crossfamily/results.json',
    'A_res': 'experiments/contagion/results.json',
    'B_gate3': 'experiments/intent_decoding/out/gate_v3_r31_on_june.json',
    'C_xr': 'experiments/conformance/results/crossruntime.json',
    'X_fmt': 'experiments/crossfamily/format/format_summary.json',
    'F_decomp': 'experiments/quant_margins/out/results_decomp.json',
    'F_wshift': 'experiments/quant_margins/out/weight_shift_diag.json',
    'R_snip': 'release/package/v1.0/corpus/discovery/build_summary.json',
    'R_nb': 'release/reports/notebook/l2_checks.json',
    'R_rep': 'release/package/v1.0/replay/discovery/build_summary.json',
    'A_tr': 'experiments/contagion/out/test_retest.json',
    'A_map': 'experiments/contagion/out/a2_map_h.json',
    'A_tpl': 'experiments/contagion/out/template_thinking_off_check.json',
    'F_res': 'experiments/quant_margins/results.json',
    'D_epred': 'paper/protocol_theory/sim/out/e_predictions_v1.json',
    'D_pred2': 'paper/protocol_theory/sim/out/prereg_predictions_v2.json',
    'D_nonident': 'paper/protocol_theory/sim/out/t3_nonident.json',
    'A_v21': 'experiments/contagion/out/v21_analysis.json',
    'A_v22S': 'experiments/contagion/out/v22S_analysis.json',
    'A_v22H': 'experiments/contagion/out/v22H_analysis.json',
    'B_proxyeq': 'experiments/intent_decoding/out/proxy_equivalence.json',
    'E_qsfreeze': 'experiments/endtoend/acceptance/p1_quotestorm_freeze_candidate.json',
    'R_qs': 'release/provenance/quotestorm_provenance_summary.json',
    'G_res': 'experiments/thirdparty/results.json',
}
SCRIPTS = {
    'A_gate': 'experiments/contagion/scripts/analyze_injection.py', 'A_union': 'experiments/contagion/scripts/analyze_injection.py',
    'A_12b': 'experiments/contagion/scripts/analyze_injection.py', 'A_e4b': 'experiments/contagion/scripts/analyze_injection.py',
    'A_copy_gate': 'experiments/contagion/scripts/ (copy check)', 'A_copy': 'experiments/contagion/scripts/ (copy check)',
    'A_rules': 'experiments/contagion/scripts/ (decision rules, PREREG_v1)', 'A_obs': 'experiments/contagion/scripts/analyze_obs.py',
    'B_gate': 'experiments/intent_decoding/analyze_replay.py + gate_summary.py', 'B_qs': 'experiments/intent_decoding/quotestorm_free_big.py',
    'B_res': 'experiments/intent_decoding/make_results.py', 'C_res': 'experiments/conformance/make_results.py',
    'C_stats': 'experiments/conformance/slips/build_corpus.py', 'C_hist': 'experiments/conformance/history/roundtrip.py',
    'D_t3': 'paper/protocol_theory/sim/t3_fit.py + t3_summary.py', 'D_boot': 'paper/protocol_theory/sim/t3_boot_extra.py',
    'D_seqs': 'paper/protocol_theory/sim/t3_seqs_check.py', 'D_replay': 'paper/protocol_theory/sim/t3_replay.py',
    'D_t1': 'paper/protocol_theory/sim/t1_ambiguity.py', 'D_t2': 'paper/protocol_theory/sim/t2_logs_by_run.py',
    'D_t4': 'paper/protocol_theory/sim/t4_order.py', 'D_t5': 'paper/protocol_theory/sim/t5_margin_model.py',
    'F_margins': 'experiments/quant_margins/analyze.py', 'F_replay': 'experiments/quant_margins/analyze_replay.py',
    'F_t5': 'paper/protocol_theory/sim/t5_quant_check.py', 'E_res': 'experiments/endtoend/ (results.json)',
    'CEN': 'experiments/format_census/census.py', 'R_priv': 'release/scripts/privacy_pipeline.py',
    'R_prov': 'release/scripts/provenance_build.py', 'X_res': 'experiments/crossfamily/ (analysis scripts; FINAL)',
    'A_res': 'experiments/contagion/scripts/analyze_injection.py + prereg analysis', 'B_gate3': 'experiments/intent_decoding/analyze_replay.py',
    'C_xr': 'experiments/conformance/diff/analyze_x.py', 'X_fmt': 'experiments/crossfamily/format/ (format analysis)',
    'F_decomp': 'experiments/quant_margins/analyze_decomp.py', 'F_wshift': 'experiments/quant_margins/weight_grid_diag.py',
    'R_snip': 'release/scripts/build_discovery_snippets.py', 'R_nb': 'release/hosting/notebook/reproduce_numbers.py', 'R_rep': 'release/scripts/build_replay_labels.py', 'A_tr': 'experiments/contagion/scripts/ (test-retest analysis)', 'A_map': 'experiments/contagion/scripts/a2_map_analysis.py',
    'A_tpl': 'experiments/contagion/scripts/check_template_thinking_off.py', 'F_res': 'experiments/quant_margins/ (make_results)',
    'D_epred': 'paper/protocol_theory/prereg/E_PREDICTIONS_v1.md (transcribed by D)', 'D_pred2': 'paper/protocol_theory/prereg/PREREG_v2*.md (transcribed by D)',
    'D_nonident': 'paper/protocol_theory/sim/t3_nonident.py', 'A_v21': 'experiments/contagion/scripts/analyze_v21_v22.py', 'A_v22S': 'experiments/contagion/scripts/analyze_v21_v22.py',
    'A_v22H': 'experiments/contagion/scripts/analyze_v21_v22.py', 'B_proxyeq': 'experiments/intent_decoding/ (proxy equivalence)',
    'E_qsfreeze': 'experiments/endtoend/acceptance/ (QuoteStorm freeze check)', 'R_qs': 'release/scripts/provenance_quotestorm.py', 'G_res': 'experiments/thirdparty/ (not yet produced)',
}
# malformed-definition tags (see release/DEFINITIONS.md §2)
DEF = {
    'A': 'M-A (canonical: vLLM-0.19.1 judge on generated text)',
    'Asyn': 'M-SYN (synthesis replica on logged args; NOT canonical)',
    'B': 'M-B census_judge (empty closer allowed; any declared key)',
    'C': 'M-C corpus labels (schema-based; logged args)',
    'D': 'M-D 13-key synthesis-style (logged args)',
    'E': 'M-E classify_args (proxy-delivered args)',
    'F': 'M-F order-replay judge (no unknown-key / special-token check)',
    'CEN': 'M-CEN census predicate (incl. noop_edit), all models pooled',
    'na': 'n/a',
}

# ----------------------------------------------------------------------------------------------- helpers
_cache = {}


def load(root, key):
    if key in _cache:
        return _cache[key]
    p = os.path.join(root, SOURCES[key])
    if not os.path.exists(p):
        _cache[key] = None
        return None
    with open(p, 'rb') as f:
        raw = f.read()
    try:
        d = json.loads(raw.decode('utf-8'), parse_constant=lambda c: float(c) if c in ('NaN', 'Infinity', '-Infinity') else c)
    except Exception:
        d = None
    _cache[key] = {'data': d, 'sha256': hashlib.sha256(raw).hexdigest(),
                   'mtime_utc': dt.datetime.fromtimestamp(os.path.getmtime(p), dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
    return _cache[key]


def dig(d, path):
    for k in path:
        if d is None:
            return None
        if isinstance(k, int):
            d = d[k] if isinstance(d, list) and -len(d) <= k < len(d) else None
        else:
            d = d.get(k) if isinstance(d, dict) else None
    return d


class Q:
    """One extracted quantity."""

    def __init__(self, src, path, kind='scalar', scale=1.0, fn=None):
        self.src, self.path, self.kind, self.scale, self.fn = src, path, kind, scale, fn

    def get(self, root):
        L = load(root, self.src)
        if L is None or L['data'] is None:
            return None
        v = dig(L['data'], self.path) if self.path is not None else L['data']
        if v is None:
            return None
        out = {'source': SOURCES[self.src], 'json_path': '/'.join(map(str, self.path or [])), 'script': SCRIPTS.get(self.src),
               'source_sha256': L['sha256'][:16], 'source_mtime_utc': L['mtime_utc']}
        try:
            if self.fn is not None:
                out.update(self.fn(v, L['data']))
            elif self.kind == 'scalar':
                out['value'] = v * self.scale
            elif self.kind == 'rate4':          # [p, lo, hi, n]
                out.update(value=v[0], ci=[v[1], v[2]], n=v[3])
            elif self.kind == 'rate3n':         # [n, p, lo, hi]
                out.update(value=v[1], ci=[v[2], v[3]], n=v[0])
            elif self.kind == 'ci3':            # [p, lo, hi]
                out.update(value=v[0], ci=[v[1], v[2]])
            elif self.kind == 'pci':            # [p, [lo, hi]]
                out.update(value=v[0], ci=list(v[1]))
            elif self.kind == 'kn':             # {k, n, rate, wilson95|ci95|lo/hi}
                ci = v.get('wilson95') or v.get('ci95') or ([v['lo'], v['hi']] if 'lo' in v else None)
                out.update(value=v.get('rate', v['k'] / v['n'] if v.get('n') else None), ci=ci, n=v.get('n'), k=v.get('k'))
            elif self.kind == 'ratio':          # {ratio, CI, ...}
                out.update(value=v['ratio'], ci=v['CI'] if 'CI' in v else v.get('ratio_CI'), n=v.get('n_contexts'))
            elif self.kind == 'rd':             # paired {diff, diff_CI}
                out.update(value=v['diff'], ci=v['diff_CI'], n=v.get('n_contexts'))
            elif self.kind == 'removal':
                out.update(value=v['fraction_removed'], ci=v['CI'], n=v.get('n_contexts'))
            elif self.kind == 'relred':
                out.update(value=v['relred_point'], ci=v['relred_wilson95'], n=v.get('before'))
            elif self.kind == 'count':
                out['value'] = len(v) if isinstance(v, (list, dict)) else v
            else:
                out['value'] = v
        except Exception as e:  # noqa: BLE001
            out['error'] = f'extract failed: {e!r}'
        return out


def holm(pvals):
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    adj = [None] * len(pvals); running = 0.0
    for r, i in enumerate(order):
        running = max(running, min(1.0, (len(pvals) - r) * pvals[i]))
        adj[i] = running
    return adj


# ----------------------------------------------------------------------------------------------- registry
# Each entry: id, label, Q(...), definition tag, claims [(where, quoted claim, claimed value, abs tolerance)], note.
# Claimed values use the SAME units as the extracted value (rates as fractions).
R = []


def E(id_, label, q, defn='na', claims=(), note='', main=True, canonical=True, cites=()):
    R.append(dict(id=id_, label=label, q=q, defn=defn, claims=list(claims), note=note, main=main, canonical=canonical, cites=list(cites)))


def cite(entry_id, *cites):
    """Attach paper-draft citation strings (`file#path` exactly as written in <!-- src: ... -->) to an entry."""
    for e in R:
        if e['id'] == entry_id:
            e['cites'].extend(cites)
            return
    raise KeyError(entry_id)


OUT, PLAN, PROG, R3 = 'OUTLINE v1 (superseded)', 'UPGRADE_PLAN.md', 'PROGRESS.md', 'R3 review'
V2 = 'OUTLINE v2'

# ---- H1 / C2 / C5: causal laundering loop (A) ----
E('A.31b.P0.cond', '31B gate P0 (original history): P(malformed | next call is edit)', Q('A_gate', ['arms', 'P0k0', 'P_malformed_given_edit'], 'rate4'), 'A',
  [(PLAN + ' §1.1/H1', '5.7%', 0.057, 0.0006), (PROG + ' 12:20', '5.7% [3.5,9.2]', 0.057, 0.0006)],
  'Conditional estimand. UPGRADE_PLAN makes the UNCONDITIONAL rate primary (next entry).')
E('A.31b.P0.uncond', '31B gate P0: unconditional P(next call is a malformed edit) [PRIMARY ESTIMAND]', Q('A_gate', ['arms', 'P0k0', 'P_malformed_edit_uncond'], 'rate4'), 'A')
E('A.31b.P1.cond', '31B gate P1k1 (one corrupted re-render + ADK error): P(malformed | edit)', Q('A_gate', ['arms', 'P1k1', 'P_malformed_given_edit'], 'rate4'), 'A',
  [(PLAN + ' §1.1/H1', '46.2%', 0.462, 0.0006), (PROG + ' 12:20', '46.2% [40.2,52.2]', 0.462, 0.0006)])
E('A.31b.P1.uncond', '31B gate P1k1: unconditional [PRIMARY]', Q('A_gate', ['arms', 'P1k1', 'P_malformed_edit_uncond'], 'rate4'), 'A')
E('A.31b.ratio.cond', '31B gate ratio P1/P0 (conditional)', Q('A_gate', ['paired_vs_P0', 'P1k1', 'cond'], 'ratio'), 'A',
  [(PLAN + ' §1.1/H1', 'x8.1 [5.4,14.9]', 8.1, 0.05), (OUT + ' thesis', '~7-10x', 8.5, 1.6), (R3, 'x6.4 [4.0,13.8] (interim)', 6.4, 0.05)],
  'R3 quoted an interim (n~100) value. results.json (union of all 31B files, n=303) gives a different number: see A.31b.ratio.union.')
E('A.31b.ratio.uncond', '31B gate ratio P1/P0 (unconditional) [PRIMARY]', Q('A_gate', ['paired_vs_P0', 'P1k1', 'uncond'], 'ratio'), 'A')
E('A.31b.ratio.union', '31B ratio in results.json (gate + pilot/interim files pooled, n=303)', Q('A_union', ['injection', '31b_old', 'gate_k1_random_sample', 'paired_vs_P0', 'P1k1', 'cond'], 'ratio'), 'A',
  [(PLAN + ' §1.1', 'x8.1 [5.4,14.9]', 8.1, 0.05)], 'Different population from the pre-registered 300-context gate set; do not cite.', main=False, canonical=False)
E('A.31b.rd.cond', '31B gate paired risk difference P1-P0 (conditional)', Q('A_gate', ['paired_vs_P0', 'P1k1', 'cond'], 'rd'), 'A',
  [(PLAN + ' §1.1', '+40.5 pp [34.1,47.2]', 0.405, 0.0006)])
E('A.31b.rd.uncond', '31B gate paired RD P1-P0 (unconditional) [PRIMARY; report first per §6]', Q('A_gate', ['paired_vs_P0', 'P1k1', 'uncond'], 'rd'), 'A')
E('A.31b.P2.cond', '31B P2 (error text only)', Q('A_gate', ['arms', 'P2k1', 'P_malformed_given_edit'], 'rate4'), 'A',
  [(PLAN + ' §1.1/H1', '1.3%', 0.013, 0.0006)])
E('A.31b.P3.cond', '31B P3 (raw slip text + nudge)', Q('A_gate', ['arms', 'P3k1', 'P_malformed_given_edit'], 'rate4'), 'A',
  [(PLAN + ' §1.1', '48.5%', 0.485, 0.0006)])
E('A.31b.P4.cond', '31B P4 (oracle quarantine: canonical old-first re-render + success)', Q('A_gate', ['arms', 'P4k1', 'P_malformed_given_edit'], 'rate4'), 'A',
  [(PLAN + ' §1.1', '3.4%', 0.034, 0.0006)])
E('A.31b.P4.removed.cond', '31B share of the P1 excess removed by P4 (conditional)', Q('A_gate', ['quarantine_removal', 'P4k1', 'cond'], 'removal'), 'A',
  [(PLAN + ' §1.1', '105.7%', 1.057, 0.0006), (PROG + ' 12:20', '105.7% [99.2,113.6]', 1.057, 0.0006), (OUT + ' C5', 'Quarantine removes >=50% of contagion', ('>=', 0.5), None)],
  'P4 is an ORACLE (intended call + success response) and flips order old-first in 148/263; the shipped quarantine (P8a) is untested.')
E('A.31b.P5.removed.cond', '31B share of the P1 excess removed by P5 (removal + note)', Q('A_gate', ['quarantine_removal', 'P5k1', 'cond'], 'removal'), 'A',
  [(PROG + ' 12:20', '105.7% [97.4,115.3]', 1.057, 0.0006)])
E('A.31b.P4.removed.uncond', 'share removed by P4 (unconditional) [PRIMARY]', Q('A_gate', ['quarantine_removal', 'P4k1', 'uncond'], 'removal'), 'A')
E('A.31b.P5.Pedit', 'P(edit) under P5 (post-treatment selection)', Q('A_gate', ['arms', 'P5k1', 'P_edit'], 'rate4'), 'A',
  [(PLAN + ' §1.2', 'P(edit) 88% -> 69% under P5', 0.69, 0.006)])
E('A.31b.P0.Pedit', 'P(edit) under P0', Q('A_gate', ['arms', 'P0k0', 'P_edit'], 'rate4'), 'A', [(PLAN + ' §1.2', '88%', 0.88, 0.006)])
E('A.31b.P4.oldfirst', 'P4 flips the next edit to old-first (count old_first)', Q('A_gate', ['arms', 'P4k1', 'edit_order', 'old_first'], 'scalar'), 'A',
  [(PLAN + ' §1.2', '148/263', 148, 0)])
E('A.31b.fidelity.logged', 'replay fidelity: logged next call malformed on the same 300 contexts', Q('A_gate', ['replay_fidelity_P0', 'logged_next_call_malformed'], 'rate4'), 'A',
  [(PROG + ' 12:20', '4.7% [2.8,7.7]', 0.047, 0.0006)])
E('A.31b.copy_share', 'share of P1 malformed edits that are verbatim copies of the laundered value', Q('A_copy_gate', ['gemma-4-31b:P1k1', 'share_of_malformed_that_are_verbatim_copies'], 'rate4'), 'A',
  [(PLAN + ' §1.2/H1', '85.4% [78.1,90.5] (105 of ~123)', 0.854, 0.0006)])
E('A.31b.noncopy_other', 'P1: malformed rate among other (non-copy, new-content) edits', Q('A_copy_gate', ['gemma-4-31b:P1k1', 'other_edit', 'malformed'], 'rate4'), 'A',
  [(PLAN + ' §0', 'non-copy edits under P1 at n=300: 20.6%', 0.206, 0.0006)])
E('A.31b.P6.interim', 'P6 (corrupted exemplar + success response) P(malformed|edit), gate interim', Q('A_union', ['injection', '31b_old', 'gate_k1_random_sample', 'arms', 'P6k1', 'P_malformed_given_edit'], 'rate4'), 'A',
  [(PLAN + ' §0', '28.6% [19.3,40.1] (n=70)', 0.286, 0.0006)], 'Superseded by the full-n P6 (next entries).', main=False, canonical=False)
E('A.31b.P6.current', 'P6 all edits (current, copy_check.json)', Q('A_copy', ['gemma-4-31b:P6k1', 'all_edits', 'malformed'], 'rate4'), 'A',
  [(PLAN + ' §0', '28.6% [19.3,40.1]', 0.286, 0.0006)])
E('A.31b.P6.rd_uncond_gate', 'P6-P0 RD unconditional on the 300 gate contexts', Q('A_rules', ['format_induction', 'gate', 'uncond'], fn=lambda v, d: {'value': v['RD'], 'ci': v['RD_CI'], 'n': v['n_contexts']}), 'A',
  note='Pre-registered rule needs RD>=+5pp with CI_lo>0 on BOTH gate and held-out; held-out pending -> "copy-on-retry" until then.')
E('A.31b.P6.decision', 'format-induction decision (pre-registered rule)', Q('A_rules', ['format_induction', 'decision'], 'raw'), 'A',
  [(PLAN + ' §4 H1', 'induction onto new content (P6 [target: confirmed on held-out])', None, None)])
E('A.31b.P7.quote_share', 'P7 (injected `"` closer): share of malformed edits carrying `"`', Q('A_rules', ['copying', 'P7_quote_closer_share_of_malformed'], 'rate4'), 'A',
  [(PLAN + ' §0', 'the injected `"` closer appears in 7/13 slips', 7 / 13, 0.005), (PLAN + ' §1.2', 'P7 own-backtick slips 6/13', 6 / 13, 0.005)])
E('A.NT.rd_uncond', 'July template (NT) P1-P0 RD unconditional (interim)', Q('A_rules', ['july_template', 'uncond'], fn=lambda v, d: {'value': v['RD'], 'ci': v['RD_CI'], 'n': v['n_contexts'], 'ratio': v.get('ratio'), 'ratio_ci': v.get('ratio_CI')}), 'A',
  [(PLAN + ' §4 H1', 'effect persists under Google\'s July template', None, None)], 'Ratio CI is infinite -> report RD only (§6).')
E('A.12b.ratio.cond', '12B (off-policy 31B histories) ratio P1/P0 conditional', Q('A_12b', ['gate', 'G1_ratio_P1k1_over_P0'], 'ratio'), 'A',
  [(PLAN + ' §1.1/H1', '12B x5.7', 5.7, 0.05), (PROG + ' 12:20', '5.7x [2.5,28]', 5.7, 0.05),
   (OUT + ' thesis', 'even for models that never authored the corruption', None, None)],
  'PLAN §5 cuts "never authored"; write "history-borne" (12B/E4B replay 31B-authored histories, off-policy).')
E('A.12b.rd.uncond', '12B RD unconditional [PRIMARY]', Q('A_12b', ['paired_vs_P0', 'P1k1', 'uncond'], 'rd'), 'A')
E('A.e4b.ratio.cond', 'E4B ratio P1/P0 conditional', Q('A_e4b', ['gate', 'G1_ratio_P1k1_over_P0'], 'ratio'), 'A',
  [(PLAN + ' §1.2', 'E4B x1.9, not significant (n=96)', 1.9, 0.05)],
  'Now CI excludes 1 but fails the >=3x gate; E4B claim must be re-worded (neither "n.s." nor "x1.9").')
E('A.e4b.rd.uncond', 'E4B RD unconditional [PRIMARY]', Q('A_e4b', ['paired_vs_P0', 'P1k1', 'uncond'], 'rd'), 'A')
E('A.obs.affected', 'share of base attempts with >=1 malformed edit (observational)', Q('A_obs', ['BASE', 'synthesis_criterion', 'attempts_with_ge1_bad'], 'ci3'), 'Asyn',
  [(PLAN + ' §1.2 DW3', '22.9% of attempts are affected', 0.229, 0.0006)], 'Uses the synthesis replica and A\'s index (drops run-41); D gives 22.05% of trajectories.', canonical=False)

E('A.obs.resolve_clean', 'resolve rate, base attempts without malformed edits (observational)', Q('A_obs', ['BASE', 'synthesis_criterion', 'resolve_clean_attempts'], 'rate4'), 'Asyn',
  [(PLAN + ' §1.2 DW3', 'resolve at 50.8% (clean)', 0.508, 0.0006)], canonical=False)
E('A.obs.resolve_bad', 'resolve rate, base attempts with >=1 malformed edit (observational)', Q('A_obs', ['BASE', 'synthesis_criterion', 'resolve_attempts_with_bad'], 'rate4'), 'Asyn',
  [(PLAN + ' §1.2 DW3', 'resolve at 45.4% (affected)', 0.454, 0.0006)], canonical=False)
E('A.obs.ceiling', 'population ceiling of a perfect fix on resolve = affected share x resolve gap', Q('A_obs', ['BASE', 'synthesis_criterion'], fn=lambda v, d: {'value': v['attempts_with_ge1_bad'][0] * (v['resolve_clean_attempts'][0] - v['resolve_attempts_with_bad'][0])}), 'Asyn',
  [(PLAN + ' §1.2 DW3', 'population effect <= 1.2 pp', ('<=', 0.0125), None), (PLAN + ' §4 H2', 'the <= 1 pp leaderboard ceiling is stated in the abstract', ('<=', 0.0100), None),
   (OUT + ' calibration', 'leaderboard value ~ <=1 pp', ('<=', 0.0100), None)],
  'Associational upper bound (affected attempts are harder); A\'s index drops one run (9,077 edits).', canonical=False)

# ---- observational contagion (replay of identical logged contexts; July template) ----
E('D.replay.31b.K0', 'identical-context replay, 31B think, clean history (K=0)', Q('D_replay', ['models', 'order_31b_think', 'natural_arm', 'K=0', 'rate_ci'], 'ci3'), 'F',
  [(OUT + ' C2', '8.9% clean', 0.089, 0.0006), (R3, '10.6%', 0.106, 0.0006)], 'OUTLINE C2 numbers came from teacher-contaminated contexts (protocol/history_split.py).')
E('D.replay.31b.K1', 'identical-context replay, 31B think, >=1 malformed in history', Q('D_replay', ['models', 'order_31b_think', 'natural_arm', 'K>=1', 'rate_ci'], 'ci3'), 'F',
  [(OUT + ' C2', '86.7% after 1 bad', 0.867, 0.0006), (R3, '64.8%', 0.648, 0.0006)])
E('D.replay.12b.K0', 'replay 12B clean', Q('D_replay', ['models', 'order_12b_think', 'natural_arm', 'K=0', 'rate_ci'], 'ci3'), 'F',
  [(OUT + ' C2', '12B/E4B 3% -> 18-25%', 0.03, 0.006)])
E('D.replay.12b.K1', 'replay 12B >=1 bad', Q('D_replay', ['models', 'order_12b_think', 'natural_arm', 'K>=1', 'rate_ci'], 'ci3'), 'F')
E('D.replay.e4b.K0', 'replay E4B clean', Q('D_replay', ['models', 'order_e4b_think', 'natural_arm', 'K=0', 'rate_ci'], 'ci3'), 'F')
E('D.replay.e4b.K1', 'replay E4B >=1 bad', Q('D_replay', ['models', 'order_e4b_think', 'natural_arm', 'K>=1', 'rate_ci'], 'ci3'), 'F')

# ---- C1 / field corpus (C) and observational denominators ----
E('C.corpus.base_edit_rate', 'base 31B-QAT edit malformation (teacher runs excluded)', Q('C_stats', ['rates', 'base'], fn=lambda v, d: {'value': v['malformed_edits'] / v['edit_calls'], 'ci': v['edit_malformed_rate_wilson95'][1:], 'n': v['edit_calls'], 'k': v['malformed_edits']}), 'C',
  [(OUT + ' C1', 'base 31B 24.3% malformed edits', 0.243, 0.0006), (PLAN + ' §1.1/§P0-R', '35.0%', 0.350, 0.0006), (PROG + ' 10:30/12:45', '34.9% (3,293/9,430)', 0.349, 0.0006)],
  'D (t3) gives 3,296/9,430 = 35.0% under a 13-key synthesis predicate; A-judge recompute expected ~3,297/9,430 (definitions audit).')
E('D.base_edit_rate', 'base edit malformation, D (t3_summary)', Q('D_t3', ['base'], fn=lambda v, d: {'value': v['malformed'] / v['n_calls'], 'n': v['n_calls'], 'k': v['malformed']}), 'D',
  [(PLAN + ' §1.1', '35.0%', 0.350, 0.0006)], canonical=False)
E('D.seqs.base_edit_rate', 'base edit malformation, D seqs check (seqs.json overwrite: 9,111 edits)', Q('D_seqs', ['base', 'malformed'], 'ci3'), 'D', canonical=False, main=False,
  note='Loses 319 edits of two runs that reuse bare task ids (seqs.update overwrite).')
E('C.corpus.records', 'slip-corpus records (parsed_malformed + raw_unparsed)', Q('C_stats', ['records'], 'scalar'), 'C', [(PLAN + ' §4 H3', '8.4k-record corpus', 8410, 100)])
E('C.corpus.contexts', 'slip-corpus prompt contexts', Q('C_stats', ['contexts'], 'scalar'), 'C', [(PLAN + ' §1.3', '8,341 contexts', 8341, 0)])
E('C.corpus.any_tool_rate', 'base malformed calls of any tool', Q('C_stats', ['rates', 'base'], fn=lambda v, d: {'value': v['malformed_calls'] / v['calls'], 'ci': v['any_call_malformed_rate_wilson95'][1:], 'n': v['calls'], 'k': v['malformed_calls']}), 'C',
  [(PLAN + ' §1.2 DW3', 'malformed calls are 5.7% of base tool calls', 0.057, 0.0006)], 'Coincides numerically with A\'s P0 5.7% -- unrelated quantities; never juxtapose.')
E('C.corpus.ft_edit_rate', 'fine-tune edit malformation', Q('C_stats', ['rates', 'team_finetune'], fn=lambda v, d: {'value': v['malformed_edits'] / v['edit_calls'], 'ci': v['edit_malformed_rate_wilson95'][1:], 'n': v['edit_calls'], 'k': v['malformed_edits']}), 'C')
E('C.corpus.backtick', 'backtick share of closers, base edit slips', Q('C_res', ['slip_corpus', 'edit_slip_closers'], fn=lambda v, d: _closer(v)), 'C',
  [(OUT + ' thesis', 'backtick ~80%', 0.80, 0.0006), (PLAN + ' §P0-R', 'backtick share 84-86%', 0.85, 0.011)],
  'Variants: 83% (B, maximal closer run), 86.5% (D, 4 canonical closers only), ~80% (synthesis, teacher incl.). Definition decides.')
E('C.corpus.laundered', 'base edit slips whose history re-render is well-formed but corrupted ("laundered")', Q('C_res', ['slip_corpus', 'history_rerender', 'base|edit_file'], fn=lambda v, d: {'value': v['laundered_wilson95'][0], 'ci': v['laundered_wilson95'][1:], 'n': v['n']}), 'C',
  [(PROG + ' 12:45', '53%', 0.53, 0.0006)])
E('C.hist.byte_identical', 'parsed-malformed calls re-entering the next prompt byte-identical (base + FT)', Q('C_res', ['slip_corpus', 'by_kind', 'parsed_malformed'], 'scalar'), 'C',
  [(PLAN + ' §1.1', 'All 7,274 laundered slips re-render byte-identically under both templates', 7274, 0)],
  'Different sense of "laundered" than C.corpus.laundered (53%): see DEFINITIONS.md.')
E('C.hist.adk_executed_all', 'ADK runner executes corrupted calls (all 7,274)', Q('C_hist', ['F6r_reverse_runner', 'outcome:tool_executed_wilson95'], 'ci3'), 'C',
  [(PROG + ' 12:45', '35.5% executed', 0.355, 0.0006)])
E('C.hist.adk_error_all', 'ADK returns "mandatory parameters" error (all 7,274)', Q('C_hist', ['F6r_reverse_runner', 'outcome:adk_error_response_wilson95'], 'ci3'), 'C',
  [(PROG + ' 12:45', '63.7%', 0.637, 0.0006)])
E('C.corpus.lost_old', 'base edit slips that lose old_string', Q('C_res', ['slip_corpus', 'base_edit_lost_arguments'], fn=lambda v, d: _lost(v)), 'C', [(PROG + ' 12:45', '96.4%', 0.964, 0.0006)])
E('CEN.calls', 'LLM calls scanned (census)', Q('CEN', ['totals', 'llm_calls'], 'scalar'), 'CEN', [(OUT + ' C1', 'census 329k calls', 329359, 1000)])
E('CEN.unparsed', 'raw tool-call text left in content (census, all models)', Q('CEN', ['totals', 'raw_toolcall_in_content'], 'scalar'), 'CEN', [(OUT + ' C1', '1,117 unparsed', 1117, 0)])
E('CEN.edit_rate_pooled', 'edit malformation pooled over ALL models (base+FT+BROKEN+teacher)', Q('CEN', ['totals'], fn=lambda v, d: {'value': v.get('bad:edit_file', 0) / v['calls:edit_file'], 'n': v['calls:edit_file'], 'k': v.get('bad:edit_file')}), 'CEN',
  [(PROG + ' 08:25', 'edit_file malformed 12.3% (4,373/35,463)', 0.123, 0.0006)], 'Pooled population; never cite as a Gemma base rate.', main=False, canonical=False)

# ---- D: observational structure (descriptive; not identified) ----
E('D.first_edit', 'base first-edit malformation (no edit visible in context)', Q('D_t3', ['base', 'desc', 'first_vs_later', 'first'], 'rate3n'), 'D',
  [(PROG + ' 09:20', 'first edit 10.8%', 0.108, 0.0006), (PLAN + ' §P0-B', 'replace 10.8% with 16.8-17.6%', 0.172, 0.0045)],
  'Variants: 17.1% (C/F, per-file first edit 471-472/2,756), 17.4% (D seqs), 17.6% (A, merged task ids); 10.8% included teacher runs.')
E('D.MR.b0', 'MR hazard excitation b0 (immediate retry)', Q('D_t3', ['base', 'MR', 'b0_run'], fn=lambda v, d: {'value': v['coef'], 'ci': v['boot_ci']}), 'D', [(PROG + ' 11:30', 'b0 4.26 [4.01,4.52]', 4.26, 0.006)])
E('D.MR.beta', 'MR run-length slope beta', Q('D_t3', ['base', 'MR', 'br_logrun'], fn=lambda v, d: {'value': v['coef'], 'ci': v['boot_ci']}), 'D', [(PROG + ' 11:30', 'beta 1.05 [0.89,1.21]', 1.05, 0.006)])
E('D.FECL.OR', 'within-trajectory conditional-logit OR (Markov-1)', Q('D_t3', ['base', 'FE_CL_markov1'], fn=lambda v, d: {'value': v['OR'], 'ci': v['OR_wald95'], 'n': v['n_informative']}), 'D',
  [(PLAN + ' §1.2', 'FE-CL OR 78.9', 78.9, 0.05)], 'Association, not identified (PLAN §5).')
E('D.compaction.out', 'natural experiment: next slip when malformed calls were compacted OUT', Q('D_t3', ['base', 'desc', 'compaction_natural_experiment(k_att>=1)', 'malformed_compacted_away'], 'rate3n'), 'D',
  [(PROG + ' 11:30', '9.6%', 0.096, 0.0006)], 'n=114; confounded by distance and retry (PLAN §1.2).')
E('D.compaction.in', 'same, malformed calls still visible', Q('D_t3', ['base', 'desc', 'compaction_natural_experiment(k_att>=1)', 'malformed_in_ctx'], 'rate3n'), 'D', [(PROG + ' 11:30', '79.2%', 0.792, 0.0006)])
E('D.cascade.beta', 'cascade power-hazard beta (bootstrap, t3_boot_extra)', Q('D_boot', ['base', 'cascade_beta_q025_med_q975'], fn=lambda v, d: {'value': v[1], 'ci': [v[0], v[2]]}), 'D',
  [(PLAN + ' §1.2', 'beta = 0.92 "near-critical"', 0.92, 0.006)], 'Retire "near-critical" (PLAN §5); t3_summary MR_RE_boot block is mis-assigned -- use t3_boot_extra.json.')
E('D.wasted_per_onset', 'wasted calls per onset E[min(L,30)]', Q('D_t3', ['base', 'KM', 'E[min(L,30)]'], 'pci'), 'D', [(PLAN + ' §1.2', '12.1 wasted calls per onset', 12.1, 0.05)])
E('D.S30', 'KM survival S(30)', Q('D_t3', ['base', 'KM', 'S(30)'], 'pci'), 'D', [(PLAN + ' §P0-D', 'S(30) ~ 0.30', 0.30, 0.006)])
E('D.dp.fit', 'episode DP waste (N=30), fitted', Q('D_t3', ['base', 'episode_dp', 'm2_N30_fit', 'E_wasted'], 'pci'), 'D', [(PROG + ' 11:30', 'waste 2.43', 2.43, 0.006)], 'Model-based; PLAN §5 keeps "-90% vs -67%" out until re-derived from P0-A2.')
E('D.dp.quar', 'episode DP waste with quarantine', Q('D_t3', ['base', 'episode_dp', 'm2_N30_quarantine_cmp', 'E_wasted'], 'pci'), 'D', [(PROG + ' 11:30', 'quarantine 0.23', 0.23, 0.0035)])
E('D.dp.onset03', 'episode DP waste with onset x0.3', Q('D_t3', ['base', 'episode_dp', 'm2_N30_onset_x0.3', 'E_wasted'], 'pci'), 'D', [(PROG + ' 11:30', 'onset x0.3 0.81', 0.81, 0.006)])
E('D.never_recover', 'cure model: share of onsets that never recover', Q('D_t3', ['base', 'cure', 'pi_absorbing'], 'pci'), 'D', [(PROG + ' 11:30', '38% never recover', 0.38, 0.006)], 'Retire "absorbing" (PLAN §5).')
E('D.T2.valid_calls', 'valid Gemma calls scanned for guarded-rule triggers (0 genuine triggers)', Q('D_t2', ['groups', 'gemma', 'valid_calls'], 'scalar'), 'D',
  [(PLAN + ' §1.1', '0 genuine triggers in 265,161 valid Gemma calls', 265161, 0)])
E('D.T1.vllm_accepts', 'vLLM 0.19.1 returns a dict for every single-closer slip (synthetic)', Q('D_t1', ['B_parity'], fn=lambda v, d: {'value': v['slipped_vllm_returned_dict'] / v['slipped'], 'n': v['slipped'], 'k': v['slipped_vllm_returned_dict'], 'intent_recovered': v['slipped_vllm_dict_equals_intent'], 'lost_key_share': v['slipped_vllm_lost_a_key'] / v['slipped']}), 'D',
  [(PLAN + ' §4 H2', 'every vLLM path accepts 100% of slips silently', 1.0, 0)])
E('D.T1.collisions', 'T1: base slips whose closer split is ambiguous (colliding pairs exist)', Q('D_t1', ['C_real_ambiguity'], fn=lambda v, d: {'value': v['n_ambiguous_split']['base'], 'n': v['n_detectable_slips']['base'], 'share': v['share_ambiguous']['base']}), 'D',
  [(OUT + ' C3', 'No text-only parser can recover intent; likelihood parse is MAP', None, None)],
  'Theorem-level claim (T1): colliding pairs exist (count shown); MAP holds under 2 stated assumptions. PLAN replaces the "impossibility" headline with per-domain Bayes risk.')
E('D.T4.holm', 'order effect on contaminated histories: Holm-adjusted p (31B think, 31B no-think, 12B, E4B)', Q('D_t4', None, fn=lambda v, d: _t4(v)), 'F',
  [(PLAN + ' §1.2', '"p < .05 in all 4 models" does not survive Holm (12B .049, E4B .039 fail)', None, None)])
E('D.T5.onset_pred', 'T5 margin model: predicted onset slip rate (blp states)', Q('D_t5', ['empirical', 'onset_clean_ctx', 'predicted_slip_rate_T0.7_topp0.95'], 'scalar'), 'na', [(PROG + ' 11:30', 'predicted 10.2%', 0.102, 0.0006)])
E('D.T5.onset_obs', 'T5: observed slip fraction (m<0)', Q('D_t5', ['empirical', 'onset_clean_ctx', 'observed_slip_frac(m<0)'], 'scalar'), 'na', [(PROG + ' 11:30', 'observed 8.0%', 0.080, 0.0006)])
E('D.traj_affected', 'base trajectories with >=1 malformed edit (D, observed)', Q('D_t3', ['base', 'observed', 'traj_affected'], 'scalar'), 'D', main=False, canonical=False)

# ---- H2: decoding (B) ----
E('B.gate.base_slip', 'B gate: first-edit closer slips (31B QAT, think on, all contexts)', Q('B_gate', ['all|tau=2.0', 'base_slip'], 'kn'), 'B',
  [(PROG + ' 11:30', '31/193 (16.1% [11.6,21.9])', 0.161, 0.0006)], 'Population includes teacher-sourced contexts and 89 forced edits (PLAN §1.2 DW3) -> re-run on Gemma-only natural contexts.')
E('B.gate.census_bad', 'B gate: census-malformed first edits', Q('B_gate', ['all|tau=2.0', 'base_census_bad'], 'kn'), 'B', [(PROG + ' 11:30', '33/193 (17.1%)', 0.171, 0.0006)])
E('B.gate.i_relred', 'rollback (i): relative reduction of closer slips', Q('B_gate', ['all|tau=2.0', 'paired', 'slip_i_nc'], 'relred'), 'B', [(PROG + ' 11:30', '100% [89.0,100]', 1.0, 0.0006), (OUT + ' C4', 'intent-preserving decoding cuts onset >=70%', ('>=', 0.70), None)])
E('B.gate.iplus_relred', '(i+) opener rule: relative reduction of census-malformed', Q('B_gate', ['all|tau=2.0', 'paired', 'census_iplus'], 'relred'), 'B', [(PROG + ' 11:30', '100% [89.6,100]', 1.0, 0.0006)])
E('B.gate.ii_relred', '(ii) post-hoc likelihood repair: relative reduction of census-malformed', Q('B_gate', ['all|tau=2.0', 'paired', 'census_ii'], 'relred'), 'B', [(PROG + ' 11:30', '87.9% [72.7,95.2]', 0.879, 0.0006)])
E('B.gate.ii_abstain', '(ii) abstentions', Q('B_gate', ['all|tau=2.0', 'ii_abstain'], 'kn'), 'B', [(PROG + ' 11:30', '4.1% abstain', 0.041, 0.0006)])
E('B.gate.false_repair_inloop', 'false repairs on in-loop valid calls', Q('B_gate', ['all|tau=2.0', 'false_repair_real'], fn=lambda v, d: {'value': v['i_changed_valid'], 'n': v['n_valid'], 'ci': v['wilson95_i']}), 'B',
  [(PROG + ' 11:30', '0/156', 0, 0), (OUT + ' C4', '<=1% false repairs, valid calls byte-identical', ('<=', 0), None)], 'Denominator drifted 156 -> current n (see value n).')
E('B.gate.natural.base_slip', 'B gate restricted to NATURAL edits: closer slips', Q('B_gate', ['natural|tau=2.0', 'base_slip'], 'kn'), 'B', note='The subset reviewers asked for (R3 Q12).')
E('B.gate.natural.i_relred', 'natural edits: rollback relative reduction', Q('B_gate', ['natural|tau=2.0', 'paired', 'slip_i_nc'], 'relred'), 'B')
E('B.qs.valid_calls', 'QuoteStorm valid calls never altered (i)/(ii)', Q('B_qs', ['all'], fn=lambda v, d: {'value': v['calls'], 'k_changed': (v.get('i_changed') or {}).get('k')}), 'B',
  [(PLAN + ' §1.1/H2', 'byte identity on 229,414 valid calls (0/229,414)', 229414, 0)])


# ---- B head-to-head on Gemma-only first-edit contexts (June template; INTERIM until >=600 contexts) ----
_H = ['head2head', 'v3_r31_on_june']
E('B.data_fix.first_edit', 'logged first-edit malformation, Gemma-only (teacher runs excluded)', Q('B_res', ['data_fix', 'logged_first_edit_malformed_gemma_only'], 'kn'), 'B',
  [(PLAN + ' §P0-B', 'replace 10.8% with 16.8-17.6% everywhere', 0.172, 0.0045)])
E('B.h2h.n_slips', 'head-to-head: natural slips in the sample (interim)', Q('B_res', _H + ['n_slips'], 'scalar'), 'B', note='n contexts in the json field n_contexts.')
E('B.h2h.lenient', 'delivered-malformed, arm 1 lenient (status quo)', Q('B_res', _H + ['all', '1_lenient', 'malformed'], 'kn'), 'B')
E('B.h2h.ipd', 'delivered-malformed, arm 5 IPD (i+)', Q('B_res', _H + ['all', '5_IPD', 'malformed'], 'kn'), 'B',
  [(PLAN + ' §P0-B', 'IPD delivered-malformed <= 1%', ('<=', 0.01), None)])
E('B.h2h.textonly', 'delivered-malformed, arm 3 text-only longest closer', Q('B_res', _H + ['all', '3_T1_text_only', 'malformed'], 'kn'), 'B',
  [(PLAN + ' §4 H2', 'It beats ... text-only repair', None, None)],
  'HONESTY CLAUSE: on the interim sample text-only ties IPD (both 0 delivered-malformed). If this holds at n>=600, PLAN requires saying IPD\'s value is rollback + the guarantee on quote-dense content.')
E('B.h2h.retry_loud', 'retry x2: calls still loud after two retries', Q('B_res', _H + ['all', '7_retry_x2', 'loud'], 'kn'), 'B',
  [(PLAN + ' §4 H2', 'It beats retry', None, None)])
E('B.h2h.grammar_silent_on_slips', 'grammar-constrained decoding: slips turned into silent corruption', Q('B_res', _H + ['slips', '10_grammar_CD', 'silent'], 'kn'), 'B',
  [(PLAN + ' §4 H2', 'Grammar-constrained decoding turns [>=90%] of slips into silent corruption', ('>=', 0.90), None)], 'n = slips in the interim sample (12).')
E('B.gold.n_slips', 'gold-intent natural slips collected (copy task)', Q('B_res', ['gold'], fn=lambda v, d: {'value': sum(x.get('n_slips', 0) for x in v.values()), 'n_contexts': sum(x.get('n_contexts', 0) for x in v.values())}), 'B',
  [(PLAN + ' §4 H2', 'IPD recovers exact intent on [>=95%] of [>=500] gold natural slips', ('>=', 500), None), (PLAN + ' §1.2 DW3', 'Real-slip intent: n = 2', 2, 0)])

# ---- H1 quantization (F) ----
E('F.dp.qat', 'decision point: expected slip probability QAT-ct (population-weighted)', Q('F_margins', ['decision_point_population', 'expected_slip_prob_qat'], 'ci3'), 'na', [(PROG + ' 10:40', 'QAT-ct 10.1% [8.7,11.8]', 0.101, 0.0006)])
E('F.dp.bf16', 'decision point: expected slip probability bf16', Q('F_margins', ['decision_point_population', 'expected_slip_prob_bf16'], 'ci3'), 'na', [(PROG + ' 10:40', 'bf16 2.7% [1.9,3.9]', 0.027, 0.0006)])
E('F.dp.ratio', 'decision point ratio QAT/bf16', Q('F_margins', ['decision_point_population', 'ratio_qat_over_bf16'], 'ci3'), 'na',
  [(PROG + ' 10:40', '3.7x [2.5,5.4]', 3.7, 0.006), (PLAN + ' §4 H1', 'population-weighted 3.7x', 3.7, 0.006), (PLAN + ' §4 H1', 'about 4x more likely than bf16', 4.0, 0.35)])
E('F.R.model_free', 'selection-corrected R = E[s_bf16]/E[s_QAT] at logged T (model-free)', Q('F_t5', ['importance_weighting_ratio', 'slip_onset'], fn=lambda v, d: {'value': v['R=E_pop[s_B]/E_pop[s_Q] (logged T, top_p .95)'], 'ci': v['R_ci95'], 'n': v['n_states']}), 'na',
  [(PLAN + ' §1.1/H1', 'R = 0.235 [0.19,0.29]', 0.235, 0.0006)])
E('F.beh.clean.qat', 'behavioural replay, clean history: QAT', Q('F_replay', ['order_replay_natural', 'clean_history', 'qat'], 'kn'), 'F', [(PROG + ' 12:20', 'QAT 10.5% [8.1,13.6]', 0.105, 0.0006)])
E('F.beh.clean.bf16', 'behavioural replay, clean history: bf16', Q('F_replay', ['order_replay_natural', 'clean_history', 'bf16'], 'kn'), 'F', [(PROG + ' 12:20', 'bf16 2.5% [1.4,4.3]', 0.025, 0.0006)])
E('F.beh.clean.ratio', 'behavioural clean-history ratio bf16/QAT', Q('F_replay', ['order_replay_natural', 'clean_history', 'ratio_bf16_over_qat'], 'ci3'), 'F',
  [(PLAN + ' §1.1', 'bf16/QAT = 0.235 [0.12,0.37] over 485 pairs', 0.235, 0.0006)])
E('F.beh.post.ratio', 'behavioural post-slip (>=1 malformed in history) ratio bf16/QAT', Q('F_replay', ['order_replay_natural', 'history_ge1_malformed', 'ratio_bf16_over_qat'], 'ci3'), 'F',
  [(PLAN + ' §1.1/P0-F', '0.78 [0.64,0.93]', 0.78, 0.006), (PLAN + ' §4 H1', 'QAT moves the post-slip hazard only x1.28', 1 / 1.28, 0.006)])
E('F.beh.contagion.qat', 'contagion ratio within QAT (post/clean)', Q('F_replay', ['order_replay_natural', 'contagion_ratio_qat'], 'ci3'), 'F', [(PROG + ' 12:20', 'QAT 6.2x [4.5,8.5]', 6.2, 0.05)])
E('F.beh.contagion.bf16', 'contagion ratio within bf16 (post/clean)', Q('F_replay', ['order_replay_natural', 'contagion_ratio_bf16'], 'ci3'), 'F',
  [(PROG + ' 12:20', 'bf16 20.5x [12.1,43.3]', 20.5, 0.05), (PLAN + ' §4 H1', 'The effect persists ... in bf16 weights', ('>', 1.0), None)],
  'Observational (identical-context replay, M-F judge). The causal bf16 P0/P1 arm (contagion_bf16.jsonl) is still running.')
E('F.margin.medians', 'end-of-new_string margin <|"|> vs best look-alike, median nats (QAT vs bf16)', Q('F_t5', ['F_paired_application', 'close:new_string'], fn=lambda v, d: {'value': v['mQ_median'], 'bf16': v['mB_median'], 'n': v['n_pairs']}), 'na',
  [(PROG + ' 10:40', 'median 6.3 vs 12.0 nats', 6.3, 0.06), (OUT + ' C8', 'Quantization narrows margins at structural tokens (QAT median < bf16 median 12.0)', ('<', 12.0), None)])

# ---- H3: conformance (C) ----
E('C.spec.tpl_calls', 'serializer byte-identical to JULY template: calls rendered (0 failures)', Q('C_res', ['reference', 'template_equivalence', 'july', 'T1_call_rendering'], fn=lambda v, d: {'value': v['n'], 'fail': v['fail']}), 'na',
  [(PLAN + ' §4 H3', 'spec byte-identical to both official templates', 3000, 0)])
E('C.spec.tpl_calls_june', 'serializer vs JUNE template: calls (0 failures)', Q('C_res', ['reference', 'template_equivalence', 'june', 'T1_call_rendering'], fn=lambda v, d: {'value': v['n'], 'fail': v['fail']}), 'na')
E('C.spec.property_checks', 'property checks P1-P7 (0 failures)', Q('C_res', ['reference', 'properties'], fn=lambda v, d: {'value': sum(x['n'] for x in v.values()), 'fail': sum(x['fail'] for x in v.values())}), 'na',
  [(PROG + ' 12:45', '76,635 property checks, 0 failures', 76635, 0)])
E('C.diff.results', 'differential results (inputs x parser paths)', Q('C_res', ['differential', 'n_results'], 'scalar'), 'na', [(R3, '193,040 results', 193040, 0)])
E('C.diff.cases', 'differential inputs', Q('C_res', ['differential', 'n_cases'], 'scalar'), 'na', [(PROG + ' 12:45', '12,065 inputs', 12065, 0)])
E('C.diff.v031_invalid_silent', 'vLLM 0.31 server on ill-formed inputs with known intent: silently wrong (FUZZ rate)', Q('C_res', ['differential', 'headline', 'vllm031.server', 'invalid_intent', 'silent_wrong'], 'kn'), 'na',
  [(PROG + ' 12:45', 'silent-wrong 77.1%', 0.771, 0.0006)], 'Fuzz-distribution rate: PLAN §5 forbids it as a headline; report per-class presence + real-input rates.', main=False)
E('C.laundering.returned', 'parser laundering: vLLM 0.31 returns calls for real raw outputs 0.19.1 left visible', Q('C_res', ['differential', 'raw_unparsed_with_tools', 'vllm030.server', 'returned_calls'], 'kn'), 'na',
  [(PLAN + ' §1.1/H3', '620/676 = 91.7%', 0.917, 0.0006)], 'vllm030.server == vllm031.server on all inputs (C README).')
E('C.laundering.schema_valid', 'parser laundering: share of those calls that are schema-valid', Q('C_res', ['differential', 'raw_unparsed_with_tools', 'vllm030.server', 'returned_calls_schema_valid'], 'kn'), 'na',
  [(PLAN + ' §1.1/H3', '20.0% [17.0,23.3]', 0.20, 0.0006)])
E('C.repros.n', 'minimal repros', Q('C_res', ['differential', 'repro_verdicts'], 'count'), 'na',
  [(PLAN + ' §1.1', 'now 38 repros', 38, 0), (R3, '28 minimal repros', 28, 0)])
E('C.hist.adk_executed_base', 'ADK executes base parsed-malformed calls (any tool)', Q('C_hist', ['F6r_reverse_runner'], fn=lambda v, d: _adk_base(v)), 'C',
  [(PLAN + ' §4 H2', 'ADK executes 19% of base slips; errors on 81%', 0.19, 0.006)], 'Denominator is base parsed-malformed calls of ANY tool; say so in the text.')


# ---- coverage of remaining OUTLINE / §4 claims ----
E('EXT.community_issues', 'community issues/PRs on Gemma-4 tool-protocol problems', Q('C_res', ['workstream'], fn=lambda v, d: {'value': None}), 'na',
  [(OUT + ' C1', 'community 40+ issues', None, None)], 'EXTERNAL: ideation/community/SYNTHESIS.md (curated list, not a measured number); cite the list, not a count.', main=False)
E('D.cascade.nonident', 'cascade law: log-likelihoods geometric / power hazard / cure / nonparametric (base)', Q('D_t3', ['cascade_model_comparison', 'base', 'loglik'], fn=lambda v, d: {'value': v.get('power_hazard(c,beta)'), 'geometric': v.get('geometric(beta=0)'), 'cure': v.get('cure(pi,q)'), 'nonparam': v.get('nonparam(q_1..q_9, q_10+)')}), 'D',
  [(PLAN + ' §4 H1', 'Logs alone cannot identify the cascade law (power hazard = beta-geometric)', None, None)],
  'The beta-geometric fit (R2: nll 800.24 vs 800.45) is not in any results file yet -> D must add it (P0-D b).')
E('F.decomp.stage', 'QAT onset increase localized to a stage (training / grid / export)', Q('F_margins', ['decomposition', 'stage_share']), 'na',
  [(PLAN + ' §4 H1', 'localized to [stage]', None, None)], 'P0-F decomposition (4 arms on 639 states) pending.')
E('D.T1.parity', 'single-closer slips with odd <|"|> parity rejected by the strict parser (synthetic)', Q('D_t1', ['B_parity'], fn=lambda v, d: {'value': v['slipped_strict_rejected'] / v['slipped'], 'n': v['slipped'], 'odd_parity': v['slipped_odd_parity']}), 'D',
  [(PLAN + ' §4 H2', 'Every single-closer slip is parity-detectable', 1.0, 0)])
E('C.real_slips.absorbed', 'real slips (1,610 reassembled): vLLM 0.31 server returns a wrong call', Q('C_res', ['differential', 'fuzz_classes', 'ABSORB_REAL', 'vllm031.server'], 'kn'), 'na',
  [(PLAN + ' §4 H2', 'every vLLM path accepts 100% of slips silently', 1.0, 0)])
E('C.repro.dos_pinned', 'DoS in the competition-pinned vLLM 0.19.1 (HANG_NESTED_BRACKET verdict, server path)', Q('C_res', ['differential', 'repro_verdicts', 'HANG_NESTED_BRACKET', 'vllm019.server'], 'raw'), 'na',
  [(PLAN + ' §4 H3', 'a DoS in the competition-pinned vLLM', None, None)], 'Security: class-level wording only until disclosed (DISCLOSURE_CHECKLIST S4/S6).')
E('C.repro.injection', 'call injection in vLLM 0.31 (CALL_INJECTION_IN_STRING verdict, server path)', Q('C_res', ['differential', 'repro_verdicts', 'CALL_INJECTION_IN_STRING', 'vllm031.server'], 'raw'), 'na',
  [(PLAN + ' §4 H3', 'a disclosed call-injection class', None, None)], 'Not yet disclosed (S1): the word "disclosed" is premature until the USER files the report.')


# =====================================================================================================================
# OUTLINE v2 (resource-first, 2026-11-04 15:00 UTC) -- these claims form the --strict gate
# =====================================================================================================================
_G = ['injection', '31b_old', 'gate_k1_random_sample']
_P = ['prereg_analysis_PREREG_v1']
_XRS = ['real_inputs', 'real_slips']


def _xr_silent(v, d):
    tg = [k for k in v if k.startswith(('vllm', 'sgl', 'llama'))]
    vis = max(v[k]['visible']['rate'] for k in tg)
    lo = min(1 - v[k]['visible']['hi'] for k in tg)
    return {'value': 1 - vis, 'ci': [lo, 1.0], 'n': max(v[k]['n'] for k in tg), 'n_paths': len(tg)}


def _xr_surface(v, d):
    tg = ['hf513.template', 'hf517.template', 'ref', 'bdecoder.strict']
    return {'value': min(v[k]['visible']['rate'] for k in tg if k in v), 'n': v['ref']['n']}


def _xr_valid(v, d):
    srv = {k: x['exact']['rate'] for k, x in v.items() if isinstance(x, dict) and 'exact' in x and not k.endswith('.utils')}
    utl = {k: x['exact']['rate'] for k, x in v.items() if isinstance(x, dict) and 'exact' in x and k.endswith('.utils')}
    return {'value': min(srv.values()), 'n': v['vllm019.tool']['n_calls'], 'min_exact_utils': min(utl.values()) if utl else None,
            'lowest_paths': sorted(srv, key=srv.get)[:3]}


E('V2.real_slips_silent', 'real slips: every vLLM / SGLang / llama.cpp path returns a wrong or empty call (min over paths)', Q('C_xr', _XRS, fn=_xr_silent), 'na',
  [(V2 + ' §2/§3 R2', '100% of 1,610 real slips, 100% [99.8, 100]', 1.0, 0.0005)])
E('V2.real_slips_surface', 'real slips: HF / strict decoder / reference surface them (min over those paths)', Q('C_xr', _XRS, fn=_xr_surface), 'na',
  [(V2 + ' §3 R2', 'HF and ours surface 100%', 1.0, 0)])
E('V2.parser_paths', 'parser paths in the conformance matrix (real valid-call columns)', Q('C_xr', ['real_inputs', 'valid_calls'], 'count'), 'na',
  [(V2 + ' §2/§3 R2', '38 parser paths', 38, 0)])
E('V2.valid_exact', 'real valid calls: lowest exact rate over server/stream/detector paths (utils separately)', Q('C_xr', ['real_inputs', 'valid_calls'], fn=_xr_valid), 'na',
  [(V2 + ' §3 R2', 'every server path is exact except vLLM 0.30-0.33 streaming, at 99.77%', 0.9977, 0.00005)],
  'Not all exact: vLLM 0.30-0.33 coerce quoted numbers (policy) and the OFFLINE gemma4_utils helpers are exact on only 29% (0.19.1) / 75% (0.30-0.33). Say "every server path exact except ...".')
def _defect_classes(v, d):
    nonpol = {'safety', 'silent loss', 'type drift'}
    third = ('vllm', 'sgl', 'llama', 'hf')
    latest = ('vllm033.', 'sgl523.', 'llamab12103.', 'hf517.')
    k, k_latest, safety = 0, 0, []
    for cls, cells in v.items():
        hit = [t for t, c in cells.items() if t.startswith(third) and c['label'] == 'defect' and set(c['buckets']) & nonpol]
        if hit:
            k += 1
            k_latest += any(t.startswith(latest) for t in hit)
            if any('safety' in cells[t]['buckets'] for t in hit):
                safety.append(cls.split(' ')[0])
    return {'value': k, 'n_classes_in_matrix': len(v), 'still_in_latest_release': k_latest, 'safety_classes': safety}


E('V2.defect_classes', 'K = parser defect classes: >=1 third-party runtime path (vLLM/SGLang/llama.cpp/HF) shows a NON-POLICY defect (safety, silent loss or type drift) on the class\'s minimal repro inputs (class_matrix = Table D)', Q('C_xr', ['class_matrix'], fn=_defect_classes), 'na',
  [(V2 + ' §2', 'found 16 parser defect classes (all 16 still in the latest tested release; 4 safety classes)', 16, 0)],
  'Policy-only cells excluded (schema coercion of quoted numbers, numeric re-spelling, lenient exact repairs, rejecting L1-only whitespace, llama.cpp single-call default). Template-level hazards are not parser classes and are counted separately.')
E('V2.v019_truncated', 'vLLM 0.19.1 server path: real raw outputs whose call text is silently truncated (reasoning parser)', Q('C_xr', ['real_inputs', 'raw_unparsed_with_tools', 'vllm019.server', 'silently_truncated'], 'kn'), 'na',
  [(V2 + ' §3 R2', '0.19.1 reasoning parser loses the call text in 22.2% of raw outputs', 0.222, 0.0006)])
E('V2.recall', 'known-issue recall (adjudicated), overall', Q('C_res', ['known_issue_recall', 'summary', 'adjudicated', 'recall'], 'kn'), 'na',
  [(V2 + ' §3 R2', 'Known-issue recall 60.4% [46.3, 73.0]', 0.604, 0.0006)])
E('V2.recall_exec', 'known-issue recall on executed paths and versions', Q('C_res', ['known_issue_recall', 'summary', 'adjudicated', 'recall_on_executed_paths_and_versions'], 'kn'), 'na',
  [(V2 + ' §3 R2', '90.6% on executed paths', 0.906, 0.0006)])
E('V2.tpl_responses', 'serializer vs July template: tool responses (0 failures)', Q('C_res', ['reference', 'template_equivalence', 'july', 'T2_tool_response_rendering'], fn=lambda v, d: {'value': v['n'], 'fail': v['fail']}), 'na',
  [(V2 + ' §3 R1', '1,500 tool responses', 1500, 0)])
E('V2.tpl_decls', 'serializer vs July template: declarations (0 failures)', Q('C_res', ['reference', 'template_equivalence', 'july', 'T3_declaration_rendering'], fn=lambda v, d: {'value': v['n'], 'fail': v['fail']}), 'na',
  [(V2 + ' §3 R1', '1,538 declarations', 1538, 0)])
E('V2.discovery_released', 'discovery split as released (snippets + pointers; teammate contexts excluded)', Q('R_snip', None, fn=lambda v, d: {'value': v['released_records'] + v['pointer_only'], 'snippets': v['released_records'], 'pointers': v['pointer_only'], 'excluded': v['excluded_teammate_records']}), 'na',
  [(V2 + ' §3 R3', 'Discovery split as released: 8,160 main-track slips (8,113 snippets + 47 pointer-only)', 8160, 0)],
  'User decision 14:25 UTC: 250 slips written under a teammate\'s private prompt are excluded; 47 unlicensed-repo slips ship as pointers. Write "8,160 slips (8,113 snippets + 47 pointers)".')
E('V2.discovery_snippets', 'discovery-split snippets with text (permissive licences only)', Q('R_snip', ['released_records'], 'scalar'), 'na',
  [(V2 + ' §3 R3', '8,107 snippets plus 53 pointer-only rows', 8107, 0)],
  'Licence rule applied everywhere (PI 15:20 UTC): the 6 tqdm (MPL-2.0 AND MIT) rows are now pointers -> 8,107 snippets + 53 pointers.')
E('V2.discovery_commit_n', 'discovery-split full contexts committed by sha256 (release after Dec 2, pending consent)', Q('R_snip', ['n_contexts_committed'], 'scalar'), 'na',
  [(V2 + ' §3 R3', 'Commitment root sha256 175e2451... over 8,091 full contexts', 8091, 0)])
E('V2.discovery_commit_root', 'discovery-split context commitment root (sha256)', Q('R_snip', ['root_sha256'], 'str'), 'na',
  [(V2 + ' §3 R3', 'Commitment root sha256 136d61f7... (placeholder path renamed 18:40 UTC; was 175e2451...)', '136d61f7', None)])
E('V2.replay_records', 'discovery replays released label-only: generation records', Q('R_rep', ['records'], 'scalar'), 'na',
  [(V2 + ' §3 R5', 'The discovery replays ship label-only: 22,463 records in 25 frozen batches', 22463, 0)])
E('V2.replay_contexts', 'discovery replays: distinct base contexts with label rows', Q('R_rep', ['n_contexts_all'], 'scalar'), 'na',
  [(V2 + ' §3 R5', 'on 1,204 contexts', 1204, 0)])
E('V2.replay_root', 'discovery replay context commitment root (sha256)', Q('R_rep', ['root_sha256'], 'str'), 'na',
  [(V2 + ' §3 R5', 'commitment root d379b4ea...', 'd379b4ea', None)])
E('V2.replay_overlap', 'replay contexts also in the slip-corpus commitment: hashes identical (independent reconstruction)', Q('R_rep', None, fn=lambda v, d: {'value': v['overlap_identical'], 'n': v['overlap']}), 'na', main=False)
E('V2.discovery_pointers', 'discovery-split pointer-only rows (47 unlicensed + 6 MPL-2.0)', Q('R_snip', ['pointer_only'], 'scalar'), 'na', [(V2 + ' §3 R3', '53 pointer-only rows (47 from unlicensed repositories, 6 MPL-2.0)', 53, 0)])
E('V2.replay_contexts_committed', 'discovery replays: base contexts committed by sha256 (teammate-prompt contexts never committed)', Q('R_rep', ['n_contexts'], 'scalar'), 'na', main=False,
  claims=[(V2 + ' §3 R5', 'on 1,204 contexts (1,072 committed)', 1072, 0)])
E('V2.replay_batches', 'discovery replays: frozen generation batches', Q('R_rep', ['n_batches'], 'scalar'), 'na', main=False,
  claims=[(V2 + ' §3 R5', '22,463 records in 25 frozen batches', 25, 0)])
E('V2.replay_teammate_ctx', 'discovery replays: contexts written under the teammate\'s private prompt (labels only; not committed)', Q('R_rep', ['teammate_contexts_not_committed'], 'scalar'), 'na', main=False,
  note='User rule: teammate-prompt contexts excluded entirely. They are not committed and not in the v1.1 candidate; whether their LABEL rows ship is a pending decision (build flag --drop-teammate-labels).')
E('V2.replay_teammate_rows', 'discovery replays: label rows generated on teammate-prompt contexts', Q('R_rep', ['label_rows_on_teammate_contexts'], 'scalar'), 'na', main=False)
for _old, _new in [('V2.maintrack_released', 'V2.discovery_released'), ('V2.maintrack_snippets', 'V2.discovery_snippets'),
                   ('V2.maintrack_pointers', 'V2.discovery_pointers'), ('V2.maintrack_commit_n', 'V2.discovery_commit_n'),
                   ('V2.maintrack_commit_root', 'V2.discovery_commit_root')]:
    _e = next(x for x in R if x['id'] == _new)
    E(_old, f'ALIAS of {_new} (split renamed maintrack -> discovery, 2026-11-04 18:30 UTC; kept so existing citations resolve)', _e['q'], _e['defn'], main=False)
E('R.qs.shipped', 'QuoteStorm payloads shipped with content (known permissive licence)', Q('R_qs', ['shipped_content'], 'scalar'), 'na', main=False)
E('R.qs.pointers', 'QuoteStorm payloads shipped as pointers (unlicensed/unknown, custom, copyleft, AGPL)', Q('R_qs', ['pointer_only'], 'scalar'), 'na', main=False)
E('V2.gold_retry', 'gold-intent subset: base-model corpus slips with retry-derived intent (B selection rule)', Q('B_res', ['gold_retry_subset', 'n_base_selected'], 'scalar'), 'B',
  [(V2 + ' §3 R3', 'Gold-intent subset of 229 retry-derived slips', 229, 0)], '279 corpus records with retry intent minus 50 fine-tune records. Evaluation status in gold_retry_subset.status.')
E('V2.gold_ipd_exact', 'gold retry subset (FINAL, 229/229 evaluated): IPD exact intent', Q('B_res', ['gold_retry_subset', 'per_decoder', 'i_nc', 'exact_intent'], 'kn'), 'B',
  [],
  'B FINAL export 2026-11-04 (results.json sha256 f9299782...): 227/229. The OUTLINE v2 §3 R3 parenthesis "(B: JSON field pending)" is stale -- the field exists and is FINAL. The >=500 G1/G1R target is a different (natural-closure) set.')
E('V2.gold_status', 'gold retry subset: evaluation status in the source', Q('B_res', ['gold_retry_subset', 'status'], 'str'), 'B', main=False)
E('V2.gold_n_evaluated', 'gold retry subset: records evaluated', Q('B_res', ['gold_retry_subset', 'n_evaluated'], 'scalar'), 'B', main=False)
E('V2.gold_cut_partial', 'gold retry subset: gold cut is a partial (composite) look-alike run', Q('B_res', ['gold_retry_subset', 'gold_cut_partial_composite_run'], 'scalar'), 'B', main=False)
for _dec, _lab in [('i_nc', 'IPD'), ('i_max', '(i)-max'), ('T1_assumed_tail', 'T1 (scored on the ASSUMED tail)'), ('ii_assumed_tail', '(ii) (scored on the ASSUMED tail)'),
                   ('retry_x2', 'retry x2'), ('greedy', 'greedy'), ('forbid_strict', 'forbid-strict'), ('grammar', 'grammar-constrained decoding')]:
    for _m, _ml in [('exact_intent', 'exact intent'), ('new_exact', 'new_string exact'), ('old_exact', 'old_string exact'), ('strict_valid', 'strict-valid call'), ('silent_corruption', 'silent corruption')]:
        E(f'B.gold_retry.{_dec}.{_m}', f'gold retry subset: {_lab} {_ml}', Q('B_res', ['gold_retry_subset', 'per_decoder', _dec, _m], 'kn'), 'B', main=False)
for _t in ('T=0.2', 'T=0.7'):
    E(f'B.gold_retry.i_nc.exact_intent.{_t}', f'gold retry subset: IPD exact intent at {_t}', Q('B_res', ['gold_retry_subset', 'by_temperature', _t, 'i_nc'], 'kn'), 'B', main=False)
E('V2.e_parity', 'proxy base config reproduces vLLM 0.19.1 prompt tokens (31B contexts)', Q('E_res', ['rendering_parity', '31b', 'prompt_tokens_identical'], 'kn'), 'E',
  [(V2 + ' §3 R4', 'Base reproduces vLLM 0.19.1 (31B prompts 40/40 identical)', 1.0, 0)])
E('V2.b_gate_slip', 'B gate FINAL (June template, 595 first-edit calls, natural+forced): closer slips', Q('B_res', ['gate_31b_think_on_final', 'baseline_closer_slips'], 'kn'), 'B',
  [(V2 + ' §3 R4/§4 E1', 'slips 17.5% (replayed 17.5%)', 0.175, 0.0006)], '406 natural + 189 forced edits pooled; report natural-only too (§6).')
E('V2.b_gate_i', 'B gate FINAL: rollback (i) relative reduction of closer slips', Q('B_res', ['gate_31b_think_on_final', 'relred_slips_i_paired'], 'relred'), 'B',
  [(V2 + ' §3 R4', '17.5% -> 0, which is 100% [96.4, 100]', 1.0, 0.0006), (V2 + ' §2', 'removes 100% of closer slips', 1.0, 0)])
E('V2.b_gate_census', 'B gate FINAL: census-malformed before', Q('B_res', ['gate_31b_think_on_final', 'baseline_census_malformed'], 'kn'), 'B',
  [(V2 + ' §3 R4', 'census-malformed 18.7%', 0.187, 0.0006)])
E('V2.b_gate_iplus', 'B gate FINAL: census-malformed after IPD (i+)', Q('B_res', ['gate_31b_think_on_final', 'after_IPD_census_malformed'], 'kn'), 'B',
  [(V2 + ' §3 R4', '-> 1.2% (93.7%)', 0.012, 0.0006)])
E('V2.b_gate_fr', 'B gate FINAL: valid calls altered by IPD', Q('B_res', ['gate_31b_think_on_final', 'false_repairs_valid_calls_altered'], fn=lambda v, d: {'value': v['IPD'], 'n': v['n_valid'], 'ci': v['wilson95_i']}), 'B',
  [(V2 + ' §3 R4', '0/480 in-loop', 0, 0), (V2 + ' §2', 'with zero false repairs', 0, 0)])
E('V2.b_cost_tok', 'B gate v3: amortized extra tokens per edit call', Q('B_gate3', ['all|tau=2.0', 'cost_i', 'amortized_extra_tokens_per_edit_call'], 'scalar'), 'B',
  [(V2 + ' §3 R4', '+15.9 tokens', 15.9, 0.06)])
E('V2.b_cost_req', 'B gate v3: amortized extra requests per edit call', Q('B_gate3', ['all|tau=2.0', 'cost_i', 'amortized_extra_requests_per_edit_call'], 'scalar'), 'B',
  [(V2 + ' §3 R4', '+0.18 requests per edit', 0.18, 0.006)])
E('V2.h2h_n_slips', 'head-to-head on real 31B slips (B results.json head2head_31b_think_on_slips, FINAL export)', Q('B_res', ['head2head_31b_think_on_slips', 'n_slips'], 'scalar'), 'B',
  [(V2 + ' §6', 'Head-to-head on 104 real slips', 104, 0), (V2 + ' §2', 'beats retry and greedy decoding; grammar-CD 97% silent', 104, 0)],
  'Regenerated by B at ~15:10 UTC (results.json sha256 f652984a...).')
E('V2.retry_fallback', 'retry x2 with lenient fallback: delivered-malformed over ALL 595 calls', Q('B_res', ['retry_lenient_all_calls', 'retry_x2_lenient_delivered_malformed'], 'kn'), 'B',
  [(V2 + ' §6', 'Retry with a lenient fallback delivers 13.9% malformed', 0.139, 0.0006)], 'Denominator = all 595 edit calls (on the 104 slips it delivers 79 malformed).')
_H2 = ['head2head_31b_think_on_slips', 'decoders']
for _dec, _tag, _vals in [('IPD (i+)', 'IPD', (102, 2, 0, 0)), ('T1 text-only longest-closer', 'T1 text-only', (101, 3, 0, 0)),
                          ('retry x2 (T=0.2), loud fallback', 'retry x2', (25, 79, 0, 0)), ('greedy (T=0)', 'greedy', (16, 0, 87, 1)),
                          ('forbid-trigger (one-step ban after <look-alike>,)', 'forbid-trigger', (0, 0, 103, 1)),
                          ('grammar-constrained decoding (exact emulation)', 'grammar-CD', (3, 0, 103, 101))]:
    for _col, _v in zip(('clean', 'loud', 'delivered_malformed', 'silent_corruption'), _vals):
        E(f'V2.h2h.{_tag}.{_col}', f'head-to-head on 104 slips: {_tag} -> {_col} (count)', Q('B_res', _H2 + [_dec, _col, 'k'], 'scalar'), 'B',
          [(V2 + ' §6', f'table row {_tag}: {_col} = {_v}', _v, 0)])
E('V2.h2h.grammar.silent_rate', 'grammar-CD: share of the 104 slips turned into silent corruption', Q('B_res', _H2 + ['grammar-constrained decoding (exact emulation)', 'silent_corruption'], 'kn'), 'B',
  [(V2 + ' §2/§6', 'grammar-constrained decoding turns 97% (97.1%) of slips into silent corruption', 0.971, 0.0006)])
E('V2.p8a', 'shipped quarantine P8a: share of the P1 excess removed (unconditional, 31B gate)', Q('A_res', _G + ['quarantine_removal', 'P8ak1', 'uncond'], 'removal'), 'A',
  [(V2 + ' §2/§3 R4', 'removes all of the history-borne excess (113%) / 113% [107, 122]', 1.13, 0.006)])
E('V2.p8b', 'shipped quarantine P8b (sanitized): share removed (unconditional)', Q('A_res', _G + ['quarantine_removal', 'P8bk1', 'uncond'], 'removal'), 'A',
  [(V2 + ' §3 R4', 'sanitized version 112%', 1.12, 0.006)])
E('V2.p9_remaining', 'informative error (P9): share of the P1 excess REMAINING (1 - removed, unconditional)', Q('A_res', _G + ['quarantine_removal', 'P9k1', 'uncond'], fn=lambda v, d: {'value': 1 - v['fraction_removed'], 'ci': [1 - v['CI'][1], 1 - v['CI'][0]], 'n': v['n_contexts']}), 'A',
  [(V2 + ' §2/§4 E3', 'better error messages leave 87%', 0.87, 0.006)])
E('V2.p6k1', 'P6k (corrupted calls + SUCCESS responses) k=1, conditional', Q('A_res', _P + ['P6k', 'cond', 'P(P6,k=1)'], fn=lambda v, d: {'value': v['est'], 'ci': v['CI']}), 'A',
  [(V2 + ' §4 E3', '11.7% at k=1 (conditional)', 0.117, 0.0006)])
E('V2.p6k2', 'P6k k=2, conditional', Q('A_res', _P + ['P6k', 'cond', 'P(P6,k=2)'], fn=lambda v, d: {'value': v['est'], 'ci': v['CI']}), 'A',
  [(V2 + ' §4 E3', '45.1% at k=2', 0.451, 0.0006)])
E('V2.p6k4', 'P6k k=4, conditional', Q('A_res', _P + ['P6k', 'cond', 'P(P6,k=4)'], fn=lambda v, d: {'value': v['est'], 'ci': v['CI']}), 'A',
  [(V2 + ' §4 E3', '84.1% at k=4', 0.841, 0.0006), (V2 + ' §9', 'conditional figures are 84.1% vs 2.6%', 0.841, 0.0006)],
  'Conditional estimand; the unconditional (primary) value is P(P6,k=4) uncond = 74.8% [69.4, 80.0] vs 2.3% (see V2.p6k4_uncond).')
E('V2.p6k4_uncond', 'P6k k=4, UNCONDITIONAL [primary estimand]', Q('A_res', _P + ['P6k', 'uncond', 'P(P6,k=4)'], fn=lambda v, d: {'value': v['est'], 'ci': v['CI']}), 'A',
  [(V2 + ' §2', 'After four such corrupted edits, 74.8% [69.4, 80.0] of next calls are malformed edits (unconditional)', 0.748, 0.0006)])
E('V2.p6k_p0_uncond', 'P6k reference P0 (clean history), UNCONDITIONAL', Q('A_res', _P + ['P6k', 'uncond', 'p0'], fn=lambda v, d: {'value': v['est'], 'ci': v['CI']}), 'A',
  [(V2 + ' §2', 'against 2.3% with a clean history', 0.023, 0.0006)])
E('V2.p6k_p0', 'P6k reference: P0 (clean history), conditional', Q('A_res', _P + ['P6k', 'cond', 'p0'], fn=lambda v, d: {'value': v['est'], 'ci': v['CI']}), 'A',
  [(V2 + ' §9', '(conditional) ... vs 2.6%', 0.026, 0.0006)])
E('V2.p6k_beta', 'P6k slope in log k (beta = Delta_4 / ln 4, conditional)', Q('A_res', _P + ['P6k', 'cond', 'Delta_4'], fn=lambda v, d: {'value': v['est'] / math.log(4), 'ci': [c / math.log(4) for c in v['CI']]}), 'A',
  [(V2 + ' §4 E3', 'logit-linear in log k (beta ~ 2.6)', 2.6, 0.1)])
E('V2.dose_D1', 'dose tier P1: first-exemplar logit step D1 (conditional)', Q('A_res', _P + ['dose_tier', 'P1', 'cond', 'free_curve_logit_linear_in_k', 'first_exemplar_step D1'], 'scalar'), 'A',
  [(V2 + ' §4 E3', 'The first exemplar is a +2.53-logit step', 2.53, 0.006)])
E('V2.dose_slope', 'dose tier P1: logit increment per additional distinct exemplar (Delta4/3, conditional)', Q('A_res', _P + ['dose_tier', 'P1', 'cond', 'free_curve_logit_linear_in_k', 'slope_per_extra_exemplar (Delta4/3)'], fn=lambda v, d: {'value': v['est'], 'ci': v['CI']}), 'A',
  [(V2 + ' §4 E3', '+0.55 [0.43, 0.68] per distinct exemplar', 0.55, 0.006)])
E('V2.rdose', 'r-dose: same exemplar shown r=4 times, logit change vs r=1 (conditional)', Q('A_res', _P + ['r_dose', 'cond', 'Delta_r4'], fn=lambda v, d: {'value': v[0], 'ci': v[1]}), 'A',
  [(V2 + ' §4 E3', 'Repeating the same exemplar adds ~0 (r-dose null)', None, None)])
E('V2.lag2', 'lag-2: share of the P1 excess kept when the exemplar is one edit back (unconditional)', Q('A_res', _P + ['lag2', 'uncond', 'lag2_excess_share'], fn=lambda v, d: {'value': v[0], 'ci': v[1]}), 'A',
  [(V2 + ' §4 E3', 'keeps 0.46 [0.29, 0.64] of the effect', 0.46, 0.006)])
E('V2.12b_p0', '12B P0 (unconditional)', Q('A_12b', ['paired_vs_P0', 'P1k1', 'uncond', 'base'], 'scalar'), 'A', [(V2 + ' §5', '12B: P0 1.5%', 0.015, 0.0006)])
E('V2.12b_p1', '12B P1 (unconditional)', Q('A_12b', ['paired_vs_P0', 'P1k1', 'uncond', 'arm'], 'scalar'), 'A', [(V2 + ' §5', '-> P1 6.5%', 0.065, 0.0006)])
E('V2.12b_p6', '12B P6 (unconditional)', Q('A_res', ['injection', '12b_old', 'gate_k1_random_sample', 'paired_vs_P0', 'P6k1', 'uncond', 'arm'], 'scalar'), 'A', [(V2 + ' §5', '12B P6 8.8%', 0.088, 0.0006)])
E('V2.12b_p8a', '12B shipped quarantine P8a removal (unconditional)', Q('A_res', ['injection', '12b_old', 'gate_k1_random_sample', 'quarantine_removal', 'P8ak1', 'uncond'], 'removal'), 'A', [(V2 + ' §5', '12B quarantine removes 117%', 1.17, 0.006)])
E('V2.e4b_p0', 'E4B P0 (unconditional)', Q('A_e4b', ['paired_vs_P0', 'P1k1', 'uncond', 'base'], 'scalar'), 'A', [(V2 + ' §5', 'E4B: P0 2.5%', 0.025, 0.0006)])
E('V2.e4b_p1', 'E4B P1 (unconditional)', Q('A_e4b', ['paired_vs_P0', 'P1k1', 'uncond', 'arm'], 'scalar'), 'A', [(V2 + ' §5', '-> P1 5.7%', 0.057, 0.0006)])
E('V2.e4b_p6', 'E4B P6 (unconditional)', Q('A_res', ['injection', 'e4b_old', 'gate_k1_random_sample', 'paired_vs_P0', 'P6k1', 'uncond', 'arm'], 'scalar'), 'A', [(V2 + ' §5', 'E4B P6 11.0%', 0.110, 0.0006)])
E('V2.e4b_ratio', 'E4B ratio P1/P0 (conditional), current n', Q('A_e4b', ['gate', 'G1_ratio_P1k1_over_P0'], 'ratio'), 'A',
  [(V2 + ' §5/§9', 'E4B x2.45 [1.46, 4.69] at n = 600; the >=3x gate fails', 2.45, 0.005)], 'n grew from 404 to 600 contexts.')
E('V2.e4b_rd', 'E4B RD P1-P0 (unconditional)', Q('A_e4b', ['paired_vs_P0', 'P1k1', 'uncond'], 'rd'), 'A',
  [(V2 + ' §5', 'E4B RD +3.2 pp [1.1, 5.3]', 0.032, 0.0006)])
E('V2.valid_utils_min', 'real valid calls: exact rate of the OFFLINE gemma4_utils helpers (vLLM 0.19.1 / 0.30-0.33)', Q('C_xr', ['real_inputs', 'valid_calls'], fn=lambda v, d: {'value': v['vllm019.utils']['exact']['rate'], 'v030_033': v['vllm031.utils']['exact']['rate'], 'n': v['vllm019.utils']['n_calls']}), 'na',
  [(V2 + ' §3 R2', "vLLM's offline gemma4_utils is exact on only 29% (0.19.1)", 0.29, 0.0006)])
E('V2.valid_utils_new', 'real valid calls: exact rate of vLLM 0.30-0.33 offline gemma4_utils', Q('C_xr', ['real_inputs', 'valid_calls', 'vllm031.utils', 'exact'], 'kn'), 'na',
  [(V2 + ' §3 R2', '... and 75.5% (0.30-0.33)', 0.755, 0.0006)])
E('V2.12b_ratio', '12B ratio P1/P0 (conditional)', Q('A_12b', ['gate', 'G1_ratio_P1k1_over_P0'], 'ratio'), 'A',
  [(V2 + ' §9', '12B x5.7 (true value x4.91 conditional)', 4.91, 0.05)])
E('V2.x_fixedpoint', 'Gemma notation: real slips that are a fixed point of parse o render (laundered share, vLLM 0.19.1 lenient)', Q('X_fmt', ['variants', 'G', 'gemma4.nonstream', 'silent_laundered_share'], 'rate4'), 'na',
  [(V2 + ' §4 E2', 'a fixed point of parse o render 88.5% of the time (X, CPU)', 0.885, 0.0006)])
E('V2.x_hermes_loud', 'hermes JSON (Qwen) native slips: non-streaming loud', Q('X_fmt', ['variants', 'J_real', 'hermes.nonstream', 'loud'], 'rate4'), 'na',
  [(V2 + ' §5', 'hermes JSON fails loudly (non-streaming)', ('>=', 0.99), None)])
E('V2.x_hermes_stream', 'hermes JSON streaming: broken arguments forwarded', Q('X_fmt', ['variants', 'J_real', 'hermes.stream', 'delivered_invalid'], 'rate4'), 'na',
  [(V2 + ' §5', 'streaming forwards broken arguments 100%', 1.0, 0.001)])
E('V2.x_xml_flaggable', 'qwen3_coder XML: silent slips flagged by a judge (share)', Q('X_fmt', ['variants', 'X_real', 'qwen3_coder.nonstream', 'silent_flagged_by_judge_share'], 'rate4'), 'na',
  [(V2 + ' §5', 'qwen3_coder XML re-synchronizes but launders silently (0% flaggable)', 0.0, 0.0005)])
E('V2.f_bf16', 'decision-point expected slip probability: bf16', Q('F_decomp', ['expected_slip_prob', 'per_arm', '1_bf16'], 'ci3'), 'na', [(V2 + ' §5', '2.7% (bf16)', 0.027, 0.0006)])
E('V2.f_ptq', 'decision-point expected slip probability: bf16 + fake Q4_0 (PTQ)', Q('F_decomp', ['expected_slip_prob', 'per_arm', '5_bf16_fakeQ4_0'], 'ci3'), 'na', [(V2 + ' §5', '11.6% PTQ', 0.116, 0.0006)])
E('V2.f_qatct', 'decision-point expected slip probability: QAT-ct (shipped)', Q('F_decomp', ['expected_slip_prob', 'per_arm', '4_qat_ct'], 'ci3'), 'na', [(V2 + ' §5', '10.1% QAT-ct', 0.101, 0.0006)])
E('V2.f_grid', 'share of the "unquantized" QAT checkpoint weights already on their Q4_0 grid', Q('F_wshift', ['frac_qat_unq_on_own_q40_grid'], 'scalar'), 'na', [(V2 + ' §5', '61% of its weights on the grid', 0.61, 0.006)])
E('V2.ceiling', 'leaderboard ceiling (affected share x resolve gap)', Q('A_obs', ['BASE', 'synthesis_criterion'], fn=lambda v, d: {'value': v['attempts_with_ge1_bad'][0] * (v['resolve_clean_attempts'][0] - v['resolve_attempts_with_bad'][0])}), 'Asyn',
  [(V2 + ' §6', 'about 1 pp (ceiling 1.24 pp)', 0.0124, 0.0003)])
E('V2.notebook_checks', 'CPU notebook: Level-2 checks that run on RELEASED files only', Q('R_nb', ['n_checks_released_files'], 'scalar'), 'na',
  [(V2 + ' §3 R5', 'Re-derives 17 headline checks from released records only', 17, 0)])
E('V2.notebook_exact', 'CPU notebook: released-file checks that are EXACT (identical counts, or identical at the producer\'s stored precision)', Q('R_nb', ['n_exact_released_files'], 'scalar'), 'na',
  [(V2 + ' §3 R5', '17 headline checks ... all exact', 17, 0)], 'Definition of "exact" in l2_checks.json/exact_definition: integer counts equal; k/n rates with the same n and k; derived ratios/removals equal at the producer\'s stored decimals (>= 3).')
E('V2.notebook_fullcorpus', 'CPU notebook: extra checks that need the full corpus (data holder only)', Q('R_nb', None, fn=lambda v, d: {'value': v['n_checks'] - v['n_checks_released_files'], 'ok': v['n_ok'] - v['n_ok_released_files']}), 'na',
  [(V2 + ' §3 R5', '(plus 4 full-corpus checks on the data holder\'s copy)', 4, 0)])
E('V2.notebook', 'CPU notebook: re-derivations from RELEASED files that match numbers.json (Level 2)', Q('R_nb', ['n_ok_released_files'], 'scalar'), 'na',
  [(V2 + ' §3 R5', 'Re-derives 17 headline checks from released records only (all pass)', 17, 0)],
  'Level 1 regenerates every number from the results JSONs. Level 2 now runs on released files only: A\'s gate (8), shipped quarantine + P9 (3), P6k dose (3), split sizes (3) = 17; plus 4 full-corpus checks that need the data holder\'s copy (21 locally).')
E('V2.disclosed', 'security classes reported upstream (filing log)', Q('R_priv', ['disclosure', 'filed']), 'na',
  [(V2 + ' §2', 'including a model-triggerable hang and call injection, all reported privately to the maintainers', None, None)],
  'Nothing is filed yet (USER files Nov 5). OUTLINE v2 §9 itself retires "disclosed" until filed -> write "reported privately to the maintainers" only after filing.')
E('V2.d_beta_geom', 'power hazard vs beta-geometric mixture: identity check (D, theory.md §R.1; max |q_A - q_B|)', Q('D_nonident', ['identity_check'],
  fn=lambda v, d: {'value': max(x['max_r<=2000 |qA - qB|'] for x in v)}), 'D',
  [(V2 + ' §4 E4', 'The power hazard is identical to a beta-geometric mixture (D §R.1)', ('<=', 1e-9), None)], 'D exported t3_nonident.json (identity check, 4 parameter values) and t3_summary.json cascade_model_comparison (delta log-lik 0.26 between the two fits).')
E('V2.e_prediction', 'D frozen prediction for E (31B delivered-malformed fullp/base; 80% PI)', Q('D_epred', ['population_31B', 'delivered_malformed_fullp_over_base'],
  fn=lambda v, d: {'value': v['point'], 'ci': v['pi80']}), 'D',
  [(V2 + ' §6', '0.12 [0.04, 0.25]', 0.12, 0.0005)], 'Transcribed verbatim by D from prereg/E_PREDICTIONS_v1.md (sha256 182365c9...) into sim/out/e_predictions_v1.json.')

# ---- targets in UPGRADE_PLAN §4 that have no result yet (status PENDING until the file exists) ----
E('A.P8a.removed', 'shipped quarantine (P8a) removes >=70% of the P1 excess [target]', Q('A_rules', ['shipped_quarantine', 'P8a']), 'A',
  [(PLAN + ' §4 H1', 'The shipped quarantine removes >=70% [target ~100%] of the excess', None, None)], 'P8a needs E\'s frozen quarantine renderer; P4 is an oracle.')
E('A.heldout.P6', 'held-out confirmation (contexts 300-599) of P6 induction', Q('A_rules', ['format_induction', 'heldout', 'uncond']), 'A',
  [(PLAN + ' §4 H1', 'induction onto new content [target: confirmed on held-out]', None, None)])
E('X.qwen.rd', 'cross-family replication: RD(P1-L - P0) in >=1 Qwen model [target]', Q('X_res', ['P1L_minus_P0']), 'na',
  [(PLAN + ' §4 H1', 'It replicates in [>=1 Qwen model]', None, None)])
E('X.json.loud', 'escaped-JSON native slips fail loudly (hermes) [target]', Q('X_res', ['format', 'hermes', 'loud_share']), 'na',
  [(PLAN + ' §4 H1', 'Escaped-JSON native slips fail loudly instead of laundering', None, None)])
E('E.pop.delivered_malformed', 'end-to-end: full\' cuts delivered-malformed calls per episode [target >=70%]', Q('E_res', ['population', 'delivered_malformed_reduction']), 'E',
  [(PLAN + ' §4 H2', 'quarantine + IPD cuts delivered-malformed calls by [>=70%]', None, None), (OUT + ' C6', 'End-to-end: fewer wasted calls/time', None, None)])
E('E.branch.resolve', 'branch-at-onset resolve change [target]', Q('E_res', ['branches', 'resolve_delta']), 'E',
  [(PLAN + ' §4 H2', 'At onset branches it changes resolve by [delta +- CI] pp', None, None)])
E('C.runtimes.new', 'new runtime columns (SGLang, llama.cpp, Ollama) [target]', Q('C_res', ['differential', 'headline', 'sglang.detector']), 'na',
  [(PLAN + ' §4 H3', 'A differential suite over vLLM x3, HF x2, SGLang, llama.cpp and Ollama', None, None)])
E('C.classes.K', 'distinct parser bug classes in the runtime x class matrix (Table 1)', Q('C_res', ['differential', 'runtime_by_class', 'vLLM 0.19.1 server', 'classes'], 'count'), 'na',
  [(PLAN + ' §4 H3', 'finds [K] defect classes', None, None), (OUT + ' C7', 'Runtimes disagree; K bug classes found', None, None)],
  'C README: 15 parser bug classes x 12 runtime paths (+19 history-conversion classes). Count from the README until a machine-readable field exists.')
E('R.disclosure.filed', 'upstream issues filed / acknowledged [target]', Q('R_priv', ['disclosure', 'filed']), 'na',
  [(PLAN + ' §4 H3', '[N] issues filed or acknowledged upstream', None, None)], 'Tracked in release/disclosure/DISCLOSURE_CHECKLIST.md (USER files).')

# ---- privacy (R) -- filled after the redaction run ----
_CTXF = ['corpus_files', 'experiments/conformance/slips/release/gemma4_slip_contexts.jsonl.xz']
E('R.pii.ctx_host_paths', 'contexts with host paths before redaction (after: 0)', Q('R_priv', _CTXF + ['group_lines_before', 'host_paths'], 'scalar'), 'na',
  [(PLAN + ' §1.3', 'host paths in 1,596/8,341 contexts', 1596, 0)], 'release/reports/privacy/PII_SCAN_REPORT.md', main=False)
E('R.pii.ctx_username', "contexts with the author's username in any form (after path rewriting) before redaction", Q('R_priv', _CTXF + ['group_lines_before', 'author_identity'], 'scalar'), 'na',
  [(PLAN + ' §1.3', 'the username in 96', 96, 2)], 'R3 counted the full username form (96); +2 contexts carry truncated/upper-case forms.', main=False)
E('R.pii.ctx_emails', 'contexts with non-reserved e-mail addresses before redaction', Q('R_priv', _CTXF + ['group_lines_before', 'emails'], 'scalar'), 'na', main=False)
E('R.pii.ctx_gitlog', 'contexts with a git log/blame/show command', Q('R_priv', _CTXF + ['group_lines_before', 'git_log_or_blame_output_commands'], 'scalar'), 'na',
  [(PLAN + ' §1.3', '707 git log dumps', 707, 10)], main=False)
E('R.pii.residual_after', 'residual identity/host hits in the staged corpus after redaction', Q('R_priv', _CTXF + ['residual_after'], fn=lambda v, d: {'value': sum(v.values())}), 'na',
  [(PLAN + ' §P0-R success', 'the release scan finds 0 PII hits', 0, 0)], main=False)
E('R.pii.gate', 'privacy gate over all release candidates', Q('R_priv', ['gate_overall'], 'raw'), 'na', main=False)
E('R.pii.ctx_emails_distinct', 'distinct non-reserved e-mail addresses pseudonymised in the contexts', Q('R_priv', ['corpus_files'], fn=lambda v, d: {'value': None}), 'na', main=False,
  note='see PII_SCAN_REPORT.md section 1 (90 distinct in contexts, 2 in records)')
E('R.prov.repos', 'repositories behind the corpus records', Q('R_prov', ['repos_total'], 'scalar'), 'na',
  [(R3, 'about 466 repositories', 466, 0)], '4 competition + 33 FreshSWE-Py + 430 SWE-rebench.', main=False)
E('R.prov.attempts', 'distinct (run, attempt) pairs among corpus records', Q('R_prov', ['attempts_distinct_run_attempt'], 'scalar'), 'na',
  [(R3, '2,505 distinct attempts in the released file', 2505, 0)], '2,505 = distinct attempt-id strings; 8 bare ids collide across runs run-03/run-05.', main=False)
E('R.prov.fresh_records', 'records from FreshSWE-Py (third-party Kaggle dataset, not team-collected)', Q('R_prov', ['by_source_dataset', 'freshswe_py'], 'scalar'), 'na',
  [(R3, 'run-39 alone contributes 2,016 (team-collected tasks)', 2016, 0)], 'All fresh_* tasks are FreshSWE-Py; run-39 is its fresh_train split (2,016 of 3,530).', main=False)
E('R.prov.pointer_only', 'records from repositories without a licence (pointer-only)', Q('R_prov', ['records_by_redistribution', 'no_license (pointer-only)'], 'scalar'), 'na', main=False)



# ---- PAPER DRAFT citations (paper/protocol/draft/PAPER_v0*.md, 2026-11-04 evening): quantities the draft cites from
# ---- workstream results files. Each entry lists the exact `file#path` strings the draft uses (cites=...).
def _rdd(v, d):
    """paired risk difference block {RD|diff, RD_CI|diff_CI, n_contexts|n, arm, base}"""
    out = {'value': v.get('RD', v.get('diff')), 'ci': v.get('RD_CI', v.get('diff_CI')), 'n': v.get('n_contexts', v.get('n'))}
    if 'arm' in v:
        out.update(arm=v['arm'], base=v['base'])
    return out


def _hh(v, d):
    """h block {n|n_states, h: [h, [lo, hi]], q(L), ...}"""
    return {'value': v['h'][0], 'ci': list(v['h'][1]), 'n': v.get('n', v.get('n_states')), 'q_L': v.get('q(L)')}


def _knc(v, d):
    """{k, n, rate, wilson95, state_cluster_boot95}"""
    return {'value': v['rate'], 'ci': v.get('wilson95') or v.get('ci95'), 'n': v['n'], 'k': v['k'], 'ci_cluster': v.get('state_cluster_boot95')}


def _count_k(v, d):
    return {'value': v['k'], 'n': v['n'], 'rate': v.get('rate')}


B_GOLD = 'experiments/intent_decoding/results.json#gold/combined_natural_slips'
for _dec, _lab in [('IPD', 'IPD'), ('T1_text_only', 'T1 text-only longest closer'), ('ii_tau2', '(ii) likelihood repair tau=2'),
                   ('grammar_CD', 'grammar-constrained decoding'), ('i_max', '(i)-max'), ('retry_x2', 'retry x2'), ('greedy', 'greedy'),
                   ('forbid_strict', 'forbid-trigger strict')]:
    E(f'B.gold.nat.{_dec}', f'gold intent, G1 + G1R natural slips (519): {_lab} exact intent (Wilson; state-cluster CI in ci_cluster)',
      Q('B_res', ['gold', 'combined_natural_slips', 'exact_intent', _dec], fn=_knc), 'B', cites=[f'{B_GOLD}/exact_intent/{_dec}'])
E('B.gold.nat.n_G1R', 'gold intent: G1R natural slips (re-sampled at the first 105 states)', Q('B_res', ['gold', 'combined_natural_slips', 'n_G1R_slips'], 'scalar'), 'B',
  cites=[f'{B_GOLD}/n_G1R_slips'])
E('B.gold.nat.n_total', 'gold intent: natural slips in all (G1 + G1R)', Q('B_res', ['gold', 'combined_natural_slips', 'n_total'], 'scalar'), 'B',
  cites=[f'{B_GOLD}/n_total'])
E('B.gold.g1r.false_repairs', 'gold intent: clean G1R closures changed by IPD (T1 in t1)', Q('B_res', ['gold', 'g1r_natural_closures', 'false_repairs_on_clean'],
  fn=lambda v, d: {'value': v['IPD_changed']['k'], 'n': v['IPD_changed']['n'], 't1': v['T1_changed']['k']}), 'B',
  cites=['experiments/intent_decoding/results.json#gold/g1r_natural_closures/false_repairs_on_clean'])
for _o in ('clean', 'loud', 'delivered_malformed', 'silent_corruption'):
    E(f'B.h2h.lenient.{_o}', f'head-to-head (104 slips): lenient status quo, {_o} (count)', Q('B_res', ['head2head_31b_think_on_slips', 'decoders', 'lenient (status quo)', _o], fn=_count_k), 'B',
      main=False, cites=['experiments/intent_decoding/results.json#head2head_31b_think_on_slips/decoders/lenient (status quo)'] if _o == 'delivered_malformed' else ())
for _arm in ('P5', 'P8a'):
    E(f'X.qwen3-8b.PF.rd_{_arm}', f'Qwen3-8B any protocol failure (malformed or dropped edit): RD {_arm} - P0 (exploratory)',
      Q('X_res', ['models', 'qwen3-8b', 'exploratory_protocol_failure', 'primary', 'paired_vs_P0', _arm, 'PF_edit'], fn=_rdd), 'na', main=False,
      cites=['experiments/crossfamily/README.md#TL;DR-4'] if _arm == 'P5' else ())
for _m in ('qwen3-8b', 'qwen3-32b'):
    for _arm in ('P0', 'P5', 'P8a'):
        E(f'X.{_m}.PF.{_arm}', f'{_m} any protocol failure (malformed or dropped edit), arm {_arm} (exploratory)',
          Q('X_res', ['models', _m, 'exploratory_protocol_failure', 'primary', 'arms', _arm, 'PF_edit'], 'rate4'), 'na', main=False,
          cites=[f'experiments/crossfamily/results.json#models/{_m}/exploratory_protocol_failure/primary/arms/{_arm}/PF_edit'])
for _m in ('qwen3-8b', 'qwen3-32b', 'qwen3.5-9b'):
    E(f'X.{_m}.rd_P1L', f'{_m}: RD(P1L - P0), unconditional, gate contexts (registered F2)', Q('X_res', ['registered_decisions', 'models', _m, 'P1L_vs_P0'],
      fn=lambda v, d, _m=_m: dict(_rdd(v, d), n=d['registered_decisions']['models'][_m]['n_contexts'])), 'na',
      cites=[f'experiments/crossfamily/results.json#registered_decisions/models/{_m}/P1L_vs_P0'])
    E(f'X.{_m}.rd_P6', f'{_m}: RD(P6 - P0), unconditional, gate contexts', Q('X_res', ['registered_decisions', 'models', _m, 'secondary', 'P6'], fn=_rdd), 'na',
      main=False, cites=['experiments/crossfamily/results.json#registered_decisions/models/qwen3-8b/secondary/P6'] if _m == 'qwen3-8b' else ())
    E(f'X.{_m}.heldout.rd_P6', f'{_m}: RD(P6 - P0), unconditional, held-out contexts', Q('X_res', ['models', _m, 'heldout', 'paired_vs_P0', 'P6', 'uncond'], fn=_rdd), 'na', main=False)
    E(f'X.{_m}.C0', f'{_m}: natural first-edit protocol failure (census, arm C0)', Q('X_res', ['registered_decisions', 'models', _m, 'arms', 'C0'], 'rate4'), 'na', main=False)
E('X.n_contexts', 'Qwen battery: contexts per model (= the Gemma gate contexts)', Q('X_res', ['registered_decisions', 'models'],
  fn=lambda v, d: {'value': max(m['n_contexts'] for m in v.values()), 'all_equal': len({m['n_contexts'] for m in v.values()}) == 1}), 'na',
  cites=['experiments/crossfamily/results.json#registered_decisions/models/*/n_contexts'])
E('X.C0.max', 'Qwen natural first-edit protocol failure: maximum over the three models (C0)', Q('X_res', ['registered_decisions', 'models'],
  fn=lambda v, d: {'value': max(m['arms']['C0'][0] for m in v.values()), 'min': min(m['arms']['C0'][0] for m in v.values())}), 'na',
  cites=['experiments/crossfamily/results.json#registered_decisions/models/*/arms/C0'])
E('X.F2.holm_max', 'Qwen registered F2 tests: largest Holm-adjusted p (6 tests)', Q('X_res', ['registered_decisions', 'F2_holm'],
  fn=lambda v, d: {'value': max(v['adjusted'].values()), 'min': min(v['adjusted'].values()), 'n': v.get('n_tests')}), 'na',
  cites=['experiments/crossfamily/results.json#registered_decisions/F2_holm/adjusted'])


def _copy_sum(models, path):
    n = cc = 0
    for m in models.values():
        b = m
        for k in path:
            b = b[k]
        n += b['all_edits']['n']; cc += (b.get('copy_corrupted') or {}).get('n', 0)
    return {'value': cc, 'n': n}


E('X.copy.gate.P1L', 'Qwen P1L edits (gate, 3 models): verbatim copies of the injected corrupted call', Q('X_res', ['registered_decisions', 'models'],
  fn=lambda v, d: _copy_sum(v, ['secondary', 'copy_check', 'P1L'])), 'na',
  cites=['experiments/crossfamily/results.json#registered_decisions/models/*/secondary/copy_check/P1L/all_edits'])
E('X.copy.heldout.P1L', 'Qwen P1L edits (held-out, 3 models): verbatim copies of the injected corrupted call', Q('X_res', ['models'],
  fn=lambda v, d: _copy_sum(v, ['heldout', 'copy_check', 'P1L'])), 'na',
  cites=['experiments/crossfamily/results.json#models/*/heldout/copy_check/P1L/all_edits'])
E('X.fmt.gemma4.absorbed', 'gemma4 non-streaming parser: silent absorption of real slips (format study)', Q('X_fmt', ['variants', 'G', 'gemma4.nonstream', 'silent_absorbed'], 'rate4'), 'na',
  cites=['experiments/crossfamily/format/format_summary.json#variants/G'])
E('A.heldout.P8a_removal', 'held-out half (294): shipped quarantine P8a removal of the P1 excess, unconditional', Q('A_res', ['decision_rules_upgrade_plan', 'heldout_replication', 'P8a_removal_of_P1_excess', 'uncond'], 'removal'), 'A',
  cites=['experiments/contagion/results.json#decision_rules_upgrade_plan/heldout_replication/P8a_removal_of_P1_excess/uncond'])
E('A.31b.P2.rd_uncond', '31B gate: RD(P2 error text only - P0), unconditional', Q('A_res', ['decision_rules_upgrade_plan', 'gate_arms_vs_P0', 'P2k1', 'uncond'], fn=_rdd), 'A',
  cites=['experiments/contagion/results.json#decision_rules_upgrade_plan/gate_arms_vs_P0/P2k1/uncond'])
E('A.p6k.n_contexts', 'P6k dose set: contexts (k_usable >= 4; non-random subset)', Q('A_res', ['prereg_analysis_PREREG_v1', 'P6k', 'cond', 'n_contexts'], 'scalar'), 'A',
  cites=['experiments/contagion/results.json#prereg_analysis_PREREG_v1/P6k/cond/n_contexts'])
E('A.heldout.rd_P1', 'held-out half (294): RD(P1 - P0), unconditional', Q('A_res', ['decision_rules_upgrade_plan', 'heldout_replication', 'P1_vs_P0', 'uncond'], fn=_rdd), 'A',
  cites=['experiments/contagion/results.json#decision_rules_upgrade_plan/heldout_replication/P1_vs_P0/uncond'])
E('A.heldout.rd_P6', 'held-out half (294): RD(P6 - P0), unconditional (format-induction rule table)', Q('A_res', ['decision_rules_upgrade_plan', 'format_induction', 'heldout', 'uncond'], fn=_rdd), 'A',
  cites=['experiments/contagion/results.json#decision_rules_upgrade_plan/format_induction/heldout/uncond'])
E('A.retest.same.P1', 'test-retest, same seed, P1 (100 contexts): malformed-verdict agreement (kappa in field)', Q('A_tr', ['same_seed', 'P1k1'],
  fn=lambda v, d: {'value': v['malformed_agreement'][0], 'ci': v['malformed_agreement'][1:3], 'n': v['malformed_agreement'][3], 'kappa': v['kappa_malformed']}), 'A',
  cites=['experiments/contagion/out/test_retest.json#same_seed/P1k1'])
E('A.retest.same.P1.kappa', 'test-retest, same seed, P1: Cohen kappa of the malformed verdict', Q('A_tr', ['same_seed', 'P1k1', 'kappa_malformed'], 'scalar'), 'A', main=False)
_A2H = ['prereg_analysis_PREREG_v1', 'A2', 'h_by_arm (unconditional, h = 1 - q(arm)/q(L))']
E('A.A2.qL', 'A2 natural post-slip states (300): q(L), malformed next edit as logged', Q('A_res', _A2H + ['P5'], fn=lambda v, d: {'value': v['q(L)'], 'n': v['n_states']}), 'A',
  cites=['experiments/contagion/results.json#prereg_analysis_PREREG_v1/A2'])
E('A.A2.h_P5', 'A2: h of removal + note (P5), unconditional', Q('A_res', _A2H + ['P5'], fn=_hh), 'A',
  cites=['experiments/contagion/results.json#prereg_analysis_PREREG_v1/A2/h_by_arm/P5'])
E('A.A2.h_Q8b', 'A2: h of the sanitized quarantine (Q8b), unconditional', Q('A_res', _A2H + ['Q8b'], fn=_hh), 'A', main=False)
E('A.A2map.h_ITT', 'A2-MAP: h of P8a-MAP (repaired call + MalformedToolCall), ITT on all 300 states', Q('A_map', ['ITT_all_300', 'Q8M'], fn=_hh), 'A',
  cites=['experiments/contagion/out/a2_map_h.json#ITT_all_300/Q8M'])
E('A.A2map.h_repaired', 'A2-MAP: h of P8a-MAP on the 282 repaired states', Q('A_map', ['repaired_282', 'Q8M'], fn=_hh), 'A',
  cites=['experiments/contagion/out/a2_map_h.json#repaired_282/Q8M'])
E('A.A2map.retry_malformed', 'A2-MAP: malformed share among retries under P8a-MAP (repaired states)', Q('A_map', ['retry_split_on_repaired', 'Q8M', 'malformed_among_retries'], 'rate4'), 'A',
  cites=['experiments/contagion/out/a2_map_h.json#retry_split_on_repaired/Q8M'])
E('A.tpl.flag_off_no_thought', 'thinking-off flag: flag-off prompts after a tool response that end at <tool_response|> (June template)', Q('A_tpl', ['endings', 'june:OFF'],
  fn=lambda v, d: {'value': sum(n for k, n in v.items() if k.startswith('<tool_response|> (nothing')), 'n': sum(v.values())}), 'A', main=False,
  cites=['experiments/contagion/out/template_thinking_off_gap.md (pending)'])
_FI = ['headline', 'replay_contagion_injection', 'P1k1:malformed_edit_any']
E('F.inj.P1.bf16', 'F 4-bit injection (396 contexts): P1k1 malformed edit, bf16 (ITT)', Q('F_res', _FI + ['bf16'], 'kn'), 'F',
  cites=['experiments/quant_margins/results.json#headline/replay_contagion_injection/P1k1:malformed_edit_any'])
E('F.inj.P1.qat', 'F 4-bit injection (396 contexts): P1k1 malformed edit, QAT-ct (ITT)', Q('F_res', _FI + ['qat'], 'kn'), 'F', main=False)
E('F.inj.P1.ratio', 'F 4-bit injection: ratio bf16 / QAT-ct (P1k1, ITT)', Q('F_res', _FI + ['ratio_bf16_over_qat'], 'ci3'), 'F', main=False)
E('F.inj.n_contexts', 'F 4-bit injection: contexts with both arms on both models', Q('F_res', ['headline', 'replay_contagion_injection', 'n_contexts_both_arms_both_models'], 'scalar'), 'F', main=False)
E('C.known_issues.n', 'community reports (issues / PRs / threads) mapped to suite cases', Q('C_res', ['known_issue_recall', 'summary', 'issues'], 'scalar'), 'na',
  cites=['experiments/conformance/results.json#known_issue_recall/summary/issues'])
E('D.epred.31b.fullp_over_base', 'D frozen prediction for E: 31B delivered-malformed fullp/base (80% PI)', Q('D_epred', ['population_31B', 'delivered_malformed_fullp_over_base'],
  fn=lambda v, d: {'value': v['point'], 'ci': v['pi80']}), 'D', cites=['paper/protocol_theory/prereg/E_PREDICTIONS_v1.md#1'])
E('D.nonident.dnll', 'cascade law non-identification: log-lik(beta-geometric) - log-lik(power hazard), base', Q('D_t3', ['cascade_model_comparison', 'base', 'nonidentification', 'delta_loglik_betageom_minus_power'], 'scalar'), 'D',
  cites=['paper/protocol_theory/theory.md#R.1'])
E('D.nonident.identity', 'beta-geometric(a=1) vs power hazard(beta=1): max |q_A - q_B| over r <= 2000 (identity check)', Q('D_nonident', ['identity_check'],
  fn=lambda v, d: {'value': max(x['max_r<=2000 |qA - qB|'] for x in v)}), 'D', main=False)
for _k in ('C1_RD_P1_P0_pp', 'C2_RD_P6_P0_pp', 'C4_P5_removal'):
    E(f'D.pred2.v2_A.{_k}', f'D frozen PREREG_v2 prediction (A, 80% PI): {_k}', Q('D_pred2', ['v2_A', _k], fn=lambda v, d: {'value': v[0], 'ci': v[1]}), 'D', main=False)


# ---- OUTLINE v2 claims attached to quantities defined above ----
def claim(entry_id, where, text, value, tol=None):
    for e in R:
        if e['id'] == entry_id:
            e['claims'].append((where, text, value, tol))
            return
    raise KeyError(entry_id)


# ---- B FINAL (sha a9b65fdb...) and A PREREG_v2.1 / v2.2, E acceptance: curated for PAPER v0.3 citations ----
_V21 = 'experiments/contagion/out/v21_analysis.json'
_V22S = 'experiments/contagion/out/v22S_analysis.json'
_V22H = 'experiments/contagion/out/v22H_analysis.json'
for _arm, _lab in (('june_off', 'June template, thinking flag OFF'), ('july_off', 'July template, thinking flag OFF'), ('june_on', 'June template, thinking ON')):
    E(f'B.thinkoff.{_arm}', f'thinking-off manipulation check (31B): call samples that still open a thought channel, {_lab}',
      Q('B_res', ['thinking_off_manipulation_check', _arm, 'with_thought_channel'], 'kn'), 'B',
      cites=['experiments/intent_decoding/README_open_section.md#13'] if _arm == 'june_off' else ())
for _dec in ('T1_text_only', 'ii_tau2', 'i_max'):
    E(f'B.gold.nat.paired_{_dec}', f'gold intent (519 natural slips): paired IPD - {_dec} exact intent (state-cluster bootstrap 95%)',
      Q('B_res', ['gold', 'combined_natural_slips', 'paired_IPD_minus_arm', _dec],
        fn=lambda v, d: {'value': v['diff'], 'ci': v['state_cluster_boot95'], 'ipd_only': v.get('IPD_only'), 'arm_only': v.get('arm_only')}), 'B',
      cites=['experiments/intent_decoding/README_head.md#TL;DR (paired IPD-T1)'] if _dec == 'T1_text_only' else ())
E('A.v21.T1.rd', 'PREREG_v2.1 (thinking flag OFF), 300 gate contexts: RD(P1 - P0), unconditional', Q('A_v21', ['claims_complete_case', 'T1', 'uncond'], fn=_rdd), 'A',
  cites=[f'{_V21}#claims_complete_case/T1/uncond/RD'])
E('A.v21.T3.removal', 'PREREG_v2.1: P8a removal of the P1 excess, unconditional', Q('A_v21', ['claims_complete_case', 'T3', 'removal_uncond'],
  fn=lambda v, d: {'value': v['removal'], 'ci': v['CI']}), 'A', cites=[f'{_V21}#claims_complete_case/T3/removal_uncond/removal'])
E('A.v21.M.opened_4arms', 'PREREG_v2.1 manipulation check: samples that open a thought (P0, P1, P6, P8a pooled)', Q('A_v21', ['manipulation_check_M_v2.1'],
  fn=lambda v, d: {'value': sum(round(v[a]['opened'][0] * v[a]['opened'][3]) for a in ('P0', 'P1', 'P6', 'P8a')) / sum(v[a]['opened'][3] for a in ('P0', 'P1', 'P6', 'P8a')),
                   'k': sum(round(v[a]['opened'][0] * v[a]['opened'][3]) for a in ('P0', 'P1', 'P6', 'P8a')), 'n': sum(v[a]['opened'][3] for a in ('P0', 'P1', 'P6', 'P8a'))}), 'A',
  cites=[f'{_V21}#manipulation_check_M_v2.1/P0/opened'])
E('A.v21.M.P5_closed_opened', 'PREREG_v2.1 manipulation check: P5 contexts where the template closes the thought, thought opened', Q('A_v21', ['manipulation_check_M_v2.1', 'P5_template_closed', 'opened'], 'rate4'), 'A',
  cites=[f'{_V21}#manipulation_check_M_v2.1/P5_template_closed/opened'])
E('A.v22S.S1.rd', 'PREREG_v2.2 S (thought suppressed): RD(P1 - P0), unconditional', Q('A_v22S', ['claims_complete_case', 'S1', 'uncond'], fn=_rdd), 'A',
  cites=[f'{_V22S}#claims_complete_case/S1/uncond'])
E('A.v22S.S3.removal', 'PREREG_v2.2 S: P8a removal of the P1 excess, unconditional', Q('A_v22S', ['claims_complete_case', 'S3', 'removal_uncond'],
  fn=lambda v, d: {'value': v['removal'], 'ci': v['CI']}), 'A', cites=[f'{_V22S}#claims_complete_case/S3/removal_uncond/removal'])
E('A.v22S.M.opened', 'PREREG_v2.2 S manipulation check: samples that open a thought (pooled)', Q('A_v22S', ['manipulation_check_M_S', 'pooled', 'opened'], 'rate4'), 'A',
  cites=[f'{_V22S}#manipulation_check_M_S/pooled/opened'])
E('A.v22H.H1.rd', 'PREREG_v2.2 H (prior reasoning stripped): RD(P1 - P0), unconditional', Q('A_v22H', ['claims_complete_case', 'H1', 'uncond'], fn=_rdd), 'A',
  cites=[f'{_V22H}#claims_complete_case/H1/uncond/RD'])
E('A.v22H.M.opened', 'PREREG_v2.2 H manipulation check: samples that open a thought (pooled)', Q('A_v22H', ['manipulation_check_H', 'pooled', 'opened'], 'rate4'), 'A', main=False)
E('A.v22H.M.no_channel', 'PREREG_v2.2 H manipulation check: samples WITHOUT a thought channel (pooled)', Q('A_v22H', ['manipulation_check_H', 'pooled', 'opened'],
  fn=lambda v, d: {'value': v[3] - round(v[0] * v[3]), 'n': v[3]}), 'A', cites=[f'{_V22H}#manipulation_check_H/pooled/opened'])
cite('A.tpl.flag_off_no_thought', 'experiments/contagion/out/template_thinking_off_check.json#endings/june:OFF')
_PE = 'experiments/intent_decoding/out/proxy_equivalence.json#findings/F2_P1_byte_identity/p1e_prefix/by_cfg/ipd/changed_adversarial'
E('B.proxyeq.ipd.changed_adv', 'proxy P1 byte identity: adversarial prefixes changed by IPD (k; n in field)', Q('B_proxyeq', ['findings', 'F2_P1_byte_identity', 'p1e_prefix', 'by_cfg', 'ipd', 'changed_adversarial'], fn=_count_k), 'B',
  cites=[_PE + '/k'])
E('B.proxyeq.ipd.changed_adv.n', 'proxy P1 byte identity: adversarial prefixes tested', Q('B_proxyeq', ['findings', 'F2_P1_byte_identity', 'p1e_prefix', 'by_cfg', 'ipd', 'changed_adversarial', 'n'], 'scalar'), 'B',
  cites=[_PE + '/n'])
_QF = 'experiments/endtoend/acceptance/p1_quotestorm_freeze_candidate.json#by_cfg/ipd/changed_all'
E('E.qsfreeze.ipd.changed', 'frozen proxy (IPD config) on QuoteStorm valid calls: calls changed (k; n in field)', Q('E_qsfreeze', ['by_cfg', 'ipd', 'changed_all'], fn=_count_k), 'E',
  cites=[_QF + '/k'])
E('E.qsfreeze.ipd.n', 'frozen proxy (IPD config) on QuoteStorm: valid calls tested', Q('E_qsfreeze', ['by_cfg', 'ipd', 'changed_all', 'n'], 'scalar'), 'E',
  cites=[_QF + '/n'])
claim('B.gold.nat.n_total', V2 + ' §6', 'Gold-intent recovery on >=500 natural slips (G1 / G1R)', ('>=', 500))
for _id, _w, _t, _v, _tol in [
    ('A.31b.P0.uncond', V2 + ' §4 E3', 'P1 row: 5.0% (P0)', 0.050, 0.0006),
    ('A.31b.P1.uncond', V2 + ' §4 E3', '-> 40.3%', 0.403, 0.0006),
    ('A.31b.rd.uncond', V2 + ' §4 E3', 'RD +35.3 pp [29.8, 41.1]', 0.353, 0.0006),
    ('A.31b.P0.cond', V2 + ' §4 E3', 'conditional 5.7', 0.057, 0.0006),
    ('A.31b.P1.cond', V2 + ' §4 E3', '-> 46.2%', 0.462, 0.0006),
    ('A.31b.ratio.cond', V2 + ' §4 E3', 'x8.1', 8.1, 0.05),
    ('A.31b.P2.cond', V2 + ' §4 E3', 'The error text alone (P2) gives 1.3%', 0.013, 0.0006),
    ('A.31b.copy_share', V2 + ' §4 E3', '85.4% of P1-malformed edits are verbatim copies', 0.854, 0.0006),
    ('A.31b.P7.quote_share', V2 + ' §4 E3', 'P7 shows 62.9% inherit an injected closer', 0.629, 0.0006),
    ('A.NT.rd_uncond', V2 + ' §4 E3', 'The July HF template ("fixed loops") does not fix it', None, None),
    ('C.spec.tpl_calls', V2 + ' §3 R1', 'byte-identical ... on 3,000 calls', 3000, 0),
    ('C.spec.tpl_calls_june', V2 + ' §3 R1', '(June-5 template) 3,000 calls', 3000, 0),
    ('C.spec.property_checks', V2 + ' §3 R1', '76,635 property checks, 0 failures', 76635, 0),
    ('B.data_fix.first_edit', V2 + ' §4 E1', 'Gemma-only first-edit slip rate 17.1% [15.8, 18.6]', 0.171, 0.0006),
    ('C.corpus.backtick', V2 + ' §4 E1', 'a backtick in 84.1% of cases', 0.841, 0.0006),
    ('C.corpus.lost_old', V2 + ' §4 E1', 'old_string is lost in 96.4%', 0.964, 0.0006),
    ('C.hist.adk_executed_base', V2 + ' §4 E1', 'In ADK, 19% of base slips execute', 0.19, 0.006),
    ('C.corpus.laundered', V2 + ' §4 E2', '53% of slips re-enter history as well-formed corrupted calls', 0.53, 0.0006),
    ('C.hist.byte_identical', V2 + ' §4 E2', 'LiteLLM/ADK 7,274/7,274 byte-identical re-render', 7274, 0),
    ('B.qs.valid_calls', V2 + ' §3 R4', '0/229,414 model-free false repairs', 229414, 0),
    ('F.beh.contagion.bf16', V2 + ' §5', 'Contagion persists in bf16 (x20.5)', 20.5, 0.05),
    ('F.dp.ratio', V2 + ' §5', '4-bit ~4x the slip probability vs bf16', 4.0, 0.35),
    ('C.corpus.base_edit_rate', V2 + ' §9', '24.3% base (true value 34.9%)', 0.349, 0.0006),
    ('D.first_edit', V2 + ' §9', '10.8% first edit (true value 16.8-17.1%)', 0.17, 0.0025),
    ('D.replay.31b.K0', V2 + ' §9', '8.9% -> 86.7% (true value 10.6% ...)', 0.106, 0.0006),
    ('D.replay.31b.K1', V2 + ' §9', '... -> 64.8%', 0.648, 0.0006),
]:
    claim(_id, _w, _t, _v, _tol)


# ----------------------------------------------------------------------------------------------- special extractors


def _closer(v):
    # edit_slip_closers: {"base": {"`": {"n":..,"share_wilson95":[...]}, ...}} or similar
    b = v.get('base') if isinstance(v, dict) else None
    if b is None:
        return {'error': 'no base'}
    key = '`' if '`' in b else next((k for k in b if 'backtick' in k), None)
    x = b[key]
    if isinstance(x, dict):
        s = x.get('share_wilson95')
        return {'value': s[0], 'ci': s[1:], 'k': x.get('n')}
    return {'value': x}


def _lost(v):
    b = v.get('base', v) if isinstance(v, dict) else v
    x = b.get('old_string') if isinstance(b, dict) else None
    if isinstance(x, dict):
        s = x.get('share_wilson95')
        return {'value': s[0], 'ci': s[1:], 'k': x.get('n')}
    return {'error': f'unexpected shape {type(x)}'}


def _t4(v):
    keys = ['order_31b_think|malformed_hist', 'order_31b_nothink|malformed_hist', 'order_12b_think|malformed_hist', 'order_e4b_think|malformed_hist']
    p = [v[k][-1] for k in keys]
    adj = holm(p)
    return {'value': max(adj), 'raw_p': dict(zip(keys, p)), 'holm_p': dict(zip(keys, adj)),
            'n_significant_holm_0.05': sum(a < 0.05 for a in adj)}


def _wilson(k, n, z=1.959964):
    if not n:
        return [None, None]
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [(c - h) / d, (c + h) / d]


def _adk_base(v):
    c = v['counts']
    k, n = c['base|outcome:tool_executed'], c['base|n']
    return {'value': k / n, 'k': k, 'n': n, 'ci': _wilson(k, n), 'error_share_base': c['base|outcome:adk_error_response'] / n}


# ----------------------------------------------------------------------------------------------- build
def fmt(x, pct=None):
    if x is None:
        return '—'
    if isinstance(x, (int,)) and not isinstance(x, bool):
        return f'{x:,}'
    if isinstance(x, float):
        if math.isnan(x):
            return 'NaN'
        if pct or (pct is None and 0 <= abs(x) <= 1.2):
            return f'{100 * x:.1f}%'
        return f'{x:.3g}' if abs(x) < 1000 else f'{x:,.0f}'
    return str(x)


def status_of(entry, val, claim):
    where, text, cval, tol = claim
    if cval is None and (val is None or val.get('value') is None):
        return 'PENDING'
    if 'error' in (val or {}) or val is None or val.get('value') is None:
        return 'MISSING-SOURCE' if val is None else 'EXTRACT-ERROR'
    if cval is None:
        return 'CHECK'  # qualitative; resolved in notes
    if '[target' in text:
        return 'PENDING'
    v = val['value']
    if isinstance(cval, str):  # hash quoted by prefix, e.g. 'root 818841b2...'
        return 'OK' if isinstance(v, str) and v.startswith(cval) else 'MISMATCH'
    if isinstance(cval, tuple):  # threshold claim, e.g. ('>=', 0.7)
        op, thr = cval
        ok = {'>=': v >= thr, '<=': v <= thr, '>': v > thr, '<': v < thr}[op]
        if '[' in text and '[target' not in text and not ok:
            return 'PENDING'  # bracketed placeholder in the plan = target not reached yet
        return 'OK' if ok else 'MISMATCH'
    if isinstance(v, (int, float)) and abs(v - cval) <= tol + 1e-12:
        return 'OK'
    return 'MISMATCH'


# ----------------------------------------------------------------------------------------------- paper draft gate
# Every <!-- src: ... --> comment in the newest paper/protocol/draft/PAPER_v*.md is resolved to numbers.json entries:
#   release/numbers.json#KEY       -> that quantity (KEY.* = a group of quantities)
#   <results>.json#<path>          -> the entry registered for that citation, else the entry with the same file and JSON
#                                     path, else an AUTO.* entry ingested from that file and path (source, path and
#                                     sha256 recorded like every other entry; listed for curation)
#   <prose>.md#...                 -> TEXT (no machine check; listed)
# The value must appear in the text before the comment (its paragraph and the one before, so tables and their captions
# work) as a whole-number token in a usual rendering (fraction, percent, pp, signed, separators, 0-3 decimals, number
# words up to twenty), or as both k and n. Rows that SOURCES_MAP.md marks QUAL or DERIVED are exempt from that check.
PATH_ALIASES = {'release/lib/': 'slipguard/'}   # project path -> public-tree path (used only when the project path is absent)
PAPER_SRC_RE = re.compile(r'<!--\s*src:(.*?)-->', re.S)
FILE_REF_RE = re.compile(r'^((?:[\w.-]+/)*[\w.-]+\.(?:json|md|py|txt|jinja|jsonl))(?:#(.+)|\s*(\(.*\))?)$', re.S)
ANNOT_RE = re.compile(r'\((?:n\s*=?\s*)?([\d][\d,]*(?:\.\d+)?)\)\s*$')
PAPER_BLOCKING = ('UNKNOWN-KEY', 'LEDGER-GAP', 'MISS')   # non-blocking: OK, OK-SET, GROUP, QUAL/DERIVED, TEXT, NODE, PENDING
_WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen',
          'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty']


def latest_paper(root):
    d = os.path.join(root, 'paper', 'protocol', 'draft')
    if not os.path.isdir(d):
        return None
    c = []
    for fn in os.listdir(d):
        m = re.fullmatch(r'PAPER_v(\d+(?:\.\d+)*)\.md', fn)
        if m:
            c.append((tuple(int(x) for x in m.group(1).split('.')), fn))
    return os.path.join(d, max(c)[1]) if c else None


def _brace_expand(s):
    m = re.search(r'\{([^{}]*,[^{}]*)\}', s)
    if not m:
        return [s]
    out = []
    for alt in m.group(1).split(','):
        out += _brace_expand(s[:m.start()] + alt.strip() + s[m.end():])
    return out


def _renders(v):
    """usual print forms of a value. Raw: integers as is (with/without thousands separators), other numbers with 1-3
    decimals. Percent: 1-2 decimals as is; whole percents only when followed by '%' or ' pp'. Signed and typographic-minus
    variants; unsigned forms of a negative only with a decimal point; number words two..twenty for counts."""
    out = set()
    if v is None or isinstance(v, bool):
        return out
    if isinstance(v, str):
        return {v[:8]}
    if not isinstance(v, (int, float)) or v != v:
        return out
    forms = [(v, 0, ''), (v, 1, '')] if float(v).is_integer() else [(v, d, '') for d in (1, 2, 3)]
    forms += [(v * 100, d, '') for d in (1, 2)] + [(v * 100, 0, suf) for suf in ('%', ' pp', '\u00a0pp', '\u2013', '-')]
    for x, dd, suf in forms:
        r = round(x, dd)
        s = f'{r:,.{dd}f}'
        for t in {s, s.replace(',', ''), s.rstrip('0').rstrip('.') if '.' in s else s}:
            out.add(t + suf)
            out.add(('−' + t[1:] if t.startswith('-') else '+' + t) + suf)
            if t.startswith('-') and ('.' in t or suf):
                out.add(t[1:] + suf)
    if float(v).is_integer() and 2 <= v <= 20:
        w = _WORDS[int(v)]
        out |= {w, w.capitalize()}
    return out


def _found(cands, text):
    for c in sorted(cands, key=len, reverse=True):
        tail = '' if c[-1:] in ('\u2013', '-') else r'(?![\d\w]|[.,]\d)'   # '17–' is followed by the range's upper end
        if c and re.search(r'(?<![\w.,])' + re.escape(c) + tail, text):
            return c
    return None


def _exemptions(paper_path):
    """keys / citations on SOURCES_MAP rows whose status is QUAL or DERIVED (in-sentence check waived)."""
    p = os.path.join(os.path.dirname(paper_path), 'SOURCES_MAP.md')
    ex = set()
    if not os.path.exists(p):
        return ex
    for line in open(p, encoding='utf-8'):
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) >= 4 and re.match(r'^(QUAL|DERIVED)', cells[-1]):
            row = ' '.join(cells[:-1])
            ex.update(re.findall(r'numbers\.json#"?([A-Za-z0-9_.\-]+(?: [A-Za-z0-9_.\-]+)*)"?', row))
            ex.update(x.strip('`') for x in re.findall(r'`[^`]*\.json#[^`]*`', row))
            ex.update(re.findall(r'`#"?([A-Za-z][A-Za-z0-9_.\-]*(?: [A-Za-z0-9_.\-]+)*)"?`', row))   # `#KEY` shorthand after a numbers.json cite
    return ex


def _resolve_path(d, path):
    """JSON path as written in the draft -> list of concrete key tuples ('*' expands; keys may contain '/';
    'h_by_arm' matches the unique key 'h_by_arm (...)')."""
    segs = path.split('/')
    out = []

    def rec(node, i, acc):
        if i == len(segs):
            out.append(tuple(acc))
            return
        if isinstance(node, list):
            if segs[i].isdigit() and int(segs[i]) < len(node):
                rec(node[int(segs[i])], i + 1, acc + [int(segs[i])])
            return
        if not isinstance(node, dict):
            return
        if segs[i] == '*':
            for k in node:
                rec(node[k], i + 1, acc + [k])
            return
        for j in range(len(segs), i, -1):
            cand = '/'.join(segs[i:j])
            if cand in node:
                rec(node[cand], j, acc + [cand])
                return
        ks = [k for k in node if isinstance(k, str) and k.startswith(segs[i] + ' (')]
        if len(ks) == 1:
            rec(node[ks[0]], i + 1, acc + [ks[0]])

    rec(d, 0, [])
    return out


def _path_variants(path):
    """the path as written, then with trailing annotations removed ('A2 (300)', 'class_matrix. Aggregation: ...')."""
    out = [path]
    p = path
    while ' (' in p:
        p = p.rsplit(' (', 1)[0].rstrip()
        out.append(p)
    for sep in ('. ', ' '):
        if sep in path:
            out.append(path.split(sep, 1)[0].rstrip('.'))
    return list(dict.fromkeys(out))


def _auto(v, d):
    if isinstance(v, bool):
        return {'value': int(v)}
    if isinstance(v, (int, float, str)):
        return {'value': v}
    if isinstance(v, list):
        if len(v) == 4 and all(isinstance(x, (int, float)) for x in v):
            return {'value': v[0], 'ci': [v[1], v[2]], 'n': v[3]}
        if len(v) == 3 and all(isinstance(x, (int, float)) for x in v):
            return {'value': v[0], 'ci': [v[1], v[2]]}
        if len(v) == 2 and isinstance(v[0], (int, float)) and isinstance(v[1], list):
            return {'value': v[0], 'ci': v[1]}
        if len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
            return {'value': None, 'ci': list(v), 'shape': 'ci'}   # an interval cited on its own: both ends must be printed
        if v and not any(isinstance(x, (int, float)) for x in v):
            return {'value': len(v), 'note_auto': 'count of listed items'}
        return {'value': None, 'shape': f'list[{len(v)}]'}
    if isinstance(v, dict):
        if 'k' in v and 'n' in v:
            return {'value': v.get('rate', v['k'] / v['n'] if v['n'] else None), 'ci': v.get('wilson95') or v.get('ci95'), 'n': v['n'], 'k': v['k']}
        if 'RD' in v or 'diff' in v:
            return _rdd(v, d)
        if isinstance(v.get('h'), list):
            return _hh(v, d)
        if 'fraction_removed' in v:
            return {'value': v['fraction_removed'], 'ci': v.get('CI'), 'n': v.get('n_contexts')}
        if 'ratio' in v:
            return {'value': v['ratio'], 'ci': v.get('CI', v.get('ratio_CI')), 'n': v.get('n_contexts')}
        if 'point' in v:
            return {'value': v['point'], 'ci': v.get('pi80')}
        if 'n' in v and isinstance(v.get('malformed'), list):
            return {'value': v['malformed'][0], 'ci': v['malformed'][1:3], 'n': v['n']}
        return {'value': None, 'shape': 'dict{' + ','.join(map(str, list(v)[:6])) + '}'}
    return {'value': None}


def paper_citations(paper_path):
    """[(line, sentence window, fragment)] for every fragment of every <!-- src: --> comment."""
    text = open(paper_path, encoding='utf-8').read()
    out = []
    for m in PAPER_SRC_RE.finditer(text):
        before = re.sub(r'<!--.*?-->', ' ', text[max(0, m.start() - 4000):m.start()], flags=re.S)
        own_para = before.endswith('\n\n') or before.rstrip(' ').endswith('\n')
        sent = '\n\n'.join(before.rstrip().split('\n\n')[-(3 if own_para else 2):])
        line_no = text.count('\n', 0, m.start()) + 1
        for frag in re.split(r';\s+', m.group(1).strip()):
            if frag.strip():
                out.append((line_no, sent, frag.strip()))
    return out


def ingest_paper_citations(root, paper_path, keep_auto=False):
    """Map every JSON citation of the draft to entries; add AUTO entries for cited paths no entry covers yet.
    Returns {citation: [entry ids]} and {citation: reason} for citations that cannot be resolved."""
    global R
    if not keep_auto:
        R[:] = [e for e in R if not e['id'].startswith('AUTO.')]
    cmap = {}
    for e in R:
        for c in e.get('cites', ()):
            cmap.setdefault(c, []).append(e['id'])
    by_path = {}
    for e in R:
        q = e['q']
        if q.path is not None and q.src in SOURCES:
            by_path.setdefault((SOURCES[q.src], tuple(q.path)), e['id'])
    src_of = {v: k for k, v in SOURCES.items()}
    unresolved = {}
    for _line, _sent, frag in paper_citations(paper_path):
        fm = FILE_REF_RE.match(frag)
        if not fm or frag.startswith('release/numbers.json#') or not fm.group(1).endswith('.json') or fm.group(2) is None:
            continue
        for c in _brace_expand(frag):
            if c in cmap:
                continue
            best = max((k for k in cmap if c.startswith(k) and (len(c) == len(k) or c[len(k)] in ' .(,')), key=len, default=None)
            if best:
                cmap[c] = cmap[best]
                continue
            fpath, jpath = c.split('#', 1)
            full = os.path.join(root, fpath)
            if not os.path.exists(full):   # the public tree relocates some project paths (e.g. release/lib -> slipguard)
                for a, b in PATH_ALIASES.items():
                    if fpath.startswith(a) and os.path.exists(os.path.join(root, b + fpath[len(a):])):
                        fpath = b + fpath[len(a):]
                        full = os.path.join(root, fpath)
                        break
            if not os.path.exists(full):
                unresolved[c] = 'file not found'
                continue
            key = src_of.get(fpath)
            if key is None:
                key = 'AUTO:' + fpath
                SOURCES[key] = fpath
                SCRIPTS.setdefault(key, '(producer of ' + fpath + ')')
            L_ = load(root, key)
            data = (L_ or {}).get('data')
            tuples = []
            for pv in _path_variants(jpath):
                tuples = _resolve_path(data, pv) if data is not None else []
                if tuples:
                    break
            if not tuples:
                unresolved[c] = 'path not found in ' + fpath
                continue
            ids = []
            for t in tuples:
                hit = by_path.get((fpath, t))
                if hit is None:
                    hit = 'AUTO.' + re.sub(r'\.json$', '', fpath) + ':' + '/'.join(map(str, t))   # full path: no basename collisions
                    if not any(e['id'] == hit for e in R):
                        E(hit, 'AUTO-ingested for the paper draft: ' + fpath + '#' + '/'.join(map(str, t)), Q(key, list(t), fn=_auto), 'na', main=False,
                          note='Ingested automatically because the draft cites it; give it a curated entry (label, definition) before the final gate.')
                    by_path[(fpath, t)] = hit
                ids.append(hit)
            cmap[c] = ids
    return cmap, unresolved


def paper_gate(root, numbers, paper_path, cmap, unresolved):
    ex = _exemptions(paper_path)
    rows = []
    for line_no, sent, frag in paper_citations(paper_path):
        row = {'line': line_no, 'ref': frag[:160]}
        targets = []
        if frag.startswith('release/numbers.json#'):
            key = frag.split('#', 1)[1].strip()
            key = key[1:key.index('"', 1)] if key.startswith('"') and '"' in key[1:] else key.split(' (')[0].strip()
            if key.endswith('.*'):
                hits = [k for k in numbers if k.startswith(key[:-1])]
                rows.append(dict(row, key=key, status='GROUP' if hits else 'UNKNOWN-KEY', n_keys=len(hits)))
                continue
            targets = [(key, frag)]
        else:
            fm = FILE_REF_RE.match(frag)
            if not fm:
                continue   # prose inside the comment
            if fm.group(2) is None:   # whole file cited, e.g. 'gate_gate31b_final.json (300)'
                am = ANNOT_RE.search(frag)
                if am and fm.group(1).endswith('.json') and os.path.exists(os.path.join(root, fm.group(1))):
                    a = am.group(1).replace(',', '')
                    raw = open(os.path.join(root, fm.group(1)), encoding='utf-8', errors='replace').read()
                    ok = bool(_found({am.group(1), a}, sent)) and re.search(r'"n(?:_\w+)?":\s*' + re.escape(a) + r'\b', raw) is not None
                    rows.append(dict(row, status='OK' if ok else 'MISS', found=f'annotated n {a}' if ok else None,
                                     context=None if ok else sent.split('\n\n')[-1][-220:]))
                else:
                    rows.append(dict(row, status='TEXT' if not fm.group(1).endswith('.json') else 'NODE', why='whole file cited'))
                continue
            for c in _brace_expand(frag):
                if c not in cmap:
                    best = max((k for k in cmap if c.startswith(k) and (len(c) == len(k) or c[len(k)] in ' .(,')), key=len, default=None)
                    if best:
                        cmap[c] = cmap[best]
                if c in cmap:
                    targets += [(k, c) for k in cmap[c]]
                else:
                    is_json = fm.group(1).endswith('.json')
                    rows.append(dict(row, ref=c[:160], status='LEDGER-GAP' if is_json else 'TEXT', why=unresolved.get(c, '') if is_json else 'prose source'))
        set_rows = []
        for key, ref in targets:
            r2 = dict(row, ref=ref[:160], key=key)
            q = numbers.get(key)
            if q is None:
                r2['status'] = 'UNKNOWN-KEY'
            elif q.get('value') is None and q.get('shape') == 'ci':
                lo, hi = q['ci']
                ok = bool(_found(_renders(lo), sent) and _found(_renders(hi), sent))
                r2.update(value=q['ci'], status='OK' if ok else 'MISS', found='interval' if ok else None,
                          context=None if ok else sent.split('\n\n')[-1][-220:])
            elif q.get('value') is None:
                r2['status'] = 'NODE' if q.get('shape') else 'PENDING'
                r2['why'] = ('cites a block, not a number: ' + q['shape']) if q.get('shape') else (q.get('error') or 'no value in the source yet')
            else:
                v = q['value']
                r2['value'] = v
                hit = _found(_renders(v), sent)
                if hit is None and isinstance(q.get('k'), (int, float)) and isinstance(q.get('n'), (int, float)):
                    hk, hn = _found(_renders(q['k']), sent), _found(_renders(q['n']), sent)
                    hit = f'{hk} of {hn}' if hk and hn else None
                am = ANNOT_RE.search(ref)
                if hit is None and am:   # 'path (300)' / '(n 1,598)': the draft cites this count of the entry
                    a = float(am.group(1).replace(',', ''))
                    if a in [x for x in (v, q.get('n'), q.get('k')) if isinstance(x, (int, float))] and _found({am.group(1)} | _renders(a), sent):
                        hit = f'annotated {am.group(1)}'
                exempt = key in ex or ref in ex or any(ref.startswith(x.split(' ')[0]) for x in ex if '#' in x)
                if hit is not None:
                    r2['status'], r2['found'] = 'OK', hit
                    ci = q.get('ci')
                    if isinstance(ci, (list, tuple)) and len(ci) == 2 and all(isinstance(x, (int, float)) for x in ci):
                        r2['ci_in_text'] = bool(_found(_renders(ci[0]), sent) and _found(_renders(ci[1]), sent))
                elif exempt:
                    r2['status'] = 'QUAL/DERIVED'
                else:
                    r2['status'] = 'MISS'
                    r2['context'] = sent.split('\n\n')[-1][-220:]
            rows.append(r2)
            if '*' in ref:
                set_rows.append(r2)
        if set_rows and any(r['status'] == 'OK' for r in set_rows):   # a wildcard citation supports a summary (max, range)
            for r in set_rows:
                if r['status'] == 'MISS':
                    r['status'], r['found'] = 'OK-SET', 'another member of the cited set appears'
    by = collections.Counter(r['status'] for r in rows)
    return {'paper': os.path.relpath(paper_path, root), 'paper_sha256': hashlib.sha256(open(paper_path, 'rb').read()).hexdigest()[:16],
            'n_refs': len(rows), 'by_status': dict(by), 'n_auto_entries': sum(1 for k in numbers if k.startswith('AUTO.')),
            'blocking': [r for r in rows if r['status'] in PAPER_BLOCKING], 'rows': rows}


def build(root, out_dir, strict=False, paper=None, claims='auto'):
    now = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    paper = paper if paper is not None else latest_paper(root)
    cmap, unresolved = ingest_paper_citations(root, paper) if paper and os.path.exists(paper) else ({}, {})
    # README files that carry <!-- src: --> comments are gated like the paper (re-export item 5)
    readmes = [os.path.join(root, d, 'README.md') for d in ('', 'slipguard', 'transcriptlab')]
    readmes = [x for x in readmes if os.path.exists(x) and PAPER_SRC_RE.search(open(x, encoding='utf-8').read())]
    for x in readmes:
        c2, u2 = ingest_paper_citations(root, x, keep_auto=True)
        cmap.update(c2); unresolved.update(u2)
    # public tree (no internal planning documents): claims come from the paper and READMEs only
    public = claims == 'public' or (claims == 'auto' and not os.path.exists(os.path.join(root, 'paper', 'protocol', 'OUTLINE.md')))
    numbers, rows = {}, []
    for e in R:
        val = e['q'].get(root)
        rec = dict(label=e['label'], definition=DEF.get(e['defn'], e['defn']), canonical=e['canonical'], main_text=e['main'], note=e['note'])
        if val:
            rec.update(val)
        else:
            rec['error'] = f'source missing: {SOURCES.get(e["q"].src)}'
        numbers[e['id']] = rec
        for c in ([] if public else e['claims']) or [None]:
            st = status_of(e, val, c) if c else ('OK' if val and 'value' in val else 'MISSING-SOURCE')
            rows.append((e, rec, c, st))
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'numbers.json'), 'w') as f:
        json.dump({'generated_utc': now, 'generator': 'release/build_numbers.py', 'root': '<project root>',
                   'n_quantities': len(numbers), 'numbers': numbers}, f, indent=1, default=str)
    pg = paper_gate(root, numbers, paper, cmap, unresolved) if paper and os.path.exists(paper) else None
    for x in readmes:   # merge README rows into the gate (same rules)
        g2 = paper_gate(root, numbers, x, cmap, unresolved)
        for r in g2['rows']:
            r['doc'] = os.path.relpath(x, root)
        if pg is None:
            pg = g2
        else:
            pg['rows'] += g2['rows']; pg['blocking'] += g2['blocking']; pg['n_refs'] += g2['n_refs']
            pg['by_status'] = dict(collections.Counter(r['status'] for r in pg['rows']))
    if pg is not None:
        pg['claims_mode'] = 'public (paper + READMEs only)' if public else 'all (incl. internal planning notes, non-blocking)'
        pg['readmes_gated'] = [os.path.relpath(x, root) for x in readmes]
    if pg is not None:
        with open(os.path.join(out_dir, 'paper_gate.json'), 'w') as f:
            json.dump(dict(pg, generated_utc=now), f, indent=1, default=str)
    write_ledger(out_dir, rows, numbers, now, pg)
    # 2026-11-06 (PI): the paper draft is the gated artefact; OUTLINE v2 claims are a non-blocking reference
    outline_v2 = [r for r in rows if r[2] and str(r[2][0]).startswith('OUTLINE v2') and r[3] in ('MISMATCH', 'MISSING-SOURCE', 'EXTRACT-ERROR')]
    bad = []
    pbad = pg['blocking'] if pg else []
    with open(os.path.join(out_dir, 'strict_gate.json'), 'w') as f:
        json.dump({'generated_utc': now, 'gate': 'FAIL' if (bad or pbad) else 'PASS', 'n_blocking': len(bad) + len(pbad),
                   'n_blocking_outline_v2': 0, 'n_outline_v2_reference_mismatches': len(outline_v2), 'n_blocking_paper': len(pbad),
                   'outline_v2_reference_mismatches': [{'id': e['id'], 'where': c[0], 'claim': c[1], 'current': rec.get('value')} for e, rec, c, st in outline_v2],
                   'paper': (pg or {}).get('paper'), 'paper_sha256': (pg or {}).get('paper_sha256'), 'paper_by_status': (pg or {}).get('by_status'),
                   'blocking': [{'id': e['id'], 'where': c[0], 'claim': c[1], 'status': st, 'current': rec.get('value'),
                                 'ci': rec.get('ci'), 'n': rec.get('n'), 'source': rec.get('source'), 'json_path': rec.get('json_path'),
                                 'note': e['note']} for e, rec, c, st in bad],
                   'blocking_paper': pbad}, f, indent=1, default=str)
    ref_note = '' if public else f'OUTLINE v2 (reference, non-blocking) mismatches {len(outline_v2)}; '
    print(f'strict gate: {"FAIL" if (bad or pbad) else "PASS"} -- {ref_note}'
          f'paper ({(pg or {}).get("paper", "none")}) blocking {len(pbad)} {(pg or {}).get("by_status", {})}')
    if public:
        print(f'{len(numbers)} quantities; {sum(r[3] in ("MISSING-SOURCE", "EXTRACT-ERROR") for r in rows)} without a source file in this tree '
              '(internal-only quantities; the paper does not cite them)')
    else:
        print(f'{len(numbers)} quantities, {len(rows)} claim rows; MISMATCH={sum(r[3] == "MISMATCH" for r in rows)} '
              f'OK={sum(r[3] == "OK" for r in rows)} MISSING/ERR={sum(r[3] in ("MISSING-SOURCE", "EXTRACT-ERROR") for r in rows)}')
    return 1 if (strict and (bad or pbad)) else 0


def ci_str(rec):
    ci = rec.get('ci')
    if not ci or any(c is None for c in ci):
        return '—'
    try:
        if all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in ci):
            if all(-0.05 <= c <= 1.2 for c in ci) and 0 <= abs(rec.get('value') or 0) <= 1.2:
                return f'[{100 * ci[0]:.1f}, {100 * ci[1]:.1f}]'
            return f'[{ci[0]:.3g}, {ci[1]:.3g}]'
    except Exception:
        pass
    return str(ci)


RECONCILIATION = """
### 3.1 Base edit denominators and malformed counts (all from logged vLLM-0.19.1 parses; teacher = Qwen/DeepSeek runs served under the Gemma alias)

| value | producer | how it arises | use? |
|---|---|---|---|
| 3,293 / 9,430 = 34.9% | C `corpus_stats.json` (schema-based labels) | complete base population | **canonical field-split rate until the M-A recompute** |
| 3,296 / 9,430 = 35.0% | D `t3_summary.json`, F `edit_index` | 13-key synthesis-style predicate (+4 leak, -1 unknown-key vs C) | variant; same population |
| 3,184 / 9,077 = 35.1% | A `observational.json` | A's log index drops every response logged before a `blp` key (run-41 352 edits, test_lp 1) | **bug** -- fix `extract_index.split_line` |
| 3,212 / 9,111 = 35.25% | D `t3_seqs_check.json`, SYN | `seqs.update` overwrites 319 edits of runs run-03/run-05 that reuse bare task ids | **bug** -- key on (run, file, attempt) |
| 3,230 / 13,301 = 24.3% | SYN `analyze2.py` (OUTLINE C1) | teacher runs included (4,190 edits at 0.4%) + overwrite | **retracted** |
| 3,312-3,314 / 13,620 = 24.3% | C progress / F / D v1 | teacher runs included | **retracted** |

### 3.2 First-edit (onset) rates

| rate | producer | numerator / denominator | definition |
|---|---|---|---|
| **16.8%** | D | 484 / 2,883 | no edit_file call visible in the context (`first_ctx`) -- **canonical "first edit"** |
| 17.1% | C, F | 471-472 / 2,756 | first edit per (log file, attempt) |
| 17.4% | D seqs | 460 / 2,647 | per task id after the overwrite bug |
| 17.6% | A | 451 / 2,564 | per task id, two runs merged, one run dropped |
| 16.9% | B (Gemma-only requeue sample) | 161 / 954 | logged first edit, census predicate |
| 10.8% | SYN, A-SYN, B logs | 472 / 4,376 | **teacher included -- retracted** |

### 3.3 Backtick share of closers (base edit slips) -- a definitional choice, not an error

| share | producer | numerator / denominator | closer definition |
|---|---|---|---|
| **84.1%** | C | 2,769 / 3,293 | closer adjacent to the comma (`"`` counts as backtick); denominator = all base edit slips |
| 83% | B | 2,679 / 3,217 | maximal look-alike run; 26 empty runs in the denominator |
| 86.5% | D T1 | 2,679 / 3,096 | only the 4 canonical closers in the denominator |
| ~80% (78.8-81.5%) | SYN / A | 2,578 / 3,271 | teacher included; no-closer cases in the denominator |

Recommendation: cite C's 84.1% [82.8, 85.3] with its definition, and the 84-86% range in prose only if both definitions are stated.

### 3.4 Attempt counts

| value | meaning |
|---|---|
| 2,756 | base (run, file, attempt) sequences with >= 1 edit (C, F) |
| 2,762 | D trajectories ((run, file, task) groups, interleaved chains split) |
| 2,647 | distinct base task ids (109 shared ids collapse) |
| 2,564 | 2,647 minus the runs A's index drops |
| 2,513 | distinct (run, attempt) pairs among corpus records of ALL models (DATASHEET coverage figure) |
| 2,505 | the same records keyed by attempt-id string only (8 ids collide across runs run-03/run-05) |

### 3.5 Two senses of "laundered" (see DEFINITIONS.md)
* **laundered (record label)**: the June-template re-render of a corrupted call is well-formed and parses back to the same corrupted arguments -- 53.0% of base edit slips (1,746 / 3,293).
* **history pass-through**: all 7,274 parsed-malformed calls (base + FT) re-enter the next prompt byte-identical and unflagged (LiteLLM/ADK). PLAN §1.1 calls these "7,274 laundered slips" -- rename to "re-rendered unflagged".
* **parser laundering**: a newer parser turns a visible failure into a silent call (vLLM 0.31: 620/676).

### 3.6 ADK outcome denominators
* 19% executed / 81% error (PLAN §4 H2) = 832 / 4,411 **base** parsed-malformed calls of **any tool** (results_history.json F6r counts).
* 35.5% executed / 63.7% error (C README) = all 7,274 parsed-malformed calls, base + fine-tunes. State the denominator every time.
"""

WARNINGS = [
    ('ESTIMAND', 'Every causal headline in OUTLINE/PLAN uses the CONDITIONAL rate P(malformed | edit). UPGRADE_PLAN §2 makes the UNCONDITIONAL rate primary and §6 says "risk differences first". Current primary numbers: P0 {A.31b.P0.uncond}, P1 {A.31b.P1.uncond}, RD {A.31b.rd.uncond} (CI {A.31b.rd.uncond:ci}), ratio {A.31b.ratio.uncond} (CI {A.31b.ratio.uncond:ci}); P4 removal {A.31b.P4.removed.uncond}. Re-write H1 with RD first.'),
    ('POPULATION', 'contagion/results.json has at times pooled the pre-registered 300-context gate with pilot/interim files (at 11:28 UTC: n=303, ratio 7.68 instead of 8.13). Now: results.json {A.31b.ratio.union} (n={A.31b.ratio.union:n}) vs gate file {A.31b.ratio.cond} (n={A.31b.ratio.cond:n}). Cite only out/gate_gate31b_final.json for the gate.'),
    ('STALE', '12B is now {A.12b.ratio.cond} (CI {A.12b.ratio.cond:ci}, n={A.12b.ratio.cond:n} contexts), not x5.7; unconditional RD {A.12b.rd.uncond} (CI {A.12b.rd.uncond:ci}).'),
    ('STALE', 'E4B is now {A.e4b.ratio.cond} (CI {A.e4b.ratio.cond:ci}, n={A.e4b.ratio.cond:n}): the CI excludes 1, so "not significant" is wrong, but it fails the pre-registered >=3x gate. Unconditional RD {A.e4b.rd.uncond} (CI {A.e4b.rd.uncond:ci}).'),
    ('DECISION', 'Format induction (P6) is NOT yet claimable under the pre-registered rule: gate RD {A.31b.P6.rd_uncond_gate} (CI {A.31b.P6.rd_uncond_gate:ci}) but the held-out half is pending (decision file says: "{A.31b.P6.decision}"). Until then the loop is "copy-on-retry" (thesis variant C wording).'),
    ('ORACLE', 'P4/P5 removal (105.7%) is for ORACLE quarantine; the shipped quarantine (P8a) has no result yet. Do not write "quarantine removes ~100%" about the proxy.'),
    ('POPULATION', 'B\'s gate (first-edit closer slips {B.gate.base_slip}, n={B.gate.base_slip:n}) mixes natural and FORCED edits and draws contexts from a pool that contains teacher runs (546/1,500); the natural-only subset is {B.gate.natural.base_slip} (n={B.gate.natural.base_slip:n}). The Gemma-only requeue is pending.'),
    ('BUG', 'paper/protocol_theory/sim/out/t3_summary.json "MR_RE_boot" CIs do not contain their point estimates (mis-assigned); use t3_boot_extra.json (PROGRESS: "bootstrap bug fixed").'),
    ('BUG', 'experiments/contagion/scripts/extract_index.py drops whole runs whose log lines put a key after "response" (definitions audit) -> A\'s observational numbers use 9,077 instead of 9,430 base edits and ~9.8k instead of 21,816 FT edits.'),
    ('NOT-A-HEADLINE', 'Fuzz-distribution rates (e.g. vLLM 0.31 silent-wrong {C.diff.v031_invalid_silent}) are rates over a generator; PLAN §5 replaces them with per-class presence and real-input rates (1,610 real slips, 676 raw outputs).'),
    ('CONFLICT', 'Base edit malformation: C {C.corpus.base_edit_rate} (3,293/9,430) vs D {D.base_edit_rate} (3,296/9,430). Same population, predicates differ on 5 calls. PLAN says "35.0%"; DATASHEET says 34.9%. Pick one definition (DEFINITIONS.md: M-A) and recompute; until then write "35% (3,293/9,430)".'),
    ('HONESTY CLAUSE', 'B\'s interim head-to-head (n={B.h2h.ipd:n} contexts, {B.h2h.n_slips} natural slips): IPD delivered-malformed {B.h2h.ipd} and text-only {B.h2h.textonly} -- a tie. PLAN §P0-B: if text-only + quarantine is within 1 pp of IPD + quarantine on natural traffic, the paper must say IPD\'s value is rollback + the guarantee on quote-dense content. Grammar-CD turned {B.h2h.grammar_silent_on_slips} of {B.h2h.grammar_silent_on_slips:n} slips into silent corruption (interim).'),
    ('UNIT', 'C counts 3,293 parsed malformed edits / 9,430 parsed edit calls; the canonical judge M-A also counts the 5 base raw-unparsed edit_file texts (3,298 / 9,435 = 34.95%). The released notebook re-derives both from the records.'),
    ('RETRACTED', 'OUTLINE C1 "24.3%", C2 "8.9% -> 86.7%", "12B/E4B 3% -> 18-25%", thesis "~7-10x" and "backtick ~80%" are teacher-contaminated or superseded. Replacement values are in the rows above.'),
]


def _fill(tmpl, numbers):
    import re as _re

    def rep(m):
        key, _, field = m.group(1).partition(':')
        rec = numbers.get(key, {})
        if '.rd' in key and field == '' and isinstance(rec.get('value'), float):
            return f'{100 * rec["value"]:+.1f} pp'
        if field == 'ci':
            return ci_str(rec)
        if field == 'n':
            return fmt(rec.get('n'))
        v = rec.get('value')
        return v if isinstance(v, str) else fmt(v)
    return _re.sub(r'\{([A-Za-z0-9_.:\-]+)\}', rep, tmpl)


def _section(where):
    w = where.replace('UPGRADE_PLAN.md', 'PLAN').replace('OUTLINE.md', 'OUTLINE').replace('PROGRESS.md', 'PROGRESS')
    return w


def write_ledger(out_dir, rows, numbers, now, pg=None):
    L = []
    L.append('# Claims ledger -- single source of truth for every number in the paper\n')
    L.append(f'*Generated {now} by `release/build_numbers.py` (do not edit by hand). Regenerate: '
             '`python release/build_numbers.py` (CPU, <5 s, stdlib only). Machine-readable twin: `release/numbers.json`.*\n')
    L.append('Each claim found in `paper/protocol/OUTLINE.md`, UPGRADE_PLAN §0/§1/§4, PROGRESS.md and R3 is matched to the '
             'quantity that the producing workstream wrote into its results JSON. **Status**: OK = matches within rounding; '
             '**MISMATCH** = claim text stale or result drifted -- fix the text before writing; CHECK = qualitative claim, read '
             'the note; PENDING = target without a result file yet. Rates in %; CIs as stored by the producer (Wilson, or '
             'attempt/context-cluster bootstrap for paired contrasts). Definitions: `release/DEFINITIONS.md`.\n')
    # ---------------- 0. paper draft gate
    if pg:
        L.append(f'\n## 0. Paper draft gate -- `{pg["paper"]}` (sha256 {pg["paper_sha256"]})\n')
        L.append(f'{pg["n_refs"]} citations in `<!-- src: -->` comments: ' + ', '.join(f'{k} {v}' for k, v in sorted(pg['by_status'].items()))
                 + '. Blocking: UNKNOWN-KEY, LEDGER-GAP (a results JSON not in numbers.json), MISS (value not in its sentence; '
                 'rows marked QUAL/DERIVED in SOURCES_MAP.md are exempt). TEXT = cited from a prose file (no machine check). '
                 'PENDING = the quantity exists but its source has no value yet. NODE = the citation points at a block (table, '
                 'dict), not at one number. OK-SET = a wildcard citation whose summary value appears.\n')
        L.append('| line | status | citation | numbers.json key | value | found as / context |')
        L.append('|---|---|---|---|---|---|')
        order = {'UNKNOWN-KEY': 0, 'LEDGER-GAP': 1, 'MISS': 2, 'PENDING': 3, 'NODE': 4, 'TEXT': 5, 'QUAL/DERIVED': 6, 'OK-SET': 7, 'GROUP': 8, 'OK': 9}
        for r in sorted(pg['rows'], key=lambda r: (order.get(r['status'], 9), r['line'])):
            if r['status'] in ('OK', 'OK-SET', 'GROUP'):
                continue
            ctx = r.get('found') or (r.get('context') or r.get('why') or '').replace('|', '/').replace('\n', ' ')[-140:]
            st = r['status']
            L.append(f'| {r["line"]} | **{st}** | `{r["ref"][:90]}` | `{r.get("key", "")}` | {fmt(r.get("value"))} | {ctx} |')
        L.append(f'\nAll other citations ({pg["by_status"].get("OK", 0)} OK, {pg["by_status"].get("OK-SET", 0)} OK-SET, '
                 f'{pg["by_status"].get("GROUP", 0)} GROUP) resolve and their value appears in the text. '
                 f'{pg.get("n_auto_entries", 0)} AUTO.* entries were ingested for this draft (curate before the final gate). '
                 'Per-citation detail, incl. whether the CI is printed: `release/paper_gate.json`.\n')
    # ---------------- 1. loud flags
    mism = [r for r in rows if r[3] == 'MISMATCH']
    L.append(f'\n## 1. LOUD FLAGS\n')
    L.append(f'### 1a. Numeric mismatches ({len(mism)} claim rows)\n')
    L.append('| claim (where) | claimed | **current** | CI | n | canonical source -> JSON path | note |')
    L.append('|---|---|---|---|---|---|---|')
    for e, rec, c, st in mism:
        L.append(f'| {e["label"]} ({_section(c[0])}) | {c[1]} | **{fmt(rec.get("value"))}** | {ci_str(rec)} | {fmt(rec.get("n"))} | '
                 f'`{rec.get("source", "?")}` -> `{rec.get("json_path", "")}` | {e["note"] or "stale or drifted"} |')
    L.append('\n### 1b. Estimand, population and definition warnings\n')
    for tag, t in WARNINGS:
        L.append(f'* **{tag}.** ' + _fill(t, numbers))
    # ---------------- 2. claims by section
    L.append('\n## 2. Claims by document section\n')
    groups = {}
    for e, rec, c, st in rows:
        if not c:
            continue
        sec = _section(c[0])
        groups.setdefault(sec, []).append((e, rec, c, st))

    def sort_key(sec):
        order = ['OUTLINE', 'PLAN §4 H1', 'PLAN §4 H2', 'PLAN §4 H3', 'PLAN §0', 'PLAN §1.1', 'PLAN §1.2', 'PLAN §1.3', 'PLAN', 'PROGRESS', 'R3']
        for i, o in enumerate(order):
            if sec.startswith(o):
                return (i, sec)
        return (99, sec)
    for sec in sorted(groups, key=sort_key):
        L.append(f'\n### {sec}\n')
        L.append('| claim as written | status | current value | CI | n | source -> JSON path | producing script | definition |')
        L.append('|---|---|---|---|---|---|---|---|')
        for e, rec, c, st in groups[sec]:
            badge = f'**{st}**' if st != 'OK' else 'OK'
            L.append(f'| {e["label"]}: "{c[1]}" | {badge} | {fmt(rec.get("value"))} | {ci_str(rec)} | {fmt(rec.get("n"))} | '
                     f'`{rec.get("source", SOURCES.get(e["q"].src, "?"))}` -> `{rec.get("json_path", "/".join(map(str, e["q"].path or [])))}` | '
                     f'`{rec.get("script", SCRIPTS.get(e["q"].src, ""))}` | {rec.get("definition", "")} |')
    # ---------------- 3. reconciliation
    L.append('\n## 3. Reconciliation of drifting numbers (definitions audit, 2026-11-04)\n')
    L.append(RECONCILIATION)
    # ---------------- 4. all quantities
    L.append('\n## 4. All quantities in numbers.json\n')
    L.append('| id | quantity | value | CI | n | source (sha256[:16], mtime) | canonical |')
    L.append('|---|---|---|---|---|---|---|')
    for i, rec in numbers.items():
        L.append(f'| `{i}` | {rec.get("label")} | {fmt(rec.get("value")) if not isinstance(rec.get("value"), str) else rec.get("value")} | '
                 f'{ci_str(rec)} | {fmt(rec.get("n"))} | `{rec.get("source", "-")}` ({rec.get("source_sha256", "-")}, {rec.get("source_mtime_utc", "-")}) | '
                 f'{"yes" if rec.get("canonical") else "no (variant)"} |')
    with open(os.path.join(out_dir, 'claims_ledger.md'), 'w') as f:
        f.write('\n'.join(L) + '\n')
    gen = os.path.join(out_dir, 'claims_ledger.generated.md')
    if os.path.exists(gen):
        os.remove(gen)


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument('--root', default=os.path.dirname(here))
    ap.add_argument('--out-dir', default=None, help='default: a fresh temporary directory in the public tree '
                    '(nothing is written into the checkout); this release/ directory in the project tree')
    ap.add_argument('--strict', action='store_true')
    ap.add_argument('--paper', default=None, help='paper draft to gate (default: newest paper/protocol/draft/PAPER_v*.md)')
    ap.add_argument('--claims', default='auto', choices=('auto', 'all', 'public'),
                    help='public = paper + READMEs only (default in a tree without the internal planning documents)')
    a = ap.parse_args()
    out_dir = a.out_dir
    if out_dir is None:
        internal = os.path.exists(os.path.join(a.root, 'paper', 'protocol', 'OUTLINE.md'))
        if internal:
            out_dir = here
        else:
            import tempfile
            out_dir = tempfile.mkdtemp(prefix='build_numbers_')
    print(f'outputs: {out_dir}')
    sys.exit(build(a.root, out_dir, a.strict, a.paper, a.claims))


if __name__ == '__main__':
    main()
