#!/usr/bin/env python3
"""Run from an extracted release or clone without pip installation."""
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is required. No system state was changed.")
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from aidbackup.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
