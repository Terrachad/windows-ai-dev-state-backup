# Limitations and threat model

This release candidate is intended for the current user's local Windows development state. It is not a system-image utility, managed enterprise backup agent, forensic preservation tool, credential-vault exporter, ransomware protection service, or atomic database snapshotter.

## Supported contract

- Windows live discovery; Python 3.11+ and local NTFS paths are required by the documented workflow.
- Standard-library engine, BAT entry points, ZIP/ZIP64 archives and SHA-256 checks.
- Exact included file content and directory sets, including empty directories and zero-byte files.
- Unencrypted output protected by local directory permissions where supported.
- Explicit current-user destinations; unexpected links and overlapping restore paths are rejected.

## Not guaranteed

Successful login, uninterrupted token validity, restoration of server-side prompt caches, recovery of cloud-only conversations, compatibility with future application database schemas, and automatic path rewriting are not guaranteed. An isolated rehearsal is a data-path test, not a fresh-Windows or authenticated application test.

Applications must be stopped. Before/after hashes and change checks catch many concurrent writes but do not provide a consistent point-in-time snapshot across independent files. Do not run another restore, manually change work directories or allow an adversarial local process to replace files while this tool is operating. Symbolic-link checks are a fail-closed guard, not a sandbox against an attacker with equal access to the filesystem.

The journal provides best-effort recovery across a multi-target restore. Power loss, disk failure or another writer can require manual recovery. No program can infer unrecorded state after a crash merely from the existence of a destination folder.

## Deliberate restrictions

UNC/network paths, device paths, arbitrary reparse trees, symlink reconstruction, sockets, NTFS alternate streams, original ownership/ACL metadata and EFS metadata are outside the contract. Metadata documents are capped at 64 MiB; normal file payloads have no configured time limit or small-file cap. This cap is a parser resource bound, not an arbitrary deadline that kills a large copy.

The new format is not automatically compatible with the historical V8 self-extracting scripts. See [migration.md](migration.md). A checked-in report means only the tests named in that report ran; it is not a broad Windows compatibility certificate.

## Backup authenticity

A checksum sidecar and a manifest can both be edited by somebody with access to the backup. They detect accidental corruption, not malicious replacement by that person. Obtain release files from a trusted source, review them, and only restore snapshots you trust. Restored settings may contain hooks or executable commands that apps run on startup.

## No silent escalation

The runtime does not elevate, change machine-wide execution policies, kill apps, uninstall apps, run login flows, or silently restore a different user's profile. Do not use administrator rights as a workaround for selecting the wrong source account.
