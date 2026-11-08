"""Paper figures for workstream A, each written as JSON (the exact plotted numbers) + SVG + PNG in out/figures/.

  fig_pathways   : (b) P(malformed | next call is edit_file) by history pathway P0..P7 at k=1, per model; bars + Wilson 95% CIs
                   (random-sample contexts; analysis file out/ana_<model>_gate_k1_random_sample.json).
  fig_dose       : (a) dose-response P(malformed | edit) vs k = 0, 1, 2, 4 for P1 (corrupted re-render) and P4 (canonical
                   re-render, quarantine), per model (nested k>=4 set; out/ana_<model>_dose_k4_nested_set.json).
  fig_copy       : (c) what the model does after the corrupted call: verbatim copy of the corrupted value / clean rewrite of
                   the same edit / other edit (malformed or clean), per arm and model (out/copy_check.json).
Palette: the dataviz reference categorical palette in its documented fixed order (adjacent-pair validated; the first
three slots validated all-pairs); light surface; text in text inks; CI whiskers in neutral ink. PNG via ImageMagick.
usage: figures.py
"""
import json, os, html, subprocess
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
OUT = f'{D}/out/figures'
SURF, INK1, INK2, MUTED, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#8a8984', '#e6e5e1'
SLOT = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
FONT = 'font-family="Inter, Helvetica, Arial, sans-serif"'
MODELS = [('31b_old', 'Gemma-4 31B QAT', 'gemma-4-31b'), ('12b_old', 'Gemma-4 12B QAT', 'gemma-4-12b'), ('e4b_old', 'Gemma-4 E4B QAT', 'gemma-4-e4b')]
ARMS = ['P0k0', 'P1k1', 'P7k1', 'P3k1', 'P6k1', 'P2k1', 'P4k1', 'P5k1']
ARM_LINES = {'P0k0': ['P0', 'original'], 'P1k1': ['P1', 'corrupted', 're-render'], 'P7k1': ['P7', 'P1, quote', 'closer'],
             'P3k1': ['P3', 'raw slip', 'text'], 'P6k1': ['P6', 'corrupted,', 'success'], 'P2k1': ['P2', 'error', 'only'],
             'P4k1': ['P4', 'canonical', 're-render'], 'P5k1': ['P5', 'removed', '+ note']}


def esc(s): return html.escape(str(s), quote=True)


def text(x, y, s, size=12, fill=INK1, anchor='start', weight='400'):
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}" {FONT}>{esc(s)}</text>'


def load(path):
    return json.load(open(path)) if os.path.exists(path) else None


def grid_y(x0, y0, w, h, ymax, step, title):
    o, v = [], 0.0
    while v <= ymax + 1e-9:
        y = y0 + h - v / ymax * h
        o.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0 + w}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        o.append(text(x0 - 8, y + 4, f'{round(100 * v)}%', 11, INK2, 'end'))
        v += step
    o.append(f'<line x1="{x0}" y1="{y0 + h}" x2="{x0 + w}" y2="{y0 + h}" stroke="{MUTED}" stroke-width="1"/>')
    if title: o.append(text(x0 - 40, y0 - 14, title, 11, INK2))
    return o


def bar_path(x, y_top, w, y_base, r=4):
    """Bar anchored at the baseline with a 4px rounded data-end (top corners only)."""
    hgt = y_base - y_top
    if hgt <= 0.5: return f'M{x:.1f},{y_base:.1f} h{w:.1f}'
    r = min(r, hgt, w / 2)
    return (f'M{x:.1f},{y_base:.1f} V{y_top + r:.1f} Q{x:.1f},{y_top:.1f} {x + r:.1f},{y_top:.1f} H{x + w - r:.1f} '
            f'Q{x + w:.1f},{y_top:.1f} {x + w:.1f},{y_top + r:.1f} V{y_base:.1f} Z')


def nice_max(hi):
    return min(1.0, max(0.1, (int(hi * 10) + 1) / 10))


