# Exactly what is and is not preserved

The implementation's source of truth is `src/aidbackup/providers.py`. The manifest records every selected component, included file, empty directory and allowed exclusion.

| Group | Locations | Restore behavior |
| --- | --- | --- |
| Agent, default | `CLAUDE_CONFIG_DIR` or `%USERPROFILE%\.claude`; `.claude.json`; `.claude.json.backup` | Automatic for selected components, with verification |
| Agent, default | `CODEX_HOME` or `%USERPROFILE%\.codex` | Automatic for selected components, with verification |
| Developer, opt-in | `.ssh`, `.gitconfig`, `.git-credentials`, Git configuration under the XDG config directory | Automatic; review signing/credential paths afterward |
| Developer, opt-in | GitHub CLI configuration, `GH_CONFIG_DIR`, `.config\gh` | Automatic; OS credential vaults are not exported |
| Developer, opt-in | `.npmrc`, `.yarnrc`, `.yarnrc.yml`, `.wslconfig` | File data only |
| Developer, opt-in | `.docker`, `.aws`, `.azure`, `.kube`, Google Cloud config | Configuration/state files, not containers, volumes or cloud resources |
| Developer, opt-in | GnuPG homes (`GNUPGHOME`, roaming `gnupg`, `.gnupg`) | Regular files only; smartcards and agents are not exported |
| Developer, opt-in | PowerShell profiles in the Windows Documents Known Folder | Automatic; referenced external scripts are not followed |
| Developer, opt-in | `%APPDATA%\Code\User`, `%APPDATA%\Cursor\User` | User data, not installed extensions or external workspaces |
| Desktop, opt-in | Roaming Claude/ChatGPT/Codex/OpenAI data; selected matching MSIX package `LocalState`, `RoamingState`, `LocalCache`, `Settings` | **Manual-only reference**; app-version compatibility and credential portability are not guaranteed |

## Important gaps

No source-code/project roots are scanned. Project files, project-level `.claude`/`.mcp.json`, `.git`, `.env`, Git LFS contents and uncommitted work in external repositories need their own backup. Conversely, full agent-state directories may themselves contain worktrees, attachments or cached code. Review their size and sensitivity.

The following are not preserved automatically: WSL Linux homes/distributions; Windows Credential Manager; DPAPI master keys; hardware-backed secrets; running Docker/WSL VMs; cloud-only conversations; remote API prompt caches; environment variable values; system registry configuration; application installers; signing certificates/private keys outside the selected paths; SSH `Include` or Git `include.path` targets outside the selected folders; external memory/MCP helper locations.

This release recognizes the documented primary agent home variables and selected developer home overrides. It does not claim to interpret every tool-specific configuration override, Kubernetes referenced certificate path, Git conditional include, or AWS shared-credentials location. Additions need tests and explicit coverage documentation before support is claimed.

## Filesystem contract

The verification contract is file content, relative path and empty-directory membership. Last-write times are copied on file copies where supported, but are not part of the integrity promise. ACLs, ownership, creation times, NTFS alternate data streams, EFS metadata, sparse-file allocation and hardlink relationships are not preserved as original metadata.

Unexpected links/reparse points, junctions, sockets and non-regular files fail closed. The only special case is an actual Claude `debug/latest` or `debug/latest.txt` reparse point, which is recorded as an excluded debug pointer. A regular file with either name is **not** excluded. OneDrive placeholders/reparse-based data must be moved or backed up through a supported hydrated, regular-file location instead.

Backups and rehearsal copies are unencrypted. Restricted directory permissions reduce local exposure but are not disk encryption.

## Sessions and login are different

Claude transcripts and related state are copied as files, not interpreted or rewritten. Codex file-based credentials are included when inside its selected state; credentials stored only in an OS keyring are not. Applications may require login again and may migrate databases on first start. A SHA-256 match does not guarantee a successful session resume in every future version.

[Official documentation references](references.md).
