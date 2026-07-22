# Combined Governed Operations

## Purpose

The repository-native governed executor supports closed operations that combine
steps which otherwise require several reviewed successor operations. Combined
operations do not weaken authorization, validation, or read-after-write
verification. They package a fixed sequence into one declarative request and one
non-overwriting result artifact.

## Development-session initialization

Executor 0.8.2 accepts the operation type
`development-session-initialize`.

The operation combines:

1. repository and remote-main refresh and verification;
2. confirmation that the governing issue is open;
3. creation and read-back verification of exactly one designated detailed-scope
   comment;
4. creation and read-back verification of exactly one designated work-breakdown
   and patch-plan comment; and
5. creation of the issue branch from the accepted fetched `main` revision.

The operation requires a clean starting checkout and exact authorization for
repository interrogation, local branch mutation, and issue comments. It rejects
an existing target branch, duplicate designated comments, a moved remote base,
non-fast-forward local `main`, malformed planning headings, and authorization
broader than the closed sequence.

The required planning headings are:

```text
## Governed detailed scope
## Governed work breakdown and patch plan
```

Standalone repository initialization, issue-comment, and branch-creation
operations remain available for recovery, correction, or work that does not
satisfy the combined operation's preconditions.

## Combined Git publication

Executor 0.8.2 accepts the operation type `git-publication`.

The operation combines:

1. exact-path staging into an initially empty index;
2. commit creation and verification;
3. branch push and remote commit verification; and
4. pull-request creation and read-back verification.

The operation requires reviewed working-tree changes (`guards.clean=false`), an
empty index before governed staging, exact authorization for interrogation,
stage, commit, push, and pull-request creation, and a previously returned
governed validation result for the same branch and parent `HEAD`.

A separately executed staging operation makes the index non-empty and therefore
makes the combined publication operation ineligible. In that recovery state,
use the standalone commit, push, and pull-request operations instead of silently
resetting the index.

## Dispatcher and compatibility

`scripts/governed-execute` routes the two combined operation types under executor
version 0.8.2. It continues to delegate legacy 0.7.0 operation descriptions to
the package executor so existing standalone operations remain usable.

Combined operations remain subject to the official governed development process:
every result must be reviewed before a successor operation assumes success, and
partial or failed execution requires a new operation identity based on observed
evidence.
