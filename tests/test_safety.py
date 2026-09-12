"""Real filesystem tests with synthetic data only. No installed apps are read."""
import copy
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from aidbackup import core
from aidbackup.cli import make_parser, select_backup
from aidbackup.providers import discover, restore_targets, locations

QUIET = lambda _: None


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aidbackup-tests-")
        self.base = Path(self.temp.name).absolute()
        self.source = self.base / "source"
        self.output = self.base / "backups"
        self.source.mkdir()
        self.claude = self.source / ".claude"
        self.codex = self.source / ".codex"
        (self.claude / "projects" / "sample").mkdir(parents=True)
        (self.codex / "sessions").mkdir(parents=True)
        (self.claude / "projects" / "sample" / "chat.jsonl").write_text('{"synthetic": true}\n', encoding="utf8")
        (self.claude / "empty-directory").mkdir()
        (self.codex / "sessions" / "chat.jsonl").write_text('{"fixture": "codex"}\n', encoding="utf8")
        (self.codex / "zero-byte.lock").write_bytes(b"")
        (self.source / ".claude.json").write_text('{"fixture": true}', encoding="utf8")
        self.components = [core.Component("claude", self.claude), core.Component("codex", self.codex),
                           core.Component("claude-global", self.source / ".claude.json", "file")]

    def tearDown(self):
        # Tests delete only their uniquely created disposable fixture directory.
        self.temp.cleanup()

    def snapshot(self):
        return core.create_snapshot(self.components, self.output, progress=QUIET)

    def targets(self):
        home = self.base / "fresh-user"
        home.mkdir(exist_ok=True)
        result = {"claude": home / ".claude", "codex": home / ".codex", "claude-global": home / ".claude.json"}
        for id, path in result.items():
            if id == "claude-global":
                path.write_text("ORIGINAL-GLOBAL", encoding="utf8")
            else:
                path.mkdir(exist_ok=True)
                (path / "original.txt").write_text("ORIGINAL-" + id, encoding="utf8")
        return result

    def change_manifest(self, root, mutate):
        m = core.read_json(root / "manifest.json")
        mutate(m)
        core.write_json(root / "manifest.json", m, replace=True)
        completion = core.read_json(root / "complete.json")
        completion["manifest_sha256"] = core.digest_file(root / "manifest.json")["sha256"]
        core.write_json(root / "complete.json", completion, replace=True)
        return m

    def assert_originals(self, targets):
        self.assertEqual(targets["claude-global"].read_text(), "ORIGINAL-GLOBAL")
        for id in ("claude", "codex"):
            self.assertEqual((targets[id] / "original.txt").read_text(), "ORIGINAL-" + id)


