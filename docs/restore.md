# Restoring after a reinstall or account change

## First check the account and the backup

Install Python and the applications you need. Run the toolkit under the Windows account that should receive the restored state. Close the applications again before restoring.

Keep a verified copy on an independent device. Never place your only backup in a directory that the restore will replace.

## Review before writing

```powershell
.\03_restore_dev_state.bat --backup "E:\AIBackups\snapshots\DEV_STATE_BACKUP_<ID>"
```

This hashes the snapshot and shows targets. It does not create destination directories, journals or recovery holds. It does not test whether the new machine can actually sign in to a service.

```powershell
.\03_restore_dev_state.bat --backup "E:\AIBackups\snapshots\DEV_STATE_BACKUP_<ID>" --apply
```

Type `RESTORE`. Every selected component is staged in a private sibling work directory and verified before any live target is moved. Originals go into an `original` hold. The staged data is renamed into place and verified again. The resulting journal records actual paths and phase transitions.

Success retains original holds. Failure attempts rollback **only for operations this transaction performed**. A failed restored tree is moved into a `failed` hold rather than recursively deleted. If another program creates a conflicting destination, automatic recovery stops for that component and preserves both the competing data and the original hold.

## Restore only selected state

```powershell
.\03_restore_dev_state.bat --backup "E:\AIBackups\snapshot" --components claude claude-global codex
```

Only components present in the snapshot and allowed by the provider list can be restored. Desktop reference components are not silently treated as supported migrations.

## A different Windows username

Default targets use the **current** profile, not the old `source_path` in the manifest. Custom homes must be configured on the new machine or explicitly mapped; the tool refuses to guess.

Create a local JSON file outside the immutable snapshot:

```json
{
  "claude": "D:\\AgentState\\claude",
  "codex": "D:\\AgentState\\codex"
}
```

Then review:

```powershell
.\03_restore_dev_state.bat --backup "E:\AIBackups\snapshot" --components claude codex --target-map ".\my-targets.json"
```

The map is an explicit user instruction. The toolkit does not automatically set `CODEX_HOME`/`CLAUDE_CONFIG_DIR`, rewrite paths inside chats, import old environment variables, or fix references to a repository's old location.

## Journals and recovery holds

Normal live restores share the current user's report directory:

```text
%LOCALAPPDATA%\AiDevStateBackup\reports\restore-<transaction>.json
```

Each target has a sibling `.aidbackup-<transaction>-<component>/` work directory. Treat journals and holds as private: names and paths can reveal sensitive information even when file contents are absent from the journal.

Do not delete anything after a failed or interrupted restore until [recovery.md](recovery.md) has been followed. A successful byte-level restore still needs a manual application check: open the app, sign in if necessary, and resume a few important sessions.
