"""Reference model-free machinery for Gemma-4 tool calls (escape-free <|"|> strings).

  call := 'call:' NAME '{' [pair (',' pair)*] '}'        pair := KEY ':' value
  value := <|"|> any-text-without-<|"|> <|"|>  |  {pairs}  |  [values]  |  true|false|null|number

Provides
  * parse_strict(text)              -> StrictParse  (structure only; whitespace between structural tokens tolerated)
  * schema_problems(parse, schema)  -> list of schema violations (unknown tool/key, duplicate, missing required, type)
  * is_valid(text, schema)          -> structurally strict AND schema valid  (the GUARD: such calls are never altered)
  * first_slip_site(text, schema, finished)      -> SlipSite for decode-time rollback (algorithm i)
  * repair_candidates(text, schema, finished)    -> complete relaxed parses for likelihood repair (algorithm ii)
  * render_call(name, pairs)        -> canonical text 'call:NAME{k:<|"|>v<|"|>,...}' (no <|tool_call> wrappers)

A *slip site* is a look-alike closer run  L  (characters from ` " ' \\ , possibly empty) inside a <|"|>-opened
top-level string, IMMEDIATELY followed by protocol structure:
   (a) [ws] ',' [ws] KEY [ws] ':'   where KEY is declared for the tool, not yet emitted, != current key, and the
       text right after ':' opens a value of KEY's type (for string KEYs this means the strict closer <|"|> of the
       current string is exactly KEY's opener), or
   (b) [ws] '}' [ws] END            (the final argument closed by a look-alike, then the call closed).
Cut candidates inside the run: content keeps run[:k], the closer is run[k:], for k = 0..len(run).
"""
from __future__ import annotations
import json, re
from dataclasses import dataclass, field

D = '<|"|>'
TC_START = '<|tool_call>'
TC_END = '<tool_call|>'
LOOKALIKE = set('`"\'\\')
WS = ' \t\n\r'
_KEY_RE = re.compile(r'[A-Za-z_][A-Za-z0-9_\-\.]*')
_NAME_RE = re.compile(r'call:([\w\-\.]+)\{')
_BARE_RE = re.compile(r'(true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)')


# ----------------------------------------------------------------------------------------------- schema
def schema_from_tools(tools):
    """OpenAI-style tool list -> {name: {'props': {key: type-or-None}, 'required': [...]} }"""
    out = {}
    for t in tools or []:
        f = t.get('function', t)
        p = (f.get('parameters') or {})
        props = {}
        for k, v in (p.get('properties') or {}).items():
            ty = v.get('type') if isinstance(v, dict) else None
            if isinstance(ty, list):
                ty = [x for x in ty if x != 'null']
                ty = ty[0] if len(ty) == 1 else None
            props[k] = {'type': ty, 'nullable': bool(isinstance(v, dict) and (v.get('nullable') or 'null' in str(v.get('type'))))}
        out[f['name']] = {'props': props, 'required': list(p.get('required') or [])}
    return out


# ----------------------------------------------------------------------------------------------- strict parse
class ParseError(Exception):
    def __init__(self, msg, pos):
        super().__init__(msg)
        self.pos = pos


@dataclass
class Pair:
    key: str
    value: object
    kind: str            # 'str' | 'bare' | 'obj' | 'arr'
    vstart: int          # start of the value text (opener for strings)
    vend: int            # end (exclusive) of the value text (after closer for strings)


@dataclass
class StrictParse:
    ok: bool
    name: str | None = None
    pairs: list = field(default_factory=list)
    error: str = ''
    pos: int = -1

    def args(self):
        return {p.key: p.value for p in self.pairs}


def _ws(s, i):
    while i < len(s) and s[i] in WS:
        i += 1
    return i