def save(name, svg, data):
    os.makedirs(OUT, exist_ok=True)
    json.dump(data, open(f'{OUT}/{name}.json', 'w'), indent=1)
    open(f'{OUT}/{name}.svg', 'w').write(svg)
    r = subprocess.run(['convert', '-density', '110', f'{OUT}/{name}.svg', f'{OUT}/{name}.png'], capture_output=True, text=True)
    print(name, 'json+svg ok | png', 'ok' if r.returncode == 0 else r.stderr[-300:])


# ---------------------------------------------------------------- (b) pathway bars
def fig_pathways():
    series = []
    for g, name, _ in MODELS:
        d = load(f'{D}/out/ana_{g}_gate_k1_random_sample.json')
        if d: series.append((g, name, d))
    arms = [a for a in ARMS if any(a in d['arms'] and d['arms'][a]['P_malformed_given_edit'][0] is not None for _, _, d in series)]
    data = {'metric': 'P(malformed | next call is edit_file), Wilson 95% CI; k = 1 (one prior edit replaced); random-sample contexts',
            'models': {name: {'n_contexts': d['n_contexts'], 'arms': {a: {'p': d['arms'][a]['P_malformed_given_edit'][0], 'ci': d['arms'][a]['P_malformed_given_edit'][1:3],
                                                                           'n_edits': d['arms'][a]['P_malformed_given_edit'][3], 'P_edit': d['arms'][a]['P_edit']}
                                                                       for a in arms if a in d['arms']}} for _, name, d in series}}
    W, H = 1040, 520; x0, y0, w, h = 90, 130, 910, 280
    hi = max(d['arms'][a]['P_malformed_given_edit'][2] or 0 for _, _, d in series for a in arms if a in d['arms'])
    ymax = nice_max(hi); step = 0.1
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', f'<rect width="{W}" height="{H}" fill="{SURF}"/>',
         text(30, 30, 'One corrupted call in the history makes the next edit malformed; quarantine removes the effect', 16, INK1, 'start', '600'),
         text(30, 52, 'P(next edit_file call is malformed) after ONE prior successful edit is shown differently (k = 1); bars = rate, whiskers = Wilson 95% CI', 12, INK2)]
    for si, (g, name, d) in enumerate(series):
        o.append(f'<rect x="{30 + 260 * si}" y="68" width="12" height="12" rx="2" fill="{SLOT[si]}"/>')
        o.append(text(48 + 260 * si, 79, f'{name.replace("Gemma-4 ", "")}  ({d["n_contexts"]} contexts)', 12, INK1))
    o += grid_y(x0, y0, w, h, ymax, step, 'malformed next edits')
    cw = w / len(arms); nb = len(series); bw = min(22, (cw - 18) / nb)
    Y = lambda v: y0 + h - v / ymax * h
    for ci, a in enumerate(arms):
        cx = x0 + cw * (ci + 0.5)
        if a == 'P4k1':
            o.append(f'<line x1="{x0 + cw * ci:.1f}" y1="{y0 - 4}" x2="{x0 + cw * ci:.1f}" y2="{y0 + h}" stroke="{MUTED}" stroke-width="1" stroke-dasharray="3 3"/>')
            o.append(text(x0 + cw * ci + 6, y0 + 10, 'history quarantine', 11, INK2))
        for li, s in enumerate(ARM_LINES[a]):
            o.append(text(cx, y0 + h + 18 + 14 * li, s, 12 if li == 0 else 11, INK1 if li == 0 else INK2, 'middle', '600' if li == 0 else '400'))
        for si, (g, name, d) in enumerate(series):
            x = cx - nb * (bw + 2) / 2 + si * (bw + 2)  # 2px surface gap between adjacent bars
            v = d['arms'].get(a)
            if not v or v['P_malformed_given_edit'][0] is None: continue
            p, lo, up, n = v['P_malformed_given_edit']
            o.append(f'<g><title>{esc(name)} | {a}: {100 * p:.1f}% [{100 * lo:.1f}, {100 * up:.1f}], n = {n} edits</title>'
                     f'<path d="{bar_path(x, Y(p), bw, Y(0))}" fill="{SLOT[si]}"/></g>')
            xm = x + bw / 2
            o.append(f'<line x1="{xm:.1f}" y1="{Y(lo):.1f}" x2="{xm:.1f}" y2="{Y(up):.1f}" stroke="{INK2}" stroke-width="1.5"/>')
            for yy in (Y(lo), Y(up)):
                o.append(f'<line x1="{xm - 3:.1f}" y1="{yy:.1f}" x2="{xm + 3:.1f}" y2="{yy:.1f}" stroke="{INK2}" stroke-width="1.5"/>')
            if si == 0:  # direct labels for the primary model only
                o.append(text(xm, Y(up) - 6, f'{100 * p:.0f}%', 10.5, INK1, 'middle'))
    o.append(text(30, H - 30, 'P0 original history. P1 the vLLM-parsed backtick slip re-rendered by the chat template + ADK missing-old_string error. P7 = P1 with a double-quote closer. '
                  'P3 raw call text + harness nudge.', 10.5, MUTED))
    o.append(text(30, H - 16, 'P6 corrupted re-render + original success response. P2 valid call + error only. P4 canonical old_string-first valid call + true result. '
                  'P5 call removed + one-line note. Labels: 31B values.', 10.5, MUTED))
    o.append('</svg>')
    save('fig_pathways', '\n'.join(o), data)