class SnapshotTests(Fixture):
    def test_snapshot_verifies_every_component(self):
        root = self.snapshot()
        m = core.verify_snapshot(root)
        self.assertEqual({c["id"] for c in m["components"]}, {c.id for c in self.components})

    def test_empty_directory_and_zero_byte_file_survive(self):
        root = self.snapshot()
        self.assertTrue((root / "data/claude/empty-directory").is_dir())
        self.assertEqual((root / "data/codex/zero-byte.lock").stat().st_size, 0)

    def test_missing_selected_source_aborts(self):
        self.components[1] = core.Component("codex", self.base / "missing")
        with self.assertRaises((core.BackupError, FileNotFoundError)):
            self.snapshot()
        self.assertEqual(list(self.output.glob("DEV_STATE_BACKUP_*")), [])

    def test_empty_primary_source_aborts(self):
        shutil.rmtree(self.codex)
        self.codex.mkdir()
        with self.assertRaises(core.BackupError):
            self.snapshot()

    def test_no_components_aborts(self):
        with self.assertRaises(core.BackupError):
            core.create_snapshot([], self.output, progress=QUIET)
        self.assertFalse(self.output.exists())

    def test_duplicate_component_aborts(self):
        self.components.append(self.components[0])
        with self.assertRaises(core.BackupError):
            self.snapshot()

    def test_destination_inside_source_aborts(self):
        with self.assertRaises(core.BackupError):
            core.create_snapshot(self.components, self.claude / "backup", progress=QUIET)

    def test_destination_is_source_ancestor_aborts(self):
        with self.assertRaises(core.BackupError):
            core.create_snapshot(self.components, self.source, progress=QUIET)

    def test_copy_failure_no_completed_snapshot(self):
        with patch("aidbackup.core.copy_file", side_effect=PermissionError("synthetic denied")):
            with self.assertRaises(PermissionError):
                self.snapshot()
        self.assertFalse(list(self.output.glob("DEV_STATE_BACKUP_*")))
        self.assertTrue(list(self.output.glob(".incomplete-*")))
        self.assertTrue((self.codex / "sessions/chat.jsonl").exists())

    def test_source_changed_during_copy_aborts(self):
        original = core.copy_file
        def changing(src, dst):
            original(src, dst)
            if src.name == "chat.jsonl":
                with open(src, "ab") as f:
                    f.write(b"mutation")
        with patch("aidbackup.core.copy_file", side_effect=changing):
            with self.assertRaises(core.BackupError):
                self.snapshot()

    def test_corruption_same_length_detected(self):
        root = self.snapshot()
        target = root / "data/claude/projects/sample/chat.jsonl"
        target.write_bytes(b"X" * target.stat().st_size)
        with self.assertRaises(core.BackupError):
            core.verify_snapshot(root)

    def test_missing_file_detected(self):
        root = self.snapshot()
        (root / "data/codex/zero-byte.lock").unlink()
        with self.assertRaises(core.BackupError):
            core.verify_snapshot(root)

    def test_extra_file_detected(self):
        root = self.snapshot()
        (root / "data/codex/surprise.txt").write_text("extra")
        with self.assertRaises(core.BackupError):
            core.verify_snapshot(root)

    def test_missing_empty_directory_detected(self):
        root = self.snapshot()
        (root / "data/claude/empty-directory").rmdir()
        with self.assertRaises(core.BackupError):
            core.verify_snapshot(root)

    def test_unexpected_component_detected(self):
        root = self.snapshot()
        (root / "data/unexpected").mkdir()
        with self.assertRaises(core.BackupError):
            core.verify_snapshot(root)

    def test_root_extra_files_detected(self):
        root = self.snapshot()
        (root / "do-not-put-scripts-here.bat").write_text("example")
        with self.assertRaises(core.BackupError):
            core.verify_snapshot(root)

    def test_manifest_checksum_mismatch(self):
        root = self.snapshot()
        with open(root / "manifest.json", "ab") as f:
            f.write(b" ")
        with self.assertRaises(core.BackupError):
            core.verify_snapshot(root)

    def test_missing_completion_marker(self):
        root = self.snapshot()
        (root / "complete.json").unlink()
        with self.assertRaises(FileNotFoundError):
            core.verify_snapshot(root)

    def test_unicode_spaces_punctuation_and_long_path(self):
        directory = self.claude / ("long-" + "a" * 90) / ("long-" + "b" * 90) / ("long-" + "c" * 90)
        os.makedirs(core.native(directory))
        filename = directory / "resume-\u00e9-\u65e5\u672c! & ' [x] %.jsonl"
        with open(core.native(filename), "wb") as f:
            f.write(b"synthetic long-path test")
        self.assertGreater(len(str(filename)), 300)
        root = self.snapshot()
        core.verify_snapshot(root)

    @unittest.skipIf(os.name == "nt", "Case-sensitive fixture for Windows collision rejection")
    def test_case_collision_refused(self):
        (self.claude / "case.txt").write_text("a")
        (self.claude / "CASE.txt").write_text("b")
        with self.assertRaises(core.BackupError):
            self.snapshot()

    def make_symlink(self, source, target, directory=False):
        try:
            os.symlink(source, target, target_is_directory=directory)
        except (OSError, NotImplementedError):
            self.skipTest("Creating symlinks requires platform support/Windows Developer Mode")

    def test_unexpected_file_symlink_refused(self):
        self.make_symlink(self.source / ".claude.json", self.codex / "linked-file")
        with self.assertRaises(core.BackupError):
            self.snapshot()

    def test_cycle_directory_link_refused(self):
        self.make_symlink(self.codex, self.codex / "cycle", directory=True)
        with self.assertRaises(core.BackupError):
            self.snapshot()

    def test_linked_source_root_refused(self):
        alias = self.base / "alias"
        self.make_symlink(self.codex, alias, directory=True)
        with self.assertRaises(core.BackupError):
            core.create_snapshot([core.Component("codex", alias)], self.output, progress=QUIET)

    def test_only_claude_debug_pointer_excluded(self):
        (self.claude / "debug").mkdir()
        (self.claude / "debug/log.txt").write_text("log")
        self.make_symlink(self.claude / "debug/log.txt", self.claude / "debug/latest")
        root = self.snapshot()
        m = core.verify_snapshot(root)
        self.assertEqual(m["components"][0]["exclusions"][0]["path"], "debug/latest")
        self.assertFalse((root / "data/claude/debug/latest").exists())

    def test_regular_debug_latest_is_not_silently_excluded(self):
        (self.claude / "debug").mkdir()
        (self.claude / "debug/latest").write_text("not a link")
        root = self.snapshot()
        self.assertEqual((root / "data/claude/debug/latest").read_text(), "not a link")