def _parse_value(s, i):
    if s.startswith(D, i):
        j = s.find(D, i + len(D))
        if j == -1:
            raise ParseError('unterminated string', i)
        return s[i + len(D):j], 'str', j + len(D)
    if i >= len(s):
        raise ParseError('missing value', i)
    c = s[i]
    if c == '{':
        obj, j = _parse_pairs(s, i + 1, '}')
        return obj, 'obj', j
    if c == '[':
        arr = []
        j = _ws(s, i + 1)
        if j < len(s) and s[j] == ']':
            return arr, 'arr', j + 1
        while True:
            v, _, j = _parse_value(s, _ws(s, j))
            arr.append(v)
            j = _ws(s, j)
            if j < len(s) and s[j] == ',':
                j += 1; continue
            if j < len(s) and s[j] == ']':
                return arr, 'arr', j + 1
            raise ParseError('bad array', j)
    m = _BARE_RE.match(s, i)
    if m:
        j = m.end()
        k = _ws(s, j)
        if k >= len(s) or s[k] in ',}]':
            t = m.group(1)
            v = True if t == 'true' else False if t == 'false' else None if t == 'null' else (float(t) if any(x in t for x in '.eE') else int(t))
            return v, 'bare', j
    raise ParseError('bad value', i)


def _parse_pairs(s, i, close):
    out = {}
    i = _ws(s, i)
    if i < len(s) and s[i] == close:
        return out, i + 1
    while True:
        i = _ws(s, i)
        m = _KEY_RE.match(s, i)
        if not m:
            raise ParseError('bad key', i)
        k = m.group(0)
        i = _ws(s, m.end())
        if i >= len(s) or s[i] != ':':
            raise ParseError('missing colon', i)
        v, _, i = _parse_value(s, _ws(s, i + 1))
        out[k] = v
        i = _ws(s, i)
        if i < len(s) and s[i] == ',':
            i += 1; continue
        if i < len(s) and s[i] == close:
            return out, i + 1
        raise ParseError('expected , or ' + close, i)


def parse_strict(text):
    """Strict structural parse of 'call:NAME{...}' (wrappers <|tool_call>/<tool_call|> must be stripped).
    Duplicate keys are kept in `pairs` (schema_problems flags them)."""
    m = _NAME_RE.match(text)
    if not m:
        return StrictParse(False, error='no call header', pos=0)
    name = m.group(1)
    s = text
    i = m.end()
    pairs = []
    try:
        i = _ws(s, i)
        if i < len(s) and s[i] == '}':
            i += 1
        else:
            while True:
                i = _ws(s, i)
                km = _KEY_RE.match(s, i)
                if not km:
                    raise ParseError('bad key', i)
                k = km.group(0)
                i = _ws(s, km.end())
                if i >= len(s) or s[i] != ':':
                    raise ParseError('missing colon', i)
                vs = _ws(s, i + 1)
                v, kind, i = _parse_value(s, vs)
                pairs.append(Pair(k, v, kind, vs, i))
                i = _ws(s, i)
                if i < len(s) and s[i] == ',':
                    i += 1; continue
                if i < len(s) and s[i] == '}':
                    i += 1; break
                raise ParseError('expected , or }', i)
        if _ws(s, i) != len(s):
            raise ParseError('trailing text after call', i)
    except ParseError as e:
        return StrictParse(False, name, pairs, str(e), e.pos)
    return StrictParse(True, name, pairs)


def _type_ok(v, kind, spec):
    ty = (spec or {}).get('type')
    if v is None:
        return bool((spec or {}).get('nullable')) or ty is None
    if ty is None:
        return True
    ty = str(ty).lower()
    if ty == 'string':
        return kind == 'str'
    if ty == 'boolean':
        return isinstance(v, bool)
    if ty == 'integer':
        return isinstance(v, int) and not isinstance(v, bool)
    if ty == 'number':
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if ty == 'array':
        return kind == 'arr'
    if ty == 'object':
        return kind == 'obj'
    return True


def schema_problems(sp: StrictParse, schema):
    probs = []
    if sp.name not in schema:
        return ['unknown_tool:%s' % sp.name]
    sc = schema[sp.name]
    seen = set()
    for p in sp.pairs:
        if p.key in seen:
            probs.append('duplicate:' + p.key)
        seen.add(p.key)
        if p.key not in sc['props']:
            probs.append('unknown_key:' + p.key)
        elif not _type_ok(p.value, p.kind, sc['props'][p.key]):
            probs.append('type:' + p.key)
    for r in sc['required']:
        if r not in seen:
            probs.append('missing:' + r)
    return probs


