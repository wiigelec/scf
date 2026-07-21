# Independent governed Git lifecycle operations

Issue #41 decomposes the Git publication lifecycle into separately authorized
operations while retaining `git-publication` for compatibility.

## Authorization boundary

Each independent operation accepts only its own capability plus repository
interrogation:

| Operation | Required authorization | Forbidden lifecycle authorization |
| --- | --- | --- |
| `git-stage` | `interrogate`, `stage` | `commit`, `push`, `pull_request` |
| `git-commit` | `interrogate`, `commit` | `stage`, `push`, `pull_request` |
| `git-push` | `interrogate`, `push` | `stage`, `commit`, `pull_request` |
| `pull-request-create` | `interrogate`, `pull_request` | `stage`, `commit`, `push` |

Unused authorization is rejected. No operation may infer permission for a
later or earlier lifecycle phase.

## `git-stage`

`git-stage` stages an exact, sorted, unique list of repository-relative paths.

Preconditions:

- the branch and `HEAD` match the guards;
- there are no unmerged paths;
- the index is empty before staging.

Postconditions:

- the staged path set exactly equals the authorized path set;
- `git diff --cached --check` passes;
- no commit or remote mutation occurs.

## `git-commit`

`git-commit` creates one commit from an already staged index.

Preconditions:

- the branch and parent `HEAD` match the guards;
- the staged path set exactly equals `expected_mutations.paths`;
- staged content passes `git diff --cached --check`.

Postconditions:

- the new commit has the expected parent;
- its committed path set exactly equals the authorized path set;
- no staging expansion, push, or pull-request mutation occurs.

## `git-push`

`git-push` publishes an already committed, clean `HEAD`.

Preconditions:

- the repository is clean;
- the current branch is attached;
- branch and `HEAD` match the guards;
- an existing destination branch, when present, is a fast-forward ancestor.

The executor pushes exactly:

```text
HEAD:refs/heads/<authorized-branch>
```

It then reads the remote branch and requires it to resolve to the guarded
commit. The operation performs no staging and creates no commit.

## `pull-request-create`

`pull-request-create` creates a pull request only after the authorized remote
head branch resolves to the exact expected commit.

Preconditions:

- the remote head branch resolves to `expected_mutations.head_sha`;
- no open pull request already exists for the same base and head.

The executor verifies the created pull request's base, head, head commit,
title, body, draft state, and open state.

## Compatibility operation

`git-publication` remains available for callers that deliberately authorize a
combined stage-and-commit flow and optional push. Its compatibility does not
weaken the independent contracts: callers needing only one lifecycle phase
must use the corresponding independent operation.

## Result interpretation

- `local-mutation-completed`: staging completed.
- `commit-completed`: an independent commit completed.
- `publication-completed`: push or pull-request creation completed.
- `guard-failed`: no mutation was attempted.
- `partial-local-mutation`: a local lifecycle mutation may be incomplete.
- `partial-remote-mutation`: a remote lifecycle mutation may be incomplete.

Every result records command evidence, starting and ending repository state,
the exact lifecycle evidence, and whether mutation was authorized, attempted,
observed, and completed.
