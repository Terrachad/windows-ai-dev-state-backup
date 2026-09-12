# Using the toolkit

## Prerequisites

The public v2 release candidate uses Python 3.11+ with only its standard library. Windows users may use the included BAT launchers with the `py` launcher, or run `python devstate.py ...` directly. Keep the complete extracted release directory together.

Download Python through the [official Windows instructions](https://docs.python.org/3/using/windows.html). Verify `py -3 --version` before proceeding. The BAT sets Python Install Manager automatic installation to false for its process. No tool downloads or app installers are run by the backup engine.

Use a local NTFS disk on Windows. UNC/network/device paths are deliberately unsupported in this release. Output directories are restricted to the current account, SYSTEM and Administrators using local ACL commands; failure to protect output permissions stops the operation.

## Before you begin

Close applications that can write the selected files. The tool compares source data before and after copying, but is not a VSS/database snapshot service. Have another independent backup of data you cannot replace.

Run as your normal user, not a different administrator account. A different account means different `USERPROFILE`, `APPDATA` and environment settings. Do not change Windows security policy to run this toolkit.

## Backup commands

```powershell
# Agent state only; detects either or both tools.
.\01_backup_dev_state.bat

# Require specific agent state; fail rather than silently skip it.
.\01_backup_dev_state.bat --tools claude codex

# Include supported developer configuration.
.\01_backup_dev_state.bat --include-dev

# Desktop data is additional manual-restore reference, not automatic restore.
.\01_backup_dev_state.bat --include-dev --include-desktop

# An explicit destination avoids guessing where a backup was written.
.\01_backup_dev_state.bat --output "E:\AIBackups\snapshots"

# A verified directory snapshot without an archive.
.\01_backup_dev_state.bat --no-archive
```

Optional configuration not installed is absent from the source list. Once a source is selected, an unreadable or inconsistent copy fails the operation. An explicitly selected primary agent with no state also fails.

Snapshots use unique IDs, not just timestamps. On failure the `.incomplete-...` directory remains for inspection and is not offered as a completed snapshot. No partial snapshot is automatically deleted.

## Verification and extraction

```powershell
.\02_verify_backup.bat --backup "E:\AIBackups\snapshots\DEV_STATE_BACKUP_<ID>"
.\02_verify_backup.bat --backup "E:\AIBackups\snapshots\DEV_STATE_BACKUP_<ID>" --compare-live
.\02_verify_backup.bat --backup "E:\AIBackups\snapshots\DEV_STATE_BACKUP_<ID>.zip"

# Verify a ZIP, then unpack it into a NEW directory.
py -3 devstate.py unpack --archive "E:\AIBackups\snapshots\DEV_STATE_BACKUP_<ID>.zip" --destination "E:\AIBackups\extracted-new"
```

A directory check verifies that directory only; it does not silently claim to have checked the sibling archive. A ZIP check requires the sidecar, verifies its hash, rejects unsafe or duplicate entry names, and reads every included payload against the manifest.

Keep tool files outside immutable snapshot directories. Unexpected files in a completed snapshot are reported as an integrity problem.

## Folder discovery

Without `--backup`, tools look for completed format-3 snapshots in the toolkit folder and its `backups/` child. One eligible candidate is displayed and selected. Multiple candidates require an explicit number; an empty answer cancels. Folder modification time is not used as proof that a backup is the correct one.

Snapshots created in another directory require `--backup`. This avoids searching all your drives or silently choosing an older backup.

## Pauses and automation

BAT windows pause at the end so errors remain readable. Set `AIDBACKUP_NO_PAUSE=1` in the process environment for scripted invocations, or call `devstate.py` directly.

Noninteractive actions require an explicit acknowledgement:

```powershell
py -3 devstate.py backup --confirm BACKUP --no-archive
py -3 devstate.py rehearse --backup "E:\AIBackups\snapshot" --confirm REHEARSE
py -3 devstate.py restore --backup "E:\AIBackups\snapshot" --apply --confirm RESTORE
```

Do not run two restores to the same targets from different accounts or manipulate their recovery folders while a restore is active. Live CLI restores for the same account share a report-directory lock.
