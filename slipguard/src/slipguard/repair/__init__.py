"""Intent-preserving decoding (IPD), verify-then-repair -- workstream E's frozen proxy code, imported unchanged.

What was evaluated is what ships: the cfgs ``base``, ``quar``, ``ipd`` and ``fullp`` run E's frozen
``Proxy.engine_chat`` / ``generate()`` / ``ipd_scan()`` / quarantine byte-for-byte (see slipguard._frozen and
``slipguard verify``). The registered end-to-end results (RESULTS.md of the release: malformed calls per episode in
the challenge's agent harness 2.47 -> 0.27, and 1.76 -> 0.37 in eight fresh replicates) are those of the ``frozen``
engine with cfg ``fullp``. The ``lite`` engine and the ``guard`` cfg are derived configurations (tested, not part of
the evaluation).

Install: ``pip install "slipguard[proxy-frozen]"`` (frozen engine: vLLM 0.19.1 on the proxy host) or
``pip install "slipguard[proxy]"`` (``engine="lite"``). A missing package raises ``EngineDependencyError`` (an
ImportError whose message names the extra).

Entry points
  slipguard proxy --backend http://vllm:8000/v1 --served gemma-4-31b --model-dir <hf model dir> --logdir <dir>
  verify(text, tools)                -> per-call strict validity + the first repairable site (no model needed)
  RepairClient(...).chat(messages, tools, **params)   -> E's engine_chat in-process (needs a vLLM backend)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .._frozen import load_e
from .proxy import EngineDependencyError

__all__ = ["verify", "VerifyReport", "strictly_valid", "RepairClient", "EVALUATED", "EngineDependencyError"]

# The configuration that carries the measured guarantees.
EVALUATED = {"engine": "frozen", "cfgs": ("ipd", "fullp"), "template": "official"}


@dataclass
class VerifyReport:
    calls: int
    strict_valid: int
    invalid: int
    plan: dict | None = None          # first repairable site: {tool, index, kind, key, ...} or None
    audit: dict = field(default_factory=dict)

    @property
    def needs_repair(self) -> bool:
        return self.plan is not None


def strictly_valid(call_text: str, tools: list[dict]) -> bool:
    """Workstream B's strict guard (structure + schema) as vendored in E's freeze. ``call_text`` = 'call:NAME{...}'."""
    gp = load_e().gemma_protocol
    return gp.strictly_valid(call_text, gp.b_schema_from_tools(tools))


def verify(text: str, tools: list[dict]) -> VerifyReport:
    """Verify every tool call in a generated completion (E's frozen ``ipd_scan``): strictly valid calls are never
    altered; the first invalid call with a repairable site (look-alike closer / drifted opener in a declared
    argument) is returned as the repair plan."""
    gp = load_e().gemma_protocol
    plan, audit = gp.ipd_scan(text, gp.b_schema_from_tools(tools), gp.IPD_RULES, {}, gp.IPD_MAX_ROUNDS)
    p = None
    if plan is not None:
        site = plan["site"]
        p = {"tool": plan["tool"], "index": plan["index"], "pos": plan["pos"], "kind": site.kind,
             "key": getattr(site, "key", None), "finished": plan["finished"]}
    return VerifyReport(calls=audit["calls"], strict_valid=audit["strict_valid"], invalid=audit["invalid"], plan=p,
                        audit=audit)


class RepairClient:
    """E's real request path (``Proxy.engine_chat``) in-process, without an HTTP server.

    Needs: aiohttp, transformers, the Gemma 4 model directory (tokenizer + chat template), a vLLM server for the
    backend (``/v1/completions`` with token-id prompts), and -- for ``engine="frozen"`` -- vLLM 0.19.1 importable.
    """

    def __init__(self, backend: str, model_dir: str, *, served: str = "gemma-4-31b", logdir: str,
                 engine: str = "frozen", template: str = "official", **opts: Any):
        from .proxy import make_proxy, proxy_args
        self.args = proxy_args(backend=backend, served=served, model_dir=model_dir, logdir=logdir, **opts)
        self.proxy = make_proxy(self.args, engine=engine, template=template)
        self._started = False

    async def chat(self, messages: list[dict], tools: list[dict] | None = None, *, cfg: str = "fullp",
                   **params: Any) -> tuple[int, dict]:
        if not self._started:
            await self.proxy.start(None)
            self._started = True
        body = {"messages": messages, "tools": tools, **params}
        rec = {"cfg": cfg}
        if cfg not in self.proxy.cfgs:
            raise KeyError(f"unknown cfg {cfg!r}; available: {sorted(self.proxy.cfgs)}")
        return await self.proxy.engine_chat(body, self.proxy.cfgs[cfg], rec)

    async def close(self) -> None:
        if self._started:
            await self.proxy.stop(None)
            self._started = False
