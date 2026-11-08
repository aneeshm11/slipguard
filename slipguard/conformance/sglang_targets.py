"""Run workstream C's own SGLang harness (diff/worker_x.py, SGLangEnv) with slipguard's experimental detector
registered under SGLang's "gemma4" name, so every SGLang target of the suite (detector / server / stream) exercises
the shim through SGLang's own FunctionCallParser and serving logic. Target names get a "gg." prefix.

    XRT_PROVIDER=sgl0523 <env with SGLang deps> conformance/sglang_targets.py CASES OUT SHARD NSHARDS --suite <C dir>
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SUITE = sys.argv[sys.argv.index("--suite") + 1]
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(SUITE, "diff"))
sys.path.insert(0, SUITE)
import worker  # noqa: E402
import worker_x  # noqa: E402


def main():
    cases_path, out_path, shard, nshards = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    env = worker_x.make_env()                     # loads SGLang's function-call modules (no sglang/__init__)
    from slipguard.integrations.sglang import register
    register("gemma4")                            # the shim replaces SGLang's gemma4 detector for this process
    import sglang.srt.function_call.gemma4_detector as gd
    from sglang.srt.function_call.function_call_parser import FunctionCallParser
    gd.Gemma4Detector = FunctionCallParser.ToolCallParserEnum["gemma4"]   # worker_x's detector target uses this name
    env.Det = gd.Gemma4Detector
    env.targets = {f"gg.{k}": v for k, v in env.targets.items()}
    import logging
    logging.disable(logging.WARNING)
    worker.run_cases(env, cases_path, out_path, shard, nshards, None, 3000, set(), lean="--lean" in sys.argv)


if __name__ == "__main__":
    main()