def is_valid(text, schema):
    sp = parse_strict(text)
    return sp.ok and not schema_problems(sp, schema)


# ----------------------------------------------------------------------------------------------- rendering
def fmt_value(v, kind=None):
    if kind == 'str' or isinstance(v, str):
        return D + v + D
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return json.dumps(v)
    if isinstance(v, dict):
        return '{' + ','.join(f'{k}:{fmt_value(x)}' for k, x in v.items()) + '}'
    if isinstance(v, list):
        return '[' + ','.join(fmt_value(x) for x in v) + ']'
    return str(v)


def render_call(name, pairs):
    """pairs: list of (key, value, kind) in emission order -> canonical call text without wrappers."""
    return 'call:' + name + '{' + ','.join(f'{k}:{fmt_value(v, kd)}' for k, v, kd in pairs) + '}'


def render_template_order(name, args: dict):
    """What the chat template re-renders into history (dictsort of keys)."""
    return 'call:' + name + '{' + ','.join(f'{k}:{fmt_value(args[k])}' for k in sorted(args)) + '}'


# ----------------------------------------------------------------------------------------------- slip sites
@dataclass
class SlipSite:
    key: str             # the string argument whose closer slipped
    content_start: int   # index of first content char of that string
    run_start: int       # start of the look-alike run (content end if k=0)
    run: str             # look-alike run (may be '')
    gap: str             # whitespace between run and the structural continuation (part of the closer)
    struct_pos: int      # index where protocol structure resumes (',' or '}')
    kind: str            # 'key' | 'end'
    next_key: str | None = None
    def cut_positions(self):
        """absolute positions at which the true delimiter may be inserted (content = text[content_start:pos]).
        Capped for pathological runs: the whole-run cut plus the last MAX_TAIL_CUTS boundaries (closers are short)."""
        n = len(self.run) + len(self.gap) + 1
        if n <= MAX_TAIL_CUTS + 1:
            return [self.run_start + k for k in range(n)]
        return [self.run_start] + [self.run_start + k for k in range(n - MAX_TAIL_CUTS, n)]

    def closer_for(self, cp):
        """look-alike closer implied by inserting the delimiter at absolute position cp (gap whitespace excluded)."""
        k = cp - self.run_start
        return self.run[k:] if 0 <= k <= len(self.run) else ''


def _look_run_before(s, lo, j):
    """maximal look-alike run ending at j (exclusive), not crossing lo; returns start index."""
    k = j
    while k > lo and s[k - 1] in LOOKALIKE:
        k -= 1
    return k


def _value_opener_ok(s, q, spec):
    """does text at q open a value compatible with spec?  (q = position right after KEY ':' and ws)"""
    ty = str((spec or {}).get('type') or '').lower()
    if ty == 'string':
        return s.startswith(D, q)
    if ty in ('boolean', 'integer', 'number'):
        m = _BARE_RE.match(s, q)
        if not m:
            return False
        k = _ws(s, m.end())
        return k >= len(s) or s[k] in ',}'
    if ty == 'array':
        return q < len(s) and s[q] == '['
    if ty == 'object':
        return q < len(s) and s[q] == '{'
    return s.startswith(D, q) or bool(_BARE_RE.match(s, q)) or (q < len(s) and s[q] in '[{')


MAX_TAIL_CUTS = 7
REPAIR_BUDGET = 20000
_KEYCONT = re.compile(r'([ \t\r\n]*),[ \t\r\n]*([A-Za-z_][A-Za-z0-9_\-\.]*)[ \t\r\n]*:[ \t\r\n]*')


