"""PREREG_v2.7 §5 soak / stress driver. Replays PNC recorded chat requests (messages + the episode's tool schema) against
live servers for a fixed wall time and records one line per request, plus a 10-second monitor line (health of every
endpoint, liveness and summed VmRSS of each named systemd scope). Frozen with PREREG_v2.7 (sha in PROGRESS.md).

  soak_drive.py --phase K1 --direct http://127.0.0.1:PORT/v1 [--proxy http://127.0.0.1:PPORT/fullp/v1 --route_p 0.5]
                --model gemma-4-31b --minutes 60 --conc 48 --out DIR [--scopes unitA,unitB] [--health URL,URL]

Request = recorded messages + tools of that schema; sampling = the recorded temperature/top_p/top_k/seed;
chat_template_kwargs as recorded; max_tokens = min(recorded, 2048); thinking_token_budget dropped (not a vLLM field).
Order: all 41,290 PNC turns shuffled with --seed (default 20261106), consumed cyclically. Route (direct / proxy) and
stream (yes / no) are drawn per request from random.Random(seed + 1) and (seed + 2), so they are exchangeable.
Per request: route, stream, status, error class, t_start, t_end, ttft (stream), finish_reason, delivered tool calls
(name + raw arguments string), content length, usage. Timeout 600 s (= a hang)."""
import argparse, asyncio, glob, json, os, random, subprocess, time
import httpx

