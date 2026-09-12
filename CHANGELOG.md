# Changelog

## 2.0.0-rc.1 — 2026-09-12

Safety-focused public release candidate. **Not yet a stable release.**

### Changed

- Shared Python 3.11+ standard-library engine with thin BAT launchers; removed duplicated/self-extracted PowerShell payloads.
- New format-3 completed snapshots, canonical manifests and exact path-set validation.
- Existing-target preservation, staged verification and journaled rollback without recursive deletion.
- Isolated restore rehearsal instead of temporarily removing live agent state.
- Explicit selection of completed snapshots and current-user destination mapping.
- Opt-in developer and manual-only desktop data collection.

### Added

- Real synthetic filesystem tests, corruption/path traversal/fault injection cases and Windows-native CI jobs.
- ZIP/ZIP64 verification, adjacent SHA-256 sidecars and validated extraction into new directories.
- Private output permissions, custom agent homes and redirected Documents handling.
- Security/reporting policy, support docs, repository guardrails, release tooling and maintainer publication helpers.

### Breaking changes

- Python is now required and the complete release directory must stay together.
- Legacy V8/draft-v1 snapshots are not automatically imported or selected.
- Desktop package data is reference-only, not automatically restored.
- See docs/migration.md and docs/validation.md before relying on this candidate.

## Historical private prototype

The earlier V8 and draft-v1 archives were personal migration prototypes. A user reported a successful Windows restore, but those builds did not have the public release's safety model or broad compatibility evidence. They are not distributed here and are not promoted as a stable public release.
