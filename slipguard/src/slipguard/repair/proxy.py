"""`slipguard proxy`: workstream E's frozen OpenAI-compatible protocol proxy.

    slipguard proxy --backend http://127.0.0.1:8000/v1 --served gemma-4-31b --model-dir <hf model dir> --logdir <dir>
    # clients use  http://127.0.0.1:8420/fullp/v1   (cfgs: pass, base, order, quar, ipd, fullp, full_order)

The evaluated configuration (``--engine frozen --template official``, the default) runs E's own ``main()`` -- the
frozen file end to end, CLI wiring included. Other options are derived configurations:
  --engine lite         tokenizer-only engine; the final parse uses slipguard's strict parser instead of vLLM 0.19.1's
                        lenient one (no vLLM needed on the proxy host). generate()/ipd_scan()/quarantine unchanged.
  --template guarded    slipguard's patched template for every cfg (thinking-off closure + control-token
                        neutralization) and an extra cfg ``guard`` (= fullp flags, + --native-tool-results if given).
The backend must be a vLLM server (the proxy calls /v1/completions with token-id prompts, return_token_ids,
allowed_token_ids and logprobs). The proxy logs every request, including the raw generation, to --logdir.

Install: ``pip install "slipguard[proxy-frozen]"`` for the default (evaluated) frozen engine, which imports vLLM
0.19.1's parsers on the proxy host; ``pip install "slipguard[proxy]"`` is enough for ``--engine lite``. A missing
dependency is reported before anything starts (:class:`EngineDependencyError`, exit status 2), naming the extra.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from .._frozen import load_e, paths

DEFAULTS = dict(host="127.0.0.1", port=8420, max_backend_conc=24, cpu_workers=6, call_timeout=900.0,
                max_interventions=8, budget_slack=1536, prior_source="ft_edit", replay_plan=None, seed_salt=None)

# ------------------------------------------------------------------------------------------------- dependencies
# Which pip extra provides which engine (pyproject.toml): [proxy-frozen] = aiohttp, transformers, jinja2 + vllm==0.19.1
# (the evaluated engine imports vLLM 0.19.1's Gemma 4 parsers); [proxy] = aiohttp, transformers, jinja2 (lite engine).
ENGINE_EXTRA = {"frozen": "proxy-frozen", "lite": "proxy"}
ENGINE_MODULES = {"frozen": ("aiohttp", "transformers", "jinja2", "vllm"), "lite": ("aiohttp", "transformers", "jinja2")}
EVALUATED_VLLM = "0.19.1"


class EngineDependencyError(ImportError):
    """A package the chosen proxy engine needs is not importable here. The message names the pip extra that installs
    it (and, for the frozen engine, the ``--engine lite`` alternative)."""


def _importable(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def missing_engine_deps(engine: str = "frozen") -> list[str]:
    """Top-level modules the engine needs that are not importable in this Python environment (nothing is imported)."""
    return [m for m in ENGINE_MODULES[engine] if not _importable(m)]


def _vllm_version() -> str | None:
    try:
        from importlib.metadata import version
        return version("vllm")
    except Exception:            # noqa: BLE001 - not installed / no metadata
        return None


def engine_dependency_message(engine: str, missing: list[str], prog: str = "slipguard proxy", *,
                              detail: str | None = None) -> str:
    where = f"this Python environment ({sys.executable})"
    lite = "pass --engine lite" if prog.startswith("slipguard ") else 'pass engine="lite"'
    if engine == "frozen":
        head = (f"{prog}: the default engine (--engine frozen, the evaluated configuration) imports vLLM "
                f"{EVALUATED_VLLM}'s Gemma 4 parsers on the proxy host, and "
                + (f"{', '.join(missing)} {'is' if len(missing) == 1 else 'are'} not installed in {where}."
                   if missing else f"they could not be imported in {where}: {detail}."))
        return (head + "\n"
                f'  fix: pip install "slipguard[proxy-frozen]"   (vLLM {EVALUATED_VLLM}\'s CUDA build: torch and nvidia '
                "wheels, several GB)\n"
                f'   or: pip install "slipguard[proxy]" and {lite}   (derived engine: tokenizer only, no vLLM '
                "on the proxy host, strict final parse; not the evaluated configuration)")
    return (f"{prog}: --engine lite needs {', '.join(missing) or 'its dependencies'}, not installed in {where}"
            + (f" ({detail})" if detail else "") + ".\n"
            '  fix: pip install "slipguard[proxy]"   (aiohttp, transformers, jinja2)')


def require_engine(engine: str = "frozen", prog: str = "slipguard proxy") -> None:
    """Raise :class:`EngineDependencyError` (with the fix) if ``engine``'s packages are not importable."""
    if engine not in ENGINE_MODULES:
        raise ValueError("engine must be frozen|lite")
    missing = missing_engine_deps(engine)
    if missing:
        raise EngineDependencyError(engine_dependency_message(engine, missing, prog), name=missing[0])


