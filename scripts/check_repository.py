#!/usr/bin/env python3
"""Publication guard: allowlist, source syntax, links, metadata and secret heuristics.

This is not a substitute for reviewing git status, Git history and secret-scanning
alerts. It does not inspect or upload real backups.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SENSITIVE = re.compile(r"(?:^|/)(?:DEV_STATE_BACKUP_[^/]*|\.incomplete-[^/]*|\.aidbackup-[^/]*|"
                       r"backups|rehearsals|reports|\.claude|\.codex|\.ssh|\.aws|\.azure|\.kube)(?:/|$)", re.I)
EXTENSIONS = {".7z", ".zip", ".jsonl", ".reg", ".sqlite", ".sqlite3", ".db", ".pem", ".pfx", ".p12", ".log"}
PATTERNS = [re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
            re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
            re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}\b"),
            re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{32,}\b"),
            re.compile(r"\bAKIA[0-9A-Z]{16}\b")]


def publication_files(root: Path = ROOT) -> list[str]:
    data = json.loads((root / "release/publish-files.json").read_text(encoding="utf8"))
    paths = data["files"]
    if not isinstance(paths, list) or len(set(paths)) != len(paths):
        raise ValueError("Publication allowlist is malformed or duplicated.")
    for rel in paths:
        if (not isinstance(rel, str) or not rel or "\\" in rel or rel.startswith("/")
                or any(x in ("", ".", "..") for x in rel.split("/"))):
            raise ValueError(f"Unsafe allowlist path: {rel!r}")
    return sorted(paths)


def check(root: Path = ROOT) -> dict:
    files = publication_files(root)
    errors = []
    for rel in files:
        path = root / rel
        if SENSITIVE.search(rel) or path.suffix.lower() in EXTENSIONS:
            errors.append(f"Sensitive/generated path in publication allowlist: {rel}")
        if not path.is_file() or path.is_symlink():
            errors.append(f"Missing/non-regular publication file: {rel}")
            continue
        if any(p.is_symlink() for p in path.parents if p != root.parent):
            errors.append(f"Symlink ancestor in publication path: {rel}")
        raw = path.read_bytes()
        if path.suffix in (".png",):
            continue
        try:
            text = raw.decode("utf8")
        except UnicodeDecodeError:
            errors.append(f"Text file is not UTF-8: {rel}")
            continue
        if any(p.search(text) for p in PATTERNS):
            errors.append(f"Possible secret signature: {rel}")
        if path.suffix == ".py":
            try:
                ast.parse(text, filename=rel)
            except SyntaxError as exc:
                errors.append(str(exc))
        if path.suffix == ".bat":
            if (raw.startswith(b"\xef\xbb\xbf") or not raw.startswith(b"@echo off\r\n")
                    or b"\n" in raw.replace(b"\r\n", b"")):
                errors.append(f"BAT must be no-BOM ASCII with CRLF: {rel}")
            if any(len(line) > 2048 for line in text.splitlines()) or "EncodedCommand" in text:
                errors.append(f"Unexpected embedded command payload: {rel}")
        if path.suffix == ".md":
            for link in re.findall(r"\]\(([^\s)]+)(?:\s[^)]*)?\)", text):
                if link.startswith(("http:", "https:", "mailto:", "#")):
                    continue
                target = (path.parent / link.split("#")[0]).resolve()
                if not target.exists():
                    errors.append(f"Broken relative link in {rel}: {link}")
        if rel.startswith(".github/workflows/"):
            for action in re.findall(r"uses:\s*([^\s#]+)", text):
                if not re.fullmatch(r"[^@]+@[0-9a-f]{40}", action):
                    errors.append(f"Unpinned action in {rel}: {action}")
            if "pull_request_target:" in text:
                errors.append(f"Untrusted PR target execution is disallowed: {rel}")
    project = json.loads((root / "release/project.json").read_text())
    package = tomllib.loads((root / "pyproject.toml").read_text())
    if package["project"]["version"] != project["python_version"]:
        errors.append("Project and package versions disagree.")
    topics = project["topics"]
    if not 1 <= len(topics) <= 20 or len(set(topics)) != len(topics):
        errors.append("Topics must be unique and at most 20.")
    if any(not re.fullmatch(r"[a-z0-9-]{1,50}", x) for x in topics):
        errors.append("Invalid GitHub topic syntax.")
    if package["project"]["dependencies"]:
        errors.append("Unexpected runtime dependency; review public dependency-free claim.")
    return {"passed": not errors, "publication_file_count": len(files), "errors": errors,
            "scope": "Syntax, allowlist, local links, version consistency, action pins and secret-pattern heuristics. "
                     "Not a complete secret scan or Windows runtime test."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = check()
    print(json.dumps(result, indent=2))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    raise SystemExit(0 if result["passed"] else 1)