class ValidationTests(Fixture):
    def test_relative_path_attack_table(self):
        invalid = ["../outside", "/absolute", "a//b", "a/./b", "a/../b", "C:/users", r"a\b",
                   "name:stream", "trailing.", "space ", "NUL", "COM1.txt", "a\x00b", "a\nb", "", None]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(core.BackupError):
                core.safe_relative(value)

    def test_valid_relative_path(self):
        self.assertEqual(core.safe_relative("projects/a ' & ! [b] %.jsonl"), "projects/a ' & ! [b] %.jsonl")

    def test_duplicate_json_key_refused(self):
        with self.assertRaises(core.BackupError):
            core.load_json_bytes(b'{"format":3,"format":99}')

    def test_invalid_schema_refused(self):
        root = self.snapshot()
        self.change_manifest(root, lambda m: m.update(format=999))
        with self.assertRaises(core.BackupError):
            core.verify_snapshot(root)

    def test_traversal_manifest_refused_even_with_matching_completion(self):
        root = self.snapshot()
        def mutate(m):
            m["components"][0]["files"][0]["path"] = "../../outside"
        self.change_manifest(root, mutate)
        with self.assertRaises(core.BackupError):
            core.verify_snapshot(root)

    def test_duplicate_manifest_file_refused(self):
        root = self.snapshot()
        def mutate(m):
            m["components"][0]["files"].append(copy.deepcopy(m["components"][0]["files"][0]))
        self.change_manifest(root, mutate)
        with self.assertRaises(core.BackupError):
            core.verify_snapshot(root)

    def test_negative_size_refused(self):
        root = self.snapshot()
        def mutate(m):
            m["components"][0]["files"][0]["size"] = -1
        self.change_manifest(root, mutate)
        with self.assertRaises(core.BackupError):
            core.verify_snapshot(root)

    def test_unknown_exclusion_refused(self):
        root = self.snapshot()
        def mutate(m):
            m["components"][1]["exclusions"] = [{"path": "sessions"}]
        self.change_manifest(root, mutate)
        with self.assertRaises(core.BackupError):
            core.verify_snapshot(root)

    def test_source_path_is_not_a_restore_target(self):
        root = self.snapshot()
        def mutate(m):
            for c in m["components"]:
                c["source_path"] = str(self.base / "never-use-this")
        m = self.change_manifest(root, mutate)
        targets = restore_targets(m, self.base / "new-home", {})
        self.assertEqual(targets["claude"], self.base / "new-home/.claude")

    def test_custom_home_requires_explicit_mapping_on_new_host(self):
        root = self.snapshot()
        def mutate(m):
            m["components"][1]["source_mode"] = "custom"
        m = self.change_manifest(root, mutate)
        with self.assertRaises(core.BackupError):
            restore_targets(m, self.base / "new-home", {})
        targets = restore_targets(m, self.base / "new-home", {}, overrides={"codex": str(self.base / "my-new-codex")})
        self.assertEqual(targets["codex"], self.base / "my-new-codex")

    def test_blank_multiple_snapshot_selection_cancels(self):
        self.snapshot()
        self.snapshot()
        with patch("builtins.input", return_value=""), self.assertRaises(core.BackupError):
            select_backup(self.output, None)

    def test_incomplete_snapshot_never_discovered(self):
        self.output.mkdir()
        (self.output / "DEV_STATE_BACKUP_incomplete/data").mkdir(parents=True)
        with self.assertRaises(core.BackupError):
            select_backup(self.output, None)

    def test_no_argument_restore_defaults_to_dry_run(self):
        args = make_parser().parse_args(["restore"])
        self.assertFalse(args.apply)
        self.assertIsNone(args.confirm)