def _engine_import_error(e: ImportError, engine: str, prog: str = "slipguard proxy") -> EngineDependencyError | None:
    """An ImportError raised while E's frozen Engine is built (e.g. a vLLM other than 0.19.1 without
    ``vllm.tool_parsers.gemma4_tool_parser``) as an EngineDependencyError with the fix; None if it is unrelated."""
    name = getattr(e, "name", None) or ""
    if isinstance(e, EngineDependencyError) or name.split(".")[0] not in ENGINE_MODULES["frozen"]:
        return None
    v = _vllm_version()
    detail = f"{type(e).__name__}: {e}" + (f" (installed vLLM: {v})" if v and name.startswith("vllm") else "")
    return EngineDependencyError(engine_dependency_message(engine, [], prog, detail=detail), name=name)


def proxy_args(*, backend: str, served: str, model_dir: str, logdir: str, **opts: Any) -> SimpleNamespace:
    p = paths()
    a = dict(DEFAULTS, backend=backend, served=served, model_dir=model_dir, logdir=logdir, configs=p.configs_json,
             prior=p.channel_prior)
    a.update(opts)
    return SimpleNamespace(**a)


def _lite_engine_class(px):
    from ..parse import extract
    from ..parse.reasoning import split_reasoning

    class LiteEngine(px.Engine):
        """Same members as E's Engine; no vLLM import; strict final parse (slipguard.parse.extract)."""

        def __init__(self, model_dir: str):   # noqa: D401 - deliberately does not call Engine.__init__ (vLLM)
            from transformers import AutoTokenizer
            gp = px.gp
            self.tok = AutoTokenizer.from_pretrained(model_dir)
            self.tpl_official = Path(model_dir, "chat_template.jinja").read_text()
            self.tpl_canonical = gp.canonical_template(self.tpl_official)
            gc = json.loads(Path(model_dir, "generation_config.json").read_text())
            eos = gc.get("eos_token_id")
            self.eos_ids = set(eos if isinstance(eos, list) else [eos])
            self.ch_start = self.tok.convert_tokens_to_ids(gp.CH_START)
            self.ch_end = self.tok.convert_tokens_to_ids(gp.CH_END)
            self.d_id = self.tok.convert_tokens_to_ids(gp.D)

        def parse(self, text: str):
            reasoning, content = split_reasoning(text)
            ex = extract(content or "", parse_thought=False)
            if not ex.calls:
                return reasoning, content, []
            calls = [{"name": c.name, "arguments": json.dumps(c.arguments, ensure_ascii=False)} for c in ex.calls]
            c = ex.content
            return reasoning, (c if c and c.strip() else None), calls

    return LiteEngine


_SENT = re.compile("\ue000(\\d+)\ue001")


def token_neutral_render_ids(engine: Any):
    """Wrap ``engine.render_ids`` so untrusted spans (tool-result text, string values of historical call arguments)
    that contain control-token text are tokenized with special-token parsing DISABLED, and everything else exactly as
    before. Clean conversations take the original path unchanged (same text, same ids). The spans sit between
    <|"|> special tokens, which the tokenizer splits on first, so the surrounding ids are those of the whole-prompt
    encoding (tested)."""
    from ..history.neutralize import has_control_text
    orig = engine.render_ids
    tok = engine.tok

    def render_ids(conv, tools, kwargs, canonical):
        spans: list[str] = []

        def sub(x):
            if isinstance(x, str):
                if has_control_text(x):
                    spans.append(x)
                    return f"\ue000{len(spans) - 1}\ue001"
                return x
            if isinstance(x, list):
                return [sub(v) for v in x]
            if isinstance(x, dict):
                return {k: sub(v) for k, v in x.items()}
            return x

        conv2 = copy.deepcopy(conv)
        for m in conv2:
            if m.get("role") == "tool" and isinstance(m.get("content"), list):
                parts = [p for p in m["content"] if isinstance(p, dict) and p.get("type") == "text"]
                joined = "".join(p.get("text") or "" for p in parts)
                if parts and has_control_text(joined):
                    parts[0]["text"] = sub(joined)
                    for p in parts[1:]:
                        p["text"] = ""
            elif m.get("role") == "assistant":
                for tc in m.get("tool_calls") or []:
                    f = tc.get("function") or {}
                    if isinstance(f.get("arguments"), dict):
                        f["arguments"] = {k: sub(v) for k, v in f["arguments"].items()}
        if not spans:
            return orig(conv, tools, kwargs, canonical)
        text2, _ = orig(conv2, tools, kwargs, canonical)
        pieces = _SENT.split(text2)
        ids: list[int] = []
        out: list[str] = []
        for i, piece in enumerate(pieces):
            if i % 2 == 0:
                if piece:
                    ids += tok.encode(piece, add_special_tokens=False)
                out.append(piece)
            else:
                span = spans[int(piece)]
                ids += tok(span, add_special_tokens=False, split_special_tokens=True)["input_ids"]
                out.append(span)
        return "".join(out), ids

    engine.render_ids = render_ids
    return engine


