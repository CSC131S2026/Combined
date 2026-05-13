#!/usr/bin/env python3
"""Run both Backend/tests and Frontend/tests as one command.

Sets PYTHONPATH to mirror the sys.path adjustments the production
entrypoints make, then runs unittest discover in each tests folder.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def run(suite: str, cwd: Path, extra_path: str) -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT), extra_path, env.get("PYTHONPATH", "")])
    print(f"\n=== {suite} ===")
    return subprocess.call(
        [sys.executable, "-m", "unittest", "discover", "tests"],
        cwd=cwd, env=env,
    )

def main() -> int:
    rc = 0
    rc |= run("Backend", ROOT / "Backend", str(ROOT / "Backend"))
    rc |= run("Frontend", ROOT / "Frontend", str(ROOT / "Frontend"))
    return rc

if __name__ == "__main__":
    sys.exit(main())
