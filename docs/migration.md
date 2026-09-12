# From the private V8 / draft v1 toolkit

`2.0.0-rc.1` is a deliberate major-version rewrite. It keeps the familiar BAT workflow but uses a shared, readable Python engine instead of four duplicated PowerShell payloads. Python 3.11+ and the complete release directory are required.

## Breaking changes

| Old draft | Public v2 candidate |
| --- | --- |
| Standalone BAT with embedded PowerShell | BAT launcher plus `devstate.py` and `src/` |
| Assumed both agent folders must exist | Detect either agent; explicitly selected missing state fails |
| In-place live-state E2E test | Isolated rehearsal only |
| Rollback could recursively delete a target | Preserved originals and failed copies; journaled recovery |
| Automatic newest-folder default | Explicit choice when multiple completed snapshots exist |
| Old `files/ClaudeCode/state` format | Format 3: manifest, completion marker, `data/<component>/` |
| Some optional data verified less thoroughly | Every included component checked by content hash and exact path set |

Existing V8 snapshots are **not** automatically selected or rewritten. Keep your old verified backups and the working private toolkit separately. Do not delete them because a new release exists. Do not re-run an old live-destructive E2E test to evaluate this release.

When the current live state is available, create a **new, separate** snapshot with v2, verify it and rehearse it. This is safer than treating a format conversion as proof that all old data was present. An offline legacy importer with clear verification limits is a roadmap item, not an implemented promise.

If only an old archive exists, preserve it and follow its original documented restoration procedure carefully. This public candidate is not a replacement recovery path for an unsupported legacy format.
