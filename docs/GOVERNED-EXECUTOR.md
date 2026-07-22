# Governed Executor

## Status, role, and authority boundary

This document specifies the proposed repository-native governed executor for
Session Continuity Framework development operations.

It is a development-process mechanism governed by the accepted SCF authority
hierarchy, `docs/OFFICIAL-GOVERNED-DEVELOPMENT-PROCESS.md`, the governing issue,
and its designated planning records. It does not create product authority,
semantic acceptance, merge authority, or permission for successor work.

This document specifies the accepted repository-native governed executor and
its declarative operation boundary for supported governed operations.

## Purpose

The governed executor reduces the trusted computing base of transient
agent-generated operation material. Security-critical execution mechanics are
implemented once in versioned, reviewable repository code rather than
reimplemented independently in every operation script.

The executor preserves these boundaries:

- the user explicitly authorizes and executes each operation;
- an operation description grants no capability the executor does not already
  implement;
- local and remote state guards are evaluated before mutation;
- edit, validation, commit, push, issue, pull-request, review, merge, and closure
  permissions remain separate;
- durable Git and GitHub objects remain authoritative evidence;
- every remote mutation is verified by reading the resulting remote object;
- one execution produces one unique, non-overwriting result artifact;
- returned evidence must be reviewed before a successor operation is assumed
  safe.

## Trust model

### Trusted components

The trusted computing base for one execution consists of:

1. the accepted repository revision containing the executor;
2. the executor entrypoint and imported repository modules;
3. the selected executor capability implementation;
4. the versioned operation and result schemas;
5. standard operating-system, Git, GitHub CLI, and repository-native tools
   invoked through executor-owned command construction;
6. the user who reviews the operation description and explicitly runs it.

### Untrusted or non-authoritative inputs

The following are treated as untrusted data:

- the declarative operation description;
- transient chat text;
- prior terminal output not returned in the current result artifact;
- environment values except where explicitly guarded and redacted;
- repository state not independently interrogated by the executor;
- remote state not independently read through the authorized remote tool;
- operation-provided strings that could be interpreted as commands, paths,
  revisions, object identifiers, or output locations.

No untrusted input may redefine executor behavior, schemas, capability
boundaries, guard semantics, redaction policy, result semantics, or verification
requirements.

## Executor identity and versioning

The executor has a semantic version recorded in repository code. Every
operation description declares:

- an operation schema version;
- a unique operation identifier;
- a required executor version or compatible version range;
- an operation-description digest calculated over canonical serialized data.

Unsupported schema versions, incompatible executor versions, duplicate
operation identities, or digest mismatches fail before mutation.

The result records the exact executor version, operation identity, operation
digest, repository revision containing the executor, and result schema version.

## Declarative operation description

An operation description is data, not executable source. It must be accepted
only after strict schema validation.

At minimum, an operation description contains:

- `schema_version`;
- `operation_id`;
- `operation_type`;
- `executor_version`;
- `repository`;
- `guards`;
- `authorization`;
- `inputs`;
- `expected_mutations`;
- `validation`;
- `publication`;
- `result`.

Unknown fields are rejected unless the applicable schema explicitly permits
them. Missing required fields, contradictory fields, unsupported operation
types, and values outside schema constraints fail before mutation.

The operation description must never contain:

- arbitrary shell commands;
- executable Python or another interpreter language;
- `eval`, command substitution, shell pipelines, or redirection syntax intended
  for execution;
- a description-provided command allowlist;
- a request to disable guards, redaction, result capture, heartbeat output, or
  verification;
- a path outside the authorized repository or result boundary;
- credentials or authentication secrets.

## Capability model

Each `operation_type` maps to one executor-owned capability. The executor owns
all privileged command construction and argument ordering.

Initial capability classes are:

- repository interrogation;
- bounded file mutation;
- repository validation;
- staging;
- commit;
- push;
- GitHub issue mutation;
- pull-request mutation;
- review action;
- merge;
- issue closure.

A capability may invoke only commands statically defined by its reviewed
implementation. Operation data may fill validated argument slots but may not
introduce a new executable, subcommand, option, environment override, shell
operator, or additional capability.

Combined operations are permitted only when a dedicated reviewed capability
explicitly composes those steps and the operation description carries each
separate authorization. Permission for one class never implies permission for
another.

## Authorization boundaries

Authorization is explicit, positive, and operation-specific.

The executor distinguishes authorization for:

- read-only interrogation;
- file edit;
- validation;
- staging;
- commit;
- fetch or branch manipulation;
- push;
- issue creation or modification;
- pull-request creation or modification;
- review submission;
- merge;
- issue closure.

An operation description cannot expand its own authorization. Missing,
ambiguous, duplicated, or contradictory authorization fails closed.

A result from one operation is evidence only. It is not implicit authorization
for a successor operation.

## Guard model

Every mutating capability evaluates exact guards before its first mutation.
Applicable guards include:

- repository root;
- canonical origin URL;
- current branch or detached state;
- exact `HEAD` revision;
- accepted base and merge-base relationship;
- configured upstream;
- ahead and behind counts;
- clean, staged, unstaged, untracked, conflicted, or ignored state as required;
- exact path inventory;
- file type, existence, mode, and digest;
- symlink and repository-boundary conditions;
- expected commit topology;
- remote repository identity;
- remote branch revision;
- issue, pull-request, review, merge, or closure object identity and expected
  state.

Guards are conjunctive unless a capability specification explicitly defines a
different closed set. A guard omitted from the operation description is not
silently inferred from remote state, chat history, or a prior result.

Guard failure produces a result without attempting mutation.

## Path and file boundaries

All repository paths are normalized relative paths rooted in the verified
repository. Absolute paths, parent traversal, NUL bytes, platform-specific
escape forms, and paths resolving outside the repository are rejected.

Symlinks are not followed for governed file mutation. A path component that is
a symlink fails the operation unless a future capability explicitly defines a
narrow, reviewed symlink behavior.

Bounded file mutation uses executor-owned forms such as:

- create a complete file at an absent guarded path;
- replace a complete file whose current digest matches;
- apply a unified patch to an exact guarded source digest;
- delete an exact guarded regular file.

Operation descriptions may not edit the executor, schemas, or operation file
being used unless the governing capability explicitly supports an isolated
self-update protocol with independent verification. The initial executor
provides no self-update capability.

## Command supervision

Commands are executed without a shell unless a reviewed repository-native
command specifically requires one. The executor records:

- executable and redacted arguments;
- working directory;
- start and finish timestamps;
- exit status or signal;
- elapsed time;
- redacted stdout and stderr;
- timeout, interruption, or supervision diagnostics.

The executor provides immediate flushed progress before long-running work and
periodic heartbeat output while a supervised command remains active.

Deterministic failure is not hidden through automatic retry. A capability may
retry only a documented transient read operation under a fixed bounded policy,
and the result must preserve every attempt.

## Mutation accounting and result states

The executor records mutation intent and observed application separately.

Every result has exactly one terminal status from this closed set:

- `guard-failed`;
- `pre-mutation-failed`;
- `partial-local-mutation`;
- `partial-remote-mutation`;
- `post-mutation-validation-failed`;
- `local-mutation-completed`;
- `commit-completed`;
- `publication-completed`.

The result also records per-step state, including whether mutation was
authorized, attempted, observed, completed, rolled back, or left unresolved.

A later validation failure does not erase a completed mutation. A successful
local command does not establish remote publication. A successful remote write
does not establish publication until read-after-write verification succeeds.

## Remote mutation and verification

Remote capabilities identify the exact repository, object type, object
identity, expected starting state, requested change, and expected resulting
state.

The executor performs remote mutation through an executor-owned `gh` command or
a future reviewed repository-native integration. After mutation it must read
the resulting remote object and compare all security-relevant fields with the
expected result.

If the write may have succeeded but verification fails, the result is
`partial-remote-mutation`. The executor must not report success merely because a
write command exited zero or returned a URL.

Remote reads do not substitute for unknown local state.

## Result artifact

One execution writes exactly one result artifact using the versioned result
schema.

The artifact contains:

- schema and executor versions;
- unique result identity;
- operation identity and digest;
- repository identity and executor revision;
- start and finish timestamps;
- starting and ending local state;
- intended and observed mutation boundaries;
- command records;
- progress and heartbeat summary;
- validation evidence;
- commit and publication evidence where applicable;
- remote read-after-write verification;
- redaction events;
- terminal status;
- unresolved diagnostics;
- safest next interaction.

The executor creates the result with exclusive-create semantics and refuses to
overwrite an existing path. Operation identity and result identity are unique
within the governed workflow.

The preferred result directory is selected by this order:

1. an explicit safe directory in the operation description that already exists
   and is outside the governed repository;
2. the platform user-download directory when reliably discoverable;
3. a secure per-user temporary output directory reported before mutation.

The executor may not create a result inside the governed repository unless a
future accepted process explicitly authorizes that behavior.

## Redaction policy

Redaction occurs before ordinary output is persisted.

The executor redacts at least:

- GitHub, Git, cloud, package-registry, and CI token forms known to the accepted
  implementation;
- authorization and proxy-authorization header values;
- credential-bearing URLs;
- values of environment variables whose names indicate tokens, passwords,
  secrets, private keys, or credentials;
- configured secret literals supplied through a protected executor channel;
- authentication material emitted by subprocesses.

Redaction replacement text identifies the category and a stable execution-local
fingerprint without preserving the secret.

The result reports that redaction occurred, the category, and the affected
record location. It does not contain the original secret.

Redaction is defense in depth. Operation descriptions containing apparent
secrets are rejected before execution rather than accepted and merely redacted.

## Overwrite and replay prevention

The executor refuses to:

- execute an operation whose unique identity is already recorded as consumed in
  the applicable local result boundary;
- overwrite an operation file, result file, or existing governed target that
  was required to be absent;
