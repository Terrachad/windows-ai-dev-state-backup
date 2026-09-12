"""Explicit backup selection, dry-run-first restore, offline runtime."""
from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile
from pathlib import Path

from . import __version__
from .core import (BackupError, absolute, content_equal, create_archive, create_snapshot,
                   digest_file, read_json, rehearse, restore_snapshot, tree, unpack_archive,
                   validate_manifest, verify_archive, verify_snapshot)
from .providers import current_context, discover, restore_targets


def progress(message: str) -> None:
    print(message, flush=True)


def select_backup(toolkit: Path, explicit: str | None) -> Path:
    if explicit:
        return absolute(os.path.abspath(explicit))
    candidates = []
    search = [toolkit, toolkit / "backups"]
    if (toolkit / "complete.json").is_file():
        candidates.append(toolkit)
    for parent in search:
        if not parent.is_dir():
            continue
        for child in parent.iterdir():
            if not child.name.startswith("DEV_STATE_BACKUP_") or not child.is_dir():
                continue
            if not (child / "complete.json").is_file():
                continue
            try:
                completion = read_json(child / "complete.json")
                manifest = read_json(child / "manifest.json")
                validate_manifest(manifest)
                if completion.get("manifest_sha256") != digest_file(child / "manifest.json")["sha256"]:
                    continue
            except (OSError, BackupError):
                continue
            candidates.append(child)
    candidates = sorted(set(candidates), key=lambda p: p.name, reverse=True)
    if not candidates:
        raise BackupError("No completed format-3 snapshots found. Incomplete/legacy folders are not eligible. "
                          "Use --backup for an explicit snapshot or see docs/migration.md.")
    if len(candidates) == 1:
        progress(f"Selected snapshot: {candidates[0]}")
        return candidates[0]
    print("\nChoose an explicit snapshot. No newest-by-default restore is performed.")
    for index, path in enumerate(candidates, 1):
        print(f"  {index}. {path.name}")
    try:
        number = int(input("Snapshot number (blank cancels): "))
    except (EOFError, ValueError) as exc:
        raise BackupError("Backup selection cancelled.") from exc
    if not 1 <= number <= len(candidates):
        raise BackupError("Invalid backup selection.")
    return candidates[number - 1]


def confirm(word: str, supplied: str | None) -> None:
    if supplied is None:
        try:
            supplied = input(f"Type {word} to continue: ")
        except EOFError as exc:
            raise BackupError("Confirmation required; operation cancelled.") from exc
    if supplied != word:
        raise BackupError("Confirmation did not match; operation cancelled.")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backup Claude Code and Codex state; restore without deleting originals.")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--toolkit", type=Path, default=Path.cwd(),
                        help="Folder containing launchers (automatically set by BATs).")
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup", help="Create a completed snapshot; sources are read-only.")
    backup.add_argument("--output", type=Path, help="Parent folder for snapshots (default: toolkit/backups).")
    backup.add_argument("--tools", nargs="+", choices=("claude", "codex"))
    backup.add_argument("--include-dev", action="store_true", help="Opt in to SSH/Git/cloud/editor state.")
    backup.add_argument("--include-desktop", action="store_true", help="Archive desktop state as manual-restore reference.")
    backup.add_argument("--no-archive", action="store_true", help="Keep a verified directory snapshot without a ZIP.")
    backup.add_argument("--confirm", choices=("BACKUP",), help="Explicit non-interactive acknowledgement of sensitive output.")
    check = commands.add_parser("check", help="Validate snapshot/ZIP contents against the completed manifest.")
    check.add_argument("--backup")
    check.add_argument("--compare-live", action="store_true", help="Also compare current-user data (before reinstall only).")
    restore = commands.add_parser("restore", help="Dry run by default; --apply enables writes after confirmation.")
    restore.add_argument("--backup")
    restore.add_argument("--apply", action="store_true")
    restore.add_argument("--components", nargs="+")
    restore.add_argument("--target-map", type=Path, help="Explicit local JSON mapping of component IDs to new absolute paths.")
    restore.add_argument("--confirm", choices=("RESTORE",))
    rehearsal = commands.add_parser("rehearse", help="Test the restore engine only in an isolated rehearsal directory.")
    rehearsal.add_argument("--backup")
    rehearsal.add_argument("--confirm", choices=("REHEARSE",))
    unpack = commands.add_parser("unpack", help="Validate then unpack a ZIP into a new, private directory.")
    unpack.add_argument("--archive", required=True, type=Path)
    unpack.add_argument("--destination", required=True, type=Path)
    return parser


