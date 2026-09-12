# Security policy

## Do not publish backup contents

Generated snapshots, ZIPs, rehearsal copies and recovery holds can contain authentication tokens, SSH private keys, cloud credentials, confidential conversations, cached code, executable hooks and sensitive configuration. Recovery journals and manifests can expose usernames, project names and paths.

Never attach real backup data to issues or pull requests. Use synthetic fixtures. Git ignore rules and heuristic scans are only additional guards; neither proves the absence of secrets.

## Reporting vulnerabilities

Use this repository's **Security → Report a vulnerability** feature when enabled. If it is unavailable, ask the maintainer to enable private reporting without posting the vulnerability details, private files or credentials publicly. Do not use a feature request or general support issue to disclose an exploit involving data loss or secret exposure.

A useful private report describes affected versions, a minimal synthetic reproduction, expected/actual behavior and the likely impact. No response-time or support SLA is promised.

## Support status

The public v2 line is a release candidate. The historical self-extracting V8/draft-v1 scripts are not part of this release or its safety guarantees. Until the release gate passes, use this candidate only with disposable fixtures or alongside independently verified backups.

## Scope of the safety design

File-data integrity, path validation, preservation of original state and observable restore recovery are in scope. Authentication portability, OS credential vault export, automatic login, protection from a malicious process with equal filesystem access, and complete disk/VM recovery are not. See [limitations](docs/limitations.md).

Checksums are not authentication. The toolkit is not an encryption product. Only restore a snapshot from a source you trust; applications may execute restored hooks or configuration on startup.

## Repository settings for maintainers

Enable private vulnerability reporting, secret scanning and push protection where available. Require the `required` CI check before merging safety changes. Keep workflow token permissions minimal and actions pinned. Do not add production secrets to CI; all tests use generated fixtures.
