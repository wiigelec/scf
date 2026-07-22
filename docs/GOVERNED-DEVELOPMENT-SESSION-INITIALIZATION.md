# Governed Development Session Initialization and Interaction

## Status, role, and governing parent

This document defines the official initialization and interaction standard for
governed Session Continuity Framework (SCF) development across independent
chatbot-user sessions.

It is a development-process support specification governed by the accepted SCF
authority hierarchy and `docs/OFFICIAL-GOVERNED-DEVELOPMENT-PROCESS.md`. It
applies the bounded planning convention in `docs/GOVERNED-ISSUE-PLANNING.md`.
It does not create product authority, replace durable Git or GitHub evidence,
authorize unrelated work, or collapse distinct authorization boundaries.

Initialization exists so a new session can establish sufficient remote and
local context to continue one bounded work item without relying on prior chat
history or model memory.

## Core properties

A conforming session interaction is:

- **authority-first**: accepted repository authority and durable governed records
  outrank transient conversation context;
- **remote-oriented**: read-only remote access may identify the repository,
  accepted process, governing issue, planning records, pull request, and likely
  next bounded action;
- **local-state explicit**: the actual local Git tree is interrogated before
  local mutation, and unknown local state is never inferred from GitHub;
- **executor-transported**: governed local and remote mutations are performed
  through `scripts/governed-execute` using uniquely named declarative operation
  descriptions;
- **user-executed**: the user runs the supplied executor command from the
  repository root;
- **result-returned**: each operation produces exactly one uniquely named result
  file outside the repository, normally in `~/Downloads`, which the user uploads
  for review;
- **bounded**: each operation declares and enforces its repository, revision,
  authorization, file, validation, and publication boundaries;
- **non-overwriting**: operation and result artifacts use unique names and are
  never silently overwritten;
- **observable**: the executor prints immediate progress and periodic heartbeat
  messages during long-running work;
- **review-gated**: no successor operation assumes a prior operation succeeded
  until its returned result has been reviewed;
- **authorization-separated**: interrogation, mutation, validation, stage,
  commit, push, issue, pull-request, review, merge, and closure permissions
  remain distinct.

## Remote session orientation

Before requesting local mutation, the chatbot should identify the smallest
durable remote context needed for the bounded task:

1. repository identity and purpose;
2. accepted authority root and official development process;
3. governing issue and its high-level scope;
4. exactly one `## Governed detailed scope` comment;
5. exactly one `## Governed work breakdown and patch plan` comment;
6. accepted base and planned working branch;
7. relevant dependency, pull-request, CI, review, merge, and issue state;
8. the next bounded local fact or operation required.

Read-only connector access may be used for orientation and review. Governed
mutation may not be performed through a direct chatbot connector write.

Remote orientation must not claim knowledge of the user's current branch,
`HEAD`, worktree, local commits, untracked files, or local divergence.

## Local-tree initialization

The first local interaction for a new or uncertain checkout is a governed
read-only repository interrogation or initialization operation.

The operation must establish, when applicable:

- repository root and canonical `origin`;
- current branch or detached-HEAD state;
- exact `HEAD`;
- accepted base availability and merge-base relationship;
- configured upstream;
- ahead/behind relationship;
- staged, unstaged, untracked, and conflicted files;
- local commits since the accepted base;
- changed-file and diff summaries;
- remote `main` identity;
- governing issue and designated planning-comment identities;
- blockers to the next planned mutation.

A clean tree is not universally required, but any non-clean state must be
explicitly understood and represented in the guards of the next operation.

Read-only interrogation performs no local or remote mutation. Repository
initialization may perform only the exact local and remote actions authorized by
its operation type and closed contract.

## Governed executor boundary

`scripts/governed-execute` and a declarative governed operation description are
the standard execution boundary for operation classes implemented by the
accepted executor. The executor owns guard evaluation, command construction,
supervision, redaction, mutation accounting, result generation, overwrite
refusal, and local or remote postcondition verification.

The operation description is data, not executable source. It may select only an
executor-recognized operation type and bounded inputs. It may not supply
free-form shell, interpreter snippets, replacement command allowlists, disabled
guards, suppressed evidence, or expanded authorization.

The user runs one repository-native command:

```sh
./scripts/governed-execute ~/Downloads/<unique-operation-name>.operation.json
```

The result destination is declared by the operation, must be outside the
repository, and must already exist. The executor refuses to overwrite an
existing result.

Unsupported operation classes remain blocked. There is no silent fallback from
an unsupported declarative operation to unrestricted script execution.

## Operation guard contract

Before mutation, the executor verifies every material precondition declared by
the operation, which may include:

- repository root and `origin` identity;
- expected branch;
- exact starting `HEAD`;
- accepted base and merge-base relationship;
- expected upstream or remote branch state;
- clean or specifically permitted worktree state;
- expected existing files, content markers, or digests;
- absence of unrelated staged, unstaged, untracked, or conflicted paths;
- uniqueness and nonexistence of target branches, comments, pull requests, or
  other remote objects;
- explicit inclusion or exclusion of validation, stage, commit, push, issue,
  pull-request, review, merge, and closure actions.

A guard failure stops before the guarded mutation. The executor records the
observed state and required correction in its result artifact.

## Mutation boundary

Each operation declares:

