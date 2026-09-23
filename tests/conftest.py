"""Make the repo root importable so tests can import the build scripts directly."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# No real boot-time refreshes under pytest. Starting the app (TestClient
# lifespan) otherwise spawns render subprocesses and scorecard pulls that
# outlive the tests and write into the repo. See app._kick_boot_refresh.
os.environ.setdefault("HVT_BOOT_REFRESH", "0")
