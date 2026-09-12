# Recovery without guessing

**Stop the apps. Keep the snapshot, ZIP, original holds, failed copies and journal. Do not run cleanup commands.**

The toolkit never promises an atomic multi-directory transaction across drives. Its recovery journal and preserved originals are designed to make interruption inspectable, including a process crash or power failure that cannot be caught in Python.

## Read the journal

Open the most recent `restore-<transaction>.json` in `%LOCALAPPDATA%\AiDevStateBackup\reports`. Do not upload it publicly without redaction.

Each entry records `target`, `stage`, `hold`, `failed`, `original_moved`, `installed` and `phase`. Check the actual filesystem too: a power loss can occur between an on-disk rename and the next journal write.

| Actual condition | Safe interpretation |
| --- | --- |
| Target exists, no original hold, entry never installed | The original may be untouched; do not delete it. |
| Original hold exists, target is absent | Preserve the hold. After checking the paths/content, the hold can be moved back to its original target. |
| Original hold and target both exist | Keep both. The target may be restored data or newly written data from another process. |
| Failed copy exists | It was retained for inspection; it is not evidence of a complete restore. |
| Status is `manual-recovery-required` | Automatic rollback encountered a conflict/error. Resolve one component at a time from the actual files and journal. |

## Conservative manual recovery

1. Make another copy of the original hold and target to a private location when space permits.
2. Verify which tree contains the pre-restore state. Do not identify it solely from a folder name.
3. With applications closed, rename a conflicting target to a separate holding name; do not delete it.
4. Move the verified original hold back only when the target path is absent.
5. Inspect the application and keep all copies until recovery is confirmed.

There is deliberately no generic `rmdir /s`, `Remove-Item -Recurse`, or auto-clean button in this procedure. Repeating `--apply` before understanding a failed transaction creates more holds and may make diagnosis harder.

## Report a problem safely

Share the tool version, Windows/Python versions, operation, short redacted error and a **synthetic reproduction**. Never post a real backup or credential/session file. See [SECURITY.md](../SECURITY.md).
