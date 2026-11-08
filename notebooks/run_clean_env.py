"""Run the quickstart in CLEAN environments (fresh venvs without pip: no third-party packages) and time it.

    python run_clean_env.py [python ...]     # default: this interpreter (each gets a fresh venv)
Writes _work/VERIFY.json. Uses only the repository tree and the PNC dataset; HOME and PYTHONPATH are not inherited.
"""
import json, os, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = HERE / "_work"
pythons = sys.argv[1:] or [sys.executable]
log = []
for py in pythons:
    tag = Path(py).name
    venv = WORK / f"venv_clean_{tag}"
    out = WORK / f"out_{tag}"
    for p in (venv, out):
        shutil.rmtree(p, ignore_errors=True)
    subprocess.run([py, "-m", "venv", "--without-pip", str(venv)], check=True)
    vpy = venv / "bin" / "python"
    pkgs = subprocess.run([str(vpy), "-c", "import sys,os; sp=[p for p in sys.path if p.endswith('site-packages')]; "
                           "print(sorted(x for p in sp if os.path.isdir(p) for x in os.listdir(p)))"],
                          capture_output=True, text=True).stdout.strip()
    env = {"PATH": f"{venv / 'bin'}:/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": str(WORK), "TRANSCRIPTLAB_ROOT": str(ROOT),
           "QUICKSTART_OUT": str(out)}
    t0 = time.time()
    r = subprocess.run([str(vpy), "-I", str(HERE / "quickstart.py")], cwd=str(WORK), env=env, capture_output=True, text=True,
                       timeout=300)
    dt = time.time() - t0
    (WORK / f"quickstart_{tag}.log").write_text(r.stdout + r.stderr)
    ver = subprocess.run([str(vpy), "-c", "import sys; print(sys.version.split()[0])"], capture_output=True, text=True).stdout.strip()
    log.append({"python": ver, "venv": "fresh, --without-pip", "site_packages": pkgs, "exit": r.returncode,
                "seconds": round(dt, 1), "under_5_min": dt < 300, "log": f"_work/quickstart_{tag}.log"})
    print(json.dumps(log[-1]))
(WORK / "VERIFY.json").write_text(json.dumps({"checked_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "runs": log}, indent=1))
sys.exit(0 if all(x["exit"] == 0 and x["under_5_min"] for x in log) else 1)
