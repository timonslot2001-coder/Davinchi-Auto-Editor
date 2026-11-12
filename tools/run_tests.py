"""Run every test script of the repo and say what passed.
usage: python tools/run_tests.py [-k text] [--quick]
  -k text   only tests whose file name contains text
  --quick   leave out the slow end-to-end test (smoke_test.py, about 5 minutes)

Tests are plain scripts with asserts (exit code 0 = passed). None of them needs Resolve, the SSD or real footage;
gridflow_test.py does need real footage and is left out."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKIP = {"gridflow_test.py", "run_tests_test.py"}      # real footage / would run this runner inside itself
SLOW = {"smoke_test.py"}


def tests(pick: str | None, quick: bool = False) -> list[Path]:
    found = sorted((REPO / "tests").glob("*_test.py")) + sorted((REPO / "VIDEO_EDITING_SYSTEM" / "tests").glob("*_test.py"))
    found += sorted((REPO / "tests").glob("*_test.js")) if shutil.which("node") else []
    skip = SKIP | (SLOW if quick else set())
    return [t for t in found if t.name not in skip and (not pick or pick in t.name)]


def main() -> int:
    pick = sys.argv[sys.argv.index("-k") + 1] if "-k" in sys.argv[:-1] else None
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    passed, failed = 0, []
    for t in tests(pick, "--quick" in sys.argv):
        cmd = ["node", str(t)] if t.suffix == ".js" else [sys.executable, str(t)]
        t0 = time.time()
        r = subprocess.run(cmd, cwd=t.parents[1], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        ok = r.returncode == 0
        print(f"{'ok  ' if ok else 'FAIL'} {t.relative_to(REPO).as_posix()} ({time.time() - t0:.1f} s)", flush=True)
        if ok:
            passed += 1
        else:
            failed.append(t)
            print("     " + "\n     ".join((r.stdout + r.stderr).strip().splitlines()[-12:]))
    print(f"{passed} passed, {len(failed)} failed")
    return 0 if passed and not failed else 1


if __name__ == "__main__":
    sys.exit(main())