class RestoreTests(Fixture):
    def test_dry_run_makes_no_files_or_content_changes(self):
        root, targets = self.snapshot(), self.targets()
        before = core.tree(self.base)
        reports = self.base / "reports"
        result = core.restore_snapshot(root, targets, reports, progress=QUIET)
        self.assertEqual(result["status"], "dry-run")
        self.assertFalse(reports.exists())
        core.content_equal(before, core.tree(self.base), "dry run")

    def test_restore_roundtrip_keeps_every_original(self):
        root, targets = self.snapshot(), self.targets()
        result = core.restore_snapshot(root, targets, self.base / "reports", apply=True, progress=QUIET)
        state = core.read_json(Path(result["journal"]))
        self.assertEqual(state["status"], "complete")
        for e in state["entries"]:
            hold = Path(e["hold"])
            self.assertTrue(hold.exists())
            if e["id"] == "claude-global":
                self.assertEqual(hold.read_text(), "ORIGINAL-GLOBAL")
            else:
                self.assertEqual((hold / "original.txt").read_text(), "ORIGINAL-" + e["id"])
        self.assertEqual(targets["claude-global"].read_text(), '{"fixture": true}')
        core.verify_snapshot(root)

    def test_restore_into_absent_targets(self):
        root = self.snapshot()
        targets = {"claude": self.base / "newuser/.claude"}
        result = core.restore_snapshot(root, targets, self.base / "reports", apply=True, progress=QUIET)
        self.assertEqual(result["status"], "complete")
        self.assertTrue((targets["claude"] / "projects/sample/chat.jsonl").is_file())

    def test_stage_copy_error_keeps_live_originals(self):
        root, targets = self.snapshot(), self.targets()
        with patch("aidbackup.core.copy_file", side_effect=PermissionError("fixture denied")):
            with self.assertRaises(core.BackupError):
                core.restore_snapshot(root, targets, self.base / "reports", apply=True, progress=QUIET)
        self.assert_originals(targets)

    def test_staging_everything_before_first_target_move(self):
        root, targets = self.snapshot(), self.targets()
        def fail(event, id):
            if event == "before_stage" and id == "codex":
                self.assert_originals(targets)
                raise OSError("fixture second staging fails")
        with self.assertRaises(core.BackupError):
            core.restore_snapshot(root, targets, self.base / "reports", apply=True, fault=fail, progress=QUIET)
        self.assert_originals(targets)

    def test_each_transaction_failure_restores_originals(self):
        for event, id in [("before_preserve", "claude"), ("after_preserve", "claude"),
                          ("after_install", "claude"), ("before_preserve", "codex"),
                          ("after_preserve", "codex"), ("after_install", "claude-global")]:
            with self.subTest(event=event, id=id):
                root, targets = self.snapshot(), self.targets()
                def fail(e, c):
                    if (e, c) == (event, id):
                        raise OSError("injected restore interruption")
                with self.assertRaises(core.BackupError):
                    core.restore_snapshot(root, targets, self.base / "reports", apply=True, fault=fail, progress=QUIET)
                self.assert_originals(targets)
                core.verify_snapshot(root)

    def test_actual_preserve_rename_failure_does_not_delete_original(self):
        root, targets = self.snapshot(), self.targets()
        original = core.rename_new
        def fail(src, dst):
            if src == targets["codex"] and dst.name == "original":
                raise PermissionError("injected failure moving original")
            return original(src, dst)
        with patch("aidbackup.core.rename_new", side_effect=fail), self.assertRaises(core.BackupError):
            core.restore_snapshot(root, targets, self.base / "reports", apply=True, progress=QUIET)
        self.assert_originals(targets)

    def test_readback_corruption_causes_rollback_and_preserves_failed_copy(self):
        root, targets = self.snapshot(), self.targets()
        def corrupt(event, id):
            if event == "after_install" and id == "codex":
                (targets[id] / "sessions/chat.jsonl").write_text("corrupt")
        with self.assertRaises(core.BackupError):
            core.restore_snapshot(root, targets, self.base / "reports", apply=True, fault=corrupt, progress=QUIET)
        self.assert_originals(targets)
        failed = list((self.base / "fresh-user").glob(".aidbackup-*/failed"))
        self.assertTrue(failed)

    def test_recovery_conflict_keeps_hold_and_competing_destination(self):
        root, targets = self.snapshot(), self.targets()
        def conflict(event, id):
            if event == "after_preserve" and id == "claude":
                targets[id].mkdir()
                (targets[id] / "external-new-data.txt").write_text("external")
                raise OSError("external process wrote new data")
        with self.assertRaisesRegex(core.BackupError, "manual-recovery-required"):
            core.restore_snapshot(root, targets, self.base / "reports", apply=True, fault=conflict, progress=QUIET)
        self.assertEqual((targets["claude"] / "external-new-data.txt").read_text(), "external")
        self.assertTrue(list(targets["claude"].parent.glob(".aidbackup-*/original/original.txt")))

    def test_keyboard_interrupt_rolls_back(self):
        root, targets = self.snapshot(), self.targets()
        def interrupt(event, id):
            if event == "after_preserve" and id == "claude":
                raise KeyboardInterrupt()
        with self.assertRaises(core.BackupError):
            core.restore_snapshot(root, targets, self.base / "reports", apply=True, fault=interrupt, progress=QUIET)
        self.assert_originals(targets)

    def test_restore_rejects_overlapping_targets(self):
        root = self.snapshot()
        with self.assertRaises(core.BackupError):
            core.restore_snapshot(root, {"claude": self.base / "dest", "codex": self.base / "dest/nested"},
                                  self.base / "reports", apply=True, progress=QUIET)

    def test_restore_rejects_backup_as_target(self):
        root = self.snapshot()
        with self.assertRaises(core.BackupError):
            core.restore_snapshot(root, {"claude": root / "data/claude"}, self.base / "reports", progress=QUIET)

    def test_restore_rejects_reports_inside_backup(self):
        root = self.snapshot()
        with self.assertRaises(core.BackupError):
            core.restore_snapshot(root, {"claude": self.base / "dest"}, root / "reports", progress=QUIET)

    def test_restore_rejects_drive_root(self):
        root = self.snapshot()
        with self.assertRaises(core.BackupError):
            core.restore_snapshot(root, {"claude": Path(self.base.anchor)}, self.base / "reports", progress=QUIET)

    def test_restore_wrong_target_type_aborts_before_writes(self):
        root = self.snapshot()
        target = self.base / "existing-file"
        target.write_text("keep")
        with self.assertRaises(core.BackupError):
            core.restore_snapshot(root, {"claude": target}, self.base / "reports", apply=True, progress=QUIET)
        self.assertEqual(target.read_text(), "keep")

    def test_corrupt_backup_aborts_before_touching_targets(self):
        root, targets = self.snapshot(), self.targets()
        (root / "data/claude-global/value").write_text("bad")
        with self.assertRaises(core.BackupError):
            core.restore_snapshot(root, targets, self.base / "reports", apply=True, progress=QUIET)
        self.assert_originals(targets)

    def test_restore_lock_conflict(self):
        reports = self.base / "reports"
        with core.restore_lock(reports):
            with self.assertRaises(core.BackupError):
                with core.restore_lock(reports):
                    self.fail("second lock should not be acquired")

    def test_rehearsal_never_changes_live_fixture(self):
        root = self.snapshot()
        original_live = core.tree(self.source)
        original_backup = core.tree(root)
        work = core.rehearse(root, self.base / "rehearsals", progress=QUIET)
        self.assertTrue((work / "targets/claude/projects/sample/chat.jsonl").is_file())
        core.content_equal(original_live, core.tree(self.source), "untouched live source")
        core.content_equal(original_backup, core.tree(root), "untouched backup")

    def test_manual_only_component_cannot_be_auto_restored(self):
        root = self.snapshot()
        def mutate(m):
            m["components"][0]["restore_allowed"] = False
        self.change_manifest(root, mutate)
        with self.assertRaises(core.BackupError):
            core.restore_snapshot(root, {"claude": self.base / "dest"}, self.base / "reports", progress=QUIET)