ap = argparse.ArgumentParser()
ap.add_argument('--phase', required=True); ap.add_argument('--direct', required=True); ap.add_argument('--proxy', default='')
ap.add_argument('--route_p', type=float, default=0.5); ap.add_argument('--model', default='gemma-4-31b')
ap.add_argument('--minutes', type=float, default=60); ap.add_argument('--conc', type=int, default=48)
ap.add_argument('--out', required=True); ap.add_argument('--seed', type=int, default=20261106)
ap.add_argument('--pnc', default=os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/pnc')); ap.add_argument('--max_tokens', type=int, default=2048)
ap.add_argument('--scopes', default=''); ap.add_argument('--health', default=''); ap.add_argument('--timeout', type=float, default=600)
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
TOOLS = {s: json.load(open(f'{a.pnc}/contexts/P-swebench-31b-{s}-v1/manifest.json'))['tools'] for s in ('S1', 'S2')}
TURNS = []
for f in sorted(glob.glob(f'{a.pnc}/episodes/*.jsonl')):
    for i, l in enumerate(open(f, encoding='utf-8')):
        TURNS.append((f, i))
random.Random(a.seed).shuffle(TURNS)
R_ROUTE, R_STREAM = random.Random(a.seed + 1), random.Random(a.seed + 2)
_cache = {}


def load_turn(f, i):
    if f not in _cache:
        if len(_cache) > 64: _cache.clear()
        _cache[f] = open(f, encoding='utf-8').read().splitlines()
    return json.loads(_cache[f][i])


def build(d):
    p = dict(d['request']['params']); p.pop('thinking_token_budget', None)
    body = {**p, 'model': a.model, 'messages': d['request']['messages'], 'tools': TOOLS[d['schema']],
            'max_tokens': min(int(p.get('max_tokens') or a.max_tokens), a.max_tokens)}
    return body


async def one(client, k, f, i, fo, route, stream):
    d = load_turn(f, i)
    base = a.proxy if route == 'proxy' else a.direct
    body = build(d); body['stream'] = stream
    rec = {'k': k, 'phase': a.phase, 'turn': f"{d['episode_id']}#{d['turn_index']}", 'route': route, 'stream': stream, 't_start': time.time()}
    try:
        if not stream:
            r = await client.post(f'{base}/chat/completions', json=body, headers={'X-E2E-Task': f'soak{a.phase}:{k}'})
            rec['status'] = r.status_code
            if r.status_code == 200:
                j = r.json(); ch = j['choices'][0]; m = ch['message']
                rec.update(finish=ch.get('finish_reason'), content_len=len(m.get('content') or ''), usage=j.get('usage'),
                           calls=[{'name': c['function']['name'], 'arguments': c['function']['arguments']} for c in (m.get('tool_calls') or [])])
            else:
                rec['body'] = r.text[:400]
        else:
            calls, content, fin, ttft = {}, 0, None, None
            async with client.stream('POST', f'{base}/chat/completions', json=body, headers={'X-E2E-Task': f'soak{a.phase}:{k}'}) as r:
                rec['status'] = r.status_code
                if r.status_code != 200:
                    rec['body'] = (await r.aread()).decode(errors='replace')[:400]
                else:
                    async for line in r.aiter_lines():
                        if not line.startswith('data: '): continue
                        x = line[6:]
                        if x.strip() == '[DONE]': break
                        j = json.loads(x)
                        if not j.get('choices'):
                            if j.get('usage'): rec['usage'] = j['usage']
                            continue
                        if ttft is None: ttft = time.time() - rec['t_start']
                        ch = j['choices'][0]; dl = ch.get('delta') or {}
                        content += len(dl.get('content') or '')
                        for tc in dl.get('tool_calls') or []:
                            c = calls.setdefault(tc.get('index', 0), {'name': '', 'arguments': ''})
                            fn = tc.get('function') or {}
                            c['name'] += fn.get('name') or ''; c['arguments'] += fn.get('arguments') or ''
                        fin = ch.get('finish_reason') or fin
            if rec['status'] == 200:
                rec.update(finish=fin, content_len=content, ttft=ttft, calls=[calls[x] for x in sorted(calls)])
    except httpx.TimeoutException as e:
        rec['error'] = 'timeout'; rec['detail'] = type(e).__name__
    except Exception as e:  # noqa: BLE001
        rec['error'] = 'transport'; rec['detail'] = f'{type(e).__name__}: {str(e)[:200]}'
    rec['t_end'] = time.time()
    fo.write(json.dumps(rec) + '\n'); fo.flush()


def scope_rss(unit):
    try:
        cg = subprocess.run(['systemctl', '--user', 'show', '-p', 'ControlGroup', '--value', unit], capture_output=True, text=True, timeout=10).stdout.strip()
        pids = open(f'/sys/fs/cgroup{cg}/cgroup.procs').read().split()
    except Exception:  # noqa: BLE001
        return {'alive': False, 'rss_kb': None, 'n_procs': 0}
    rss = 0
    for p in pids:
        try:
            for l in open(f'/proc/{p}/status'):
                if l.startswith('VmRSS:'): rss += int(l.split()[1])
        except Exception:  # noqa: BLE001
            pass
    return {'alive': len(pids) > 0, 'rss_kb': rss, 'n_procs': len(pids)}


async def monitor(stop, fm):
    async with httpx.AsyncClient(timeout=5) as c:
        while not stop.is_set():
            rec = {'t': time.time(), 'health': {}, 'scopes': {}}
            for h in [x for x in a.health.split(',') if x]:
                try: rec['health'][h] = (await c.get(h)).status_code
                except Exception as e: rec['health'][h] = f'ERR {type(e).__name__}'  # noqa: BLE001
            for u in [x for x in a.scopes.split(',') if x]:
                rec['scopes'][u] = scope_rss(u)
            fm.write(json.dumps(rec) + '\n'); fm.flush()
            try: await asyncio.wait_for(stop.wait(), 10)
            except asyncio.TimeoutError: pass


async def main():
    t_end = time.time() + 60 * a.minutes
    fo = open(f'{a.out}/requests_{a.phase}.jsonl', 'a'); fm = open(f'{a.out}/monitor_{a.phase}.jsonl', 'a')
    json.dump({'args': vars(a), 'n_turns': len(TURNS), 'start': time.time()}, open(f'{a.out}/run_{a.phase}.json', 'w'))
    stop = asyncio.Event(); mon = asyncio.create_task(monitor(stop, fm))
    lim = httpx.Limits(max_connections=a.conc * 2, max_keepalive_connections=a.conc * 2)
    async with httpx.AsyncClient(timeout=httpx.Timeout(a.timeout, connect=30), limits=lim) as client:
        sem = asyncio.Semaphore(a.conc); tasks = set(); k = 0
        while time.time() < t_end:
            await sem.acquire()
            f, i = TURNS[k % len(TURNS)]
            route = 'proxy' if (a.proxy and R_ROUTE.random() < a.route_p) else 'direct'
            stream = R_STREAM.random() < 0.5
            t = asyncio.create_task(one(client, k, f, i, fo, route, stream)); tasks.add(t)
            t.add_done_callback(lambda x: (tasks.discard(x), sem.release()))
            k += 1
        print(f'{a.phase}: submitted {k}; draining {len(tasks)} in flight', flush=True)
        if tasks: await asyncio.wait(tasks)
    stop.set(); await mon
    json.dump({'args': vars(a), 'n_turns': len(TURNS), 'submitted': k, 'end': time.time()}, open(f'{a.out}/run_{a.phase}.done.json', 'w'))
    print(f'finished {a.phase} {k} requests', flush=True)


asyncio.run(main())