def sites_in_string(s, key, content_start, region_end, emitted, schema_tool, finished, unterminated):
    """All slip sites inside one top-level string whose content spans [content_start, region_end)."""
    props = schema_tool['props'] if schema_tool else {}
    out = []
    # (a) closer run + ',' + declared, not-yet-emitted key + ':' + compatible value opener
    for m in _KEYCONT.finditer(s, content_start, len(s)):
        comma_ws_start = m.start()
        if comma_ws_start >= region_end:
            break
        k2 = m.group(2)
        if k2 == key or k2 in emitted or k2 not in props:
            continue
        q = m.end()
        # string-typed next key: its opener must be the strict closer of the current string (q == region_end)
        if not _value_opener_ok(s, q, props[k2]):
            continue
        ty = str(props[k2].get('type') or '').lower()
        if ty == 'string' and q != region_end:
            continue
        if ty != 'string' and q > region_end:
            continue
        rs = _look_run_before(s, content_start, comma_ws_start)
        out.append(SlipSite(key, content_start, rs, s[rs:comma_ws_start], m.group(1), comma_ws_start + len(m.group(1)), 'key', k2))
    # (b) closer run + '}' + END  (only for an unterminated final string in a finished call)
    if unterminated and finished:
        t = s[content_start:region_end].rstrip(WS)
        if t.endswith('}'):
            br = content_start + len(t) - 1
            j = br
            while j > content_start and s[j - 1] in WS:
                j -= 1
            rs = _look_run_before(s, content_start, j)
            out.append(SlipSite(key, content_start, rs, s[rs:j], s[j:br], br, 'end', None))
    return out


def _scan_first_site(text, schema, finished=True):
    """Left-to-right strict reading; the first string whose strict closer is NOT locally consistent (or which is
    unterminated) is searched for a slip site.  Local consistency = the closer is followed by ',' + a declared key + ':'
    or by '}' + end of call."""
    m = _NAME_RE.match(text)
    if not m or m.group(1) not in schema:
        return None
    sc = schema[m.group(1)]
    s = text
    i = m.end()
    emitted = []
    while True:
        i = _ws(s, i)
        if i >= len(s) or s[i] == '}':
            return None
        km = _KEY_RE.match(s, i)
        if not km:
            return None
        k = km.group(0)
        i = _ws(s, km.end())
        if i >= len(s) or s[i] != ':':
            return None
        vs = _ws(s, i + 1)
        if s.startswith(D, vs):
            cs = vs + len(D)
            e = s.find(D, cs)
            unterm = e == -1
            region_end = len(s) if unterm else e
            if not unterm:
                j = _ws(s, e + len(D))
                nk = _KEY_RE.match(s, _ws(s, j + 1)) if (j < len(s) and s[j] == ',') else None
                locally_ok = (nk is not None and nk.group(0) in sc['props'] and _ws(s, nk.end()) < len(s)
                              and s[_ws(s, nk.end())] == ':') or (j < len(s) and s[j] == '}' and _ws(s, j + 1) == len(s))
                if locally_ok:
                    emitted.append(k)
                    i = j
                    if s[i] == ',':
                        i += 1; continue
                    return None
            sites = sites_in_string(s, k, cs, region_end, set(emitted), sc, finished, unterm)
            return sites[0] if sites else None
        else:
            try:
                _, _, i = _parse_value(s, vs)
            except ParseError:
                return None
            emitted.append(k)
            i = _ws(s, i)
        if i < len(s) and s[i] == ',':
            i += 1; continue
        return None


def first_slip_site(text, schema, finished=True):
    """Decode-time detector (algorithm i). Returns None for every strictly valid call (GUARD).  Otherwise:
    if complete minimal relaxed parses exist (global evidence), the site of the earliest cut among them;
    else the first slip site on the strict left-to-right reading (_scan_first_site).
    Everything after the returned site is regenerated by the model."""
    if is_valid(text, schema):
        return None
    cands = repair_candidates(text, schema, finished=finished, max_cost=3)
    best = None
    for c in cands:
        if c.sites and (best is None or c.cuts[0][1] < best[0]):
            best = (c.cuts[0][1], c.sites[0])
    if best is not None:
        return best[1]
    return _scan_first_site(text, schema, finished)


# ----------------------------------------------------------------------------------------------- opener drift (extension i+)
@dataclass
class OpenerSite:
    """A declared STRING argument whose value does not start with the true delimiter (the model wrote a JSON/Python
    literal or bare text instead).  Rollback point = right after 'KEY:' ; the true delimiter is forced there."""
    key: str
    colon_end: int
    vstart: int
    lead: str
    kind: str = 'opener'
    force: str = D          # canonical text forced at the rollback point


