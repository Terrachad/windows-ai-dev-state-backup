#!/usr/bin/env python3
"""Build deterministic ZIP assets from the reviewed publication allowlist only."""
import argparse
import hashlib
import json
import stat
import sys
import zipfile
from pathlib import Path

from check_repository import ROOT, check, publication_files


def build(output: Path, *, source: bool = False) -> Path:
    result = check()
    if not result["passed"]:
        raise SystemExit("Publication checks failed: " + "; ".join(result["errors"]))
    project = json.loads((ROOT / "release/project.json").read_text())
    flavor = "source" if source else "windows"
    name = f"{project['slug']}-{project['version']}-{flavor}"
    output.mkdir(parents=True, exist_ok=True)
    destination = output / (name + ".zip")
    if destination.exists():
        raise SystemExit(f"Refusing to overwrite an existing release asset: {destination}")
    files = publication_files()
    if not source:
        runtime = {"devstate.py", "LICENSE", *[rel for rel in files if "/" not in rel and rel.endswith(".md")]}
        files = [rel for rel in files if rel in runtime or rel.endswith(".bat")
                 or rel.startswith(("src/", "docs/", "assets/")) or rel in {"release/project.json", "release/local-validation.json"}]
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in files:
            info = zipfile.ZipInfo(name + "/" + rel, date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, (ROOT / rel).read_bytes(), compresslevel=9)
    with zipfile.ZipFile(destination) as z:
        if z.testzip() is not None:
            raise SystemExit("Build archive integrity check failed.")
    sha = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(destination.suffix + ".sha256").write_text(sha + "  " + destination.name + "\n", encoding="ascii")
    print(destination)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--source", action="store_true")
    args = parser.parse_args()
    build(args.output, source=args.source)
