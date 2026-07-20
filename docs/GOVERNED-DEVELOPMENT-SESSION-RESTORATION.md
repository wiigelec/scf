# Governed Development Session Restoration

## Status, role, and governing parent

This document defines the official read-only restoration protocol for governed
Session Continuity Framework (SCF) development context across independent
assistant-user sessions.

It is a development-process support specification governed by the accepted SCF
authority hierarchy and the
`docs/OFFICIAL-GOVERNED-DEVELOPMENT-PROCESS.md` process. It applies the bounded
planning convention in `docs/GOVERNED-ISSUE-PLANNING.md`. It does not create
product authority, change lifecycle state, authorize successor work, or replace
the governing issue and its designated planning records.

Restoration exists so a new session can identify the smallest authoritative
context sufficient to continue a bounded work item without relying on prior chat
history or model memory.

## Restoration properties

A conforming restoration is:

- **read-only**: it observes evidence but performs no repository, GitHub, planning,
  acceptance, merge, closure, or lifecycle mutation;
- **authority-first**: accepted repository authority and durable governed records
  outrank transient conversation state;
- **identity-preserving**: exact document, branch, commit, issue, comment, pull
  request, CI, and supplied-evidence identities are recorded when known;
- **evidence-separated**: remotely verifiable, repository-local, and user-supplied
  local-only evidence remain distinguishable;
- **bounded**: it retrieves the smallest authoritative context sufficient for the
  active task instead of recursively loading unrelated repository content;
- **non-inventive**: missing required context produces an explicit underspecified
  result rather than architectural invention or undocumented inference;
- **deterministic**: equivalent inputs produce the same machine-readable result
  ordering and status;
- **action-bounded**: it identifies only the next action authorized by current
  authority and lifecycle evidence.

## Authority and discovery order

Restoration proceeds in this order:

1. identify the repository and supplied development branch;
2. identify the observed repository revision and working-tree classification;
3. discover the accepted SCF authority root and applicable authority chain;
4. discover the official governed development process;
5. identify the governing issue;
6. identify exactly one designated `## Governed detailed scope` comment;
7. identify exactly one designated
   `## Governed work breakdown and patch plan` comment;
8. verify strict accepted dependencies when dependency correctness matters;
9. inspect the branch commit topology and changed-file boundary;
10. identify validation, certification, pull-request, CI, review, merge, and issue
    state evidence;
11. incorporate explicitly supplied local-only evidence;
12. determine the lifecycle frontier and next authorized action.

A conflict between durable sources is reported as unresolved. Restoration must not
silently select whichever source is most convenient.

## Evidence classes

### Remote evidence

Remote evidence is independently resolvable through an accepted remote service,
including repository identity, remotely visible branches and commits, issue and
planning records, pull requests, CI runs, merge commits, and issue closure state.

Remote evidence is not automatically semantic acceptance. Passing CI remains
technical evidence for an exact revision.

### Repository-local evidence

Repository-local evidence is observable from the supplied local tree, including:

- repository root and configured remote identity;
- current branch;
- `HEAD`, merge base, parent topology, and commit subjects;
- tracked and untracked working-tree state;
- changed-file inventory and diff;
- repository documents, schemas, validators, tests, manifests, and registrations;
- locally created commits that may not yet be remotely visible.

A local commit remains local-only until its exact SHA is independently resolvable
through the remote repository.

### User-supplied local-only evidence

User-supplied local-only evidence includes terminal transcripts, generated artifact
identities, validation output, certification output, and other observations that a
new session cannot independently obtain from the remote repository.

Such evidence must record its source or reference and must not be relabeled as
remote evidence. A transcript may support a claim that a command ran, but only the
content actually shown by the transcript is recoverable.

### Transient conversation context

Chat history and model memory may help locate durable evidence but are not durable
authority or completion evidence. Restoration must succeed without prior
conversation history when the required durable and explicitly supplied evidence is
available.

## Required identity fields

A restoration result records the following fields when applicable:

- repository full name and canonical remote;
- supplied branch and observed branch;
- accepted base revision, observed `HEAD`, and merge base;
- working-tree classification;
- authority-root path and revision identity;
- applicable authority-document paths and identities;
- official-process path and identity;
- governing issue number and state;
- designated detailed-scope comment identity;
- designated work-breakdown comment identity;
- strict dependency identities and accepted evidence;
- planned patch, expected files, and planned commit subject;
- observed commits, changed files, and branch-local evidence;
- validation and certification commands, outcomes, and tested revisions;
- pull request, CI runs, reviews, merge commit, and closure state;
- local-only evidence references;
- unresolved requirements;
- lifecycle frontier;
- next authorized action.

An unknown field remains unknown. It is not populated from a guess.

## Lifecycle frontier

The lifecycle frontier is the furthest state supported by current evidence. States
remain non-equivalent and may include:

- planning prepared;
- patch execution pending;
- patch execution failed;
- patch partially applied;
- patch recovered;
- local patch committed;
- branch locally validated;
- branch clean-revision certified;
- branch pushed;
- pull request open;
- exact PR-head CI passed;
- semantic review complete;
- exact revision accepted;
- merged;
- governing issue closed.