class ArchiveTests(Fixture):
    def archive(self):
        root = self.snapshot()
        return root, core.create_archive(root, progress=QUIET)

    def test_zip_full_content_roundtrip(self):
        root, archive = self.archive()
        core.verify_archive(archive)
        unpacked = core.unpack_archive(archive, self.base / "unpacked", progress=QUIET)
        core.content_equal(core.tree(root), core.tree(unpacked), "archive roundtrip")

    def test_zip_includes_zero_files_and_empty_directories(self):
        _, archive = self.archive()
        with zipfile.ZipFile(archive) as z:
            self.assertIn("data/claude/empty-directory/", z.namelist())
            self.assertEqual(z.read("data/codex/zero-byte.lock"), b"")

    def test_checksum_corruption_detected(self):
        _, archive = self.archive()
        with open(archive, "ab") as f:
            f.write(b"damaged")
        with self.assertRaises(core.BackupError):
            core.verify_archive(archive)

    def test_missing_sidecar_refused(self):
        _, archive = self.archive()
        Path(str(archive) + ".sha256").unlink()
        with self.assertRaises(FileNotFoundError):
            core.verify_archive(archive)

    def test_archive_creation_will_not_overwrite_existing_archive(self):
        root, archive = self.archive()
        before = archive.read_bytes()
        with self.assertRaises(core.BackupError):
            core.create_archive(root, progress=QUIET)
        self.assertEqual(before, archive.read_bytes())

    def test_unpack_refuses_existing_destination(self):
        _, archive = self.archive()
        target = self.base / "exists"
        target.mkdir()
        (target / "keep").write_text("keep")
        with self.assertRaises(core.BackupError):
            core.unpack_archive(archive, target, progress=QUIET)
        self.assertEqual((target / "keep").read_text(), "keep")

    def modify_zip(self, archive, name, data, attrs=None):
        with zipfile.ZipFile(archive, "a") as z:
            info = zipfile.ZipInfo(name)
            if attrs is not None:
                info.external_attr = attrs
            z.writestr(info, data)
        Path(str(archive) + ".sha256").write_text(core.digest_file(archive)["sha256"] + "  " + archive.name)

    def test_zip_slip_refused_before_extraction(self):
        _, archive = self.archive()
        self.modify_zip(archive, "../outside.txt", b"no")
        with self.assertRaises(core.BackupError):
            core.unpack_archive(archive, self.base / "unpack", progress=QUIET)
        self.assertFalse((self.base / "outside.txt").exists())
        self.assertFalse((self.base / "unpack").exists())

    def test_zip_unknown_member_refused(self):
        _, archive = self.archive()
        self.modify_zip(archive, "surprise.txt", b"not in manifest")
        with self.assertRaises(core.BackupError):
            core.verify_archive(archive)

    def test_zip_duplicate_member_refused(self):
        _, archive = self.archive()
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.modify_zip(archive, "data/codex/zero-byte.lock", b"duplicate")
        with self.assertRaises(core.BackupError):
            core.verify_archive(archive)

    def test_zip_symlink_refused(self):
        _, archive = self.archive()
        self.modify_zip(archive, "link", b"/other", (stat.S_IFLNK | 0o777) << 16)
        with self.assertRaises(core.BackupError):
            core.verify_archive(archive)

    def test_zip_case_alias_refused(self):
        _, archive = self.archive()
        self.modify_zip(archive, "DATA/CODEX/zero-byte.lock", b"collision")
        with self.assertRaises(core.BackupError):
            core.verify_archive(archive)

    def test_in_archive_same_size_payload_corruption_detected(self):
        _, archive = self.archive()
        altered = self.base / "altered.zip"
        with zipfile.ZipFile(archive) as src, zipfile.ZipFile(altered, "w") as dst:
            for info in src.infolist():
                data = src.read(info)
                if info.filename.endswith("sample/chat.jsonl"):
                    data = b"X" * len(data)
                dst.writestr(info, data)
        with self.assertRaises(core.BackupError):
            core.verify_archive(altered, require_sidecar=False)


