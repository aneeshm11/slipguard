"""slipguard weight audit / repair — library entry points (pre-freeze; wrapped by slipguard.weights).

    audit_checkpoint(model=None, *, endpoint=None, served_name=None, reference=None, pack=CORE, split='heldout',
                     mode='endpoint'|'hf'|'weights', device='cuda') -> certificate dict
    repair_adapter(model, out_dir, *, reference, pack=CORE, extractions=None, device='cuda', **solver_opts)
                     -> (adapter_dir, certificate dict)

Certificate schema: slipguard.weights.certificate/v1 (fields agreed with workstream L)."""
import hashlib, json, os, subprocess, sys, time, glob
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H)
CORE = os.path.join(H, 'data', 'core_items.jsonl')
VERSION = 'wsa-0.1'


def _sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def _model_id(d):
    if not d or not os.path.isdir(d):
        return None
    idx = os.path.join(d, 'model.safetensors.index.json')
    return {'config_sha256': _sha(os.path.join(d, 'config.json')) if os.path.exists(os.path.join(d, 'config.json')) else None,
            'index_sha256': _sha(idx) if os.path.exists(idx) else None,
            'shards': len(glob.glob(os.path.join(d, '*.safetensors')))}


def _cert(kind, model, metrics, checks, extra=None, pack=CORE):
    return {'schema': 'slipguard.weights.certificate/v1', 'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'tool': {'name': 'slipguard-weights', 'version': VERSION, 'kind': kind},
            'model': _model_id(model) if model else None,
            'decision_points': {'pack_sha256': _sha(pack), 'source': 'PNC (public corpus, CC BY 4.0)', 'split_rule': 'sha256(episode_id) parity'},
            'metrics': metrics, 'checks': checks, 'verdict': all(c['pass'] for c in checks) if checks else None, **(extra or {})}


def audit_checkpoint(model=None, *, endpoint=None, served_name=None, reference=None, pack=CORE, split='heldout', mode='endpoint',
                     device='cuda', max_total=None, conc=8, slip_threshold=None):
    if mode == 'endpoint':
        from audit import audit_checkpoint as _ep
        m = _ep(endpoint, served_name, split=split, items=pack, conc=conc, max_total=max_total)
    elif mode == 'weights':
        out = subprocess.run([sys.executable, os.path.join(H, 'weights_proxy.py'), '--out', '/dev/stdout'], capture_output=True, text=True)
        m = {'weights_proxy_stdout': out.stdout[-4000:], 'note': 'screen only: blind to PTQ (keeps the bf16 embedding)'}
    elif mode == 'hf':
        raise NotImplementedError('hf mode: run hf_extract.py --arm <arm> then t1_scores.py (generic --model_dir pending at freeze)')
    else:
        raise ValueError(mode)
    checks = []
    se = (m.get('string_end_closers') or {})
    if slip_threshold is not None and se.get('E_slip_T1'):
        checks.append({'id': 'E_slip', 'metric': 'mean look-alike prob per string end (T=1)', 'value': se['E_slip_T1'][0],
                       'threshold': slip_threshold, 'pass': se['E_slip_T1'][0] <= slip_threshold})
    return _cert('audit', model, m, checks)


def repair_adapter(model, out_dir, *, reference, pack=CORE, extractions=None, device='cuda', lam=1.0, rho=0.0, alpha=1.0, iters=0):
    """extractions = (quantized .pt, teacher .pt) from hf_extract.py; the closed-form solve is CPU-only."""
    if extractions is None:
        raise NotImplementedError('run hf_extract.py for the quantized model and the teacher first (GPU), then pass extractions=')
    qat, teacher = extractions
    cmd = [sys.executable, os.path.join(H, 'repair_memit.py'), '--qat', qat, '--teacher', teacher, '--lams', str(lam), '--rhos', str(rho),
           '--alphas', str(alpha), '--iters', str(iters), '--eval_split', 'heldout', '--save_adapter', out_dir,
           '--out', os.path.join(out_dir, 'repair_eval.json')]
    if model and os.path.isdir(model):
        cmd += ['--embed', model]
    subprocess.run(cmd, check=True)
    ev = json.load(open(os.path.join(out_dir, 'repair_eval.json')))['results'][0]
    se = ev['string_end']
    checks = [{'id': 'slip_reduction', 'metric': 'held-out E_slip reduction vs base', 'value': se['reduction'], 'threshold': 0.5, 'pass': se['reduction'] >= 0.5}]
    for name in ('generic_pnc', 'generic_wikitext'):
        if name in ev:
            checks.append({'id': f'{name}_dNLL', 'metric': 'held-out next-token NLL change (nats)', 'value': ev[name]['dNLL_mean'],
                           'threshold': 0.01, 'pass': ev[name]['dNLL_mean'] <= 0.01})
    files = sorted(glob.glob(os.path.join(out_dir, 'adapter_*')))
    cert = _cert('repair', model, ev, checks, extra={'adapter': {f.split('/')[-1]: _sha(f) for f in files},
                                                    'solver': json.load(open(os.path.join(out_dir, 'repair_certificate.json')))})
    json.dump(cert, open(os.path.join(out_dir, 'certificate.json'), 'w'), indent=1)
    return out_dir, cert
