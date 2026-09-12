"""Backup integrity and non-destructive restore primitives.

No shell, app login, credential broker, network client, or recursive delete is
used by this module. A snapshot is not eligible until complete.json exists.
"""
from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import time
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping

from . import FORMAT_VERSION, __version__

CHUNK = 1024 * 1024
Progress = Callable[[str], None]
Fault = Callable[[str, str], None]
MAX_MANIFEST = 64 * 1024 * 1024
_HEX = re.compile(r"[a-f0-9]{64}\Z")
_ID = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
_RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?\Z", re.I)


class BackupError(RuntimeError):
    """A validation, safety or integrity requirement was not met."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def token() -> str:
    return uuid.uuid4().hex


def absolute(path: str | Path) -> Path:
    # Do not resolve() symlinks away before checking them.
    value = os.fspath(path)
    if not value or not os.path.isabs(value):
        raise BackupError(f"An absolute path is required: {value!r}")
    if os.name == "nt" and (value.startswith("\\\\") or value.startswith("//")):
        raise BackupError("UNC and device paths are outside this release's local-disk scope.")
    return Path(os.path.abspath(value))


def native(path: Path) -> str:
    """Extended-length Windows path for file I/O; presentation paths stay normal."""
    value = os.fspath(path)
    if os.name == "nt" and not value.startswith("\\\\?\\"):
        return "\\\\?\\" + value
    return value


def lexists(path: Path) -> bool:
    return os.path.lexists(native(path))


def is_link(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def reject_links(path: Path) -> None:
    """Reject symlinks/junctions in every existing ancestor, including path."""
    path = absolute(path)
    for item in reversed((path, *path.parents)):
        try:
            info = os.lstat(native(item))
        except FileNotFoundError:
            continue
        if is_link(info):
            raise BackupError(f"Reparse point / symbolic link is not supported: {item}")


def inside(path: Path, root: Path) -> bool:
    p, r = os.path.normcase(str(absolute(path))), os.path.normcase(str(absolute(root)))
    return p == r or p.startswith(r.rstrip(os.sep) + os.sep)


def disjoint(paths: Iterable[Path]) -> None:
    items = list(paths)
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            if inside(a, b) or inside(b, a):
                raise BackupError(f"Overlapping paths are not allowed: {a} ; {b}")


def safe_relative(value: str) -> str:
    """A canonical, portable, slash-separated relative Windows filename."""
    if not isinstance(value, str) or not value or "\\" in value:
        raise BackupError(f"Unsafe relative path: {value!r}")
    parts = value.split("/")
    for part in parts:
        if (not part or part in (".", "..") or part.endswith((" ", "."))
                or any(ord(c) < 32 or c in '<>:"|?*' for c in part)
                or _RESERVED.fullmatch(part)):
            raise BackupError(f"Unsafe or non-portable path: {value!r}")
    return value


def join_safe(root: Path, rel: str) -> Path:
    return root.joinpath(*safe_relative(rel).split("/"))


def private_dir(path: Path, *, new: bool = False) -> None:
    reject_links(path)
    if new and lexists(path):
        raise BackupError(f"Destination already exists: {path}")
    os.makedirs(native(path), mode=0o700, exist_ok=not new)
    if os.name != "nt":
        os.chmod(path, 0o700)
        return
    # Paths/arguments are passed without a command shell. No global ACL changes.
    system32 = Path(os.environ["SystemRoot"]) / "System32"
    result = subprocess.run([str(system32 / "whoami.exe"), "/user", "/fo", "csv", "/nh"],
                            check=True, capture_output=True, text=True, errors="replace")
    rows = list(csv.reader(io.StringIO(result.stdout.strip())))
    sid = rows[-1][-1] if rows else ""
    if not re.fullmatch(r"S-1-[0-9-]+", sid):
        raise BackupError("Could not determine current-user SID for private output ACLs.")
    result = subprocess.run([str(system32 / "icacls.exe"), native(path), "/inheritance:r",
                             "/grant:r", f"*{sid}:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F",
                             "*S-1-5-32-544:(OI)(CI)F"], capture_output=True, text=True, errors="replace")
    if result.returncode:
        raise BackupError("Cannot protect output permissions. Use an NTFS local destination. "
                          + result.stderr.strip())


def _json_bytes(obj: object) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def write_json(path: Path, obj: object, *, replace: bool = False) -> None:
    data = _json_bytes(obj)
    reject_links(path)
    temp = path.with_name(path.name + ".tmp-" + token()) if replace else path
    with open(native(temp), "xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    if replace:
        os.replace(native(temp), native(path))


def _unique_pairs(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise BackupError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json_bytes(data: bytes) -> dict:
    if len(data) > MAX_MANIFEST:
        raise BackupError("Manifest exceeds the documented 64 MiB safety limit.")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupError("Invalid UTF-8 JSON metadata.") from exc
    if not isinstance(value, dict):
        raise BackupError("Expected a JSON object.")
    return value


def read_json(path: Path) -> dict:
    reject_links(path)
    with open(native(path), "rb") as stream:
        return load_json_bytes(stream.read(MAX_MANIFEST + 1))


def _read_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)


def digest_file(path: Path) -> dict:
    reject_links(path)
    before = os.lstat(native(path))
    if not stat.S_ISREG(before.st_mode) or is_link(before):
        raise BackupError(f"Not a regular file: {path}")
    digest, count = hashlib.sha256(), 0
    fd = os.open(native(path), _read_flags())
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise BackupError(f"File replaced while opening: {path}")
        while block := stream.read(CHUNK):
            digest.update(block)
            count += len(block)
        after = os.fstat(stream.fileno())
    current = os.lstat(native(path))
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    if stamp(opened) != stamp(after) or stamp(after) != stamp(current) or count != opened.st_size:
        raise BackupError(f"File changed while hashing. Close its application: {path}")
    return {"size": count, "sha256": digest.hexdigest()}


def tree(root: Path, *, claude: bool = False) -> dict:
    root = absolute(root)
    reject_links(root)
    if not os.path.isdir(native(root)):
        raise BackupError(f"Directory missing: {root}")
    files, directories, excluded, seen = [], [], [], set()
    todo = [(root, "")]
    while todo:
        directory, prefix = todo.pop()
        with os.scandir(native(directory)) as scan:
            entries = sorted(scan, key=lambda e: e.name.casefold())
        for entry in entries:
            rel = safe_relative(prefix + entry.name)
            key = rel.casefold()
            if key in seen:
                raise BackupError(f"Case-insensitive path collision: {rel}")
            seen.add(key)
            item = join_safe(root, rel)
            info = entry.stat(follow_symlinks=False)
            if is_link(info):
                if claude and key in ("debug/latest", "debug/latest.txt"):
                    excluded.append({"path": rel, "reason": "Claude debug pointer (reparse point)"})
                    continue
                raise BackupError(f"Link/reparse point would escape or loop: {item}")
            if stat.S_ISDIR(info.st_mode):
                directories.append(rel)
                todo.append((item, rel + "/"))
            elif stat.S_ISREG(info.st_mode):
                files.append({"path": rel, **digest_file(item)})
            else:
                raise BackupError(f"Unsupported file type: {item}")
    return {"files": sorted(files, key=lambda x: x["path"]),
            "directories": sorted(directories), "exclusions": sorted(excluded, key=lambda x: x["path"])}


def content_equal(expected: dict, actual: dict, label: str) -> None:
    # Excluded links are deliberately not restored. Every included byte is checked.
    for key in ("files", "directories"):
        if expected[key] != actual[key]:
            e = {x["path"]: x for x in expected["files"]}
            a = {x["path"]: x for x in actual["files"]}
            missing, extra = sorted(e.keys() - a.keys()), sorted(a.keys() - e.keys())
            changed = sorted(k for k in e.keys() & a.keys() if e[k] != a[k])
            raise BackupError(f"{label}: mismatch; missing={missing[:5]}, extra={extra[:5]}, "
                              f"changed={changed[:5]}, directory_set_changed="
                              f"{expected['directories'] != actual['directories']}")


def copy_file(source: Path, target: Path) -> None:
    reject_links(source)
    reject_links(target)
    os.makedirs(native(target.parent), mode=0o700, exist_ok=True)
    fd = os.open(native(source), _read_flags())
    with os.fdopen(fd, "rb") as src, open(native(target), "xb") as dst:
        before = os.fstat(src.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise BackupError(f"Not a regular source: {source}")
        while block := src.read(CHUNK):
            dst.write(block)
        dst.flush()
        os.fsync(dst.fileno())
        after = os.fstat(src.fileno())
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise BackupError(f"Source changed while copying: {source}")
    os.utime(native(target), ns=(after.st_atime_ns, after.st_mtime_ns))


def copy_tree(source: Path, target: Path, expected: dict, progress: Progress) -> None:
    os.makedirs(native(target), mode=0o700, exist_ok=True)
    for rel in expected["directories"]:
        os.makedirs(native(join_safe(target, rel)), mode=0o700, exist_ok=True)
    last = time.monotonic()
    for index, item in enumerate(expected["files"], 1):
        copy_file(join_safe(source, item["path"]), join_safe(target, item["path"]))
        if time.monotonic() - last >= 2 or index == len(expected["files"]):
            progress(f"Copied {index}/{len(expected['files'])} files")
            last = time.monotonic()


@dataclass(frozen=True)
class Component:
    id: str
    source: Path
    kind: str = "directory"
    source_mode: str = "default"
    restore_allowed: bool = True


def _component_tree(component: Component) -> dict:
    if component.kind == "file":
        return {"files": [{"path": "value", **digest_file(component.source)}],
                "directories": [], "exclusions": []}
    return tree(component.source, claude=component.id == "claude")


def create_snapshot(components: Iterable[Component], output: Path, *, progress: Progress = print) -> Path:
    components, output = list(components), absolute(output)
    if not components:
        raise BackupError("No source components selected.")
    ids = [c.id for c in components]
    if len(set(ids)) != len(ids) or any(not _ID.fullmatch(x) for x in ids):
        raise BackupError("Component IDs must be unique lowercase identifiers.")
    for c in components:
        if c.kind not in ("file", "directory") or c.source_mode not in ("default", "custom"):
            raise BackupError("Invalid component kind or source mode.")
        reject_links(absolute(c.source))
        disjoint([output, c.source])
    private_dir(output)
    identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + token()[:12]
    stage = output / (".incomplete-" + identifier)
    final = output / ("DEV_STATE_BACKUP_" + identifier)
    private_dir(stage, new=True)
    manifest = {"format": FORMAT_VERSION, "tool_version": __version__, "id": identifier,
                "created_utc": now(), "components": []}
    try:
        for component in components:
            progress(f"Hashing source: {component.id}")
            before = _component_tree(component)
            if component.id in ("claude", "codex") and not before["files"]:
                raise BackupError(f"Selected {component.id} state is empty.")
            payload = stage / "data" / component.id
            os.makedirs(native(payload), mode=0o700)
            progress(f"Copying {component.id}: {len(before['files'])} files")
            if component.kind == "file":
                copy_file(component.source, payload / "value")
            else:
                copy_tree(component.source, payload, before, progress)
            content_equal(before, tree(payload), component.id + " copied data")
            after = _component_tree(component)
            content_equal(before, after, component.id + " live data changed during backup")
            if before["exclusions"] != after["exclusions"]:
                raise BackupError("Excluded-link set changed while copying.")
            manifest["components"].append({"id": component.id, "kind": component.kind,
                "source_path": str(component.source), "source_mode": component.source_mode,
                "restore_allowed": component.restore_allowed, **before})
        write_json(stage / "manifest.json", manifest)
        write_json(stage / "complete.json", {"format": FORMAT_VERSION, "id": identifier,
                    "manifest_sha256": digest_file(stage / "manifest.json")["sha256"]})
        verify_snapshot(stage, progress=progress)
        rename_new(stage, final)
        progress(f"Snapshot complete: {final}")
        return final
    except BaseException:
        progress(f"Backup did not finish. Retained incomplete directory: {stage}")
        raise


def validate_manifest(m: dict) -> None:
    if m.get("format") != FORMAT_VERSION:
        raise BackupError("Unsupported snapshot format. See docs/migration.md.")
    if not isinstance(m.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", m["id"]):
        raise BackupError("Invalid snapshot identifier.")
    if not isinstance(m.get("components"), list) or not m["components"]:
        raise BackupError("Snapshot contains no component declarations.")
    ids = set()
    for c in m["components"]:
        if not isinstance(c, dict) or not isinstance(c.get("id"), str) or not _ID.fullmatch(c["id"]):
            raise BackupError("Invalid component identifier.")
        if c["id"] in ids:
            raise BackupError("Duplicate component identifier.")
        ids.add(c["id"])
        if c.get("kind") not in ("directory", "file") or type(c.get("restore_allowed")) is not bool:
            raise BackupError("Invalid component declaration.")
        if c.get("source_mode") not in ("default", "custom"):
            raise BackupError("Invalid source mode.")
        if any(not isinstance(c.get(k), list) for k in ("files", "directories", "exclusions")):
            raise BackupError("Invalid file/directory declarations.")
        names = set()
        dirs = set()
        for d in c["directories"]:
            key = safe_relative(d).casefold()
            if key in names:
                raise BackupError("Duplicate or case-colliding directory.")
            names.add(key)
            dirs.add(d)
        for f in c["files"]:
            if not isinstance(f, dict):
                raise BackupError("Invalid file record.")
            key = safe_relative(f.get("path")).casefold()
            if key in names:
                raise BackupError("Duplicate or case-colliding file.")
            names.add(key)
            if type(f.get("size")) is not int or f["size"] < 0 or not _HEX.fullmatch(str(f.get("sha256", ""))):
                raise BackupError("Invalid size/hash in file record.")
            if set(f) != {"path", "size", "sha256"}:
                raise BackupError("Unrecognized file-record fields.")
        for path in c["directories"] + [f["path"] for f in c["files"]]:
            parent = path.rpartition("/")[0]
            if parent and parent not in dirs:
                raise BackupError("Missing declared parent directory.")
        if c["kind"] == "file" and (len(c["files"]) != 1 or c["files"][0]["path"] != "value" or c["directories"]):
            raise BackupError("File components require exactly one value payload.")
        if c["id"] in ("claude", "codex") and not c["files"]:
            raise BackupError("Empty required agent state.")
        for exclusion in c["exclusions"]:
            if (not isinstance(exclusion, dict) or c["id"] != "claude"
                    or (not isinstance(exclusion.get("path"), str) or exclusion["path"].casefold() not in ("debug/latest", "debug/latest.txt"))):
                raise BackupError("Unrecognized exclusion policy.")
        if c["files"] != sorted(c["files"], key=lambda f: f["path"]) or c["directories"] != sorted(c["directories"]):
            raise BackupError("Manifest records must be canonical and sorted.")


def verify_snapshot(root: Path, *, progress: Progress = lambda _: None) -> dict:
    root = absolute(root)
    reject_links(root)
    completion = read_json(root / "complete.json")
    manifest_hash = digest_file(root / "manifest.json")["sha256"]
    if completion.get("manifest_sha256") != manifest_hash or completion.get("format") != FORMAT_VERSION:
        raise BackupError("Completion marker or manifest checksum mismatch.")
    m = read_json(root / "manifest.json")
    validate_manifest(m)
    if completion.get("id") != m["id"]:
        raise BackupError("Snapshot identifier mismatch.")
    allowed = {"manifest.json", "complete.json", "data"}
    with os.scandir(native(root)) as entries:
        if {e.name for e in entries} != allowed:
            raise BackupError("Snapshot root contains unexpected/missing items; keep tools outside it.")
    with os.scandir(native(root / "data")) as entries:
        if {e.name for e in entries} != {c["id"] for c in m["components"]}:
            raise BackupError("Snapshot data component set does not match its manifest.")
    for c in m["components"]:
        progress(f"Verifying {c['id']}: {len(c['files'])} files")
        content_equal(c, tree(root / "data" / c["id"]), c["id"])
    return m


def rename_new(source: Path, target: Path) -> None:
    reject_links(source)
    reject_links(target)
    if lexists(target):
        raise BackupError(f"Refusing to overwrite during rename: {target}")
    os.rename(native(source), native(target))


def validate_target(target: Path, snapshot: Path) -> None:
    target = absolute(target)
    if target == Path(target.anchor) or target == Path.home():
        raise BackupError(f"Refusing broad/root restore target: {target}")
    reject_links(target)
    disjoint([target, snapshot])
    if os.name == "nt":
        for key in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
            if os.environ.get(key) and inside(target, absolute(os.environ[key])):
                raise BackupError(f"Refusing system-directory restore: {target}")


def plan_restore(root: Path, targets: Mapping[str, Path], *, progress: Progress = lambda _: None) -> list[dict]:
    m = verify_snapshot(root, progress=progress)
    by_id = {c["id"]: c for c in m["components"]}
    if not targets:
        raise BackupError("No restore components selected.")
    for key in targets:
        if key not in by_id or not by_id[key]["restore_allowed"]:
            raise BackupError(f"Unknown or manual-only restore component: {key}")
    disjoint([absolute(p) for p in targets.values()])
    plan = []
    for key, destination in targets.items():
        target = absolute(destination)
        validate_target(target, root)
        c = by_id[key]
        if lexists(target):
            info = os.lstat(native(target))
            if is_link(info) or (c["kind"] == "directory") != stat.S_ISDIR(info.st_mode):
                raise BackupError(f"Restore target has wrong type or is a link: {target}")
        plan.append({"id": key, "kind": c["kind"], "source": str(root / "data" / key),
                     "target": str(target), "existing": lexists(target), "component": c})
    return plan


@contextlib.contextmanager
def restore_lock(folder: Path):
    private_dir(folder)
    lock = folder / ".restore.lock"
    reject_links(lock)
    with open(native(lock), "a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise BackupError("Another restore is using this report directory.") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _verify_target(record: dict, path: Path) -> None:
    c = record["component"]
    if c["kind"] == "file":
        got = {"files": [{"path": "value", **digest_file(path)}], "directories": []}
    else:
        got = tree(path)
    content_equal(c, got, record["id"] + " restored payload")


def restore_snapshot(root: Path, targets: Mapping[str, Path], reports: Path, *,
                     apply: bool = False, progress: Progress = print,
                     fault: Fault = lambda _event, _id: None) -> dict:
    """Stage ALL components before changing targets; never delete originals.

    fault is test-only dependency injection, not exposed by the command-line UI.
    Reports/holds are retained after failure, including interrupted transactions.
    """
    root, reports = absolute(root), absolute(reports)
    plan = plan_restore(root, targets, progress=progress)
    disjoint([reports, root, *[absolute(p) for p in targets.values()]])
    if not apply:
        return {"status": "dry-run", "plan": plan}
    with restore_lock(reports):
        # Recheck after acquiring the lock, before making filesystem changes.
        plan = plan_restore(root, targets, progress=progress)
        transaction = token()
        journal_path = reports / ("restore-" + transaction + ".json")
        state = {"version": 1, "transaction": transaction, "started_utc": now(),
                 "backup": str(root), "status": "preparing", "entries": []}
        def checkpoint():
            write_json(journal_path, state, replace=True)
        checkpoint()
        try:
            for record in plan:
                target = Path(record["target"])
                os.makedirs(native(target.parent), mode=0o700, exist_ok=True)
                # One private sibling directory keeps staged files and originals secure.
                work = target.parent / (".aidbackup-" + transaction + "-" + record["id"])
                private_dir(work, new=True)
                stage, hold, failed = work / "staged", work / "original", work / "failed"
                entry = {"id": record["id"], "target": str(target), "stage": str(stage),
                         "hold": str(hold), "failed": str(failed), "original_moved": False,
                         "installed": False, "phase": "staging"}
                state["entries"].append(entry)
                checkpoint()
                progress(f"Staging and verifying: {record['id']}")
                fault("before_stage", record["id"])
                if record["kind"] == "file":
                    copy_file(Path(record["source"]) / "value", stage)
                else:
                    copy_tree(Path(record["source"]), stage, record["component"], progress)
                _verify_target(record, stage)
                entry["phase"] = "staged"
                checkpoint()
            state["status"] = "installing"
            checkpoint()
            for record, entry in zip(plan, state["entries"]):
                target, stage, hold = Path(entry["target"]), Path(entry["stage"]), Path(entry["hold"])
                fault("before_preserve", record["id"])
                # Detect new activity during staging; do not silently replace a new target.
                if lexists(target) != record["existing"]:
                    raise BackupError(f"Destination appeared/disappeared during staging: {target}")
                if lexists(target):
                    entry["phase"] = "preserve-pending"
                    checkpoint()
                    rename_new(target, hold)
                    entry["original_moved"] = True
                    entry["phase"] = "preserved"
                    checkpoint()
                fault("after_preserve", record["id"])
                entry["phase"] = "install-pending"
                checkpoint()
                rename_new(stage, target)
                entry["installed"] = True
                entry["phase"] = "installed"
                checkpoint()
                fault("after_install", record["id"])
                _verify_target(record, target)
            state["status"] = "complete"
            checkpoint()
            progress(f"Restore verified. Recovery journal: {journal_path}")
            return {"status": "complete", "journal": str(journal_path), "plan": plan}
        except BaseException as exc:
            state["status"] = "rolling-back"
            state["error"] = str(exc)
            with contextlib.suppress(OSError):
                checkpoint()
            recovery_errors = []
            for entry in reversed(state["entries"]):
                target, hold, failed = Path(entry["target"]), Path(entry["hold"]), Path(entry["failed"])
                try:
                    if entry["installed"] and lexists(target):
                        rename_new(target, failed)  # Never recursive-delete the restored tree.
                        entry["installed"] = False
                    if entry["original_moved"]:
                        rename_new(hold, target)
                        entry["original_moved"] = False
                    entry["phase"] = "rolled-back"
                except BaseException as recovery_error:
                    entry["phase"] = "manual-recovery-required"
                    recovery_errors.append(str(recovery_error))
            state["status"] = "manual-recovery-required" if recovery_errors else "rolled-back"
            state["recovery_errors"] = recovery_errors
            with contextlib.suppress(OSError):
                checkpoint()
            raise BackupError(f"Restore failed: {exc}. Recovery status: {state['status']}. "
                              f"Keep all .aidbackup-* folders. Journal: {journal_path}") from exc


def rehearse(root: Path, output: Path, *, progress: Progress = print) -> Path:
    root, output = absolute(root), absolute(output)
    m = verify_snapshot(root, progress=progress)
    disjoint([root, output])
    private_dir(output)
    work = output / ("rehearsal-" + token())
    private_dir(work, new=True)
    targets = {}
    for c in m["components"]:
        if not c["restore_allowed"]:
            continue
        target = work / "targets" / c["id"]
        os.makedirs(native(target.parent), mode=0o700, exist_ok=True)
        if c["kind"] == "directory":
            os.mkdir(native(target))
            with open(native(target / "synthetic-original.txt"), "xb") as f:
                f.write(b"Rehearsal fixture, not live user data.\n")
        else:
            with open(native(target), "xb") as f:
                f.write(b"Rehearsal fixture, not live user data.\n")
        targets[c["id"]] = target
    restore_snapshot(root, targets, work / "reports", apply=True, progress=progress)
    progress(f"Rehearsal passed without selecting live targets. Retained: {work}")
    return work


def _expected_archive_entries(m: dict) -> tuple[dict, set]:
    files = {}
    dirs = {"data/"}
    for c in m["components"]:
        prefix = f"data/{c['id']}/"
        dirs.add(prefix)
        dirs.update(prefix + d + "/" for d in c["directories"])
        for item in c["files"]:
            files[prefix + item["path"]] = item
    return files, dirs


def create_archive(root: Path, *, progress: Progress = print) -> Path:
    root = absolute(root)
    m = verify_snapshot(root, progress=progress)
    archive = root.with_name(root.name + ".zip")
    partial = root.with_name(root.name + ".zip.partial-" + token())
    if lexists(archive):
        raise BackupError("Archive already exists; not overwriting it.")
    files, dirs = _expected_archive_entries(m)
    with zipfile.ZipFile(native(partial), "x", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=1, allowZip64=True, strict_timestamps=False) as z:
        for d in sorted(dirs):
            z.writestr(d, b"")
        for index, rel in enumerate(["manifest.json", "complete.json", *sorted(files)], 1):
            z.write(native(join_safe(root, rel)), arcname=rel)
            if index % 100 == 0 or index == len(files) + 2:
                progress(f"Archived {index}/{len(files) + 2} files (no copy/archive time limit)")
    verify_archive(partial, require_sidecar=False, progress=progress)
    # Detect changes to the snapshot while building the archive, before publishing it.
    verify_snapshot(root, progress=progress)
    rename_new(partial, archive)
    checksum = digest_file(archive)["sha256"]
    with open(native(Path(str(archive) + ".sha256")), "x", encoding="ascii") as f:
        f.write(checksum + "  " + archive.name + "\n")
    progress(f"Archive verified: {archive}")
    return archive


def verify_archive(archive: Path, *, require_sidecar: bool = True,
                   progress: Progress = lambda _: None) -> dict:
    archive = absolute(archive)
    reject_links(archive)
    if require_sidecar:
        sidecar = Path(str(archive) + ".sha256")
        reject_links(sidecar)
        with open(native(sidecar), "r", encoding="ascii") as f:
            fields = f.read(4096).split()
            if not fields:
                raise BackupError("Archive SHA-256 sidecar is empty.")
            expected_hash = fields[0]
        if not _HEX.fullmatch(expected_hash) or digest_file(archive)["sha256"] != expected_hash:
            raise BackupError("Archive SHA-256 mismatch.")
    with zipfile.ZipFile(native(archive)) as z:
        names = set()
        for item in z.infolist():
            key = safe_relative(item.filename.rstrip("/")).casefold()
            if key in names:
                raise BackupError("Duplicate/case-colliding ZIP entry.")
            names.add(key)
            mode = (item.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode) or item.flag_bits & 1:
                raise BackupError("ZIP links or encrypted entries are not supported.")
        for name in ("manifest.json", "complete.json"):
            if z.getinfo(name).file_size > MAX_MANIFEST:
                raise BackupError("Oversized archive metadata.")
        raw = z.read("manifest.json")
        m = load_json_bytes(raw)
        completion = load_json_bytes(z.read("complete.json"))
        validate_manifest(m)
        if (completion.get("manifest_sha256") != hashlib.sha256(raw).hexdigest()
                or completion.get("id") != m["id"] or completion.get("format") != FORMAT_VERSION):
            raise BackupError("Archive completion/manifest mismatch.")
        files, dirs = _expected_archive_entries(m)
        if set(z.namelist()) != set(files) | dirs | {"manifest.json", "complete.json"}:
            raise BackupError("Archive contents do not exactly match the manifest.")
        for index, (rel, expected) in enumerate(files.items(), 1):
            info = z.getinfo(rel)
            if info.file_size != expected["size"]:
                raise BackupError(f"Archive file size mismatch: {rel}")
            sha, count = hashlib.sha256(), 0
            with z.open(info) as f:
                while block := f.read(CHUNK):
                    sha.update(block)
                    count += len(block)
            if count != expected["size"] or sha.hexdigest() != expected["sha256"]:
                raise BackupError(f"Archive file hash mismatch: {rel}")
            if index % 100 == 0:
                progress(f"Verified archive payload {index}/{len(files)}")
        return m


def unpack_archive(archive: Path, destination: Path, *, progress: Progress = print) -> Path:
    archive, destination = absolute(archive), absolute(destination)
    verify_archive(archive, progress=progress)
    disjoint([archive, destination])
    private_dir(destination, new=True)
    with zipfile.ZipFile(native(archive)) as z:
        for item in z.infolist():
            target = join_safe(destination, item.filename.rstrip("/"))
            reject_links(target)
            if item.is_dir():
                os.makedirs(native(target), mode=0o700, exist_ok=True)
            else:
                os.makedirs(native(target.parent), mode=0o700, exist_ok=True)
                with z.open(item) as src, open(native(target), "xb") as dst:
                    while block := src.read(CHUNK):
                        dst.write(block)
    verify_snapshot(destination, progress=progress)
    return destination
