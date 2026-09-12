"""Publication and CLI tests; temporary source copies and synthetic fixtures only."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from aidbackup import core
from aidbackup.providers import restore_targets

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_repository
import configure_github
from test_safety import Fixture, QUIET


class AdditionalSafetyTests(Fixture):
    def test_empty_archive_checksum_is_a_clear_failure(self):
        archive = core.create_archive(self.snapshot(), progress=QUIET)
        Path(str(archive) + '.sha256').write_text('')
        with self.assertRaisesRegex(core.BackupError, 'sidecar is empty'):
            core.verify_archive(archive)

    def test_non_string_target_map_is_rejected(self):
        m = core.verify_snapshot(self.snapshot())
        with self.assertRaisesRegex(core.BackupError, 'path strings'):
            restore_targets(m, self.base / 'new-profile', {}, overrides={'claude': 17})

    def test_malformed_exclusion_is_rejected(self):
        root = self.snapshot()
        self.change_manifest(root, lambda m: m['components'][0]['exclusions'].append({'path': None}))
        with self.assertRaises(core.BackupError):
            core.verify_snapshot(root)

    def test_source_only_toolkit_can_verify_zip_without_platform_discovery(self):
        archive = core.create_archive(self.snapshot(), progress=QUIET)
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'devstate.py'), 'check',
                                 '--backup', str(archive)], cwd=self.base,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('ARCHIVE VERIFIED', result.stdout)

    def test_rehearsal_cli_uses_only_selected_fixture_snapshot(self):
        root = self.snapshot()
        before = core.tree(self.source)
        toolkit = self.base / 'toolkit'
        toolkit.mkdir()
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'devstate.py'), '--toolkit',
                                 str(toolkit), 'rehearse', '--backup', str(root), '--confirm', 'REHEARSE'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        core.content_equal(before, core.tree(self.source), 'live source untouched')
        self.assertEqual(len(list((toolkit / 'rehearsals').glob('rehearsal-*'))), 1)

    def test_cli_typo_fails_before_any_work(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'devstate.py'), 'restore', '--aply'],
                                cwd=self.base, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('unrecognized arguments', result.stderr)


class PublicationTests(unittest.TestCase):
    def test_allowlist_and_docs_checks_pass(self):
        result = check_repository.check()
        self.assertTrue(result['passed'], result)

    def test_no_real_state_allowed_in_source_manifest(self):
        paths = check_repository.publication_files()
        self.assertTrue(paths)
        self.assertTrue(all(not check_repository.SENSITIVE.search(p) for p in paths))
        self.assertIn('release/publish-files.json', paths)

    def test_repository_slug_validation(self):
        self.assertEqual(configure_github.validate_repo('valid-owner/windows-ai-dev-state-backup'),
                         'valid-owner/windows-ai-dev-state-backup')
        for bad in ('https://github.com/me/repo', '../repo', 'user/a b', 'user/x;cmd', 'single'):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                configure_github.validate_repo(bad)

    def test_metadata_commands_do_not_claim_a_release(self):
        cmds = configure_github.commands('valid-owner/windows-ai-dev-state-backup')
        self.assertTrue(all(cmd[0] == 'gh' for cmd in cmds))
        self.assertFalse(any('release' in cmd for cmd in cmds))
        self.assertTrue(any('private-vulnerability-reporting' in ' '.join(cmd) for cmd in cmds))

    def test_publish_preview_does_not_call_git_or_github(self):
        # Empty PATH proves preview does not require or call git/gh. Python is absolute.
        env = dict(os.environ, PATH='')
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/publish.py'),
                                 '--repo', 'valid-owner/windows-ai-dev-state-backup', '--public'],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('DRY RUN', result.stdout)

    def test_runtime_has_no_recursive_delete_or_network_library(self):
        import ast
        for path in (ROOT / 'src/aidbackup').glob('*.py'):
            text = path.read_text()
            parsed = ast.parse(text)
            for item in ast.walk(parsed):
                if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute):
                    self.assertNotIn(item.func.attr, ('rmtree', 'unlink', 'remove'), path.name)
                if isinstance(item, ast.Import):
                    self.assertFalse(any(n.name.split('.')[0] in {'requests', 'urllib', 'http', 'socket'}
                                         for n in item.names), path.name)

    def test_launcher_files_have_crlf_no_bom_and_small_commands(self):
        for path in ROOT.glob('*.bat'):
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b'@echo off\r\n'))
            self.assertNotIn(b'\n', raw.replace(b'\r\n', b''))
            self.assertLess(max(map(len, raw.splitlines())), 2048)
            self.assertIn(b'DisableDelayedExpansion', raw)

    def test_release_metadata_is_explicitly_prerelease(self):
        project = json.loads((ROOT / 'release/project.json').read_text())
        self.assertTrue(project['prerelease'])
        self.assertIn('-rc.', project['version'])
        if project['repository'] is not None:
            configure_github.validate_repo(project['repository'])  # Set only after real publication.

    def test_build_is_deterministic_and_allowlisted(self):
        with tempfile.TemporaryDirectory(prefix='aidbackup-buildtest-') as temp:
            base = Path(temp)
            zips = []
            for folder in ('one', 'two'):
                result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/build_release.py'),
                                         '--source', '--output', str(base / folder)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                zips.append(next((base / folder).glob('*.zip')))
            self.assertEqual(zips[0].read_bytes(), zips[1].read_bytes())
            with zipfile.ZipFile(zips[0]) as z:
                self.assertIsNone(z.testzip())
                files = {name.split('/', 1)[1] for name in z.namelist()}
                self.assertEqual(files, set(check_repository.publication_files()))
                self.assertFalse(any('/.git/' in p for p in z.namelist()))
            checksum = Path(str(zips[0]) + '.sha256').read_text().split()[0]
            self.assertEqual(hashlib.sha256(zips[0].read_bytes()).hexdigest(), checksum)

    def test_runtime_release_extracts_and_displays_help(self):
        with tempfile.TemporaryDirectory(prefix='aidbackup-runtimetest-') as temp:
            base = Path(temp)
            result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/build_release.py'),
                                     '--output', str(base / 'dist')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with zipfile.ZipFile(next((base / 'dist').glob('*.zip'))) as z:
                z.extractall(base / 'expanded')
            app = next((base / 'expanded').iterdir())
            help_result = subprocess.run([sys.executable, '-B', str(app / 'devstate.py'), '--help'],
                                         cwd=base, capture_output=True, text=True)
            self.assertEqual(help_result.returncode, 0, help_result.stdout + help_result.stderr)
            self.assertIn('rehearse', help_result.stdout)
            self.assertTrue((app / 'src/aidbackup/core.py').exists())
            self.assertFalse((app / 'tests').exists())
            self.assertTrue((app / 'release/local-validation.json').exists())
            for doc in app.rglob('*.md'):
                for link in re.findall(r'\]\(([^\s)]+)(?:\s[^)]*)?\)', doc.read_text(encoding='utf8')):
                    if link.startswith(('http:', 'https:', 'mailto:', '#')):
                        continue
                    self.assertTrue((doc.parent / link.split('#')[0]).resolve().exists(),
                                    str(doc.relative_to(app)) + ': ' + link)

    def test_documented_sensitive_outputs_are_gitignored(self):
        if not shutil.which('git'):
            self.skipTest('Git unavailable in test environment')
        with tempfile.TemporaryDirectory(prefix='aidbackup-gitignore-') as temp:
            work = Path(temp)
            shutil.copy2(ROOT / '.gitignore', work)
            subprocess.run(['git', 'init', '-q'], cwd=work, check=True)
            sensitive = ['backups/private.txt', '.claude/projects/x.jsonl', '.codex/auth.json',
                         'DEV_STATE_BACKUP_example/manifest.json', '.ssh/id_ed25519', 'archive.zip',
                         'reports/restore-1.json', '.aidbackup-transaction-claude/original/data',
                         'another/secret.db', '.git-credentials', 'my-targets.json']
            for name in sensitive:
                result = subprocess.run(['git', 'check-ignore', '--no-index', name], cwd=work,
                                         capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, name)

    def test_workflows_do_not_upload_user_data_globs(self):
        for path in (ROOT / '.github/workflows').glob('*.yml'):
            text = path.read_text()
            self.assertNotIn('pull_request_target:', text)
            self.assertNotIn('path: **', text)
            self.assertNotIn('path: .', text)
            self.assertIn('persist-credentials: false', text)
