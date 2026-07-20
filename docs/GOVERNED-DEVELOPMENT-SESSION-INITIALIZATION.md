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
- **remote-oriented**: the chatbot may use read-only remote access to identify the
  repository, accepted process, governing issue, planning records, pull request,
  and likely next bounded action;
- **local-state explicit**: the actual local Git tree is interrogated before local
  mutation, and unknown local state is never inferred from GitHub;
- **script-transported**: every governed local or remote mutation is performed
  through a uniquely named, guarded, agent-developed Python script;
- **user-executed**: the user runs the supplied script from the repository root;
- **result-returned**: each script execution produces exactly one uniquely named
  result file in `~/Downloads`, which the user uploads to the chatbot;
- **bounded**: each script declares and enforces its operation, repository,
  revision, file, and publication boundaries;
- **non-overwriting**: scripts and result artifacts use unique names and are never
  silently overwritten;
- **observable**: scripts print immediate, flushed progress and periodic heartbeat
  messages during long-running work;
- **review-gated**: no successor operation assumes a prior script succeeded until
  the returned result has been reviewed;
- **authorization-separated**: interrogation, mutation, validation, commit, push,
  pull-request, issue, review, merge, and closure permissions remain distinct.

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

The first local interaction for a new or uncertain checkout is a read-only
guarded interrogation script.

The interrogation must establish, when applicable:

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
explicitly understood and included in the preconditions of the next script.

Interrogation performs no local or remote mutation.

## Prospective governed-executor transition

Upon acceptance and merge of Issue #31, `scripts/governed-execute` and a
declarative governed operation description become the default execution boundary
for operation classes implemented by the accepted executor. The executor owns
guard evaluation, command construction, supervision, redaction, mutation
accounting, result generation, overwrite refusal, and local or remote
postcondition verification.

The operation description is data, not executable source. It may select only an
executor-recognized operation type and bounded inputs. It may not supply
free-form shell, interpreter snippets, replacement command allowlists, disabled
guards, suppressed evidence, or expanded authorization.

The user runs one repository-native command:

```sh
./scripts/governed-execute /path/to/<unique-operation>.json
```

The result destination is declared by the operation, must be outside the
repository, and must already exist. The executor refuses to overwrite an
existing result. A bootstrap wrapper may only locate and verify the accepted
executor and invoke it; it may not reimplement executor mechanics.

Unsupported operation classes remain blocked unless an explicit governed
transition exception authorizes the legacy protocol. There is no silent fallback
from an unsupported declarative operation to unrestricted script execution.

## Legacy guarded-script protocol and historical work

The guarded agent-developed Python script remains the controlling execution
boundary until Issue #31 is accepted and merged. It also remains valid historical
evidence for work properly performed under Issue #24 and may continue to govern
already-open work unless that work is explicitly migrated.

The chatbot:

1. designs one bounded operation;
2. creates a uniquely named Python script for download;
3. supplies exactly one literal command block;
4. reviews the returned result before preparing another script.

The user:

1. retains the script in `~/Downloads`;
2. starts from the repository root;
3. runs the single supplied command;
4. observes terminal progress;
5. uploads the script's single result file to the chatbot;
6. does not rerun or improvise recovery after a failure unless directed through
   a separately identified script.

The script invokes standard `git`, `gh`, Python, and repository-native commands
as needed. The transport protocol is not a replacement for Git or GitHub; it is
the controlled interaction boundary through which those tools are used.

## User-facing command contract

The user-facing command is exactly one literal command of the form:

```sh
python ~/Downloads/<unique-script-name>.py
```

The command:

- is run while the shell is already at the repository root;
- contains no `cd`;
- contains no shell variable assignment or expansion;
- contains no heredoc;
- contains no command substitution;
- contains no pipe, redirection, semicolon, `&&`, or other chained operation;
- is safe to copy directly into `zsh`.

Every script filename must be unique within the development workflow. A
replacement or corrected script receives a new filename even when the earlier
script was never run.

## Script guard contract

Before mutation, a script verifies all preconditions material to its operation,
which may include:

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
- explicit inclusion or exclusion of commit, push, issue, pull-request, review,
  merge, and closure actions.

A guard failure stops before the guarded mutation. The script records the
observed state and required correction in its result artifact.

## Mutation boundary

Each script declares:

- governing issue;
- operation identifier;
- expected starting state;
- intended local file or Git-object boundary;
- intended remote-object boundary;
- commands it may invoke;
- validations it will run;
- whether it may stage, commit, fetch, switch branches, push, create or update a
  pull request, edit an issue, review, merge, or close;
- intended terminal state.

Permission for one boundary does not imply permission for another. In
particular, permission to edit does not imply permission to commit, and
permission to commit does not imply permission to push.

## Terminal progress and heartbeat

Terminal output is the user-facing execution display.

A script must:

