#!/usr/bin/env python3
"""Create a NEW GitHub repository from an allowlisted clean source directory.

Dry run by default. Actual publication requires --apply, --public/--private,
installed Git/GitHub CLI, an authenticated account and typed repo confirmation.
Existing Git histories/remotes are refused rather than accidentally published.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from check_repository import ROOT, SENSITIVE, check, publication_files
from configure_github import configure, validate_repo


def checked(command, **kwargs):
    print(subprocess.list2cmdline(command), flush=True)
    return subprocess.run(command, check=True, cwd=ROOT, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="OWNER/windows-ai-dev-state-backup")
    visibility = parser.add_mutually_exclusive_group()
    visibility.add_argument("--public", action="store_true")
    visibility.add_argument("--private", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--seed-issues", action="store_true")
    args = parser.parse_args()
    repo = validate_repo(args.repo)
    result = check()
    if not result["passed"]:
        raise SystemExit("Publication preflight failed: " + "; ".join(result["errors"]))
    mode = "--public" if args.public else "--private"
    project = json.loads((ROOT / "release/project.json").read_text())
    create = ["gh", "repo", "create", repo, mode, "--source", str(ROOT), "--remote", "origin", "--push",
              "--description", project["description"]]
    print("Allowlisted source files only. Real backup directories and old Git history are not included.")
    print("Planned repository visibility:", "public" if args.public else "private")
    print(subprocess.list2cmdline(create))
    if not args.apply:
        print("DRY RUN: no Git repository, commit, network request or upload was created.")
        configure(repo, apply=False, seed_issues=args.seed_issues)
        return 0
    if not (args.public or args.private):
        raise SystemExit("Actual publication requires explicit --public or --private.")
    if not shutil.which("gh") or not shutil.which("git"):
        raise SystemExit("Install Git and the official GitHub CLI, then run gh auth login locally.")
    if (ROOT / ".git").exists():
        raise SystemExit("Use a fresh extracted source folder. Existing history is refused to avoid publishing past secrets.")
    parent_repo = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=ROOT,
                                 capture_output=True, text=True)
    if parent_repo.returncode == 0:
        raise SystemExit("This source folder is inside an existing Git worktree; use a separate clean directory.")
    # Refuse an extraction directly into a backup workspace, even though add is allowlisted.
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT).as_posix()
        if SENSITIVE.search(rel):
            raise SystemExit(f"Real state/output directory found. Publish from a separate source folder: {rel}")
    checked(["gh", "auth", "status"])
    identity = []
    for field in ("user.name", "user.email"):
        proc = subprocess.run(["git", "config", "--get", field], cwd=ROOT, capture_output=True, text=True)
        if proc.returncode or not proc.stdout.strip():
            raise SystemExit(f"Configure your own Git {field} before publishing. No identity will be invented.")
        identity.append(proc.stdout.strip())
    print("Git author:", identity[0], "<" + identity[1] + ">")
    print("This will create and push a", "PUBLIC" if args.public else "PRIVATE", "repository.")
    if input(f"Type {repo} to authorize publication: ") != repo:
        raise SystemExit("Cancelled without creating a repository.")
    # No git add . or add --all: only enumerated source paths are staged.
    checked(["git", "init", "--initial-branch=main"])
    checked(["git", "add", "--", *publication_files()])
    staged = checked(["git", "diff", "--cached", "--name-only", "-z"], capture_output=True).stdout
    paths = {x.decode("utf8").replace("\\", "/") for x in staged.split(b"\x00") if x}
    if not paths <= set(publication_files()):
        raise SystemExit("Unexpected staged file detected; publication stopped.")
    checked(["git", "diff", "--cached", "--check"])
    checked(["git", "commit", "-m", "Prepare safety-focused v2.0.0-rc.1 candidate"])
    checked(create)
    failures = configure(repo, apply=True, seed_issues=args.seed_issues)
    print("Source published. Do NOT announce a stable release: wait for CI and the manual release gate.")
    print("Run the Draft release workflow only after CI is green; upload assets/social-preview.png in Settings.")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"Publication stopped: {exc}. Check what completed before retrying.")
