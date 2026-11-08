"""Shared setup for running the official swegemma 0.2.11 harness locally (workstream E).

- Docker sandbox through the ROOTLESS daemon (DOCKER_HOST below). Rootless docker has no cpu cgroup
  controller delegated, so the harness's cpu_period/cpu_quota cannot be applied: ContainerManager.start is
  patched to drop them; mem_limit=4g and network_mode=none are kept (containers inherit dockerd's
  CPU affinity, cores 112-135).
- All temp files (swegemma's unpacked-wheel tar cache uses tempfile.gettempdir()) stay under this directory.
"""
from __future__ import annotations

import os
from pathlib import Path

E2E = Path(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'experiments/endtoend'))
COMP = Path(os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'data/comp'))
os.environ['TMPDIR'] = os.environ.get('E2E_TMP', str(E2E / 'tmp'))
os.environ.setdefault('DOCKER_HOST', 'unix:///var/run/docker.sock')
os.environ.setdefault('DOCKER_CONFIG', os.path.join(os.environ.get('TRANSCRIPTLAB_ROOT', '.'), 'docker/cli'))
os.environ.setdefault('LITELLM_LOCAL_MODEL_COST_MAP', 'True')
os.environ.setdefault('LITELLM_TELEMETRY', 'False')
os.environ.setdefault('LITELLM_LOG', 'WARNING')
os.environ.setdefault('OPENAI_API_KEY', 'EMPTY')
os.environ.setdefault('OTEL_SDK_DISABLED', 'true')
os.environ.setdefault('HF_HUB_OFFLINE', '1')
import tempfile  # noqa: E402

tempfile.tempdir = os.environ['TMPDIR']

import contextvars  # noqa: E402

import swegemma.sandbox.docker as sd  # noqa: E402

CUR_TASK: contextvars.ContextVar[str] = contextvars.ContextVar('cur_task', default='')  # '<cfg>:<instance_id>'

MODEL_ALIAS = 'gemma-4-31b-it-qat-w4a16-ct'


def _start_no_cpu_quota(self) -> str:
    """ContainerManager.start without cpu_period/cpu_quota (unsupported by rootless docker here)."""
    with self._lock:
        while self._idle_containers:
            idle_cid = self._idle_containers.pop()
            try:
                c = self.client.containers.get(idle_cid)
                if getattr(c, 'status', 'running') in ('running', 'created'):
                    self._active_containers.add(idle_cid)
                    if self._default_container_id is None:
                        self._default_container_id = idle_cid
                    return idle_cid
            except Exception:  # noqa: BLE001
                pass
        if not self._image_resolved:
            self.config.image = sd.resolve_sandbox_image(self.config.image, client=self.client)
            self._image_resolved = True
    container = self.client.containers.run(
        self.config.image, command='sleep infinity', detach=True,
        network_mode=self.config.network_mode, mem_limit=self.config.mem_limit,
        working_dir=self.config.working_dir, environment=self.config.environment,
        labels={'e2e': 'workstream-E', 'e2e_run': os.environ.get('E2E_RUN', 'none')})
    cid = str(container.id or '')
    with self._lock:
        self._active_containers.add(cid)
        if self._default_container_id is None:
            self._default_container_id = cid
    return cid


sd.ContainerManager.start = _start_no_cpu_quota


def declared_model(sub_dir) -> str:
    from adk_submission.discovery import discover_declared_models
    m = discover_declared_models(Path(sub_dir))
    assert len(m) == 1, m
    return next(iter(m))


def install_wheel_routing(task_ids=None):
    """Per-task wheel sets (wheelsel.py) for every task in tasks.jsonl."""
    import wheelsel
    from swegemma.models import load_tasks
    tasks = {t.instance_id: t for t in load_tasks(COMP / 'tasks.jsonl')}
    wheelsel.install(CUR_TASK, tasks)
    return tasks


def make_models(api_base: str, alias: str = MODEL_ALIAS):
    """ModelRegistry with the declared alias routed to our proxy (served-name mapping is done by the proxy)."""
    from adk_submission import ModelRegistry
    from adk_submission.resolvers.generation import install_litellm_reasoning_patch
    from google.adk.models.lite_llm import LiteLlm
    install_litellm_reasoning_patch()
    reg = ModelRegistry()
    reg.register(alias, LiteLlm(model=f'openai/{alias}', api_base=api_base, api_key='EMPTY'))
    return reg


def base_config(results_dir: Path, models, *, sub_dir: Path, task_ids, concurrency: int, budget: dict,
                skip_agent_patch: bool = False):
    from google.adk.agents.context_cache_config import ContextCacheConfig
    from google.adk.apps._configs import EventsCompactionConfig
    from swegemma.config import EvalConfig, build_submission_limits
    limits, gen_constraints = build_submission_limits()
    return EvalConfig(
        tasks_path=COMP / 'tasks.jsonl', snapshots_dir=COMP / 'snapshots', results_dir=results_dir,
        submission_dir=sub_dir, models=models, sandbox='docker', image='swebench-sandbox:latest',
        wheels_dir=Path(os.environ.get('E2E_WHEELS', str(E2E / 'wheels_aug'))), graph_dir=str(COMP / 'graphs'), embeddings_dir=str(COMP / 'embeddings'),
        timeout_seconds=int(budget.get('timeout_seconds', 300)), verification_timeout_seconds=300,
        max_time_minutes=float(budget.get('max_time_minutes', 60)), max_tool_calls=budget.get('max_tool_calls'),
        max_turns=budget.get('max_turns'), limits=limits, generation_constraints=gen_constraints,
        context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10),
        events_compaction_config=EventsCompactionConfig(compaction_interval=15, overlap_size=2,
                                                        token_threshold=14336, event_retention_size=5),
        verbose=False, concurrency=concurrency, display_mode='quiet', task_ids=list(task_ids),
        skip_agent_patch=skip_agent_patch)