class ProviderTests(Fixture):
    def test_single_tool_installation_supported(self):
        shutil.rmtree(self.claude)
        result = discover(self.source, {})
        self.assertEqual([c.id for c in result], ["codex"])

    def test_missing_explicit_tool_fails(self):
        shutil.rmtree(self.codex)
        with self.assertRaises(core.BackupError):
            discover(self.source, {}, tools=["codex"])

    def test_custom_codex_home_discovered(self):
        custom = self.base / "custom-codex"
        custom.mkdir()
        result = discover(self.source, {"CODEX_HOME": str(custom)})
        codex = next(c for c in result if c.id == "codex")
        self.assertEqual(codex.source, custom)
        self.assertEqual(codex.source_mode, "custom")

    def test_custom_claude_home_discovered(self):
        custom = self.base / "custom-claude"
        custom.mkdir()
        result = discover(self.source, {"CLAUDE_CONFIG_DIR": str(custom)})
        self.assertEqual(next(c for c in result if c.id == "claude").source, custom)

    def test_invalid_custom_home_not_silently_ignored(self):
        with self.assertRaises(core.BackupError):
            discover(self.source, {"CODEX_HOME": str(self.base / "missing")})

    def test_developer_secrets_are_opt_in(self):
        (self.source / ".ssh").mkdir()
        self.assertNotIn("ssh", [c.id for c in discover(self.source, {})])
        self.assertIn("ssh", [c.id for c in discover(self.source, {}, include_dev=True)])

    def test_redirected_documents_supported(self):
        docs = self.base / "OneDrive/Documents"
        found = {x.id: x.path for x in locations(self.source, {"AIDBACKUP_DOCUMENTS": str(docs)})}
        self.assertEqual(found["powershell"], docs / "PowerShell")

    def test_unknown_component_not_restored_from_untrusted_metadata(self):
        m = {"components": [{"id": "system-dll", "source_mode": "default", "restore_allowed": True}]}
        with self.assertRaises(core.BackupError):
            restore_targets(m, self.source, {})

    def test_custom_gh_configuration_restore_requires_current_mapping(self):
        m = {"components": [{"id": "gh", "source_mode": "custom", "restore_allowed": True}]}
        with self.assertRaises(core.BackupError):
            restore_targets(m, self.source, {})
        custom = self.base / "new-gh-home"
        self.assertEqual(restore_targets(m, self.source, {"GH_CONFIG_DIR": str(custom)})["gh"], custom)

    def test_old_username_not_reused(self):
        root = self.snapshot()
        m = core.verify_snapshot(root)
        new = self.base / "NewUser"
        result = restore_targets(m, new, {})
        self.assertEqual(result["codex"], new / ".codex")
        self.assertEqual(result["claude-global"], new / ".claude.json")


