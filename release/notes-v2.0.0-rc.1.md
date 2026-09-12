# AI Dev State Backup 2.0.0-rc.1

A safety-focused release candidate for backing up Claude Code, OpenAI Codex and optional Git/SSH developer state on Windows.

## What is new

- Readable, dependency-free Python engine with small Windows BAT launchers.
- Complete manifests, SHA-256 verification and explicit completed snapshots.
- No-write restore plans; all selected components staged and verified before target changes.
- Existing state and failed replacements retained in private recovery locations.
- An isolated restore rehearsal instead of a test that moves live `.claude` / `.codex` directories.
- Custom agent homes, current-user destination mapping and optional developer state.
- ZIP/ZIP64 snapshots with checksum sidecars and verified, new-directory extraction.

## Read before installing

This is a **prerelease**, not an established backup product. Python 3.11+ is required.
Extract the complete Windows ZIP; keep `src/` and `devstate.py` with the BATs.
Snapshots are **unencrypted** and may contain private keys, tokens and conversation content.
Keep an independent backup and read the validation and limitations documents.

The public format is not a drop-in importer for the earlier private V8 toolkit.
Do not discard an older working backup because this candidate exists.

## Validation

Review the exact-commit CI results and the validation report attached to the source.
Windows CI configuration is not, by itself, a successful Windows test.
Authenticated application/session-resume testing and independent review remain separate release gates.

## Download

- `*-windows.zip`: launchers, engine, safety documentation and branding assets.
- `*-source.zip`: full source, tests, CI and maintainer tools.
- Adjacent `.sha256` files: detect accidental archive changes; they are not signatures.

Please report reproducible problems with synthetic data. Never attach a real snapshot or recovery journal.
