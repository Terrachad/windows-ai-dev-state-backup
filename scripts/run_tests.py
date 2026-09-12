#!/usr/bin/env python3
"""Dependency-free test runner; emits machine-readable evidence on request."""
import argparse
import json
import platform
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "src"))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    start = time.perf_counter()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
              "platform": platform.platform(), "tests": result.testsRun,
              "passed": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
              "failures": len(result.failures), "errors": len(result.errors),
              "skipped": [{"test": str(t), "reason": why} for t, why in result.skipped],
              "duration_seconds": round(time.perf_counter() - start, 3),
              "successful": result.wasSuccessful(),
              "scope": "Synthetic fixtures only; not an authenticated Claude/Codex UI restore test."}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
