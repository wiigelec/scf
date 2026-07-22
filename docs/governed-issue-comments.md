# Governed GitHub issue-comment operations

Issue #37 adds a bounded remote operation for creating or updating one top-level
GitHub issue comment.

## Operation type

```text
issue-comment-mutation
```

Supported actions are `create` and `update`.

The operation requires only `interrogate` and `issue` authorization. Every other
authorization flag must be false.

## Create

Create requires an explicit issue number and the complete intended Markdown
body. `required_heading` may guard a designated planning comment. When supplied,
the body must begin with that exact level-two heading and creation refuses an
existing comment beginning with the same heading.

The executor reads the issue and existing comments before mutation, creates
exactly one comment, reads the resulting comment by immutable numeric identifier,
and verifies the complete body.

## Update

Update requires an explicit numeric comment identifier and complete replacement
body. The executor verifies that the comment belongs to the declared issue.
`expected_body_sha256` may guard the prior body before mutation.

The executor patches exactly that identifier, reads it back, and verifies the
complete replacement body.

## Failure interpretation

A failed local or remote guard produces `guard-failed` without mutation.

When GitHub may have accepted a write but read-after-write verification fails,
the result is `partial-remote-mutation`. Such an operation must not be blindly
retried; the exact issue and comment identifier must first be inspected.

Verified completion uses `publication-completed` and records the repository,
issue, action, comment identifier, URL, author, body, and body digest.

## Security boundary

The executor owns every `gh api` command and runs without a shell. Comment
Markdown is serialized into a temporary JSON payload and is never interpreted as
shell input. The payload file is outside the repository and removed after use.
Command output remains subject to the executor's credential-redaction policy.
