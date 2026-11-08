"""Static SVG figures (paper) from the analysis JSONs; rasterised to PNG with ImageMagick for inspection.

fig_k1_pathways.svg : P(malformed | next call is edit_file) by history pathway at k=1, per model, Wilson 95% CIs.
fig_dose.svg        : dose-response P(malformed | edit) vs k (0, 1, 2, 4) per pathway, small multiples per model.
Palette: the dataviz reference categorical palette in its documented fixed order (validated adjacent-pair; first three
slots validated all-pairs), light surface. Text uses text inks, never series colors.
usage: figures.py  (reads out/ana_<group>_gate_k1_random_sample.json and out/ana_<group>_dose_k4_nested_set.json)
"""
import json, os, html, subprocess
D = os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/contagion')
SURF, INK1, INK2, MUTED, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#8a8984', '#e6e5e1'
SLOT = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
FONT = 'font-family="Inter, Helvetica, Arial, sans-serif"'
MODELS = [('31b_old', 'Gemma-4 31B QAT'), ('12b_old', 'Gemma-4 12B QAT'), ('e4b_old', 'Gemma-4 E4B QAT')]
PATH_LABEL = {'P0k0': 'none (k=0)', 'P1': 'corrupted re-render + error', 'P2': 'error message only', 'P3': 'raw slip text + nudge',
              'P6': 'corrupted re-render + success', 'P4': 'quarantine: canonical re-render', 'P5': 'quarantine: removed + note'}
K1_ORDER = ['P0k0', 'P1k1', 'P7k1', 'P2k1', 'P3k1', 'P6k1', 'P4k1', 'P5k1']
SHORT = {'P0k0': ['P0', 'none'], 'P1k1': ['P1', 'corrupted', 're-render'], 'P2k1': ['P2', 'error', 'only'], 'P3k1': ['P3', 'raw slip', 'text'],
         'P6k1': ['P6', 'corrupted,', 'success'], 'P7k1': ['P7', 'corrupted', '(" closer)'], 'P4k1': ['P4', 'canonical', 're-render'], 'P5k1': ['P5', 'removed', '+ note']}


def esc(s): return html.escape(str(s), quote=True)


def text(x, y, s, size=12, fill=INK1, anchor='start', weight='400'):
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}" {FONT}>{esc(s)}</text>'


def load(group, part):
    p = f'{D}/out/ana_{group}_{part}.json'
    return json.load(open(p)) if os.path.exists(p) else None


def yaxis(x0, y0, w, h, ymax, step, label):
    out = []
    v = 0.0
    while v <= ymax + 1e-9:
        y = y0 + h - v / ymax * h
        out.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0 + w}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        out.append(text(x0 - 8, y + 4, f'{round(100 * v)}%', 11, INK2, 'end'))
        v += step
    out.append(f'<line x1="{x0}" y1="{y0 + h}" x2="{x0 + w}" y2="{y0 + h}" stroke="{MUTED}" stroke-width="1"/>')
    if label: out.append(text(x0 - 40, y0 - 14, label, 11, INK2, 'start'))
    return out


