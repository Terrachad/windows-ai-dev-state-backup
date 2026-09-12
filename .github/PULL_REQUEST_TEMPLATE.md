## What changed, and why?

## Validation

Exact commands, environment and results. Distinguish synthetic tests from actual application tests.

## Safety review

- [ ] No real backup, credential, transcript, private path or runtime journal is included.
- [ ] Tests use synthetic fixtures only.
- [ ] New failure paths retain original data and recovery artifacts.
- [ ] Default restore remains a no-write dry run.
- [ ] No secret, source directory or live state is accessed by CI.
- [ ] Public claims and the publication allowlist match the change.

## Limitations / follow-up