def run(args: argparse.Namespace) -> int:
    toolkit = absolute(os.path.abspath(args.toolkit))
    if args.command == "backup":
        home, env = current_context()
        components = discover(home, env, include_dev=args.include_dev,
                              include_desktop=args.include_desktop, tools=args.tools)
        print(f"Current Windows profile: {home}")
        print("Close the applications first. Backups are UNENCRYPTED and may contain tokens/private keys.")
        print("No external project roots are scanned; agent-owned state may itself contain cached code/worktrees.")
        for component in components:
            print(f"  {component.id}: {component.source}" + (" [manual restore only]" if not component.restore_allowed else ""))
        output = absolute(os.path.abspath(args.output)) if args.output else toolkit / "backups"
        print(f"Destination: {output}")
        confirm("BACKUP", args.confirm)
        snapshot = create_snapshot(components, output, progress=progress)
        if not args.no_archive:
            create_archive(snapshot, progress=progress)
        print("BACKUP COMPLETE. Verify the independent copy and rehearse before relying on it.")
    elif args.command == "check":
        root = select_backup(toolkit, args.backup)
        if root.is_file():
            if args.compare_live:
                raise BackupError("Unpack first to compare a ZIP against live state.")
            verify_archive(root, progress=progress)
            print("ARCHIVE VERIFIED: sidecar hash, manifest, exact entry set and every included payload.")
        else:
            m = verify_snapshot(root, progress=progress)
            if args.compare_live:
                home, env = current_context()
                targets = restore_targets(m, home, env)
                for c in m["components"]:
                    if c["id"] not in targets:
                        continue
                    target = targets[c["id"]]
                    got = tree(target, claude=c["id"] == "claude") if c["kind"] == "directory" else {
                        "files": [{"path": "value", **digest_file(target)}], "directories": []}
                    content_equal(c, got, c["id"] + " current live comparison")
            print("SNAPSHOT VERIFIED: all included files and empty directories match.")
            print("This verifies the selected snapshot, not an unselected archive or login validity.")
    elif args.command == "restore":
        root = select_backup(toolkit, args.backup)
        m = verify_snapshot(root, progress=progress)
        home, env = current_context()
        overrides = read_json(absolute(os.path.abspath(args.target_map))) if args.target_map else {}
        targets = restore_targets(m, home, env, selected=args.components, overrides=overrides)
        # All live restores by this user share a lock/report root across toolkit copies.
        reports = absolute(env["LOCALAPPDATA"]) / "AiDevStateBackup" / "reports"
        result = restore_snapshot(root, targets, reports, apply=False, progress=progress)
        print(f"Profile receiving data: {home}")
        print("Close all target applications. Restored configuration can include hooks/commands; trust the source.")
        for item in result["plan"]:
            print(f"  {item['id']} -> {item['target']} (existing={item['existing']})")
        for c in m["components"]:
            if not c["restore_allowed"]:
                print(f"  MANUAL-ONLY: {c['id']} is retained in the backup, not restored automatically.")
        if not args.apply:
            print("DRY RUN COMPLETE. No destination, report, or backup files were written.")
            return 0
        confirm("RESTORE", args.confirm)
        restore_snapshot(root, targets, reports, apply=True, progress=progress)
        print("RESTORE COMPLETE. Existing data is preserved in the journal's hold locations.")
    elif args.command == "rehearse":
        root = select_backup(toolkit, args.backup)
        print("Writes only a new rehearsal directory; live Claude/Codex paths are not selected.")
        print("The rehearsal is another unencrypted copy of sensitive data; keep it private.")
        confirm("REHEARSE", args.confirm)
        rehearse(root, toolkit / "rehearsals", progress=progress)
    elif args.command == "unpack":
        destination = absolute(os.path.abspath(args.destination))
        unpack_archive(absolute(os.path.abspath(args.archive)), destination, progress=progress)
        print(f"EXTRACTED AND VERIFIED: {destination}")
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return run(make_parser().parse_args(argv))
    except (BackupError, OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        print(f"\nSTOPPED: {exc}", file=sys.stderr, flush=True)
        print("Do not delete backups, incomplete snapshots, journals or .aidbackup-* recovery folders.",
              file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted. Keep recovery folders and journals; see docs/recovery.md.", file=sys.stderr)
        return 130