def fig_k1():
    W, H = 980, 500; x0, y0, w, h = 86, 128, 860, 280
    series = [(g, name, load(g, 'gate_k1_random_sample')) for g, name in MODELS]
    series = [(g, n, d) for g, n, d in series if d]
    cats = [c for c in K1_ORDER if any(c in d['arms'] for _, _, d in series)]
    hi = max([d['arms'][c]['P_malformed_given_edit'][2] or 0 for _, _, d in series for c in cats if c in d['arms']] + [0.1])
    ymax = min(1.0, (int(hi * 10) + 1) / 10); step = 0.1 if ymax > 0.3 else 0.05
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         f'<rect width="{W}" height="{H}" fill="{SURF}"/>',
         text(x0 - 60, 30, 'Next edit_file call malformed, by what the history shows about ONE prior edit (k = 1)', 16, INK1, 'start', '600'),
         text(x0 - 60, 52, 'Real pre-edit agent states (base QAT models, thinking on); dots = P(malformed | next call is edit_file), whiskers = Wilson 95% CI', 12, INK2)]
    o += yaxis(x0, y0, w, h, ymax, step, 'P(malformed | next call is edit_file)')
    cw = w / len(cats); offs = [-(len(series) - 1) / 2 * 16 + 16 * i for i in range(len(series))]
    for ci, c in enumerate(cats):
        cx = x0 + cw * (ci + 0.5)
        if c in ('P4k1',):  # visual group divider between contagion pathways and quarantine
            o.append(f'<line x1="{x0 + cw * ci:.1f}" y1="{y0 - 6}" x2="{x0 + cw * ci:.1f}" y2="{y0 + h}" stroke="{MUTED}" stroke-width="1" stroke-dasharray="3 3"/>')
        for li, s in enumerate(SHORT[c]):
            o.append(text(cx, y0 + h + 18 + 14 * li, s, 12 if li == 0 else 11, INK1 if li == 0 else INK2, 'middle', '600' if li == 0 else '400'))
        for si, (g, name, d) in enumerate(series):
            a = d['arms'].get(c)
            if not a or a['P_malformed_given_edit'][0] is None: continue
            p, lo, up, n = a['P_malformed_given_edit']
            x = cx + offs[si]; col = SLOT[si]
            Y = lambda v: y0 + h - v / ymax * h
            o.append(f'<line x1="{x:.1f}" y1="{Y(lo):.1f}" x2="{x:.1f}" y2="{Y(up):.1f}" stroke="{col}" stroke-width="2" stroke-linecap="round"/>')
            o.append(f'<g><title>{esc(name)} | {esc(c)}: {100 * p:.1f}% [{100 * lo:.1f}, {100 * up:.1f}], n = {n} edits</title>'
                     f'<circle cx="{x:.1f}" cy="{Y(p):.1f}" r="5" fill="{col}" stroke="{SURF}" stroke-width="2"/></g>')
            if c == 'P1k1':  # selective direct labels on the key contrast, above each whisker (no collisions)
                o.append(text(x, Y(up) - 7, f'{100 * p:.0f}%', 11, INK1, 'middle'))
    o.append(text(x0 + cw * cats.index('P4k1') + 6 if 'P4k1' in cats else x0, y0 + 12, 'history quarantine', 11, INK2))
    o.append(text(x0 + cw + 6, y0 + 12, 'contagion pathways', 11, INK2))
    lx = x0 - 60
    for si, (g, name, d) in enumerate(series):
        o.append(f'<circle cx="{lx + 250 * si + 6}" cy="{76}" r="5" fill="{SLOT[si]}"/>')
        o.append(text(lx + 250 * si + 16, 80, f'{name.replace("Gemma-4 ", "")}  ({d["n_contexts"]} contexts)', 12, INK1))
    o.append(text(x0 - 60, H - 14, 'P0 = original history. One prior successful edit is replaced: P1 vLLM-parsed backtick slip re-rendered by the template + ADK error; '
                  'P2 valid call + error; P3 raw call text + harness nudge;', 10.5, MUTED))
    o.append(text(x0 - 60, H - 2, 'P7 = P1 with a double-quote closer; P6 corrupted re-render + original success; P4 canonical old_string-first valid call + true result; '
                  'P5 call removed + note. Histories are 31B trajectories.', 10.5, MUTED))
    o.append('</svg>')
    return '\n'.join(o)