- identify itself and its intended operation immediately;
- print numbered or otherwise clear phases;
- print meaningful progress before and after each material step;
- flush each progress message immediately;
- report the observed state relevant to guard decisions;
- print periodic heartbeat messages during long-running subprocesses;
- clearly distinguish success, guard failure, failure before mutation, partial
  application, and validation failure after mutation;
- end with the exact result-file path and an instruction to upload it.

Heartbeat output must not replace captured command output in the result file.
A supervisory loop may capture subprocess stdout and stderr while printing
elapsed-time messages to the terminal.

## Single result artifact

Each script execution produces exactly one uniquely named result file in
`~/Downloads`.

The result filename is derived from the unique script filename, for example:

```text
scf_issue_24_patch_1_20260720T120000Z_a1b2c3.result.json
```

The script must refuse to overwrite an existing result file. It must not create
separate log, patch, transcript, or diagnostic artifacts.

The single result file contains enough structured evidence to determine:

- schema version;
- script filename, digest, and operation;
- repository root and remote identity;
- starting and ending branch, `HEAD`, upstream, and worktree state;
- intended and observed local and remote mutation boundaries;
- commands, start and finish times, exit codes, stdout, and stderr;
- files or remote objects created, changed, deleted, or left unexpected;
- validation commands and outcomes;
- commit, push, issue, pull-request, review, merge, and closure attempts and
  verified results;
- diagnostics;
- whether mutation was attempted and completed;
- the safest next interaction.

Credentials and authentication secrets must not be copied into the result.
Where a command emits credentials or sensitive tokens, the script must redact
them before writing the result.

## Execution-state distinctions

At minimum, a result distinguishes:

- `guard-failed`: a required precondition failed before mutation;
- `failed-before-mutation`: execution failed before the guarded mutation began;
- `partial-local-mutation`: local state may have changed before failure;
- `partial-remote-mutation`: one or more remote mutations completed before
  failure;
- `mutation-completed-validation-failed`: intended mutation completed but
  required validation did not pass;
- `completed`: the intended non-commit operation and its verification completed;
- `completed-and-committed`: the intended commit was created and verified;
- `completed-and-published`: the intended remote publication was completed and
  verified.

A failed or partial attempt, recovery script, correction script, and later
successful attempt remain separately identifiable. A later success does not
erase earlier execution evidence.

## Validation and inspection

After a bounded file mutation, the script normally captures:

- `git status --short`;
- changed-file inventory;
- `git diff --check`;
- diff statistics and relevant diff content;
- focused tests;
- required repository validation.

Unexpected changed paths or failed required checks prevent an included commit
unless the governing plan explicitly defines another safe terminal state.

Long validation runs must provide heartbeat output. Complete command output is
stored in the one result artifact.

## Commit, push, and remote GitHub operations

Commit, push, and remote GitHub mutations use the same transport protocol.

A commit script verifies the exact reviewed changed-file boundary, validation
state, starting `HEAD`, planned commit subject, and absence of unrelated
changes. It stages only intended paths, creates the commit, records the exact
SHA, and verifies the post-commit tree.

A publication script verifies the exact reviewed branch head, worktree,
remote, upstream, validation evidence, and explicit publication authority. It
uses standard `git` commands to push and standard `gh` commands for issue,
pull-request, review, merge, and closure operations.

Remote success is verified by reading the resulting remote object. Command exit
status alone is not sufficient verification.

## Failure and recovery behavior

A script must attempt to write its single result file even when execution
fails, provided doing so is safe.

Automatic retry must not conceal deterministic failure. A failed mutation is
not silently retried until it appears successful.

When partial application is possible, terminal output must instruct the user
not to rerun the script. The chatbot reviews the returned result and prepares a
new uniquely named recovery script with guards based on the observed state.

Manual correction by the user is outside the standard governed mutation path
unless the governing plan explicitly authorizes instruction-only work.

## Evidence and authority boundary

The script and result artifact are transient execution evidence. They are not
accepted repository authority, durable planning records, or proof of semantic
acceptance.

Git and GitHub retain their normal roles:

- accepted authority and process live in accepted repository revisions;
- issue bodies and designated comments govern scope and plans;
- commits and pull requests provide implementation evidence;
- repository validation and CI provide mechanical evidence;
- review and explicit acceptance provide semantic evidence;
- merge and issue closure remain separate lifecycle facts.

A local commit remains local-only until its exact SHA is remotely resolvable.
A result artifact may report a remote mutation, but the chatbot should verify
important remote state through read-only access when available.

## Success boundary

This standard is satisfied when a new independent chatbot-user session can:

1. orient itself to the bounded remote work from durable evidence;
2. interrogate the actual local checkout without mutation;
3. route every governed local and remote mutation through one unique guarded
   Python script;
4. give the user one literal command run from the repository root;
5. provide clear terminal progress and heartbeat output;
6. receive exactly one unique non-overwriting result file;
7. distinguish failure, partial application, validation, commit, and publication
   states;
8. review the returned evidence before authorizing or designing the next
   operation;
9. proceed without relying on prior chat history or inventing unknown local
   state.