Restoration records completed states, remaining states, and the next authorized
action. It must not infer acceptance from validation, CI, merge, or issue state
alone.

## Chat-developed local execution artifacts

### Guarded user-run Python scripts

Chat-developed repository work may be delivered as a guarded Python script for the
user to run against the local Git tree. The execution method identifier is:

`user-run-python-script`

The script is a transient execution vehicle. It is not accepted repository state
by default, and its existence is not proof that it ran.

For each script, restoration records when available:

- filename;
- SHA-256 digest;
- exact invocation command;
- expected repository identity;
- expected branch;
- accepted base and expected starting `HEAD`;
- expected clean or otherwise specified working-tree state;
- intended changed-file boundary;
- planned tests and validation commands;
- planned commit subject;
- whether push or pull-request creation is prohibited or included;
- supplied transcript or evidence reference.

### Script execution states

Script state is one of:

- `pending`: the artifact exists or was supplied, but no execution evidence exists;
- `failed`: execution stopped with an error and completion was not established;
- `partially-applied`: execution changed local state before stopping;
- `recovered`: a separately identified recovery action repaired or completed work
  after a failed or partial attempt;
- `completed`: supplied evidence establishes the intended terminal state.

A failed script, repository effects from that failure, a recovery script, and the
final successful execution remain separately identifiable. Restoration must not
collapse them into a single successful event.

### Transcript evidence

A user-supplied terminal transcript is local-only evidence. It may establish the
invocation used, guards, files changed, tests, validation, command outcomes,
resulting commit SHA, cleanliness, and whether publication occurred.

Absence of transcript evidence leaves execution pending or underspecified. A script
body alone cannot establish execution.

### Local and remote visibility

A transcript may establish a resulting local commit SHA. That commit remains
local-only evidence until the exact SHA is remotely resolvable.

Push, pull-request creation, CI execution, semantic review, acceptance, merge, and
issue closure are separate facts. Restoration reports each independently.

### Exact next command

When a guarded script is pending and its preconditions remain satisfied, restoration
may identify its exact invocation as the next authorized action, for example:

`python ~/Downloads/scf_issue_11_patch_1.py`

This is identification of an already authorized bounded action, not authorization
for broader work.

## Complete restoration result

A result is `complete` for the active task only when the evidence necessary to
identify the repository and branch, authority chain, official process, governing
issue and designated planning records, accepted base and observed revision, active
patch, completed and remaining work, lifecycle frontier, evidence boundaries, and
the exact next authorized action is available.

Completeness is task-relative. It does not mean the governing issue is complete.

## Underspecified restoration result

A result is `underspecified` when any required identity or evidence for the active
task cannot be resolved. It records resolved identities, missing or conflicting
requirements, why each matters, the smallest exact evidence needed, and the last
lifecycle state actually supported.

Examples include missing authority, missing or duplicate designated planning
comments, branch or revision mismatch, script reported as run without a transcript,
a transcript naming an unavailable commit, stale certification, or stale CI.

Underspecified is not failure, completion, or permission to invent missing
architecture. It is an explicit bounded result.

## No-mutation boundary

Restoration must not create, edit, or delete repository files; stage or commit
changes; alter branches; push; create or edit issues, comments, checklists, pull
requests, or reviews; trigger CI; accept, merge, close, reopen, or authorize work;
or write a repository-local lifecycle or planning registry.

A future executable restoration entrypoint must inspect before-and-after repository
state and demonstrate that its own operation caused no mutation.

## Deterministic machine-readable result

Where machine-readable output is implemented, it must use an explicit schema
version, stable field names and deterministic ordering, distinguish `complete` and
`underspecified`, identify evidence classes, preserve exact identities, list
unresolved requirements, identify the lifecycle frontier and next action, and
avoid credentials or conversation memory.

The result is a retrieval record, not a durable copy of live lifecycle state.

## Representative recovery cases

Validation must cover at least:

1. a complete restoration with exact next action;
2. a pending guarded Python script;
3. a failed script followed by a separately identified recovery script;
4. a completed script producing a local-only commit;
5. the same commit after it becomes remotely visible;
6. missing authority;
7. missing or duplicate planning records;
8. branch or revision mismatch;
9. stale certification or CI evidence;
10. proof that restoration performs no mutation;
11. deterministic repeated output.

## Failure and incomplete-evidence behavior

Tool failure, inaccessible remote evidence, malformed supplied evidence, and
ambiguous identities produce explicit diagnostics. They must not be silently
retried until a convenient result appears.

When required evidence is unavailable, restoration states exactly what is missing
and returns `underspecified`. Optional omissions are recorded without converting
the result into a false pass.

## Success boundary

This protocol is satisfied when a new independent session can recover the bounded
development context, distinguish all evidence classes, identify chat-developed
local execution artifacts, report the lifecycle frontier, and state the exact next
authorized action without relying on prior chat history and without mutating state.
