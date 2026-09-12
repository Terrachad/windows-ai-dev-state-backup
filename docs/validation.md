# Validation status

**2.0.0-rc.1 is a release candidate. Do not equate a configured CI workflow with a passing Windows test.**

The local evidence file is [local-validation.json](../release/local-validation.json).
It records the actual environment, counts and skipped native-platform tests.
The suite uses synthetic files only. It does not read the maintainer's chat data,
use real credentials or call an AI service.

## Recorded local result

| Measurement | Result |
| --- | --- |
| Environment | Linux, Python 3.13.5 |
| Discovered tests | 116 |
| Passed | 112 |
| Failures / errors | 0 / 0 |
| Skipped | 4 Windows-native tests |
| Measured statement + branch coverage | 87.56% across in-process runtime modules |

The report is evidence for this candidate's source at preparation time, not a
claim that a future commit has the same results. Subprocess execution and
Windows-only branches are not fully represented in the coverage percentage.

## What was executed locally

A Linux / Python 3.13 run exercises actual filesystem backup, archive verification,
isolated restore, injected copy/rename/readback failures, recovery journaling,
path validation and publication tooling. This is executable integration testing,
not substring checks over a BAT file.

Tests include missing/empty inputs; zero-byte files and empty directories; Unicode,
spaces and shell punctuation; paths over 300 characters; link/cycle refusal;
corrupted or incomplete snapshots; same-size hash corruption; custom locations;
new account mapping; dry-run immutability; failed staging; failed preservation;
post-install corruption; interrupted transactions; rollback conflicts; lock
contention; malicious ZIP paths, duplicate entries and symlinks; and deterministic,
allowlisted release packaging.

Repository checks inspect source syntax, relative Markdown links, immutable
GitHub Action refs, version consistency, publication allowlists and common secret
signatures. These checks are useful but are not a complete security audit.

## Not executed in the local environment

- Native Windows ACL, locked-file, junction and CMD launcher behavior. These tests
  are scheduled in the Windows CI matrix and are explicitly skipped on Linux.
- All advertised Python/Windows combinations. The exact-commit CI runs must pass
  before publishing a release candidate for external testing.
- Restoring and resuming an authenticated Claude Code/Codex conversation in the
  rewritten engine; file verification is not an application compatibility test.
- Power-loss/reboot recovery across every journal transition.
- A third-party security or data-loss audit.

The earlier private V8 prototype had a user-reported successful personal restore.
That result is **not** counted as validation of this rewritten public engine.

## Required stable-release gate

1. The `required` CI job passes for the exact source commit.
2. Standard-user Windows 11 + local NTFS behavior is tested on disposable data.
3. A disposable-profile Claude/Codex session restore is checked manually with
   versions recorded and without publishing credentials or transcripts.
4. Safety/recovery paths receive independent review.
5. Documentation, privacy boundaries and legacy-format incompatibility are accurate.

Do not add a green badge or a "fully tested" claim until evidence supports it.
The [release process](releasing.md) deliberately creates a **draft prerelease**.
