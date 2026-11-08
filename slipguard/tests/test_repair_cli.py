"""repair.verify (E's ipd_scan), CLI commands, and (if a model dir is given) a small P1 run."""
import json
import os
import subprocess
import sys

import pytest

from slipguard._vendor.gemmaproto import CHANNEL_CLOSE, STR, TOOL_CALL_CLOSE, TOOL_CALL_OPEN, render_call
from slipguard.repair import strictly_valid, verify

TOOLS = json.load(open(os.path.join(os.path.dirname(__file__), "..", "src", "slipguard", "data", "tools_edit.json")))
EDIT = render_call("edit_file", {"filepath": "a.py", "new_string": "x = 1", "old_string": "x = 0"})
SLIP = EDIT.replace("x = 1" + STR + ",old", "x = 1`,old")
ENV = dict(os.environ, PYTHONPATH=os.path.join(os.path.dirname(__file__), "..", "src"))


def test_verify_plans_a_repair_only_for_the_slip():
    assert verify(EDIT, TOOLS).plan is None and verify(EDIT, TOOLS).strict_valid == 1
    v = verify(SLIP, TOOLS)
    assert v.needs_repair and v.plan["kind"] in ("key", "end") and v.plan["tool"] == "edit_file"   # closer sites
    assert strictly_valid(EDIT[len(TOOL_CALL_OPEN):-len(TOOL_CALL_CLOSE)], TOOLS)


def _cli(*args, stdin=""):
    return subprocess.run([sys.executable, "-m", "slipguard", *args], input=stdin, capture_output=True, text=True,
                          env=ENV, timeout=600)


def test_cli_parse_check_paths():
    r = _cli("check", stdin=EDIT)
    assert r.returncode == 0 and "OK" in r.stdout
    r = _cli("check", stdin=SLIP)
    assert r.returncode == 1
    r = _cli("parse", "--per-call", stdin="hi " + EDIT)
    assert json.loads(r.stdout)["calls"][0]["name"] == "edit_file"
    assert _cli("plugin-path").stdout.strip().endswith("vllm_plugin.py")
    assert _cli("template-path").stdout.strip().endswith("gemma4_july_guarded.jinja")


def test_cli_verify_without_model():
    r = _cli("verify")
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout)
    assert out["frozen"]["ok"] and out["conformance"]["ok"]


def test_p1_small_if_model_available():
    md = os.environ.get("SLIPGUARD_MODEL_DIR")
    if not md:
        pytest.skip("set SLIPGUARD_MODEL_DIR to a Gemma 4 model dir")
    pytest.importorskip("aiohttp")
    pytest.importorskip("transformers")
    from slipguard.verify import check_p1
    r = check_p1(md, engine="lite", limit=20)
    assert r["ok"] and all(v["changed"] == 0 for v in r["by_cfg"].values())


def test_cli_bench_parse_small():
    r = _cli("bench", "parse", "--max-args", "2000", "--max-string", "100000")
    assert r.returncode == 0, r.stderr[-1000:]
    rows = [json.loads(l) for l in r.stdout.splitlines() if l.startswith("{")]
    assert {x["family"] for x in rows} == {"many_string_args", "long_string"}


def test_cli_bench_transcripts_delegates():
    r = _cli("bench", "transcripts", "--", "--help")
    assert r.returncode in (0, 2)          # 2 = transcriptlab not installed (message printed), else its own help


def test_cli_audit(tmp_path):
    D = STR
    bad_args = {"filepath": "a.py", "new_string": "y`,old_string:"}          # a laundered slip
    conv = {"tools": TOOLS, "messages": [
        {"role": "user", "content": "fix"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {
            "name": "edit_file", "arguments": json.dumps(bad_args)}}]},
        {"role": "tool", "tool_call_id": "c1", "content": json.dumps({"result": "ok " + CHANNEL_CLOSE})}]}
    clean = {"tools": TOOLS, "messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]}
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps(conv) + "\n" + json.dumps(clean) + "\n")
    r = _cli("audit", str(p), "--json")
    rows = [json.loads(l) for l in r.stdout.splitlines()]
    kinds = {f["finding"] for f in rows[0]["findings"]}
    assert {"malformed_call", "control_text", "serialized_result", "thinking_off_gap"} <= kinds
    assert rows[1]["findings"] == [] and r.returncode == 1
    assert D  # (token constant used by the fixture builders above)


