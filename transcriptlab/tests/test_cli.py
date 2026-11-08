"""CPU tests of the transcriptlab CLI (stdlib unittest; also collected by pytest).

    TRANSCRIPTLAB_ROOT=<repository root> python -B -m unittest discover -s transcriptlab/tests -v
    (pytest also works: python -B -m pytest -p no:cacheprovider transcriptlab/tests)

Outputs go to a fresh directory under the system temp dir ($TMPDIR) and are removed at the end (keep them with
TRANSCRIPTLAB_KEEP_TEST_OUTPUT=1). -B / PYTHONDONTWRITEBYTECODE keeps bytecode out of the tree; the frozen scripts the
CLI starts never write bytecode either.

* unit: arm rules, cost estimate, job list, hash verification (no data needed);
* golden (need the released results): the CLI's job list and ids equal the registered ones; `report` reproduces the
  paper's bf16 row byte-for-byte and X's Qwen3-Coder-30B analysis from the released generation files;
* end to end on a mock backend (need the public states, a tokenizer and vLLM 0.19.1 installed): `run` then
  `report` on a 3-state pilot; the frozen judge flags exactly the slipped calls the mock emitted.
Tests whose inputs are absent are skipped, with the reason.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True   # nothing below writes __pycache__ into the tree

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE))

from transcriptlab import backends as B  # noqa: E402
from transcriptlab import cli  # noqa: E402

try:
    ROOT = B.find_root(None)
except B.SetupError:
    ROOT = None
WORK = Path(tempfile.mkdtemp(prefix="transcriptlab_tests_"))   # under $TMPDIR (the system temp dir by default)


def tearDownModule():
    if not os.environ.get("TRANSCRIPTLAB_KEEP_TEST_OUTPUT"):
        shutil.rmtree(WORK, ignore_errors=True)
    else:
        print(f"test outputs kept in {WORK}", file=sys.stderr)

MODELS = Path(os.environ.get("TRANSCRIPTLAB_MODELS", (ROOT / "models") if ROOT else "models"))


def have(*rel) -> bool:
    return ROOT is not None and all((ROOT / r).exists() for r in rel)


def have_pnc() -> bool:
    """the PNC S1 manifest is reachable (data/pnc in the tree, or $PNC_ROOT): `run` needs it, even with --dry-run."""
    if ROOT is None:
        return False
    try:
        B.corpus_manifest(ROOT)
        return True
    except (B.SetupError, OSError, ValueError, KeyError):
        return False


NO_PNC = "PNC dataset not attached (download it to <root>/data/pnc or set PNC_ROOT)"


@contextlib.contextmanager
def env_and_cwd(cwd=None, **env):
    """temporarily set (value) / unset (None) environment variables and change the cwd."""
    old_cwd = os.getcwd()
    old = {k: os.environ.get(k) for k in env}
    try:
        for k, v in env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = str(v)
        if cwd is not None:
            os.chdir(cwd)
        yield
    finally:
        os.chdir(old_cwd)
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def importable(*mods) -> bool:
    import importlib.util
    return all(importlib.util.find_spec(m) is not None for m in mods)


def run_cli(*argv) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cli.main([str(a) for a in argv])
    return rc, buf.getvalue()


def jsonl(path) -> list:
    with open(path) as f:
        return [json.loads(line) for line in f]


def tmpdir(tag: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f"{tag}_", dir=WORK))


def fake_root(tag: str) -> Path:
    """a directory that passes the root test (a stub run_injection.py; nothing in it is ever executed here)."""
    r = tmpdir(tag)
    (r / B.A_SCRIPTS).mkdir(parents=True)
    (r / B.A_SCRIPTS / "run_injection.py").write_text("# stub\n")
    return r.resolve()


class Unit(unittest.TestCase):
    def test_estimate_is_states_times_arms(self):
        e = B.estimate(300, ["P0", "P1", "P6", "P8a"])
        self.assertEqual(e["generations"], 1200)
        self.assertEqual(e["upper_bound_new_tokens"], 1200 * B.MAX_NEW)

    def test_arm_rules(self):
        self.assertEqual(B.parse_arms("P0,P1,P6,P8a", "gemma4"), ["P0", "P1", "P6", "P8a"])
        with self.assertRaises(B.SetupError):
            B.parse_arms("P0,P1", "gemma4")          # the gemma4 analysis needs the whole core set
        with self.assertRaises(B.SetupError):
            B.parse_arms("P1,P6", "hermes")          # no reference arm
        with self.assertRaises(B.SetupError):
            B.parse_arms("P0,P9", "hermes")
        self.assertEqual([B.x_arm(a) for a in B.parse_arms("P0,P1,P1N,P5,P6,P8a", "mistral")],
                         ["P0", "P1L", "P1N", "P5", "P6", "P8a"])

    def test_gemma_plan_shape(self):
        states = [{"context_id": f"c{i}", "rank": i + 1, "half": "H1"} for i in range(3)]
        plan = B.gemma_plan(states, ["P0", "P1", "P6", "P8a"])
        self.assertEqual(len(plan), 12)
        self.assertEqual({(j["pathway"], j["k"]) for j in plan}, {("P0", 0), ("P1", 1), ("P6", 1), ("P8a", 1)})
        self.assertEqual([j["id"] for j in plan[:4]], ["c0"] * 4)   # arms of one state stay adjacent (prefix cache)

    def test_summary_formatting(self):
        ana = {"complete_states": 2, "episodes": 2, "missing": {}, "uncond": {
            "P0": [0.0, 0.0, 0.0], "P1": [0.5, 0.0, 1.0], "P6": [0.0, 0.0, 0.0], "P8a": [0.0, 0.0, 0.0],
            "RD_P1_P0": [0.5, 0.0, 1.0], "RD_P6_P0": [0.0, 0.0, 0.0], "P8a_removal": [1.0, 1.0, 1.0, 0.0],
            "bf16_minus_QAT_same_states": {"n_states": 0}}}
        txt = "\n".join(cli.summarize({"model": "m", "format": "gemma4", "pool": "A1", "n_states": 2}, ana))
        self.assertIn("P1    50.0% [0.0, 100.0]", txt)
        self.assertIn("quarantine removal of the P1 excess: 100%", txt)

    def test_outside_the_repository_the_error_says_what_to_do(self):
        """pip-only user, cwd outside the repository, no TRANSCRIPTLAB_ROOT: exit 2 with an actionable message."""
        old_cwd, old_env = os.getcwd(), os.environ.pop("TRANSCRIPTLAB_ROOT", None)
        err = io.StringIO()
        try:
            os.chdir(os.path.abspath(os.sep))     # the filesystem root: no repository above it, nothing written
            with contextlib.redirect_stderr(err):
                rc, _ = run_cli("verify")
        finally:
            os.chdir(old_cwd)
            if old_env is not None:
                os.environ["TRANSCRIPTLAB_ROOT"] = old_env
        msg = err.getvalue()
        self.assertEqual(rc, 2)
        for s in ("TRANSCRIPTLAB_ROOT", "inside a clone of the repository", "--root", "PNC", "3 GB", "PNC_ROOT"):
            self.assertIn(s, msg)

    def test_root_precedence_flag_env_recorded(self):
        """R4 practitioner 4.16: a run JSON that records root "." (every released run) must not override
        $TRANSCRIPTLAB_ROOT or --root. Precedence: --root > $TRANSCRIPTLAB_ROOT > recorded (absolute, still a root) >
        parents of the run directory > parents of the cwd."""
        env_root, flag_root, rec_root = fake_root("envroot"), fake_root("flagroot"), fake_root("recroot")
        run_dir, cwd = tmpdir("run"), tmpdir("cwd")
        with env_and_cwd(cwd, TRANSCRIPTLAB_ROOT=env_root):
            self.assertEqual(B.resolve_root(None, recorded=".", near=run_dir), (env_root, "$TRANSCRIPTLAB_ROOT"))
            self.assertEqual(B.resolve_root(None, recorded=str(rec_root), near=run_dir)[0], env_root)
            self.assertEqual(B.resolve_root(str(flag_root), recorded=str(rec_root), near=run_dir), (flag_root, "--root"))
        with env_and_cwd(cwd, TRANSCRIPTLAB_ROOT=None):
            self.assertEqual(B.resolve_root(None, recorded=str(rec_root), near=run_dir)[0], rec_root)
            inner = rec_root / "experiments" / "transcriptlab_cli" / "run_x"
            inner.mkdir(parents=True)
            self.assertEqual(B.resolve_root(None, recorded=".", near=inner),        # a released run inside its tree
                             (rec_root, "nearest parent of the run directory"))
            gone = str(WORK / "moved_away")                                          # recorded root no longer exists
            self.assertEqual(B.resolve_root(None, recorded=gone, near=inner)[0], rec_root)
        with env_and_cwd(cwd, TRANSCRIPTLAB_ROOT=cwd):                               # an explicit non-root is an error
            with self.assertRaises(B.SetupError) as cm:
                B.resolve_root(None, recorded=str(rec_root))
            self.assertIn("$TRANSCRIPTLAB_ROOT", str(cm.exception))

    def test_report_uses_env_root_not_recorded_dot(self):
        """`report` on a run that records root "." with $TRANSCRIPTLAB_ROOT set: the env root is used (it used to fail
        with exit 2, 'is not a TranscriptLab repository root', because "." resolved to the cwd)."""
        env_root, cwd = fake_root("envroot_report"), tmpdir("cwd_report")
        run_dir = tmpdir("released_run")
        (run_dir / "transcriptlab_run.json").write_text(json.dumps({"root": ".", "format": "gemma4", "model": "m"}))
        err = io.StringIO()
        with env_and_cwd(cwd, TRANSCRIPTLAB_ROOT=env_root), contextlib.redirect_stderr(err):
            rc, out = run_cli("report", run_dir, "--quiet")
        self.assertIn(f"root: {env_root} ($TRANSCRIPTLAB_ROOT; the run recorded .)", out)
        self.assertNotIn("is not a TranscriptLab repository root", err.getvalue())
        self.assertEqual(rc, 2)                                      # gets past the root: stops at the missing gen.jsonl
        self.assertIn("gen.jsonl missing", err.getvalue())

    def test_corpus_accepts_root_contexts_dir_or_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "pnc"; s1 = root / "contexts" / Path(B.CORPUS_S1).name; s1.mkdir(parents=True)
            m = s1 / "manifest.json"; m.write_text("{}")
            for arg in (root, s1, m):
                self.assertEqual(B.corpus_manifest(Path(d), str(arg)), m.resolve())
            with self.assertRaises(B.SetupError):
                B.corpus_manifest(Path(d), str(Path(d) / "empty_dir_missing"))
            (Path(d) / "empty").mkdir()
            with self.assertRaises(B.SetupError):
                B.corpus_manifest(Path(d), str(Path(d) / "empty"))

    def test_boot_adapts_requests_for_new_models_only(self):
        import subprocess
        try:
            import httpx  # noqa: F401
        except ImportError:
            self.skipTest("httpx not installed")
        with tempfile.TemporaryDirectory() as d:
            fz = Path(d)
            (fz / "qwenproto.py").write_text(
                "MODELS = {'reg': {'fmt': 'hermes'}}\n"
                "class T:\n"
                "    eos_token_id = 9; unk_token_id = None; unk_token = None; bos_token = '<s>'; bos_token_id = 1\n"
                "    def convert_tokens_to_ids(self, x): return {'<|im_end|>': 7, '<|end_of_text|>': 8}.get(x)\n"
                "    def __call__(self, s, add_special_tokens=False): return {'input_ids': ([1] if add_special_tokens else []) + list(range(len(s)))}\n"
                "def hf_tok(mk): return T()\n")
            (fz / "run_ext.py").write_text(
                "import asyncio, json, sys, httpx, qwenproto as qp\n"
                "TOK = qp.hf_tok(sys.argv[1]); STOP = [TOK.convert_tokens_to_ids('<|im_end|>'), TOK.convert_tokens_to_ids('<|endoftext|>')]\n"
                "seen = []\n"
                "def h(req): seen.append(json.loads(req.content)); return httpx.Response(200, text='ok')\n"
                "async def main():\n"
                "    async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:\n"
                "        async with c.stream('POST', 'http://x/v1/completions', json={'prompt': '<s>hi', 'stop_token_ids': STOP}) as r:\n"
                "            await r.aread()\n"
                "asyncio.run(main()); b = seen[0]; print(b['stop_token_ids'], b.get('add_special_tokens'))\n")
            def boot(reg, mk):
                r = subprocess.run([sys.executable, "-c", cli.BOOT, str(fz), str(fz / "run_ext.py"), json.dumps(reg), mk],
                                   capture_output=True, text=True, check=True)
                return r.stdout.strip()
            self.assertEqual(boot({"mk": "new", "entry": {"fmt": "hermes"}}, "new"), "[7, 8, 9] False")
            self.assertEqual(boot({"mk": "reg"}, "reg"), "[7, None] None")   # registered models: request unchanged

    def test_interp_keeps_venv_symlink(self):
        """--python <venv>/bin/python must not be resolved to the base interpreter (that drops the venv's packages)."""
        with tempfile.TemporaryDirectory() as d:
            link = Path(d) / "python"
            link.symlink_to(sys.executable)
            self.assertEqual(cli._interp(str(link)), str(link.absolute()))
            self.assertNotEqual(cli._interp(str(link)), str(Path(sys.executable).resolve()))


@unittest.skipUnless(ROOT is not None, "TranscriptLab tree not found (set TRANSCRIPTLAB_ROOT)")
class Tree(unittest.TestCase):
    def test_estimate_command_prints_1200(self):
        rc, out = run_cli("estimate", "--pool", "A1", "--arms", "P0,P1,P6,P8a")
        self.assertEqual(rc, 0)
        self.assertIn("300 states x 4 arms = 1,200 generations", out)

    def test_every_command_prints_the_root_it_uses(self):
        """R4 practitioner 2.9: root auto-discovery is never silent."""
        rc, out = run_cli("verify", "--root", ROOT)
        self.assertEqual(rc, 0, out)
        self.assertEqual(out.splitlines()[0], f"root: {ROOT} (--root)")
        rc, out = run_cli("estimate", "--root", ROOT)
        self.assertTrue(out.startswith(f"root: {ROOT} (--root)"))

    def test_frozen_files_match_pins(self):
        for fmt in ("gemma4", "hermes"):
            rows = B.check_pinned(ROOT, fmt)
            self.assertTrue(rows and all(r["ok"] for r in rows), [r for r in rows if not r["ok"]])

    def test_verify_detects_a_changed_file(self):
        fake = tmpdir("fakeroot")
        dst = fake / B.A_SCRIPTS
        dst.mkdir(parents=True)
        for name in B.A_PINNED:
            shutil.copy(ROOT / B.A_SCRIPTS / name, dst / name)
        # the export record of the tree under test, if any (public tree: the scripts are path-rewritten exports)
        base = json.loads((ROOT / B.EXPORT_PINS).read_text()) if (ROOT / B.EXPORT_PINS).exists() else {"files": {}}
        base.setdefault("files", {})
        (fake / B.EXPORT_PINS).write_text(json.dumps(base))
        self.assertTrue(all(r["ok"] for r in B.check_pinned(fake, "gemma4")))      # untouched copies pass
        rel = f"{B.A_SCRIPTS}/variants.py"
        target = fake / rel
        with open(target, "a") as f:
            f.write("\n# edited\n")
        st = {Path(r["file"]).name: r["status"] for r in B.check_pinned(fake, "gemma4")}
        self.assertEqual(st["variants.py"], "DIFF")
        self.assertIn(st["run_injection.py"], ("frozen", "exported"))
        rc, out = run_cli("verify", "--root", fake)
        self.assertEqual(rc, 1)
        self.assertIn("DIFF", out)
        # a file passes as an export only if the record names exactly this export of exactly the pinned frozen file
        pins = json.loads(json.dumps(base))
        pins["files"][rel] = {"frozen_sha256": B.A_PINNED["variants.py"], "exported_sha256": B.sha256(target)}
        (fake / B.EXPORT_PINS).write_text(json.dumps(pins))
        st = {Path(r["file"]).name: r["status"] for r in B.check_pinned(fake, "gemma4")}
        self.assertEqual(st["variants.py"], "exported")
        with open(target, "a") as f:
            f.write("# a further edit\n")
        self.assertEqual({Path(r["file"]).name: r["status"] for r in B.check_pinned(fake, "gemma4")}["variants.py"], "DIFF")
        pins["files"][rel] = {"frozen_sha256": "0" * 64, "exported_sha256": B.sha256(target)}   # export of another file
        (fake / B.EXPORT_PINS).write_text(json.dumps(pins))
        self.assertEqual({Path(r["file"]).name: r["status"] for r in B.check_pinned(fake, "gemma4")}["variants.py"], "DIFF")

    @unittest.skipUnless(have(B.META_S1), "state metadata absent")
    def test_meta_localization_changes_only_the_two_paths(self):
        src = tmpdir("meta")
        with open(ROOT / B.META_S1) as f, open(src / "meta.jsonl", "w") as fo:
            for i, line in enumerate(f):
                if i == 5:
                    break
                d = json.loads(line)
                d["contexts_file"] = "/nonexistent/x/contexts.jsonl"
                d["template_path"] = "/nonexistent/x/chat_template.jinja"
                fo.write(json.dumps(d) + "\n")
        corpus = src / "corpus"
        corpus.mkdir()
        (corpus / "manifest.json").write_text("{}")
        dst, loc = B.localized_meta(ROOT, corpus / "manifest.json", src, src / "meta.jsonl")
        self.assertTrue(loc)
        for a, b in zip(jsonl(src / "meta.jsonl"), jsonl(dst)):
            self.assertEqual(b["contexts_file"], str(corpus / "contexts.jsonl"))
            self.assertEqual(b["template_path"], str(corpus / "chat_template.jinja"))
            a.pop("contexts_file"); a.pop("template_path"); b.pop("contexts_file"); b.pop("template_path")
            self.assertEqual(a, b)
        with open(ROOT / B.META_S1) as f:
            first = json.loads(f.readline())
        resolvable = all(B._resolve(ROOT, first[k]).exists() for k in ("contexts_file", "template_path"))
        if resolvable:   # in-project (absolute) or public tree with the dataset at <root>/data/pnc (repo-relative)
            same, loc2 = B.localized_meta(ROOT, B.corpus_manifest(ROOT), src)
            self.assertFalse(loc2)
            self.assertEqual(same, ROOT / B.META_S1)
            rel_rec = dict(first, contexts_file=os.path.relpath(B._resolve(ROOT, first["contexts_file"]), ROOT),
                           template_path=os.path.relpath(B._resolve(ROOT, first["template_path"]), ROOT))
            (src / "meta_rel.jsonl").write_text(json.dumps(rel_rec) + "\n")       # repo-relative form, as exported
            self.assertEqual(B.localized_meta(ROOT, corpus / "manifest.json", src, src / "meta_rel.jsonl"),
                             (src / "meta_rel.jsonl", False))

    @unittest.skipUnless(have_pnc(), NO_PNC)
    @unittest.skipUnless(have("experiments/contagion/data/confirmatory/plans/plan_bf16_core_full.jsonl"), "registered plan absent")
    def test_job_list_equals_registered_core_plan(self):
        out = tmpdir("dry")
        rc, _ = run_cli("run", "--base", "http://127.0.0.1:9/v1", "--model", "m", "--tokenizer", "t", "--out", out, "--dry-run")
        self.assertEqual(rc, 0)
        mine = [(j["id"], j["pathway"], j["k"]) for j in jsonl(out / "plan.jsonl")]
        reg = [(j["id"], j["pathway"], j["k"]) for j in
               jsonl(ROOT / "experiments/contagion/data/confirmatory/plans/plan_bf16_core_full.jsonl")]
        self.assertEqual(mine, reg)
        self.assertEqual(len(mine), 1200)

    @unittest.skipUnless(have_pnc(), NO_PNC)
    @unittest.skipUnless(have("experiments/crossfamily/out/ext/ids_A1.txt"), "X's id list absent")
    def test_ids_equal_registered_extension_ids(self):
        out = tmpdir("dryx")
        rc, _ = run_cli("run", "--format", "qwen3_coder", "--mk", "qwen3-coder-30b", "--base", "http://127.0.0.1:9/v1",
                        "--model", "m", "--out", out, "--dry-run")
        self.assertEqual(rc, 0)
        self.assertEqual((out / "ids.txt").read_text().split(),
                         (ROOT / "experiments/crossfamily/out/ext/ids_A1.txt").read_text().split())

    @unittest.skipUnless(have_pnc(), NO_PNC)
    @unittest.skipUnless(have("experiments/contagion/out/main/rCbf16_v2.jsonl", "experiments/contagion/out/confirmatory/bf16_core_all.json")
                         and importable("numpy"), "bf16 run file or numpy absent")
    def test_report_reproduces_the_paper_bf16_row(self):
        out = tmpdir("bf16")
        run_cli("run", "--base", "http://127.0.0.1:9/v1", "--model", "gemma-4-31b-bf16", "--tokenizer", "t", "--out", out,
                "--dry-run")
        os.symlink(ROOT / "experiments/contagion/out/main/rCbf16_v2.jsonl", out / "gen.jsonl")
        (out / "run.log").write_text("finished 1200 in 0.0 min\n")
        rc, txt = run_cli("report", out, "--quiet")
        self.assertEqual(rc, 0, txt)
        self.assertEqual(json.loads((out / "analysis.json").read_text()),
                         json.loads((ROOT / "experiments/contagion/out/confirmatory/bf16_core_all.json").read_text()))
        self.assertIn("P1     9.0% [5.7, 12.5]", txt)

    @unittest.skipUnless(have_pnc(), NO_PNC)
    @unittest.skipUnless(have("experiments/crossfamily/out/ext/gen_qwen3-coder-30b.jsonl",
                              "experiments/crossfamily/out/ext/ana_qwen3-coder-30b.json") and importable("numpy", "vllm"),
                         "X's released generations or numpy/vllm absent")
    def test_report_reproduces_x_extension_row(self):
        out = tmpdir("xrow")
        run_cli("run", "--format", "qwen3_coder", "--mk", "qwen3-coder-30b", "--base", "http://127.0.0.1:9/v1",
                "--model", "qwen3-coder-30b", "--out", out, "--dry-run")
        os.symlink(ROOT / "experiments/crossfamily/out/ext/gen_qwen3-coder-30b.jsonl", out / "gen.jsonl")
        rc, txt = run_cli("report", out, "--quiet")
        self.assertEqual(rc, 0, txt)
        mine = json.loads((out / "analysis.json").read_text())
        reg = json.loads((ROOT / "experiments/crossfamily/out/ext/ana_qwen3-coder-30b.json").read_text())
        for arm in ("P0", "P1L", "P1N", "P5", "P6", "P8a"):
            self.assertEqual(mine["arms"][arm]["P_malformed_edit_uncond"], reg["arms"][arm]["P_malformed_edit_uncond"], arm)
        for arm in ("P1L", "P6"):
            self.assertEqual(mine["paired_vs_P0"][arm]["uncond"], reg["paired_vs_P0"][arm]["uncond"], arm)


GEMMA_TOK = MODELS / "gemma-4-31b-it-qat-w4a16-ct"
QWEN_TOK = MODELS / "Qwen3-8B"


@unittest.skipUnless(ROOT is not None and have(B.META_S1) and have_pnc() and importable("vllm", "transformers", "httpx", "numpy"),
                     "public states, PNC dataset, vLLM 0.19.1, transformers, httpx or numpy absent")
class EndToEndMock(unittest.TestCase):
    @unittest.skipUnless(GEMMA_TOK.exists(), f"Gemma 4 tokenizer not at {GEMMA_TOK}")
    def test_gemma4_pilot_run_and_report(self):
        from mock_backend import MockServer
        out = tmpdir("e2e_gemma")
        with MockServer("gemma4", served="mock-gemma") as m:
            rc, txt = run_cli("run", "--base", m.base, "--model", "mock-gemma", "--tokenizer", GEMMA_TOK,
                              "--limit-states", 3, "--conc", 4, "--out", out)
            self.assertEqual(rc, 0, txt)
            self.assertIn("3 states x 4 arms = 12 generations", txt)
        recs = jsonl(out / "gen.jsonl")
        self.assertEqual(len(recs), 12)
        self.assertTrue(all(not r.get("error") and r.get("judge") for r in recs), [r.get("error") for r in recs])
        flagged = sum(bool(r["judge"].get("malformed")) for r in recs)
        self.assertEqual(flagged, sum(x["bad"] for x in m.log))   # the judge flags exactly the slipped calls
        rc, txt = run_cli("report", out, "--quiet", "--B", 200)
        self.assertEqual(rc, 0, txt)
        ana = json.loads((out / "analysis.json").read_text())
        self.assertEqual(ana["complete_states"], 3)
        self.assertIn("TranscriptLab report: mock-gemma (gemma4), pool A1, 3 states", txt)

    @unittest.skipUnless(QWEN_TOK.exists(), f"Qwen3-8B tokenizer not at {QWEN_TOK}")
    def test_new_hermes_model_pilot_run(self):
        from mock_backend import MockServer
        out = tmpdir("e2e_hermes")
        with MockServer("hermes", served="my-hermes-model") as m:
            rc, txt = run_cli("run", "--format", "hermes", "--base", m.base, "--model", "my-hermes-model",
                              "--tokenizer", QWEN_TOK, "--limit-states", 2, "--conc", 4, "--workers", 2, "--out", out)
            self.assertEqual(rc, 0, txt)
        recs = jsonl(out / "gen.jsonl")
        self.assertEqual(len(recs), 8)
        self.assertTrue(all(r.get("judge") is not None for r in recs), [r.get("error") for r in recs])
        self.assertEqual(sum(x["bad"] for x in m.log), sum(bool(r["judge"].get("malformed")) for r in recs))
        run = json.loads((out / "transcriptlab_run.json").read_text())
        self.assertEqual(run["mk"], "my-hermes-model")


if __name__ == "__main__":
    unittest.main(verbosity=2)