# ---------------------------------------------------------------- (a) dose-response P1 vs P4
def fig_dose():
    KS = ['0', '1', '2', '4']; PATHS = [('P1', 'P1 corrupted re-render + error', 0), ('P4', 'P4 quarantine: canonical re-render', 3)]
    panels = []
    for g, name, _ in MODELS:
        d = load(f'{D}/out/ana_{g}_dose_k4_nested_set.json')
        if d and any((d['dose_response'].get(f'{p}_upto_k4') or {}).get('curve') for p, _, _ in PATHS): panels.append((g, name, d))
    data = {'metric': 'P(malformed | next call is edit_file) vs k = number of most recent prior edits replaced; Wilson 95% CI; nested set of contexts with >= 4 clean prior edits; k = 0 is the original history',
            'models': {}}
    hi = 0.1
    for g, name, d in panels:
        data['models'][name] = {}
        for p, lab, _ in PATHS:
            cur = (d['dose_response'].get(f'{p}_upto_k4') or {})
            if not cur.get('curve'): continue
            data['models'][name][p] = {'n_contexts': cur['n_contexts'], 'curve': {k: {'p': v['P_malformed_given_edit'][0], 'ci': v['P_malformed_given_edit'][1:3], 'n_edits': v['P_malformed_given_edit'][3],
                                                                                        'P_edit': v['P_edit']} for k, v in cur['curve'].items()}}
            for v in cur['curve'].values():
                if v['P_malformed_given_edit'][2] is not None: hi = max(hi, v['P_malformed_given_edit'][2])
    if not panels: print('fig_dose: no dose data yet'); return
    ymax = nice_max(hi); step = 0.1 if ymax > 0.3 else 0.05
    PW = 520 if len(panels) == 1 else 300; PH = 250; W = max(1000, 70 + len(panels) * (PW + 60) + 40); H = 470; y0 = 130
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', f'<rect width="{W}" height="{H}" fill="{SURF}"/>',
         text(20, 30, 'More corrupted calls in the history, more malformed next edits; canonical re-render stays at baseline', 16, INK1, 'start', '600'),
         text(20, 52, 'k most recent prior edits replaced (k = 0: original history); contexts with >= 4 clean prior edits; whiskers = Wilson 95% CI', 12, INK2)]
    for pi_, (p, lab, slot) in enumerate(PATHS):
        lx = 20 + 330 * pi_
        o.append(f'<line x1="{lx}" y1="76" x2="{lx + 22}" y2="76" stroke="{SLOT[slot]}" stroke-width="2"/><circle cx="{lx + 11}" cy="76" r="4" fill="{SLOT[slot]}" stroke="{SURF}" stroke-width="2"/>')
        o.append(text(lx + 30, 80, lab, 12, INK1))
    for gi, (g, name, d) in enumerate(panels):
        x0 = 80 + gi * (PW + 60)
        o += grid_y(x0, y0, PW, PH, ymax, step, 'malformed next edits' if gi == 0 else '')
        o.append(text(x0 + PW / 2, y0 - 34, name, 13, INK1, 'middle', '600'))
        X = lambda k: x0 + 20 + int(k) * (PW - 40) / 4  # proportional dose axis (k = 0, 1, 2, 4)
        Y = lambda v: y0 + PH - v / ymax * PH
        for k in KS: o.append(text(X(k), y0 + PH + 18, f'k = {k}', 11, INK2, 'middle'))
        for p, lab, slot in PATHS:
            cur = (d['dose_response'].get(f'{p}_upto_k4') or {}).get('curve')
            if not cur: continue
            pts = [(k, cur[k]['P_malformed_given_edit']) for k in KS if k in cur and cur[k]['P_malformed_given_edit'][0] is not None]
            if len(pts) < 2: continue
            o.append('<polyline fill="none" stroke="%s" stroke-width="2" stroke-linejoin="round" points="%s"/>' % (SLOT[slot], ' '.join(f'{X(k):.1f},{Y(v[0]):.1f}' for k, v in pts)))
            for k, v in pts:
                o.append(f'<line x1="{X(k):.1f}" y1="{Y(v[1]):.1f}" x2="{X(k):.1f}" y2="{Y(v[2]):.1f}" stroke="{SLOT[slot]}" stroke-width="1.5" stroke-opacity="0.7"/>')
                o.append(f'<g><title>{esc(name)} | {p} k={k}: {100 * v[0]:.1f}% [{100 * v[1]:.1f}, {100 * v[2]:.1f}], n = {v[3]} edits</title>'
                         f'<circle cx="{X(k):.1f}" cy="{Y(v[0]):.1f}" r="4.5" fill="{SLOT[slot]}" stroke="{SURF}" stroke-width="2"/></g>')
            kl, vl = pts[-1]
            o.append(text(X(kl) + 8, Y(vl[0]) + 4, f'{100 * vl[0]:.0f}%', 10.5, INK1))
        ncx = max((d['dose_response'].get(f'{p}_upto_k4') or {}).get('n_contexts', 0) for p, _, _ in PATHS)
        o.append(text(x0 + PW / 2, y0 + PH + 40, f'n = {ncx} contexts', 11, MUTED, 'middle'))
    off = ' (off-policy for 12B/E4B)' if len(panels) > 1 else ''
    o.append(text(20, H - 28, f'Histories are real 31B agent trajectories{off}. P1: each replaced call shown as the vLLM-parsed backtick slip + ADK error;', 10.5, MUTED))
    o.append(text(20, H - 14, 'P4: shown as a canonical old_string-first valid call + its true result. Pre-registered (PREREG_v1); rule D-M verdict: none of M1-M3 (step + logit-linear accumulation).', 10.5, MUTED))
    o.append('</svg>')
    save('fig_dose', '\n'.join(o), data)