def test_cli_audit_without_tool_declarations_is_explicit(tmp_path):
    """No tool declarations: the malformed_call check cannot run -- it must say so (stderr + JSON field), never pass
    silently; --tools accepts a list or a manifest-style {"tools": [...]} object; --require-tools exits 2."""
    bad_args = {"filepath": "a.py", "new_string": "y`,old_string:"}          # a laundered slip
    msgs = [{"role": "user", "content": "fix"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {
                "name": "edit_file", "arguments": json.dumps(bad_args)}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "ok"}, {"role": "assistant", "content": "done"}]
    p = tmp_path / "plain.jsonl"
    p.write_text(json.dumps(msgs) + "\n")                                    # a bare message list: no declarations
    r = _cli("audit", str(p), "--json")
    row = json.loads(r.stdout.splitlines()[0])
    assert row["malformed_call"] == "not checked (no tool declarations)" and row["findings"] == []
    assert "WARNING" in r.stderr and "SKIPPED" in r.stderr and "--tools" in r.stderr and r.returncode == 0
    r = _cli("audit", str(p), "--require-tools")
    assert r.returncode == 2 and "not checked" in r.stdout
    for tools_doc in (TOOLS, {"tools": TOOLS, "other": "manifest fields"}):
        t = tmp_path / "tools.json"
        t.write_text(json.dumps(tools_doc))
        r = _cli("audit", str(p), "--json", "--tools", str(t), "--require-tools")
        row = json.loads(r.stdout.splitlines()[0])
        assert row["malformed_call"] == "checked" and r.returncode == 1 and "WARNING" not in r.stderr
        assert [f["finding"] for f in row["findings"]] == ["malformed_call"]


def test_weight_repair_not_shipped(tmp_path):
    for cmd in ("repair-weights", "verify-certificate"):
        r = _cli(cmd, "--model", str(tmp_path))
        assert r.returncode == 2 and "not shipped" in r.stderr and "registered gate" in r.stderr
    r = _cli("audit-weights", "-h")
    assert r.returncode == 0 and "--endpoint" in r.stdout and "--from-records" in r.stdout

# ---- 0.1.2: clean-install review (R4 practitioner steps 4.1, 4.2, 4.3, 4.7, 5.3) ----------------------------------
def _cli_blocked(blocked, *args):
    """The CLI in a subprocess where the modules in ``blocked`` cannot be imported (as in a venv without them).
    aiohttp's run_app is replaced first, so no server can start whatever the code path."""
    code = ("import sys\n"
            f"for m in {list(blocked)!r}:\n"
            "    sys.modules[m] = None\n"
            "try:\n"
            "    import aiohttp.web\n"
            "    def _no(*a, **k):\n"
            "        raise SystemExit('run_app reached')\n"
            "    aiohttp.web.run_app = _no\n"
            "except ImportError:\n"
            "    pass\n"
            "from slipguard.cli import main\n"
            "sys.exit(main(sys.argv[1:]))\n")
    return subprocess.run([sys.executable, "-c", code, *args], capture_output=True, text=True,
                          env=dict(ENV, CUDA_VISIBLE_DEVICES=""), timeout=600)


