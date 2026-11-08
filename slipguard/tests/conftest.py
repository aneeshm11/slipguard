import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
if os.path.isdir(SRC) and SRC not in sys.path and not os.environ.get("SLIPGUARD_TEST_INSTALLED"):
    sys.path.insert(0, SRC)

# scale of the randomized property tests (1 = default CI size; set SLIPGUARD_TEST_SCALE=10 for the release run)
SCALE = float(os.environ.get("SLIPGUARD_TEST_SCALE", "1"))
