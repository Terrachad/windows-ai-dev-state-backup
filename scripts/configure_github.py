#!/usr/bin/env python3
"""Preview/apply repository metadata. Uses installed gh authentication, not tokens in files."""
from __future__ import annotations
import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate_repo(repo: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", repo):
        raise ValueError("Use a GitHub OWNER/REPOSITORY identifier, not a URL.")
    return repo


def commands(repo: str) -> list[list[str]]:
    repo = validate_repo(repo)
    project = json.loads((ROOT / "release/project.json").read_text())
    return [
        ["gh", "repo", "edit", repo, "--description", project["description"], "--enable-issues",
         "--enable-discussions", "--enable-wiki=false", "--enable-projects=false",
         "--enable-squash-merge", "--enable-merge-commit=false", "--enable-rebase-merge=false",
         "--delete-branch-on-merge", "--add-topic", ",".join(project["topics"])],
        ["gh", "api", "--method", "PUT", f"repos/{repo}/private-vulnerability-reporting"],
        ["gh", "repo", "edit", repo, "--enable-secret-scanning", "--enable-secret-scanning-push-protection"],
    ]


def configure(repo: str, apply: bool = False, seed_issues: bool = False) -> int:
    failures = 0
    for command in commands(repo):
        print(subprocess.list2cmdline(command))
        if apply:
            proc = subprocess.run(command, check=False)
            if proc.returncode:
                failures += 1
                print("Setting not applied; check repository permissions/plan. No success is assumed.")
    labels = json.loads((ROOT / "release/labels.json").read_text())
    for label in labels:
        cmd = ["gh", "label", "create", label["name"], "--repo", repo, "--color", label["color"],
               "--description", label["description"], "--force"]
        print(subprocess.list2cmdline(cmd))
        if apply and subprocess.run(cmd, check=False).returncode:
            failures += 1
    if seed_issues:
        issues = json.loads((ROOT / "release/initial-issues.json").read_text())
        existing = set()
        if apply:
            response = subprocess.run(["gh", "issue", "list", "--repo", repo, "--state", "all", "--limit", "200",
                                       "--json", "title"], check=True, capture_output=True, text=True)
            existing = {x["title"] for x in json.loads(response.stdout)}
        for issue in issues:
            if issue["title"] in existing:
                continue
            cmd = ["gh", "issue", "create", "--repo", repo, "--title", issue["title"],
                   "--body", issue["body"], "--label", ",".join(issue["labels"])]
            print(subprocess.list2cmdline(cmd))
            if apply and subprocess.run(cmd, check=False).returncode:
                failures += 1
    print("Manual checks remain: social preview upload, branch protection, owner/reviewer assignment and CI results.")
    return failures


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", required=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--seed-issues", action="store_true")
    a = p.parse_args()
    validate_repo(a.repo)
    raise SystemExit(1 if configure(a.repo, a.apply, a.seed_issues) else 0)