def first_opener_site(text, schema):
    if is_valid(text, schema):
        return None
    m = _NAME_RE.match(text)
    if not m or m.group(1) not in schema:
        return None
    sc = schema[m.group(1)]
    s = text
    i = m.end()
    while True:
        i = _ws(s, i)
        if i >= len(s) or s[i] == '}':
            return None
        km = _KEY_RE.match(s, i)
        if not km:
            return None
        k = km.group(0)
        i = _ws(s, km.end())
        if i >= len(s) or s[i] != ':':
            return None
        vs = _ws(s, i + 1)
        spec = sc['props'].get(k)
        if spec is not None and str(spec.get('type') or '').lower() == 'string' and not s.startswith(D, vs):
            return OpenerSite(k, i + 1, vs, s[vs:vs + 6])
        if s.startswith(D, vs):
            e = s.find(D, vs + len(D))
            if e == -1:
                return None
            j = _ws(s, e + len(D))
            nk = _KEY_RE.match(s, _ws(s, j + 1)) if (j < len(s) and s[j] == ',') else None
            if nk is not None and nk.group(0) in sc['props']:
                i = j + 1; continue
            return None
        try:
            _, _, i = _parse_value(s, vs)
        except ParseError:
            return None
        i = _ws(s, i)
        if i < len(s) and s[i] == ',':
            i += 1; continue
        return None


_QKEYCONT = re.compile(r'([ \t\r\n]*),[ \t\r\n]*(["\'])([A-Za-z_][A-Za-z0-9_\-\.]*)\2[ \t\r\n]*:')


def first_kwarg_site(text, schema):
    """EXTENSION (opt-in rule 'kwarg'): Python-kwargs drift at a top-level key position, e.g. `filepath="x.py"`.
    Scans the strict reading left to right; at the first declared KEY followed by '=' instead of ':', the rollback point
    is right after KEY and the forced text is ':' + <|"|> (string-typed) or ':' (other types)."""
    if is_valid(text, schema):
        return None
    m = _NAME_RE.match(text)
    if not m or m.group(1) not in schema:
        return None
    sc = schema[m.group(1)]
    s = text
    i = m.end()
    while True:
        i = _ws(s, i)
        km = _KEY_RE.match(s, i)
        if not km:
            return None
        k = km.group(0)
        j = _ws(s, km.end())
        if j < len(s) and s[j] == '=' and k in sc['props']:
            ty = str(sc['props'][k].get('type') or '').lower()
            return OpenerSite(k, km.end(), j, s[j:j + 6], kind='kwarg', force=':' + (D if ty == 'string' else ''))
        if j >= len(s) or s[j] != ':':
            return None
        vs = _ws(s, j + 1)
        try:
            _, _, i = _parse_value(s, vs)
        except ParseError:
            return None
        i = _ws(s, i)
        if i < len(s) and s[i] == ',':
            i += 1; continue
        return None


def first_qkey_site(text, schema):
    """EXTENSION (opt-in rule 'qkey'): JSON-mode slip inside a top-level string: a look-alike run followed by
    `, "KEY":` (quoted, declared, not yet emitted key).  Returned as a SlipSite (kind 'key'), so the deployed
    noisy-channel cut + resume applies; the canonical continuation uses the bare key."""
    if is_valid(text, schema):
        return None
    m = _NAME_RE.match(text)
    if not m or m.group(1) not in schema:
        return None
    sc = schema[m.group(1)]
    s = text
    i = m.end()
    emitted = set()
    while True:
        i = _ws(s, i)
        km = _KEY_RE.match(s, i)
        if not km:
            return None
        k = km.group(0)
        j = _ws(s, km.end())
        if j >= len(s) or s[j] != ':':
            return None
        vs = _ws(s, j + 1)
        if s.startswith(D, vs):
            cs = vs + len(D)
            e = s.find(D, cs)
            region_end = len(s) if e == -1 else e
            for qm in _QKEYCONT.finditer(s, cs, region_end):
                k2 = qm.group(3)
                if k2 == k or k2 in emitted or k2 not in sc['props']:
                    continue
                rs = _look_run_before(s, cs, qm.start())
                return SlipSite(k, cs, rs, s[rs:qm.start()], qm.group(1), qm.start() + len(qm.group(1)), 'key', k2)
            if e == -1:
                return None
            emitted.add(k)
            i = _ws(s, e + len(D))
        else:
            try:
                _, _, i = _parse_value(s, vs)
            except ParseError:
                return None
            emitted.add(k)
            i = _ws(s, i)
        if i < len(s) and s[i] == ',':
            i += 1; continue
        return None