def make_proxy(args: Any, *, engine: str = "frozen", template: str = "official", native_tool_results: bool = False,
               token_neutralize: bool = False):
    """Construct E's Proxy (unchanged class for the evaluated configuration; a thin subclass for derived ones).
    Raises :class:`EngineDependencyError` (an ImportError naming the pip extra) if the engine's packages are missing."""
    if engine not in ("frozen", "lite") or template not in ("official", "guarded", "closure"):
        raise ValueError("engine must be frozen|lite and template official|guarded|closure")
    require_engine(engine, prog="slipguard.repair")
    E = load_e(with_proxy=True)
    px = E.e2e_proxy
    derived = template != "official" or native_tool_results or token_neutralize
    cls = px.Proxy
    if derived:
        from ..history import transforms as T

        class SlipguardProxy(px.Proxy):
            async def engine_chat(self, body, cfg, rec):
                if cfg.get("slipguard") and native_tool_results:
                    msgs, acts = T.native_tool_results(body.get("messages") or [])
                    if acts:
                        body = {**body, "messages": msgs}
                        rec["slipguard_native_tool_results"] = len(acts)
                return await super().engine_chat(body, cfg, rec)
        cls = SlipguardProxy
    saved = px.Engine
    if engine == "lite":
        px.Engine = _lite_engine_class(px)
    try:
        proxy = cls(args)
    except ImportError as e:
        err = _engine_import_error(e, engine, prog="slipguard.repair")
        if err is None:
            raise
        raise err from e
    finally:
        px.Engine = saved
    if template != "official":
        from ..template import text as template_text
        t = template_text(template)
        proxy.engine.tpl_official = t
        proxy.engine.tpl_canonical = px.gp.canonical_template(t)
    if token_neutralize:
        token_neutral_render_ids(proxy.engine)
    if derived:
        proxy.cfgs["guard"] = {**copy.deepcopy(proxy.cfgs["fullp"]), "slipguard": True}
        proxy.logs["guard"] = open(Path(args.logdir) / "proxy_guard.jsonl", "a", buffering=1)
        proxy.stats["guard"] = {"requests": 0, "errors": 0, "interventions": 0}
    proxy.slipguard = {"engine": engine, "template": template, "native_tool_results": native_tool_results,
                       "token_neutralize": token_neutralize, "evaluated": not derived and engine == "frozen"}
    return proxy


def _cfg_names() -> list[str]:
    """the cfg routes of E's frozen configs.json, in file order (read as JSON; nothing is imported)."""
    try:
        with open(paths().configs_json, encoding="utf-8") as f:
            return list(json.load(f))
    except (OSError, ValueError):
        return ["pass", "base", "order", "quar", "ipd", "fullp", "full_order"]


class _HelpFormatter(argparse.RawDescriptionHelpFormatter):
    """keeps the epilog's layout and appends real defaults (not None / False) to the option help."""

    def _get_help_string(self, action):
        h = action.help or ""
        if action.default not in (None, False, argparse.SUPPRESS) and "%(default)" not in h:
            h += " (default: %(default)s)"
        return h


