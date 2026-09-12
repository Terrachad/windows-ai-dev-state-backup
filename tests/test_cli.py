"""In-process CLI flows over real synthetic files, with only account discovery substituted."""
import contextlib
import io
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from aidbackup import cli, core
from test_safety import Fixture, QUIET


class CLITests(Fixture):
    def invoke(self, *args, env_home=None, answer=None):
        home = env_home or self.source
        env = {'LOCALAPPDATA': str(self.base / 'local-app-data')}
        out, err = io.StringIO(), io.StringIO()
        with patch.object(cli, 'current_context', return_value=(home, env)), \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            if answer is None:
                result = cli.main(list(args))
            else:
                with patch('builtins.input', return_value=answer):
                    result = cli.main(list(args))
        return result, out.getvalue(), err.getvalue()

    def test_backup_cli_creates_snapshot_and_archive(self):
        rc, out, err = self.invoke('--toolkit', str(self.base), 'backup', '--output', str(self.output),
                                   '--confirm', 'BACKUP')
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(len(list(self.output.glob('DEV_STATE_BACKUP_*.zip'))), 1)
        self.assertIn('BACKUP COMPLETE', out)

    def test_backup_cli_without_archive(self):
        rc, out, err = self.invoke('--toolkit', str(self.base), 'backup', '--no-archive',
                                   '--confirm', 'BACKUP')
        self.assertEqual(rc, 0, out + err)
        self.assertFalse(list(self.output.glob('*.zip')))
        self.assertTrue(list(self.output.glob('DEV_STATE_BACKUP_*')))

    def test_backup_rejected_confirmation_has_no_output(self):
        rc, out, err = self.invoke('--toolkit', str(self.base), 'backup', answer='NO')
        self.assertEqual(rc, 1)
        self.assertFalse(self.output.exists())

    def test_check_live_compares_synthetic_sources(self):
        root = self.snapshot()
        rc, out, err = self.invoke('check', '--backup', str(root), '--compare-live')
        self.assertEqual(rc, 0, out + err)
        self.assertIn('SNAPSHOT VERIFIED', out)

    def test_check_live_detects_mutation(self):
        root = self.snapshot()
        (self.codex / 'sessions/chat.jsonl').write_text('Changed after backup')
        rc, out, err = self.invoke('check', '--backup', str(root), '--compare-live')
        self.assertEqual(rc, 1)
        self.assertIn('mismatch', err)

    def test_zip_compare_live_is_rejected(self):
        archive = core.create_archive(self.snapshot(), progress=QUIET)
        rc, out, err = self.invoke('check', '--backup', str(archive), '--compare-live')
        self.assertEqual(rc, 1)
        self.assertIn('Unpack first', err)

    def test_restore_default_is_dry_run_with_no_profile_writes(self):
        root = self.snapshot()
        destination = self.base / 'new-account'
        rc, out, err = self.invoke('restore', '--backup', str(root), env_home=destination)
        self.assertEqual(rc, 0, out + err)
        self.assertFalse(destination.exists())
        self.assertFalse((self.base / 'local-app-data').exists())
        self.assertIn('DRY RUN COMPLETE', out)

    def test_restore_cli_applies_current_account_mapping(self):
        root = self.snapshot()
        destination = self.base / 'new-account'
        rc, out, err = self.invoke('restore', '--backup', str(root), '--apply', '--confirm', 'RESTORE',
                                   env_home=destination)
        self.assertEqual(rc, 0, out + err)
        self.assertTrue((destination / '.claude.json').is_file())
        core.content_equal(core.tree(self.codex), core.tree(destination / '.codex'), 'restored by CLI')
        self.assertIn('RESTORE COMPLETE', out)

    def test_restore_confirmation_refusal_does_not_write(self):
        root = self.snapshot()
        destination = self.base / 'new-account'
        rc, out, err = self.invoke('restore', '--backup', str(root), '--apply', env_home=destination, answer='NO')
        self.assertEqual(rc, 1)
        self.assertFalse(destination.exists())

    def test_restore_one_component_with_explicit_target_map(self):
        root = self.snapshot()
        target = self.base / 'custom-location'
        mapping = self.base / 'targets.json'
        mapping.write_text(json.dumps({'codex': str(target)}))
        rc, out, err = self.invoke('restore', '--backup', str(root), '--components', 'codex',
                                   '--target-map', str(mapping), '--apply', '--confirm', 'RESTORE')
        self.assertEqual(rc, 0, out + err)
        core.content_equal(core.tree(self.codex), core.tree(target), 'explicit target')

    def test_cli_unpack_roundtrip(self):
        root = self.snapshot()
        archive = core.create_archive(root, progress=QUIET)
        target = self.base / 'unpacked'
        rc, out, err = self.invoke('unpack', '--archive', str(archive), '--destination', str(target))
        self.assertEqual(rc, 0, out + err)
        core.verify_snapshot(target)

    def test_cli_rehearse_requires_confirmation(self):
        root = self.snapshot()
        rc, out, err = self.invoke('--toolkit', str(self.base), 'rehearse', '--backup', str(root), answer='NO')
        self.assertEqual(rc, 1)
        self.assertFalse((self.base / 'rehearsals').exists())

    def test_no_snapshot_discovery_fails_clearly(self):
        rc, out, err = self.invoke('--toolkit', str(self.base), 'check')
        self.assertEqual(rc, 1)
        self.assertIn('No completed format-3 snapshots', err)

    def test_single_snapshot_discovery(self):
        root = self.snapshot()
        rc, out, err = self.invoke('--toolkit', str(self.base), 'check')
        self.assertEqual(rc, 0, out + err)
        self.assertIn(root.name, out)

    def test_multiple_snapshots_require_explicit_choice(self):
        self.snapshot()
        self.snapshot()
        rc, out, err = self.invoke('--toolkit', str(self.base), 'check', answer='')
        self.assertEqual(rc, 1)
        self.assertIn('cancelled', err)
        rc, out, err = self.invoke('--toolkit', str(self.base), 'check', answer='1')
        self.assertEqual(rc, 0, out + err)
