# References and upstream assumptions

Reviewed on 2026-09-12. Paths and authentication behavior can change upstream; add a fixture and update the coverage documentation when supporting a new layout.

## Agent and Windows behavior

- [Claude Code: manage sessions](https://code.claude.com/docs/en/sessions) — JSONL transcripts, directory selection, retention and session resume behavior.
- [Claude Code: user configuration directory](https://code.claude.com/docs/en/claude-directory) — Windows `.claude` location, `CLAUDE_CONFIG_DIR`, and global `.claude.json` state.
- [OpenAI Codex authentication](https://developers.openai.com/codex/auth) — file/keyring/auto/ephemeral credentials, `CODEX_HOME`, `auth.json`, and sensitivity of cached tokens. Follow any official redirect.
- [Windows maximum path length](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation) — extended-length paths and legacy path behavior.
- [Python on Windows](https://docs.python.org/3/using/windows.html) — official runtime/launcher installation and automatic-install controls.
- [Python zipfile](https://docs.python.org/3/library/zipfile.html) — ZIP64, archive member metadata and streamed archive access.

## Repository operation

- [GitHub topics](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics) — accurate topic metadata helps repositories be discovered; at most 20 topics.
- [GitHub social preview](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview) — manual upload of the supplied social card.
- [Secure use of GitHub Actions](https://docs.github.com/en/actions/reference/security/secure-use) — minimum token permissions and immutable action references.
- [GitHub CLI repository creation](https://cli.github.com/manual/gh_repo_create), [repository settings](https://cli.github.com/manual/gh_repo_edit), and [releases](https://cli.github.com/manual/gh_release_create).
- [GitHub secret scanning](https://docs.github.com/en/code-security/how-tos/secure-your-secrets/detect-secret-leaks/enable-secret-scanning) and [push protection](https://docs.github.com/en/code-security/how-tos/secure-your-secrets/prevent-future-leaks/enable-push-protection).

The project's own test report and source code, not these links, are the evidence for its implementation-specific claims.
