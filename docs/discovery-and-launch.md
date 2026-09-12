# Discovery and launch plan

## Positioning

**Display name:** AI Dev State Backup

**Repository slug:** `windows-ai-dev-state-backup`

**One-sentence promise:** Back up Claude Code and Codex state before a Windows reinstall, then verify and rehearse a restore without testing on live data.

The name prioritizes the terms a developer is likely to search for over an
unrelated brand word. The README introduction naturally includes Windows,
Claude Code, Codex, backup, restore, Git/SSH and local chat history. Do not stuff
those terms into every heading.

The exact About description and 16 scoped topics are maintained in
`release/project.json` and applied by `scripts/configure_github.py`. Topics are
metadata, not a ranking or star guarantee. Do not tag unrelated ecosystems.

## Before announcing

- Complete native Windows CI and the documented release gates.
- Publish a clearly labelled candidate with assets, checksum files and readable notes.
- Upload the social preview, enable Discussions and verify private vulnerability reporting.
- Keep the quick start near the top, explain Python and NTFS requirements, and keep warnings prominent.
- Create the scoped initial issues, not fake usage reports or artificial activity.

Do not claim a count of users/stars, independent auditing, official endorsement,
zero risk or universal compatibility. Do not buy stars, mass-message users or
cross-post the same text into unrelated communities.

## GitHub release / Discussion draft

**Title:** Introducing AI Dev State Backup: Claude Code and Codex snapshots for Windows

> I built a local backup tool after migrating a Windows development environment.
> It preserves supported Claude Code/Codex state, verifies included files with
> SHA-256, and rehearses restoration in a separate folder rather than moving live
> agent directories out of the way.
>
> The public build is a safety-focused rewrite with small BAT launchers and a
> Python 3.11+ standard-library engine. Optional Git/SSH and developer config is
> opt-in. Output is unencrypted and may contain tokens or private keys.
>
> This is a release candidate. The validation page separates executed tests from
> what still needs checking; sign-in and session-resume behavior are not guaranteed
> by a checksum. I am looking for synthetic Windows compatibility reports and
> review of the recovery paths before a stable release.
>
> The README has the quick start, exact scope and limitations. A useful bug report
> or safety review is especially welcome. Star it to find it again when you plan
> your next reinstall.

Replace any claim about passing Windows tests with the exact current evidence
before posting. Add the real repository/release URL only after publication.

## Short announcement draft

> Moving Windows installs and worried about your local Claude Code/Codex state?
> AI Dev State Backup snapshots supported state, verifies every included file and
> rehearses restores in an isolated folder. BAT entry points, Python 3.11+, MIT.
> Release candidate; unencrypted output and clear limitations. Looking for
> synthetic Windows testing and safety review—not production-data uploads.

## Where to share

Start with a release Discussion and a short, genuine migration write-up on your
own developer profile. Share with relevant Claude Code/Codex or Windows developer
communities only where their current self-promotion rules allow it. Demonstrate
with synthetic data; avoid real screenshots of paths, accounts and transcripts.
Answer questions before reposting elsewhere.

## Useful signals after launch

Watch reproducible issue quality, download failures, successful synthetic
compatibility reports, README questions and recovery problems. Stars and views
can indicate interest, but they do not demonstrate safety or retention. Do not
collect telemetry from backup contents. Keep user support private when it could
expose credentials.

## Future improvements

A short synthetic-data demo recording, an independently reviewed Windows test
report and a validated legacy importer will build more durable trust than a large
set of decorative badges. Encryption, signed releases and additional providers
belong on the roadmap until they are implemented and tested.
