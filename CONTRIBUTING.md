# Contributing

Small, reproducible safety improvements are more valuable here than a large feature list.

## Setup

Python 3.11+ is sufficient for the runtime and tests; no test framework or live agent installation is required.

```powershell
py -3 scripts/run_tests.py
py -3 scripts/check_repository.py
```

Use a fresh branch and add a synthetic regression test before changing behavior. Do not use your real `.claude`, `.codex`, SSH keys or cloud credentials as fixtures.

## Safety rules

1. Keep restore dry-run as the default and confirm real writes explicitly.
2. Never add recursive deletion of a live target, original hold or backup to a recovery path.
3. Stage and verify every selected component before moving originals.
4. Never use a backup's absolute source paths as current write destinations.
5. Fail on unreadable selected sources, corrupt hashes, path collisions and unexpected links.
6. Keep network, package managers, login flows and forced app termination out of the backup engine.
7. An isolated rehearsal must never select or mutate live agent paths.

Changes to provider paths need scope documentation and a fixture. Changes to the manifest require a format-version decision and migration notes. Do not quietly expand default collection to new credential sources.

## Pull requests

Explain the user problem, before/after behavior, risks, rollback behavior and tests actually run. Mark Windows tests as pending if they were not executed. Update documentation and the changelog. The PR template has the minimum checklist.

Do not claim “all edge cases tested.” Do not add a green badge for a test that did not run. A passing Linux fixture suite does not establish Windows ACL or desktop-app behavior.

## Releases

Follow [the maintainer release gate](docs/releasing.md). Source version, tag, changelog and package metadata must agree. Distribution ZIPs are built from an explicit allowlist, not from an arbitrary working-directory glob.