def first_violation(text, schema, finished=True, rules=('closer',)):
    """left-most repairable violation among the enabled rules ('closer' = look-alike closer slip, 'opener' = drifted
    opener of a string argument; opt-in extensions 'kwarg' and 'qkey').  None for strictly valid calls (guard)."""
    if is_valid(text, schema):
        return None
    c = []
    if 'kwarg' in rules:
        s3 = first_kwarg_site(text, schema)
        if s3 is not None:
            c.append((s3.colon_end, s3))
    if 'qkey' in rules:
        s4 = first_qkey_site(text, schema)
        if s4 is not None:
            c.append((s4.run_start, s4))
    if 'closer' in rules:
        s1 = first_slip_site(text, schema, finished)
        if s1 is not None:
            c.append((s1.run_start, s1))
    if 'opener' in rules:
        s2 = first_opener_site(text, schema)
        if s2 is not None:
            c.append((s2.colon_end, s2))
    return min(c, key=lambda x: x[0])[1] if c else None


# ----------------------------------------------------------------------------------------------- relaxed parses (algorithm ii)
@dataclass
class Candidate:
    pairs: list               # [(key, value, kind)]
    cuts: list                # [(site_key, cut_pos, closer_text)]
    cost: int
    sites: list = field(default_factory=list)   # SlipSite per cut
    def text(self, name):
        return render_call(name, self.pairs)


LAST_REPAIR_INCOMPLETE = [False]


def repair_candidates(text, schema, finished=True, max_cost=2, max_cands=64):
    """All complete parses under the relaxed grammar (a top-level string may be closed by a look-alike run at a
    slip site, any cut inside the run) that are schema-valid; returns the minimal-cost ones (cost = #slips).
    Returns [] for valid calls (they are returned unchanged by the guard) and when nothing explains the text."""
    if is_valid(text, schema):
        return []
    m = _NAME_RE.match(text)
    if not m or m.group(1) not in schema:
        return []
    name = m.group(1)
    sc = schema[name]
    s = text
    results = []
    budget = [REPAIR_BUDGET]

    def close_ok(i):
        return _ws(s, i) == len(s)

    def rec(i, pairs, cuts, cost, sites=()):
        budget[0] -= 1
        if budget[0] < 0 or len(results) >= max_cands * 4:
            return
        i = _ws(s, i)
        if i < len(s) and s[i] == '}' and not pairs:
            if close_ok(i + 1):
                results.append((cost, list(pairs), list(cuts), list(sites)))
            return
        km = _KEY_RE.match(s, i)
        if not km:
            return
        k = km.group(0)
        if k not in sc['props'] or any(p[0] == k for p in pairs):
            return
        j = _ws(s, km.end())
        if j >= len(s) or s[j] != ':':
            return
        vs = _ws(s, j + 1)
        emitted = {p[0] for p in pairs}
        if s.startswith(D, vs):
            cs = vs + len(D)
            e = s.find(D, cs)
            unterm = e == -1
            region_end = len(s) if unterm else e
            # option A: strict closer
            if not unterm:
                after = _ws(s, e + len(D))
                val = s[cs:e]
                if after < len(s) and s[after] == ',':
                    rec(after + 1, pairs + [(k, val, 'str')], cuts, cost, sites)
                elif after < len(s) and s[after] == '}' and close_ok(after + 1):
                    results.append((cost, pairs + [(k, val, 'str')], list(cuts), list(sites)))
            # option B: slip sites
            if cost < max_cost:
                for site in sites_in_string(s, k, cs, region_end, emitted | {k}, sc, finished, unterm):
                    for cp in site.cut_positions():
                        val = s[cs:cp]
                        closer = s[cp:site.struct_pos]
                        c2 = cuts + [(k, cp, closer)]
                        s2 = list(sites) + [site]
                        if site.kind == 'key':
                            rec(site.struct_pos + 1, pairs + [(k, val, 'str')], c2, cost + 1, s2)
                        else:
                            if close_ok(site.struct_pos + 1):
                                results.append((cost + 1, pairs + [(k, val, 'str')], c2, s2))
        else:
            try:
                v, kind, i2 = _parse_value(s, vs)
            except ParseError:
                return
            i2 = _ws(s, i2)
            if i2 < len(s) and s[i2] == ',':
                rec(i2 + 1, pairs + [(k, v, kind)], cuts, cost, sites)
            elif i2 < len(s) and s[i2] == '}' and close_ok(i2 + 1):
                results.append((cost, pairs + [(k, v, kind)], list(cuts), list(sites)))

    rec(m.end(), [], [], 0)
    if budget[0] < 0:
        LAST_REPAIR_INCOMPLETE[0] = True
        return []          # enumeration too complex -> no candidates (callers abstain / fall back to the scan)
    LAST_REPAIR_INCOMPLETE[0] = False
    good = []
    for cost, pairs, cuts, sts in results:
        keys = [p[0] for p in pairs]
        if any(r not in keys for r in sc['required']):
            continue
        if any(not _type_ok(v, kd, sc['props'].get(kk)) for kk, v, kd in pairs):
            continue
        good.append(Candidate(pairs, cuts, cost, sts))
    if not good:
        return []
    mc = min(c.cost for c in good)
    good = [c for c in good if c.cost == mc]
    # dedupe by rendered text
    seen, out = set(), []
    for c in good:
        t = c.text(name)
        if t not in seen:
            seen.add(t); out.append(c)
    return out[:max_cands]


