# Public-release safety review

This is a first-party engineering review, not an external security audit.
The earlier personal prototype was useful for one recovery, but a successful
personal restore did not justify shipping its unsafe failure paths to strangers.

| Finding in the personal prototype | Public candidate response | Evidence |
| --- | --- | --- |
| Some rollback branches recursively deleted a destination even when preserving it had failed. | Runtime has no recursive delete; tracks each preserve/install transition and retains original/failed trees. | Injected preservation, install and readback failures. |
| End-to-end tests moved live agent state away and called broader restore logic. | Rehearsal selects a new isolated destination only, using the same restore engine. | Original fixture source and snapshot unchanged after rehearsal. |
| Long encoded BAT commands, temp-script roots and nested shell quoting caused launch failures. | Small CRLF/no-BOM launchers call a readable Python engine by file path. | Launcher structure tests; native CMD test pending Windows CI. |
| Backup discovery relied on the presence of two folders and could select partial data. | Completion marker plus matching manifest; explicit choice when multiple candidates exist. | Missing/corrupted markers and incomplete-directory selection tests. |
| Only the main agent trees were checked deeply; optional state could be silently lost. | Every included component has canonical file hashes, lengths and directory sets. | Optional single-file/directory roundtrip tests. |
| Restore coverage drifted from backup coverage and old paths could be reused. | Allowlisted providers, current-user mapping and explicit manual-only categories. | Custom-home, unknown-provider and renamed-user tests. |
| Giant hidden commands or optional external inventories obscured progress. | No runtime package inventory/network/API calls; phase/progress messages and no copy/archive deadlines. | Source audit and command-line tests. |
| ZIP integrity checks could just open streams without validating payloads. | Read every included entry and compare length/SHA-256; reject traversal/duplicates/unexpected members. | Archive corruption and malicious-entry tests. |
| Tests were mostly text-pattern checks marketed too strongly. | Executed synthetic filesystem tests with machine-readable results; explicit Windows skips. | [Validation](validation.md). |

## Remaining boundaries

Filesystem operations are not a transactional disk snapshot. Applications must be
closed; a hostile process racing the filesystem is outside the threat model.
A killed interpreter or power loss may require manual journal-guided recovery.
No unencrypted backup utility can make copied secrets safe to publish.
Checksums are not signatures and do not authorize arbitrary backups.

These are reasons to remain a release candidate, not reasons to hide limitations.
