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

Large backups can legitimately take time. There are no runtime copy/hash/archive timeouts. The tool prints component progress and file counts; a single very large file can take time between updates. Check disk activity rather than assuming a silent interval proves a hang. Archive compression uses a fast setting, not maximum compression.

Never upload an unredacted backup, raw authentication file or entire recovery journal for diagnosis. Use a synthetic reproduction.