def build_parser() -> argparse.ArgumentParser:
    epilog = (
        "routes:\n"
        "  clients use http://HOST:PORT/<cfg>/v1 as their OpenAI base URL, e.g. http://127.0.0.1:8420/fullp/v1\n"
        f"  cfgs: {', '.join(_cfg_names())}; derived options add cfg 'guard' (= fullp + the option)\n"
        "  evaluated: cfg fullp (or ipd) with --engine frozen --template official (the defaults)\n"
        "engines and pip extras:\n"
        f'  frozen (default, evaluated)  pip install "slipguard[proxy-frozen]"  (imports vLLM {EVALUATED_VLLM} on the proxy host)\n'
        '  lite (derived, no vLLM)      pip install "slipguard[proxy]"\n'
        "  the backend is a separate, stock vLLM server (e.g. vllm serve <model> --port 8000)\n"
        "exit status: 2 if the engine's packages are missing (the message names the extra)")
    ap = argparse.ArgumentParser(prog="slipguard proxy", description=__doc__.split("\n\n")[0],
                                 formatter_class=_HelpFormatter, epilog=epilog)
    ap.add_argument("--backend", required=True, help="vLLM server base URL, e.g. http://127.0.0.1:8000/v1")
    ap.add_argument("--served", default="gemma-4-31b", help="model name served by the backend")
    ap.add_argument("--model-dir", required=True, help="Gemma 4 model dir (tokenizer, chat_template.jinja, generation_config.json)")
    ap.add_argument("--logdir", required=True, help="request logs (raw generations) are written here")
    ap.add_argument("--host", default=DEFAULTS["host"], help="listen address")
    ap.add_argument("--port", type=int, default=DEFAULTS["port"], help="listen port")
    ap.add_argument("--engine", choices=["frozen", "lite"], default="frozen",
                    help="frozen = E's evaluated engine (needs [proxy-frozen]); lite = derived, no vLLM (needs [proxy])")
    ap.add_argument("--template", choices=["official", "guarded", "closure"], default="official",
                    help="guarded = closure + text-level neutralization; closure = thinking-off closure only")
    ap.add_argument("--token-neutralize", action="store_true",
                    help="tokenize untrusted spans with special-token parsing disabled (preferred over text-level)")
    ap.add_argument("--native-tool-results", action="store_true", help="cfg guard: unwrap ADK {'result': ...} tool results")
    ap.add_argument("--max-backend-conc", type=int, default=DEFAULTS["max_backend_conc"], help="concurrent backend calls")
    ap.add_argument("--cpu-workers", type=int, default=DEFAULTS["cpu_workers"], help="CPU threads for rendering/parsing")
    ap.add_argument("--call-timeout", type=float, default=DEFAULTS["call_timeout"], help="seconds per backend call")
    ap.add_argument("--max-interventions", type=int, default=DEFAULTS["max_interventions"], help="IPD repairs per turn")
    ap.add_argument("--budget-slack", type=int, default=DEFAULTS["budget_slack"], help="extra tokens allowed for repairs")
    ap.add_argument("--prior-source", default=DEFAULTS["prior_source"], help="channel prior used by the IPD cut rule")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    try:                                   # before anything is imported or started: a clear message, not a traceback
        require_engine(a.engine)
    except EngineDependencyError as e:
        print(e, file=sys.stderr)
        return 2
    if a.engine == "frozen" and a.template == "official" and not a.native_tool_results and not a.token_neutralize:
        # the evaluated configuration: E's frozen main(), unchanged
        px = load_e(with_proxy=True).e2e_proxy
        sys.argv = ["e2e_proxy", "--host", a.host, "--port", str(a.port), "--backend", a.backend, "--served", a.served,
                    "--model-dir", a.model_dir, "--logdir", a.logdir, "--max-backend-conc", str(a.max_backend_conc),
                    "--cpu-workers", str(a.cpu_workers), "--call-timeout", str(a.call_timeout),
                    "--max-interventions", str(a.max_interventions), "--budget-slack", str(a.budget_slack),
                    "--prior-source", a.prior_source]
        print(f"slipguard proxy: evaluated configuration (frozen engine, official template) on http://{a.host}:{a.port}/<cfg>/v1",
              file=sys.stderr)
        try:
            px.main()
        except ImportError as e:           # e.g. a vLLM other than 0.19.1 without the gemma4 parser modules
            err = _engine_import_error(e, a.engine)
            if err is None:
                raise
            print(err, file=sys.stderr)
            return 2
        return 0
    from aiohttp import web
    args = proxy_args(backend=a.backend, served=a.served, model_dir=a.model_dir, logdir=a.logdir, host=a.host,
                      port=a.port, max_backend_conc=a.max_backend_conc, cpu_workers=a.cpu_workers,
                      call_timeout=a.call_timeout, max_interventions=a.max_interventions, budget_slack=a.budget_slack,
                      prior_source=a.prior_source)
    try:
        proxy = make_proxy(args, engine=a.engine, template=a.template, native_tool_results=a.native_tool_results,
                           token_neutralize=a.token_neutralize)
    except EngineDependencyError as e:
        print(str(e).replace("slipguard.repair:", "slipguard proxy:", 1).replace('pass engine="lite"', "pass --engine lite"),
              file=sys.stderr)
        return 2
    app = web.Application(client_max_size=256 * 1024 ** 2)
    app.on_startup.append(proxy.start)
    app.on_cleanup.append(proxy.stop)
    app.router.add_post("/{cfg}/v1/chat/completions", proxy.chat)
    app.router.add_get("/{cfg}/v1/models", proxy.models)
    app.router.add_get("/health", proxy.health)
    print(f"slipguard proxy: DERIVED configuration engine={a.engine} template={a.template} "
          f"token_neutralize={a.token_neutralize} native_tool_results={a.native_tool_results} "
          f"on http://{a.host}:{a.port}/<cfg>/v1 (extra cfg: guard)", file=sys.stderr)
    web.run_app(app, host=a.host, port=a.port, access_log=None, print=lambda *_: None)
    return 0
