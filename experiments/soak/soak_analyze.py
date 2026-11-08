"""PREREG_v2.7 §5 soak analysis (frozen with the prereg). Reads DIR/requests_{K1,K2}.jsonl, DIR/monitor_{K1,K2}.jsonl,
DIR/run_{K1,K2}.json and the proxy log directory, and evaluates K-a..K-e exactly as registered.
  soak_analyze.py --dir DIR --proxy_logs PROXYLOGDIR --proxy_scope UNIT --stock_scope UNIT --plugin_scope UNIT --out OUT.json
Definitions:
  ctx400      HTTP 400 whose body mentions the context length (excluded from K-b on every route; counted).
  error       any other non-200 status, or a transport error; 'timeout' (600 s) = a hang.
  repaired    a proxy-routed request whose proxy record (matched by X-E2E-Task) has an 'ipd_repair' event.
  TTLB        t_end - t_start of a 200 response.
  K-e         see call_cats(): proxy gate = 0 delivered calls with 'leak' or 'non_json' (IPD passes strictly-valid
              calls and key-position slips it cannot repair through, known from E2E fullp: 59/63 malformed deliveries
              were key slips like start_line", 0 leaks); plugin gate = 0 'leak'/'non_json'/'bad_key' (strict grammar).
              Schema-only categories and special tokens are reported for every route.
  RSS growth  median VmRSS of the scope over minutes 10-12 vs over the last 2 minutes of the phase (MB)."""
