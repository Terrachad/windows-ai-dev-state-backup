# Troubleshooting

| Message or symptom | What to check |
| --- | --- |
| Python required | Install Python 3.11+, verify `py -3 --version`, and keep the complete release directory together. |
| No completed format-3 snapshot | Use the explicit `--backup` directory. Incomplete and legacy V8 folders are intentionally not guessed as valid. |
| Source changed during backup | Close the writer, keep the failed attempt separate and start a new backup. Do not omit database/WAL files to force success. |
| Link/reparse point refused | The tool does not follow links into unknown locations. Use a regular-file source, or another backup method for that component. |
| Permission/ACL protection failure | Confirm the current Windows account and local NTFS destination. Do not change ownership of unrelated user folders. |
| A source is missing | Check `CODEX_HOME` / `CLAUDE_CONFIG_DIR` and the actual user profile. Missing explicitly selected state is fatal. |
| Hash/path-set mismatch | Treat it as an incomplete/corrupted or changed artifact. Compare against the original verified copy; do not edit its manifest to pass. |
| Restore stage fails | Originals have not yet been moved if staging did not finish. Retained work folders and the journal show the actual state. |
| Manual recovery required | Stop apps, keep all holds and follow [recovery.md](recovery.md). |
| App asks for login | Local file restoration cannot guarantee portability of OS-bound or expired credentials. |
| App cannot find a project | Verify external project paths and drive letters. The tool does not rewrite absolute paths or copy external repositories. |
| Old PowerShell MAX_PATH error | The v2 engine no longer uses `Get-FileHash` or extracted PowerShell scripts. Use Python 3.11+ and supported regular-file paths. |

## Synthetic examples

### Missing custom `CODEX_HOME`

For example, a deliberately fake setting of `CODEX_HOME=C:\Synthetic\MissingCodexHome` can produce:

```text
STOPPED: Configured custom codex directory is missing: C:\Synthetic\MissingCodexHome
```

Discovery reads the current `CODEX_HOME` value and requires that custom path to be an existing directory; it does not silently fall back to `%USERPROFILE%\.codex`. This check does not search for another Codex home, validate a login or token, inspect cloud-only state, or prove that application sessions are portable.

Stop and inspect the environment setting. Deliberately correct it to the intended existing directory, or remove the override only if you intend to use the default home. Do not create an empty directory merely to bypass the check, delete or move either possible state directory, edit a backup manifest, or publish real paths or contents in a report.

### Long-path error

A tool encountering a deliberately fake deep path such as `C:\Synthetic\DeepTree\...\session.jsonl` might report `[WinError 206] The filename or extension is too long`. This is a representative Windows error, not proof that it came from this toolkit. The v2 Python engine uses extended-length Windows paths for file I/O, and its synthetic suite covers a path longer than 300 characters; it does not enable Windows long-path policy, change filesystem capabilities, or guarantee that shells, old V8/PowerShell tooling, archive viewers, editors, Claude, or Codex accept the same path.

An error from an old PowerShell workflow does not show that v2 failed. For a v2 error, report the operation and a redacted or synthetic path. Keep the source, backup, incomplete snapshot, journal, and recovery holds; identify whether the failing path is in the source, toolkit, or destination; then retry only with the current v2/Python workflow and a supported local NTFS location. A shorter destination helps only when the failing path is under that destination. Do not rename or delete source state, edit manifests, omit files, or discard recovery artifacts to force success.

Large backups can legitimately take time. There are no runtime copy/hash/archive timeouts. The tool prints component progress and file counts; a single very large file can take time between updates. Check disk activity rather than assuming a silent interval proves a hang. Archive compression uses a fast setting, not maximum compression.

Never upload an unredacted backup, raw authentication file or entire recovery journal for diagnosis. Use a synthetic reproduction.