- operation identifier and type;
- governing repository and exact expected starting state;
- intended local file or Git-object boundary;
- intended remote-object boundary;
- requested authorization flags;
- validations and publication behavior;
- intended terminal state;
- unique result destination.

Permission for one boundary does not imply permission for another. In
particular, permission to edit does not imply permission to commit, and
permission to commit does not imply permission to push.

## Terminal progress and heartbeat

Terminal output is the user-facing execution display.

The executor must:

- identify its version and operation immediately;
- print numbered or otherwise clear phases;
- print meaningful progress before and after each material step;
- flush progress messages promptly;
- report the observed state relevant to guard decisions;
- print periodic heartbeat messages during long-running subprocesses;
- clearly distinguish success, guard failure, failure before mutation, partial
  local mutation, partial remote mutation, and validation failure;
- end with the exact result-file path and safest next interaction.

Heartbeat output must not replace captured command output in the result file.
A supervisory loop may capture subprocess stdout and stderr while printing
elapsed-time messages to the terminal.

## Single result artifact

Each operation execution produces exactly one uniquely named result file outside
the repository, normally in `~/Downloads`.

The executor must refuse to overwrite an existing result file. It must not
create unplanned log, patch, transcript, or diagnostic artifacts.

The single result file contains enough structured evidence to determine:

- schema and executor versions;
- operation identifier and digest;
- repository root and remote identity;
- starting and ending branch, `HEAD`, upstream, and worktree state;
- intended and observed local and remote mutation boundaries;
- supervised commands, timing, exit codes, stdout, and stderr;
- files or remote objects created, changed, deleted, or left unexpected;
- validation commands and outcomes;
- stage, commit, push, issue, pull-request, review, merge, and closure attempts
  and verified results;
- diagnostics;
- whether mutation was authorized, attempted, observed, and completed;
- the safest next interaction.

Credentials and authentication secrets must not be copied into the result.
Where a command emits credentials or sensitive tokens, the executor must redact
them before writing the result.

## Execution-state distinctions

At minimum, a result distinguishes:

- `guard-failed`: a required precondition failed before mutation;
- `pre-mutation-failed`: execution failed before the guarded mutation began;
- `partial-local-mutation`: local state may have changed before failure;
- `partial-remote-mutation`: one or more remote mutations completed before
  failure;
- `mutation-completed-validation-failed`: intended mutation completed but
  required validation did not pass;
- a completed local mutation;
- completed validation;
- completed commit or publication with read-after-write verification.

A failed or partial attempt, recovery operation, correction operation, and later
successful attempt remain separately identifiable. A later success does not
erase earlier execution evidence.

## Validation and inspection

After a bounded file mutation, successor governed validation normally captures:

- `git status --short`;
- changed-file inventory;
- `git diff --check`;
- diff statistics and relevant diff content;
- focused tests;
- required repository validation.

Unexpected changed paths or failed required checks prevent publication unless
the governing plan explicitly defines another safe terminal state.

Long validation runs must provide heartbeat output. Complete command output is
stored in the one result artifact.

## Commit, push, and remote GitHub operations

Commit, push, and remote GitHub mutations use executor-recognized operation
types with explicit authorization and guards.

A commit operation verifies the exact reviewed changed-file boundary, validation
state, starting `HEAD`, planned commit subject, and absence of unrelated changes.
It stages only intended paths, creates the commit, records the exact SHA, and
verifies the post-commit tree.

A publication operation verifies the exact reviewed branch head, worktree,
remote, upstream, validation evidence, and explicit publication authority. It
uses executor-owned `git` and `gh` commands for the authorized publication
boundary.

Remote success is verified by reading the resulting remote object. Command exit
status alone is not sufficient verification.

## Failure and recovery behavior

The executor must attempt to write its single result file even when execution
fails, provided doing so is safe.

Automatic retry must not conceal deterministic failure. A failed mutation is
not silently retried until it appears successful.

When partial application is possible, terminal output must instruct the user
not to rerun the operation. The returned result is reviewed before a new
uniquely named recovery operation is prepared with guards based on the observed
state.

Manual correction by the user is outside the standard governed mutation path
unless the governing plan explicitly authorizes instruction-only work.

## Evidence and authority boundary

The operation description and result artifact are transient execution evidence.
They are not accepted repository authority, durable planning records, or proof
of semantic acceptance.

Git and GitHub retain their normal roles:

- accepted authority and process live in accepted repository revisions;
- issue bodies and designated comments govern scope and plans;
- commits and pull requests provide implementation evidence;
- repository validation and CI provide mechanical evidence;
- review and explicit acceptance provide semantic evidence;
- merge and issue closure remain separate lifecycle facts.

A local commit remains local-only until its exact SHA is remotely resolvable. A
result artifact may report a remote mutation, but important remote state should
be verified through read-only access when available.

## Success boundary

This standard is satisfied when a new independent chatbot-user session can:

1. orient itself to the bounded remote work from durable evidence;
2. interrogate or initialize the actual local checkout through the governed
   executor;
3. route every governed local and remote mutation through one uniquely named
   declarative operation description;
4. give the user one literal executor command run from the repository root;
5. provide clear terminal progress and heartbeat output;
6. receive exactly one unique non-overwriting result artifact;
7. review that artifact before authorizing any successor operation;
8. preserve distinct validation, commit, push, pull-request, review, merge, and
   closure boundaries;
9. continue safely without prior chat history or model memory.
