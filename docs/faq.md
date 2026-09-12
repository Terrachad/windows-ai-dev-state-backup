# Frequently asked questions

### Does this back up my code repositories?

It does not scan arbitrary project folders. Full assistant-owned state may still
contain worktrees, code snippets, hooks, commands, uploads or cached files.
Treat every snapshot as sensitive. See [scope](scope.md).

### Will cached authentication tokens keep working?

Local files in selected state are preserved. Credential-store keys, expired or
revoked tokens, and server-side caches are not made portable by copying files.
Expect to authenticate again. This tool does not bypass login or MFA.

### Can I restore under a different Windows username?

Default destinations use the current account. Custom homes require current
configuration or an explicit mapping. Paths embedded inside conversations or
configuration are not automatically rewritten. See [restore](restore.md).

### Is it still just four BAT files?

No. This public candidate keeps BAT entry points but requires Python 3.11+ and
the adjacent `devstate.py`/`src/` engine. Extract the complete runtime package.
This makes the code readable and testable instead of hiding it in encoded BATs.

### Does a successful rehearsal prove my chats will resume?

It demonstrates that the file restore engine works for that snapshot in isolated
targets. It does not establish application-version compatibility, login validity
or permission behavior after every possible reinstall.

### Why not make it automatically delete old recovery copies?

Preserved originals are a recovery option. The runtime deliberately has no
recursive cleanup operation. Verify your real applications and keep a separate
backup before making your own retention decisions.

### Can I use my earlier V8 backup with this release?

Not automatically. The public candidate uses a new format. Keep the private
working backup and tool; follow [migration](migration.md). An importer is planned,
not implemented.
