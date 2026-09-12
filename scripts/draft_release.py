#!/usr/bin/env python3
"""Draft an explicit RC from CI's exact commit; no stable or latest release."""
import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from check_repository import ROOT, check
from configure_github import validate_repo


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    project = json.loads((ROOT / 'release/project.json').read_text())
    if not project['prerelease'] or not re.fullmatch(r'\d+\.\d+\.\d+-rc\.\d+', project['version']):
        raise SystemExit('Only explicit release candidates are supported by this workflow.')
    if not check()['passed']:
        raise SystemExit('Publication checks failed.')
    repo = validate_repo(os.environ.get('GITHUB_REPOSITORY', 'example-owner/windows-ai-dev-state-backup'))
    sha = os.environ.get('GITHUB_SHA', '')
    if a.apply and (os.environ.get('GITHUB_ACTIONS') != 'true' or not re.fullmatch(r'[a-f0-9]{40}', sha)):
        raise SystemExit('Apply mode is restricted to the validated GitHub Actions workflow.')
    tag = 'v' + project['version']
    notes = ROOT / 'release' / ('notes-' + tag + '.md')
    files = []
    for flavor in ('windows', 'source'):
        archive = ROOT / 'dist' / f"{project['slug']}-{project['version']}-{flavor}.zip"
        sidecar = Path(str(archive) + '.sha256')
        if not archive.is_file() or not sidecar.is_file():
            raise SystemExit('Build both allowlisted assets before drafting a release.')
        if hashlib.sha256(archive.read_bytes()).hexdigest() != sidecar.read_text().split()[0]:
            raise SystemExit('Release asset checksum mismatch.')
        files.extend([str(archive), str(sidecar)])
    command = ['gh', 'release', 'create', tag, *files, '--repo', repo, '--draft', '--prerelease',
               '--latest=false', '--target', sha or '<CI commit>', '--title', 'AI Dev State Backup ' + tag,
               '--notes-file', str(notes)]
    print(subprocess.list2cmdline(command))
    if a.apply:
        subprocess.run(command, cwd=ROOT, check=True)
    else:
        print('DRY RUN: no release created.')


if __name__ == '__main__':
    main()