def fig_dose():
    panels = [(g, name, load(g, 'dose_k4_nested_set')) for g, name in MODELS]
    panels = [(g, n, d) for g, n, d in panels if d and d.get('dose_response')]
    if not panels: return None
    PW, PH = 330, 250; W = 60 + len(panels) * (PW + 40) + 230; H = 440; y0 = 112
    paths = ['P1', 'P3', 'P6', 'P2', 'P5', 'P4']
    hi = 0.1
    for _, _, d in panels:
        for p in paths:
            cur = (d['dose_response'].get(f'{p}_upto_k4') or {}).get('curve') or {}
            for v in cur.values():
                if v['P_malformed_given_edit'][2] is not None: hi = max(hi, v['P_malformed_given_edit'][2])
    ymax = min(1.0, (int(hi * 10) + 1) / 10); step = 0.1 if ymax > 0.3 else 0.05
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', f'<rect width="{W}" height="{H}" fill="{SURF}"/>',
         text(20, 30, 'Dose-response: malformed next edit vs number of prior edits shown corrupted (k)', 16, INK1, 'start', '600'),
         text(20, 52, 'Nested set: contexts with >= 4 clean prior edits; each line = one history pathway; whiskers = Wilson 95% CI', 12, INK2)]
    KS = ['0', '1', '2', '4']
    for pi, (g, name, d) in enumerate(panels):
        x0 = 80 + pi * (PW + 40)
        o += yaxis(x0, y0, PW, PH, ymax, step, 'malformed next edits' if pi == 0 else '')
        o.append(text(x0 + PW / 2, y0 - 30, f'{name}', 13, INK1, 'middle', '600'))
        X = lambda k: x0 + 18 + KS.index(k) * (PW - 36) / 3
        Y = lambda v: y0 + PH - v / ymax * PH
        for k in KS: o.append(text(X(k), y0 + PH + 18, f'k = {k}', 11, INK2, 'middle'))
        for si, p in enumerate(paths):
            cur = (d['dose_response'].get(f'{p}_upto_k4') or {}).get('curve')
            if not cur: continue
            col = SLOT[si]; pts = [(k, cur[k]['P_malformed_given_edit']) for k in KS if k in cur and cur[k]['P_malformed_given_edit'][0] is not None]
            if len(pts) < 2: continue
            o.append('<polyline fill="none" stroke="%s" stroke-width="2" stroke-linejoin="round" points="%s"/>' % (col, ' '.join(f'{X(k):.1f},{Y(v[0]):.1f}' for k, v in pts)))
            for k, v in pts:
                o.append(f'<line x1="{X(k):.1f}" y1="{Y(v[1]):.1f}" x2="{X(k):.1f}" y2="{Y(v[2]):.1f}" stroke="{col}" stroke-width="1" stroke-opacity="0.6"/>')
                o.append(f'<g><title>{esc(name)} | {p} k={k}: {100 * v[0]:.1f}% [{100 * v[1]:.1f}, {100 * v[2]:.1f}], n = {v[3]} edits</title>'
                         f'<circle cx="{X(k):.1f}" cy="{Y(v[0]):.1f}" r="4" fill="{col}" stroke="{SURF}" stroke-width="2"/></g>')
        o.append(text(x0 + PW / 2, y0 + PH + 40, f'n = {d["n_contexts"]} contexts', 11, MUTED, 'middle'))
    lx = 80 + len(panels) * (PW + 40) - 10
    for si, p in enumerate(paths):
        o.append(f'<line x1="{lx}" y1="{y0 + 10 + 22 * si}" x2="{lx + 18}" y2="{y0 + 10 + 22 * si}" stroke="{SLOT[si]}" stroke-width="2"/>')
        o.append(f'<circle cx="{lx + 9}" cy="{y0 + 10 + 22 * si}" r="4" fill="{SLOT[si]}" stroke="{SURF}" stroke-width="2"/>')
        o.append(text(lx + 26, y0 + 14 + 22 * si, f'{p} {PATH_LABEL[p]}', 11, INK1))
    o.append('</svg>')
    return '\n'.join(o)


os.makedirs(f'{D}/out/fig', exist_ok=True)
for name, svg in (('fig_k1_pathways', fig_k1()), ('fig_dose', fig_dose())):
    if not svg: print('skip', name); continue
    open(f'{D}/out/fig/{name}.svg', 'w').write(svg)
    r = subprocess.run(['convert', '-density', '110', f'{D}/out/fig/{name}.svg', f'{D}/out/fig/{name}.png'], capture_output=True, text=True)
    print(name, 'svg ok', '| png', 'ok' if r.returncode == 0 else r.stderr[-300:])