@unittest.skipUnless(os.name == "nt", "Windows-native behavior; scheduled in Windows CI, not executed in this Linux run")
class WindowsTests(Fixture):
    def test_ntfs_private_output_acl_protected(self):
        root = self.snapshot()
        env = dict(os.environ, AIDBACKUP_ACL_TEST=str(root))
        proc = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                               "(Get-Acl -LiteralPath $env:AIDBACKUP_ACL_TEST).AreAccessRulesProtected"],
                              capture_output=True, text=True, env=env, check=True)
        self.assertIn("True", proc.stdout)

    def test_locked_source_file_fails_instead_of_being_skipped(self):
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        target = self.codex / "sessions/chat.jsonl"
        handle = kernel.CreateFileW(str(target), 0x80000000, 0, None, 3, 0, None)
        self.assertNotEqual(handle, wintypes.HANDLE(-1).value)
        try:
            with self.assertRaises(OSError):
                self.snapshot()
        finally:
            kernel.CloseHandle(handle)

    def test_cmd_launcher_from_different_working_directory(self):
        repo = Path(__file__).resolve().parents[1]
        target = self.base / "tool space! & apostrophe' [x]"
        target.mkdir()
        shutil.copy2(repo / "devstate.py", target)
        shutil.copytree(repo / "src", target / "src")
        shutil.copy2(repo / "02_verify_backup.bat", target)
        env = dict(os.environ, AIDBACKUP_NO_PAUSE="1")
        comspec = os.environ["COMSPEC"]
        launcher = target / "02_verify_backup.bat"
        command_line = f'"{comspec}" /d /v:off /s /c ""{launcher}" --help"'
        result = subprocess.run(
            command_line, executable=comspec, shell=False,
            cwd=self.base, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--compare-live", result.stdout)

    def test_windows_junction_is_refused(self):
        target = self.codex / "junction"
        result = subprocess.run([os.environ["COMSPEC"], "/d", "/c", "mklink", "/J", str(target), str(self.claude)],
                                capture_output=True, text=True)
        if result.returncode:
            self.skipTest("Cannot create junction on this runner filesystem")
        try:
            with self.assertRaises(core.BackupError):
                self.snapshot()
        finally:
            os.rmdir(target)  # Remove only this fixture junction, not its target.