import argparse, glob, json, os, re, sys
import numpy as np
sys.path.insert(0, os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'slipguard/src'))
from slipguard._frozen import load_e  # noqa: E402
qr = load_e().quarantine_renderer
ap = argparse.ArgumentParser()
ap.add_argument('--dir', required=True); ap.add_argument('--proxy_logs', required=True); ap.add_argument('--out', required=True)
ap.add_argument('--proxy_scope', required=True); ap.add_argument('--stock_scope', required=True); ap.add_argument('--plugin_scope', required=True)
ap.add_argument('--pnc', default=os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc'))
a = ap.parse_args()
TOOLS = {s: json.load(open(f'{a.pnc}/contexts/P-swebench-31b-{s}-v1/manifest.json'))['tools'] for s in ('S1', 'S2')}
SCH = {s: qr.tool_schemas(t) for s, t in TOOLS.items()}
NAMES = {s: {t['function']['name'] if 'function' in t else t['name'] for t in TOOLS[s]} for s in TOOLS}
CTRL = ('<|"|>', '<|tool_call>', '<tool_call|>', '<|channel>', '<channel|>', '<|tool_response>', '<tool_response|>', '<|turn>', '<turn|>')
CTX = re.compile(r'context length|maximum context|maximum model length|too long|exceeds the max', re.I)


def jl(p):
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


prox = {}
for f in glob.glob(os.path.join(a.proxy_logs, '*.jsonl')):
    for r in jl(f):
        if str(r.get('task', '')).startswith('soak'): prox[r['task']] = r


def cls(r):
    if r.get('error'): return r['error']
    if r.get('status') == 200: return 'ok'
    if r.get('status') == 400 and CTX.search(r.get('body', '') or ''): return 'ctx400'
    return 'error'


KEY = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def call_cats(c, schema):
    """-> set of categories of a delivered call. PROTOCOL corruption: 'non_json' (arguments not a JSON object),
    'leak' (absorbed look-alike closer + declared key text in a string value: the laundering signature),
    'bad_key' (a key that is not an identifier, e.g. start_line" -- a key-position slip the strict grammar rejects).
    SCHEMA-only (the model's own content errors, delivered by design by strict parsers): 'unknown_tool', 'missing',
    'unknown_key'. Reported: 'special_token' (control-token text inside a value)."""
    try: args = json.loads(c['arguments'] or '{}')
    except Exception: return {'non_json'}  # noqa: BLE001
    if not isinstance(args, dict): return {'non_json'}
    out = set()
    if any(not KEY.match(k) for k in args): out.add('bad_key')
    if c['name'] not in NAMES[schema]: out.add('unknown_tool'); return out
    try: r = qr.classify_args(c['name'], args, SCH[schema])
    except Exception: return out | {'classify_error'}  # noqa: BLE001
    for w in r.get('why') or []:
        out.add('missing' if w.startswith('missing') else w)
    return out


def q(x, p): return float(np.percentile(x, p)) if len(x) else None


def route_stats(rs, label):
    n = len(rs); c = [cls(r) for r in rs]
    ok = [r for r, k in zip(rs, c) if k == 'ok']
    ttlb = np.array([r['t_end'] - r['t_start'] for r in ok])
    calls = [(cc, r['turn'].split('#')[0].rsplit('__', 1)[1]) for r in ok for cc in (r.get('calls') or [])]
    v = [call_cats(cc, s) for cc, s in calls]
    from collections import Counter
    cat = Counter(x for cs in v for x in cs)
    n_eval = n - c.count('ctx400')
    return {'route': label, 'n': n, 'ok': c.count('ok'), 'ctx400': c.count('ctx400'), 'errors': c.count('error'), 'transport': c.count('transport'),
            'hangs_timeout': c.count('timeout'),
            'error_rate_excl_ctx400': round((c.count('error') + c.count('transport') + c.count('timeout')) / n_eval, 5) if n_eval else None,
            'ttlb_median_s': q(ttlb, 50), 'ttlb_p99_s': q(ttlb, 99), 'n_calls': len(calls),
            'calls_protocol_corrupt': sum(1 for cs in v if cs & {'non_json', 'leak', 'bad_key'}),
            'calls_leak_or_nonjson': sum(1 for cs in v if cs & {'non_json', 'leak'}), 'call_categories': dict(cat),
            'error_examples': [r.get('body') or r.get('detail') for r, k in zip(rs, c) if k in ('error', 'transport')][:5]}


def rss_growth(mon, unit, t0, t1):
    s = [(m['t'], (m['scopes'].get(unit) or {}).get('rss_kb')) for m in mon]
    s = [(t, v) for t, v in s if v is not None]
    a_ = [v for t, v in s if t0 + 600 <= t <= t0 + 720]; b_ = [v for t, v in s if t1 - 120 <= t <= t1]
    return round((np.median(b_) - np.median(a_)) / 1024, 1) if a_ and b_ else None


def avail(mon, units):
    bad = [m for m in mon if any(not (m['scopes'].get(u) or {}).get('alive') for u in units) or any(v != 200 for v in m['health'].values())]
    return {'samples': len(mon), 'bad_samples': len(bad), 'first_bad': bad[0] if bad else None}


res = {'_status': 'PREREG_v2.7 §5 (frozen soak analysis)'}
for ph in ('K1', 'K2'):
    rs = jl(f'{a.dir}/requests_{ph}.jsonl'); mon = jl(f'{a.dir}/monitor_{ph}.jsonl'); run = json.load(open(f'{a.dir}/run_{ph}.json'))
    done = json.load(open(f'{a.dir}/run_{ph}.done.json')) if os.path.exists(f'{a.dir}/run_{ph}.done.json') else {}
    t0, t1 = run['start'], run['start'] + 60 * run['args']['minutes']
    o = {'n_requests': len(rs), 'submitted': done.get('submitted'), 'minutes': run['args']['minutes'], 'conc': run['args']['conc']}
    if ph == 'K1':
        d = [r for r in rs if r['route'] == 'direct']; p = [r for r in rs if r['route'] == 'proxy']
        for r in p: r['repaired'] = any((e or {}).get('ev') == 'ipd_repair' for e in (prox.get(f"soakK1:{r['k']}") or {}).get('events') or [])
        o['proxy_records_matched'] = sum(1 for r in p if f"soakK1:{r['k']}" in prox)
        o['direct'] = route_stats(d, 'direct stock'); o['proxy'] = route_stats(p, 'proxy fullp')
        o['proxy_repaired_n'] = sum(r['repaired'] for r in p)
        o['proxy_not_repaired'] = route_stats([r for r in p if not r['repaired']], 'proxy fullp, not repaired')
        o['proxy_repaired'] = route_stats([r for r in p if r['repaired']], 'proxy fullp, repaired')
        md, pd_ = o['direct']['ttlb_median_s'], o['proxy_not_repaired']['ttlb_median_s']
        o['latency_ratio_median'] = round(pd_ / md, 4) if md and pd_ else None
        o['latency_ratio_p99'] = round(o['proxy_not_repaired']['ttlb_p99_s'] / o['direct']['ttlb_p99_s'], 4) if o['direct']['ttlb_p99_s'] else None
        o['rss_growth_mb'] = {'proxy': rss_growth(mon, a.proxy_scope, t0, t1), 'stock_server': rss_growth(mon, a.stock_scope, t0, t1)}
        o['availability'] = avail(mon, [a.proxy_scope, a.stock_scope])
    else:
        o['plugin'] = route_stats(rs, 'plugin server')
        o['rss_growth_mb'] = {'plugin_server': rss_growth(mon, a.plugin_scope, t0, t1)}
        o['availability'] = avail(mon, [a.plugin_scope])
    res[ph] = o
K1, K2 = res['K1'], res['K2']
crit = {
    'K-a': K1['availability']['bad_samples'] == 0 and K2['availability']['bad_samples'] == 0
           and K1['proxy']['hangs_timeout'] == 0 and K2['plugin']['hangs_timeout'] == 0,
    'K-b': (K1['proxy']['error_rate_excl_ctx400'] <= K1['direct']['error_rate_excl_ctx400'] + 0.005)
           and K2['plugin']['error_rate_excl_ctx400'] <= 0.005,
    'K-c': K1['latency_ratio_median'] is not None and K1['latency_ratio_median'] <= 1.15 and K1['latency_ratio_p99'] <= 1.50,
    'K-d': K1['rss_growth_mb']['proxy'] is not None and K1['rss_growth_mb']['proxy'] <= 256
           and K2['rss_growth_mb']['plugin_server'] is not None and K1['rss_growth_mb']['stock_server'] is not None
           and K2['rss_growth_mb']['plugin_server'] <= K1['rss_growth_mb']['stock_server'] + 512,
    'K-e': K1['proxy']['calls_leak_or_nonjson'] == 0 and K2['plugin']['calls_protocol_corrupt'] == 0}
res['criteria'] = crit
res['verdict'] = 'SOAK PASS' if all(crit.values()) else 'FAIL: ' + ', '.join(k for k, v in crit.items() if not v)
res['reported_not_gated'] = {'direct_stock_hangs': K1['direct']['hangs_timeout'], 'direct_stock_protocol_corrupt_calls': [K1['direct']['calls_protocol_corrupt'], K1['direct']['n_calls']],
                             'proxy_key_slip_passthrough': [K1['proxy']['calls_protocol_corrupt'] - K1['proxy']['calls_leak_or_nonjson'], K1['proxy']['n_calls']],
                             'plugin_vs_K1_direct_median_ttlb': [K2['plugin']['ttlb_median_s'], K1['direct']['ttlb_median_s']]}
json.dump(res, open(a.out, 'w'), indent=1, default=str)
print(json.dumps({'verdict': res['verdict'], 'criteria': crit, 'reported': res['reported_not_gated']}, indent=1, default=str))
