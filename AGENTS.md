# Contributor instructions for coding agents

This repository handles sensitive user state. Read SECURITY.md and docs/architecture.md before changing filesystem code.

- Run `python scripts/run_tests.py` and `python scripts/check_repository.py`.
- Use generated temporary fixtures only. Never discover or access a real local user profile in tests.
- Never add recursive deletion to the runtime, restore rollback or rehearsal path.
- Keep original holds, a persisted journal, and verify-before-swap ordering.
- Never derive restore destinations from a backup manifest's source paths.
- Do not execute restored hooks, log in to apps, call AI services or install tools during backup/recovery.
- Do not leak file contents into logs, CI artifacts, examples or test reports.
- Describe platform-specific checks not executed; do not replace runtime tests with source-string assertions.
- Keep prerelease labels until the documented Windows and manual application gates pass.
- Publishing is a maintainer action. Do not create public issues, releases or pushes without authorization.
