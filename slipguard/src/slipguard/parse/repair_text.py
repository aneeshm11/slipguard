"""Opt-in, text-only repair of a malformed call (per-call mode). Never silent: the repair is recorded, the call is
marked (``warnings == ['repaired', 'repair_rule:<kwarg|closer>']``; the vLLM plugin gives it an id ending in ``-ggrepaired``), and nothing after
the repaired call is delivered as a call.

Scope (two rules, both conservative):
* kwarg drift on a NON-string declared argument (``start_line=668``): '=' becomes ':' (workstream B's kwarg site rule).
  On the PNC corpus vLLM 0.19.1 silently DROPPED such an argument in 445 of 41,290 natural turns.
* closer slips -- a top-level string argument closed by a run of look-alike characters (backtick, quotes, escaped
  quotes, ...) at a slip site, i.e. before ``,<declared key>:`` or at the end of the arguments. The candidate
parses come from workstream B's relaxed grammar (``repair_candidates``, vendored in E's frozen proxy files; schema-
valid parses of minimal cost). Without token likelihoods the cut inside a look-alike run is ambiguous, so two
rules must AGREE: (1) the whole run is the closer (the cut E's proxy uses when no likelihood scorer is available) and
(2) the closer with the highest probability under the frozen channel prior of base-model edit slips
(configs/channel_prior.json, `base_edit`). Otherwise nothing is repaired. Opener drift, JSON-style strings, doubled
delimiters, Python literals and everything else stay loud. The repaired call must be strictly valid under B's guard
and parse back strictly to the same values.

An empty or whitespace-only run is a MISSING closer, not a look-alike: it stays loud (whether the whitespace belongs to
the value is undecidable from the text; on public PNC traffic one such cut disagreed with the model's own retry).

Measured on workstream C's suite (slips for which B's grammar has a candidate): real slips 1,419 repaired exactly,
0 wrongly, 168 left loud; synthetic mutants 705 / 0 / 473 and E-family 309 / 0 / 51 (the prior is estimated from
the same logs as the real slips; the synthetic families are out of sample). On public PNC turns whose intent is
known from a later clean retry: see results/conformance_pnc/.

Text-only repair is ill-posed in general (a string may legitimately contain "`,old_string:"); token-level repair
(IPD, `slipguard proxy`) is preferred whenever the model is reachable.
"""
from __future__ import annotations

from typing import Callable, Iterable

from .._vendor.gemmaproto.parser import ParseError, ToolCall
from .._vendor.gemmaproto.tokens import TOOL_CALL_CLOSE, TOOL_CALL_OPEN


def make_repair_fn(tools: Iterable[dict]) -> Callable[[str, int], ToolCall | None]:
    from .._frozen import load_e
    import json
    from .._frozen import paths
    gp = load_e().gemma_protocol
    BG = gp.BG
    bschema = gp.b_schema_from_tools([t if isinstance(t, dict) else dict(t) for t in tools])
    with open(paths().channel_prior, encoding="utf-8") as f:
        pr = json.load(f)
    prior = gp.ChannelPrior(pr["priors"]["base_edit"], pr.get("alpha", 0.5))

    def repair(region: str, start: int) -> ToolCall | None:
        if not (region.startswith(TOOL_CALL_OPEN) and region.endswith(TOOL_CALL_CLOSE)):
            return None
        body = region[len(TOOL_CALL_OPEN):-len(TOOL_CALL_CLOSE)]
        m = BG._NAME_RE.match(body)
        if not m or m.group(1) not in bschema:
            return None
        name = m.group(1)
        fixed, rule = _kwarg_fix(body), "kwarg"
        if fixed is None:
            fixed, rule = _closer_fix(body, name), "closer"
        if fixed is None or not BG.is_valid(fixed, bschema):
            return None
        from . import parse_call
        try:
            tc = parse_call(TOOL_CALL_OPEN + fixed + TOOL_CALL_CLOSE)
        except ParseError:
            return None
        return ToolCall(name=name, arguments=tc.arguments, span=(start, start + len(region)), key_order=tc.key_order,
                        canonical=False, warnings=["repaired", "repair_rule:" + rule])

    def _kwarg_fix(body: str) -> str | None:
        """Python-kwargs drift on NON-string declared arguments (`start_line=668`): '=' -> ':' (B's kwarg site rule).
        String-typed arguments are left alone (the value's quoting is ambiguous without the model)."""
        s = body
        for _ in range(8):
            if BG.is_valid(s, bschema):
                return s if s != body else None
            site = BG.first_kwarg_site(s, bschema)
            if site is None or site.force != ":":
                return None
            s = s[:site.colon_end] + ":" + s[site.vstart + 1:]
        return None

    def _closer_fix(body: str, name: str) -> str | None:
        cands = BG.repair_candidates(body, bschema, finished=True)
        if not cands or BG.LAST_REPAIR_INCOMPLETE[0]:
            return None
        def choose(score):
            best = max(score(c) for c in cands)
            texts = {c.text(name) for c in cands if score(c) == best}
            return texts.pop() if len(texts) == 1 else None
        whole = choose(lambda c: sum(len(ct) for _, _, ct in c.cuts))                       # longest closers
        by_prior = choose(lambda c: (round(sum(prior.logp(ct) for _, _, ct in c.cuts), 9),  # most probable closers
                                     sum(len(ct) for _, _, ct in c.cuts)))
        if whole is None or whole != by_prior:
            return None                       # ambiguous without likelihoods: stay loud
        if any(not ct.strip() for c in cands if c.text(name) == whole for _, _, ct in c.cuts):
            return None                       # an empty / whitespace-only run is a MISSING closer, not a look-alike
        return whole

    return repair