- reuse a result identity;
- silently replace a conflicting result destination.

The initial implementation may use non-overwriting result existence as the
local replay boundary. A later durable replay registry would require separate
governance and is not implied by this specification.

## Portability and invocation

The repository entrypoint is `./scripts/governed-execute`.

The entrypoint selects a supported interpreter through repository-owned logic
and does not require the user-facing command to name a particular `python`
binary. The user runs one literal command from the repository root:

```sh
./scripts/governed-execute /path/to/<unique-operation>.json
```

The entrypoint verifies the repository root and executor revision before loading
the operation.

The path may be outside `~/Downloads`; result placement follows the safe
directory policy above. Portability must not weaken unique naming,
non-overwrite, repository-root, or evidence requirements.

## Progress and heartbeat output

The executor prints an immediate flushed message identifying:

- executor version;
- operation identity and type;
- repository;
- intended mutation and publication boundaries;
- result destination.

It prints meaningful progress at each guard, mutation, validation, and
verification phase. While a supervised operation runs without producing a
phase transition, it emits periodic heartbeat output with elapsed time and the
current phase.

Terminal output ends with the exact result path and an instruction to return
that artifact for review.

## Failure behavior

The executor fails closed when:

- schema or version validation fails;
- authorization is missing or inconsistent;
- an unknown field or capability appears;
- a guard fails;
- a path escapes its boundary;
- an output would overwrite an existing artifact;
- a command cannot be constructed from executor-owned capability logic;
- redaction cannot safely classify persistable output;
- a remote mutation cannot be verified.

The executor preserves partial-application evidence. It must not claim rollback
unless rollback was explicitly authorized, attempted, and verified.

## Compatibility and retained guarantees

Repository-supported governed operations use the versioned executor and
declarative operation descriptions. Security-critical mechanics are executor
requirements rather than transient operation logic.

The executor retains unique operation and result identity, one-command
execution, explicit user execution, progress, heartbeat, no-overwrite, exact
guards, complete evidence, result upload, and review-before-successor
requirements.

Operation descriptions may not redefine guard semantics, command construction,
redaction, mutation accounting, result generation, or remote verification.
Unsupported operation classes fail closed unless a separately accepted process
change adds the required capability.

Accepted historical execution results remain evidence for the work they
recorded. Historical evidence does not authorize new work or an unsupported
mutation path.

## Threat analysis

The design addresses these principal threats:

### Permission expansion by operation data

Mitigation: strict schemas, closed capability identifiers, executor-owned
command construction, unknown-field rejection, and separate authorization.

### Arbitrary code or shell injection

Mitigation: no executable payloads, no free-form commands, no shell by default,
validated argument slots, and static capability implementations.

### Repository or path confusion

Mitigation: exact repository and revision guards, normalized repository-relative
paths, symlink rejection, digest guards, and no inference from remote state.

### False success after partial application

Mitigation: distinct mutation accounting, closed terminal statuses, preserved
command evidence, post-mutation validation, and remote read-after-write
verification.

### Secret persistence

Mitigation: reject secrets in operation data, redact before persistence,
environment-name detection, credential-URL filtering, and redaction-event
records.

### Replay or overwrite

Mitigation: unique operation and result identities, exclusive-create output,
target absence or digest guards, and refusal to reuse known result paths.

### Executor self-modification

Mitigation: operation descriptions cannot modify executor or schema paths under
the initial capability set; executor updates require separately governed
repository changes.

### Stale evidence

Mitigation: results identify exact revisions and remote objects; later commits
or remote changes require fresh execution, validation, CI, review, and
acceptance evidence.

## Initial implementation conformance

The initial executor implementation conforms to this specification only when
permanent tests cover at least:

- unsupported versions and unknown fields;
- operation attempts to broaden capability or authorization;
- repository, revision, worktree, path, digest, and remote-object guard failure;
- path traversal and symlink rejection;
- operation and result overwrite refusal;
- timeout, interruption, nonzero exit, and heartbeat behavior;
- pre-mutation failure;
- partial local mutation;
- post-mutation validation failure;
- partial remote mutation and remote verification mismatch;
- secret redaction across arguments, stdout, stderr, environment-derived data,
  and credential-bearing URLs;
- successful local mutation, commit, and verified publication;
- compatibility and retained executor guarantees.

Mechanical conformance does not replace full-diff review, threat review,
semantic acceptance, CI, merge, or issue closure.

## Effective operation boundary

This specification is effective repository policy for supported governed
operations.

New governed operations use the executor when it supports the required
operation class. Accepted historical work remains valid evidence for the work it
recorded, but does not authorize new operations or unsupported capabilities.

Security-critical mechanics are owned by the reviewed executor. A compatibility
wrapper may locate and verify the executor and invoke a declarative operation,
but may not reconstruct guard, command, redaction, mutation-accounting, result,
or verification logic.

Unsupported operations fail closed. They never silently fall back to arbitrary
shell, unrestricted scripts, or direct connector mutation.