# ----------------------------------------------------------------------------------------------- helpers
def split_call(raw):
    """raw generated text after the forced/natural '<|tool_call>' -> call text (without trailing <tool_call|>)."""
    t = raw
    if t.startswith(TC_START):
        t = t[len(TC_START):]
    k = t.find(TC_END)
    if k != -1:
        t = t[:k]
    return t


SIG_ANY = re.compile(r'([`"\'\\]*)\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*:')


def census_judge(call_text, schema, tool='edit_file'):
    """Same criterion as the team's census/order replay: parse with vLLM's lenient parser, then
    malformed if a required key is missing, a value leaks '<closer>,<declared key>:' or a special token, or an
    unknown key appears.  Returns (ok, why, args)."""
    from vllm.tool_parsers.gemma4_tool_parser import _parse_gemma4_args
    m = re.match(r'call:([\w\-\.]+)\{(.*)\}\s*$', call_text, re.S)
    if not m:
        return False, 'no_close', {}
    name = m.group(1)
    try:
        args = _parse_gemma4_args(m.group(2))
    except Exception:
        return False, 'parser_exc', {}
    if name not in schema:
        return False, 'unknown_tool', args
    sc = schema[name]
    miss = [k for k in sc['required'] if k not in args]
    if miss:
        return False, 'missing:' + ','.join(miss), args
    for k, v in args.items():
        if isinstance(v, str):
            for mm in SIG_ANY.finditer(v):
                if mm.group(2) in sc['props']:
                    return False, 'leak', args
            if D in v or TC_END in v or TC_START in v:
                return False, 'leak_tok', args
    if any(k not in sc['props'] for k in args):
        return False, 'extra_key', args
    return True, 'ok', args