def test_proxy_without_vllm_names_the_fix(tmp_path):
    """default --engine frozen without vLLM: exit 2 and a message naming [proxy-frozen] and --engine lite, not a bare
    ModuleNotFoundError traceback; nothing is started or written."""
    common = ["--backend", "http://127.0.0.1:9/v1", "--model-dir", str(tmp_path / "model"), "--logdir", str(tmp_path / "logs")]
    r = _cli_blocked(["vllm"], "proxy", *common)
    assert r.returncode == 2 and "Traceback" not in r.stderr, r.stderr[-2000:]
    for s in ('pip install "slipguard[proxy-frozen]"', 'pip install "slipguard[proxy]"', "--engine lite", "vllm"):
        assert s in r.stderr, s
    assert not (tmp_path / "logs").exists()
    r = _cli_blocked(["transformers"], "proxy", "--engine", "lite", *common)
    assert r.returncode == 2 and 'pip install "slipguard[proxy]"' in r.stderr and "Traceback" not in r.stderr
    r = _cli_blocked(["vllm.tool_parsers.gemma4_tool_parser"], "proxy", *common)     # a vLLM without the gemma4 parser
    assert r.returncode == 2 and "slipguard[proxy-frozen]" in r.stderr and "Traceback" not in r.stderr, r.stderr[-2000:]
    r = _cli_blocked(["vllm"], "verify", "--model-dir", str(tmp_path / "model"))        # builds the same Proxy
    assert r.returncode == 2 and "slipguard[proxy-frozen]" in r.stderr and "--engine lite" in r.stderr
    from slipguard.repair import EngineDependencyError
    from slipguard.repair.proxy import missing_engine_deps
    assert issubclass(EngineDependencyError, ImportError) and set(missing_engine_deps("lite")) <= {"aiohttp", "transformers", "jinja2"}


def test_proxy_help_shows_defaults_and_routes():
    r = _cli("proxy", "--help")
    assert r.returncode == 0
    text = " ".join(r.stdout.split())                    # argparse wraps the help lines
    for s in ("default: 8420", "default: frozen", "fullp", "ipd", "full_order", '"slipguard[proxy-frozen]"', '"slipguard[proxy]"'):
        assert s in text, s


def test_version_and_plugin_path_environment_note():
    from slipguard import __version__
    r = _cli("--version")
    assert r.returncode == 0 and r.stdout.strip() == f"slipguard {__version__}"
    r = _cli("plugin-path", "vllm")
    assert r.returncode == 0 and len(r.stdout.splitlines()) == 1 and r.stdout.strip().endswith("vllm_plugin.py")
    assert "same python environment as vllm" in r.stderr.lower() and "pip install slipguard" in r.stderr
    assert _cli("plugin-path", "-q").stderr == ""


def test_parse_per_call_exit_status():
    r = _cli("parse", "--per-call", stdin=SLIP)
    d = json.loads(r.stdout)
    assert d["errors"] and d["calls"] == [] and r.returncode == 1
    r = _cli("parse", "--per-call", stdin="hi " + EDIT)
    assert r.returncode == 0 and json.loads(r.stdout)["errors"] == []


def test_audit_help_documents_input_and_exit_status():
    r = _cli("audit", "--help")
    assert r.returncode == 0 and "exit status" in r.stdout and '"messages"' in r.stdout


def test_vllm_plugin_without_slipguard_says_what_to_do():
    """vLLM loads the plugin by path; if slipguard is not importable in vLLM's environment the error says so."""
    pytest.importorskip("vllm")
    from slipguard.integrations import plugin_path
    code = ("import runpy, sys\n"
            "sys.modules['slipguard'] = None\n"
            "try:\n"
            "    runpy.run_path(sys.argv[1])\n"
            "except ModuleNotFoundError as e:\n"
            "    print(e)\n"
            "    sys.exit(3)\n")
    r = subprocess.run([sys.executable, "-c", code, plugin_path("vllm")], capture_output=True, text=True,
                       env=dict(ENV, CUDA_VISIBLE_DEVICES=""), timeout=600)
    assert r.returncode == 3, r.stderr[-2000:]
    assert "vLLM's Python environment" in r.stdout and "pip install slipguard" in r.stdout
