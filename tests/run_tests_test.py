"""The test runner runs the chosen tests and reports a count.
usage: python tests/run_tests_test.py"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
r = subprocess.run([sys.executable, str(ROOT / "tools" / "run_tests.py"), "-k", "grade_looks"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
assert r.returncode == 0, r.stdout + r.stderr
assert "1 passed, 0 failed" in r.stdout, r.stdout
r = subprocess.run([sys.executable, str(ROOT / "tools" / "run_tests.py"), "-k", "no_such_test_xyz"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
assert r.returncode == 1 and "0 passed, 0 failed" in r.stdout, "nothing selected is not a pass"
print("run tests test ok")
