# Publishing and release procedure

## 1. Publish source from a clean directory

Extract the **source** ZIP into a new directory separate from any real backups.
The runtime ZIP intentionally omits maintainer scripts and CI.

Install Git and the official GitHub CLI, then authenticate locally with
`gh auth login`. Configure your own Git author name/email. No script asks you to
paste a personal access token into a file or chat.

Preview (replace the owner placeholder with your account or organization):

```powershell
py -3 scripts/publish.py --repo YOUR-OWNER/windows-ai-dev-state-backup --public --seed-issues
```

This is a dry run: it does not initialize Git, commit, create a repository or upload.

After reviewing the planned visibility and author:

```powershell
py -3 scripts/publish.py --repo YOUR-OWNER/windows-ai-dev-state-backup --public --seed-issues --apply
```

Type the exact `OWNER/REPOSITORY` identifier when prompted. The helper:

- refuses existing Git history and directories that contain recognizable live backup state;
- stages only files in `release/publish-files.json`, not `git add .`;
- creates a new `main` repository and pushes the allowlisted initial source;
- sets the description/topics, issues/discussions, squash merge and labels;
- requests secret scanning, push protection and private vulnerability reporting;
- optionally opens the bounded, honest initial roadmap issues.

If a setting fails because of permissions or account policy, it is reported as
not applied. Do not assume the entire run was atomic. Inspect completed actions
before retrying. For an already published repository, use normal reviewed Git
commits and `scripts/configure_github.py --repo OWNER/REPO` instead; that helper is
also dry-run by default.

## 2. Finish repository setup

Upload `assets/social-preview.png` under Settings → General → Social preview.
Check the actual description/topics, Security tab, labels and Discussions.
Enable a branch rule/ruleset for `main`: pull requests, resolved conversations,
required `required` CI check, no force pushes and no branch deletion. A solo
maintainer should choose review rules they can actually satisfy; do not invent
an unavailable second reviewer or lock out maintenance.

The package does not install a fake CODEOWNERS owner. Add the real maintainer/team
only after the GitHub owner is known. Choose notification/support responsibilities.
Set the actual repository URL in `release/project.json` in a reviewed follow-up
commit. No OWNER-based broken badges or fake homepage are shipped.

## 3. Validate the exact commit

Review [validation](validation.md). Check every matrix job, not just the final
badge. Investigate native Windows skips and all failures before announcing.
Perform the disposable-profile manual application test separately.
Never upload actual backups as Actions artifacts; the workflows upload only
sanitized reports created by synthetic tests.

## 4. Build and draft a candidate

Local reproducible builds:

```powershell
py -3 scripts/run_tests.py
py -3 scripts/check_repository.py
py -3 scripts/build_release.py --output dist
py -3 scripts/build_release.py --output dist --source
```

Both ZIPs have SHA-256 sidecars. Builds use the reviewed publication allowlist,
fixed ZIP entry timestamps and deterministic file ordering. This is not a digital
signature or a claim of reproducibility across every zlib version.

In GitHub Actions, run **Draft release candidate** from `main`. It reruns Windows
validation, then builds both assets and creates a draft prerelease at the exact
workflow commit. It does not silently mark a stable/latest release. Existing tags
or releases should be inspected; the helper does not replace uploaded assets.

Review the draft notes, assets and checksums. Publish the candidate only when the
native validation is green and the limitations are visible. Announce stable only
after completing the separate stable-release gate.

## 5. Maintain it

Review Dependabot's SHA-pinned Action updates. Triage reproducible safety failures
before adding providers. Update the changelog, coverage table and tests together.
Keep runtime dependencies zero unless a reviewed change justifies a new trust
boundary. Track validation results by exact commit, not by a floating "latest" claim.

For launch copy, see [discovery and launch](discovery-and-launch.md).