# ----------------------------------------------------------------------------------------------- grammar-CD emulation
def grammar_state(text, schema):
    """Schema-aware grammar walk (what a grammar-constrained decoder enforces: <|"|> is the ONLY string closer,
    declared keys only, no duplicates, required keys before '}', typed values).  Returns
    (v, state, info): v = length of the longest viable prefix of `text`; state in
    {'complete','after_value','key','colon','value','string','header'} = what the grammar expects at v."""
    m = _NAME_RE.match(text)
    if not m or m.group(1) not in schema:
        return 0, 'header', {}
    sc = schema[m.group(1)]
    s = text
    i = m.end()
    emitted = []
    while True:
        j = _ws(s, i)
        if j >= len(s):
            return len(s), ('key' if not emitted else 'key'), {'emitted': emitted, 'sc': sc}
        km = _KEY_RE.match(s, j)
        if (not km) or km.group(0) not in sc['props'] or km.group(0) in emitted:
            if not emitted and j < len(s) and s[j] == '}' and not sc['required']:
                return j + 1, 'complete', {'emitted': emitted, 'sc': sc}
            return j, 'key', {'emitted': emitted, 'sc': sc}
        k = km.group(0)
        c = _ws(s, km.end())
        if c >= len(s):
            return len(s), 'colon', {'emitted': emitted, 'key': k, 'sc': sc}
        if s[c] != ':':
            return c, 'colon', {'emitted': emitted, 'key': k, 'sc': sc}
        vs = _ws(s, c + 1)
        ty = str(sc['props'][k].get('type') or '').lower()
        if ty == 'string':
            if not s.startswith(D, vs):
                return vs, 'value', {'emitted': emitted, 'key': k, 'type': ty, 'sc': sc}
            e = s.find(D, vs + len(D))
            if e == -1:
                return len(s), 'string', {'emitted': emitted, 'key': k, 'sc': sc}
            i = e + len(D)
        else:
            try:
                v, kind, i2 = _parse_value(s, vs)
            except ParseError:
                return vs, 'value', {'emitted': emitted, 'key': k, 'type': ty, 'sc': sc}
            if not _type_ok(v, kind, sc['props'][k]):
                return vs, 'value', {'emitted': emitted, 'key': k, 'type': ty, 'sc': sc}
            i = i2
        emitted.append(k)
        a = _ws(s, i)
        missing = [r for r in sc['required'] if r not in emitted]
        if a < len(s) and s[a] == ',' and len(emitted) < len(sc['props']):
            i = a + 1
            continue
        if a < len(s) and s[a] == '}' and not missing:
            return a + 1, 'complete', {'emitted': emitted, 'sc': sc}
        return i, 'after_value', {'emitted': emitted, 'missing': missing, 'sc': sc}


def grammar_force(state, info):
    """minimal legal continuation a schema grammar forces at a violation (the model then continues freely)."""
    sc = info.get('sc') or {'props': {}, 'required': []}
    def opener(k):
        ty = str((sc['props'].get(k) or {}).get('type') or '').lower()
        return D if ty == 'string' else ('false' if ty == 'boolean' else '')
    def next_key():
        miss = [r for r in sc['required'] if r not in info.get('emitted', [])]
        rest = [k for k in sc['props'] if k not in info.get('emitted', [])]
        return (miss or rest or [None])[0]
    if state == 'after_value':
        if info.get('missing'):
            k = next_key()
            return ',' + k + ':' + opener(k)
        return '}'
    if state == 'key':
        k = next_key()
        return (k + ':' + opener(k)) if k else '}'
    if state == 'colon':
        return ':' + opener(info['key'])
    if state == 'value':
        return opener(info['key'])
    if state == 'string':
        return D
    return ''


# ----------------------------------------------------------------------------------------------- delivery / corruption
LEAK_IN_VALUE = re.compile(r'[`"\'\\]+\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*:')


def runtime_view(text, finished, schema):
    """What a lenient runtime (vLLM 0.19.1 gemma4 parser + harness schema check) does with the call:
    accepted = finished, declared tool, all required keys, no unknown keys.
    silent_corruption = accepted AND (strict-invalid OR a value carries look-alike+','+declared-key+':' text OR a
    special token)."""
    ok, why, args = census_judge(text, schema) if finished else (False, 'no_close', {})
    m = _NAME_RE.match(text)
    name = m.group(1) if m else None
    sc = schema.get(name) if name else None
    accepted = bool(finished and sc and all(r in args for r in sc['required']) and all(k in sc['props'] for k in args))
    strict = finished and is_valid(text, schema)
    leak = False
    if sc:
        for v in args.values():
            if isinstance(v, str):
                if D in v or TC_END in v or TC_START in v:
                    leak = True
                for mm in LEAK_IN_VALUE.finditer(v):
                    if mm.group(1) in sc['props']:
                        leak = True
    return {'accepted': accepted, 'strict_valid': bool(strict), 'leak_text': leak,
            'silent_corruption': bool(accepted and ((not strict) or leak)), 'census_ok': ok}