# ---------------------------------------------------------------- (c) copy vs rewrite
def fig_copy():
    cc = load(f'{D}/out/copy_check.json')
    if not cc: print('fig_copy: no copy_check.json'); return
    rows = []
    for model_id, mname in (('gemma-4-31b', '31B'), ('gemma-4-12b', '12B'), ('gemma-4-e4b', 'E4B')):
        for arm, alab in (('P1k1', 'P1 corrupted re-render'), ('P7k1', 'P7 quote closer'), ('P3k1', 'P3 raw slip text'), ('P6k1', 'P6 corrupted + success')):
            r = cc.get(f'{model_id}:{arm}')
            if not r or r['all_edits']['n'] < 20: continue

            def cnt(c, mal):
                x = r.get(c)
                if not x: return 0
                k = round(x['malformed'][0] * x['n'])
                return k if mal else x['n'] - k
            seg = {'copy': cnt('copy_corrupted', True) + cnt('copy_corrupted', False),
                   'rewrite_clean': cnt('clean_retry', False), 'rewrite_malformed': cnt('clean_retry', True),
                   'other_malformed': cnt('same_content_other', True) + cnt('other_edit', True) + cnt('unparsed_or_no_key', True),
                   'other_clean': cnt('same_content_other', False) + cnt('other_edit', False) + cnt('unparsed_or_no_key', False)}
            rows.append({'model': mname, 'arm': arm, 'label': f'{mname}  {alab}', 'n_edits': r['all_edits']['n'], 'segments': seg,
                         'share_of_malformed_that_are_verbatim_copies': r.get('share_of_malformed_that_are_verbatim_copies')})
    if not rows: print('fig_copy: no rows'); return
    SEGS = [('copy', 'verbatim copy of the corrupted value (malformed)', 0), ('other_malformed', 'other edit, malformed', 1),
            ('rewrite_malformed', 'rewrite of the same edit, malformed', 4), ('rewrite_clean', 'clean rewrite of the same edit', 2), ('other_clean', 'other edit, clean', 3)]
    data = {'metric': 'Next edit_file calls after one corrupted prior call (k = 1), classified by comparing the generated new_string with the corrupted value shown in the history (byte-exact) and with the original clean value',
            'rows': rows}
    W = 1040; RH = 34; H = 150 + RH * len(rows) + 60; x0, w = 250, 740; y0 = 120
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', f'<rect width="{W}" height="{H}" fill="{SURF}"/>',
         text(20, 30, 'What the model writes after one corrupted call in its history', 16, INK1, 'start', '600'),
         text(20, 52, 'Share of next edit_file calls after ONE corrupted prior call, by what the model wrote (generated new_string vs the value the history shows)', 12, INK2)]
    pos = [(20, 74), (360, 74), (540, 74), (790, 74), (20, 94)]
    for si, (key, lab, slot) in enumerate(SEGS):
        lx, ly = pos[si]
        o.append(f'<rect x="{lx}" y="{ly - 10}" width="12" height="12" rx="2" fill="{SLOT[slot]}"/>')
        o.append(text(lx + 18, ly, lab, 11.5, INK1))
    for ri, r in enumerate(rows):
        y = y0 + ri * RH
        o.append(text(x0 - 10, y + 17, r['label'], 12, INK1, 'end'))
        tot = sum(r['segments'].values()); x = x0
        for key, lab, slot in SEGS:
            v = r['segments'][key]
            if v == 0: continue
            sw = w * v / tot
            o.append(f'<g><title>{esc(r["label"])} | {esc(lab)}: {v}/{tot} ({100 * v / tot:.1f}%)</title>'
                     f'<rect x="{x:.1f}" y="{y}" width="{max(0.5, sw - 2):.1f}" height="{RH - 10}" rx="2" fill="{SLOT[slot]}"/></g>')
            if sw > 34: o.append(text(x + sw / 2 - 1, y + 17, f'{100 * v / tot:.0f}%', 10.5, '#ffffff' if slot in (0, 5, 6) else INK1, 'middle', '600'))
            x += sw
        o.append(text(x0 + w + 8, y + 17, f'n = {tot}', 11, INK2))
    o.append(text(20, H - 24, 'Byte-exact = the generated new_string equals the corrupted value (original + closer + ",old_string:"); clean rewrite = equals the original value. '
                  'Histories are 31B trajectories.', 10.5, MUTED))
    o.append('</svg>')
    save('fig_copy', '\n'.join(o), data)


if __name__ == '__main__':
    fig_pathways(); fig_dose(); fig_copy()
