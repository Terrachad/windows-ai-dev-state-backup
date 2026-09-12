# Roadmap

Status labels describe plans, not shipping promises or dates.

## Release gate: v2.0.0 stable

- [ ] Windows Server 2022/2025 CI matrix passes on Python 3.11 and 3.14.
- [ ] Windows 11 client manual validation: NTFS, long paths, changed username and current app session resume.
- [ ] Windows 10 client compatibility validation or a narrower advertised support statement.
- [ ] Independent review of restore/rollback, archive parsing and private output permissions.
- [ ] Publish reproducible test evidence and release asset hashes.
- [ ] Enable repository security features and protect the `required` check.

## Next candidates

- [ ] Offline, read-only inspection and explicit migration of legacy V8 snapshots.
- [ ] Granular provider selection and external configuration-path reporting.
- [ ] A reviewed encryption workflow that never exposes passphrases in command lines or logs.
- [ ] Signed/attested release assets after an actual signing/provenance workflow is established.
- [ ] Read-only recovery-journal inspector with no automatic destructive actions.
- [ ] Better very-large-file progress without sacrificing integrity checks.

## Deliberately not planned for the initial release

Automatic Windows reinstallation, partitioning, automatic app login, OS credential-vault export, uploading backups to arbitrary cloud services, running apps' hooks, or destructively testing real user profiles.

Feature requests must state their data scope, threat model, verification behavior and effect on existing backups. “More automatic” is not automatically safer.
