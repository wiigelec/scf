# Session Continuity Framework

This repository contains the **Session Continuity Framework (SCF)**.

Its nested foundational specification is **SCF Contract Foundation**.
The Contract Foundation defines the generic architecture, authority model,
construction constraints, and minimum conformance rules from which governed
SCF applications are developed.


## Repository lifecycle

SCF repository work is governed by
[`docs/OFFICIAL-GOVERNED-DEVELOPMENT-PROCESS.md`](docs/OFFICIAL-GOVERNED-DEVELOPMENT-PROCESS.md).
The provisional process in
[`bootstrap/INITIAL-DEVELOPMENT-PROCESS.md`](bootstrap/INITIAL-DEVELOPMENT-PROCESS.md)
is retained as historical bootstrap evidence and is superseded for new work.

The evidence and completion boundary for the repository's entry into normal
governed development are recorded in
[`planning/BOOTSTRAP-TO-DEVELOPMENT-TRANSITION.md`](planning/BOOTSTRAP-TO-DEVELOPMENT-TRANSITION.md).
That lifecycle record does not authorize any particular successor feature;
successor work still requires its own governed issue and accepted scope.

## Repository state

This repository has completed its bootstrap-to-development transition and now
operates under normal governed development. It contains the accepted durable
Level 0 authority, local repository validation, continuous integration, the
official governed development process, and independent-session initialization.
This lifecycle completion does not authorize any particular successor feature;
successor work still requires its own governed issue and accepted scope.

## Authority

`authority/level-0/SCF-LEVEL-0.json` is the proposed durable Level 0 root.
It is derived from `authority/core/SCF-CORE.json`, which remains historical
bootstrap foundational authority and is not the permanent Level 0 artifact.

Run `./scripts/validate` from the repository root and see
[`authority/README.md`](authority/README.md) for the hierarchy.

## Development process

Governed repository work follows the
[official governed development process](docs/OFFICIAL-GOVERNED-DEVELOPMENT-PROCESS.md).
It defines authority discovery, bounded authorization, planning, implementation,
validation, review, correction, acceptance, merge, closure, and successor-work
boundaries.

The three-record bounded-work planning convention is documented in
[`docs/GOVERNED-ISSUE-PLANNING.md`](docs/GOVERNED-ISSUE-PLANNING.md).

Independent sessions initialize the smallest authoritative development context
through the
[governed development-session initialization and interaction standard](docs/GOVERNED-DEVELOPMENT-SESSION-INITIALIZATION.md).

A chatbot may use read-only remote access for orientation, then uses a guarded
read-only Python interrogation script to establish the actual local branch, exact
`HEAD`, worktree state, divergence, local commits, and planned mutation boundary.

Every governed local or remote mutation is transported through a uniquely named,
agent-developed guarded Python script downloaded to `~/Downloads`. The user runs
exactly one literal command from the repository root:

```sh
python ~/Downloads/<unique-script-name>.py
```

Each script prints immediate progress and heartbeat messages, enforces its exact
authorization boundary, and writes exactly one unique non-overwriting result file
in `~/Downloads` for upload and review before any successor action. Direct chatbot
connector writes are not a governed mutation path, and the workflow does not depend
on prior chat history or model memory.

`bootstrap/INITIAL-DEVELOPMENT-PROCESS.md` is retained as historical bootstrap
evidence and is prospectively superseded by the official process.

## Repository validation

Run the read-only development validation gate from the repository root:

```sh
./scripts/validate
```

The default complete-work mode validates the effective working-tree filesystem
view: tracked files at their current paths plus untracked, non-ignored JSON files.
Deleted paths are absent, rename destinations replace their sources, ignored files
are excluded, unresolved conflicts fail before checks run, and symlinks are not
followed outside the repository. Focused mode uses the same state source for only
the selected checks. Certification instead validates the exact current `HEAD` tree
and requires a clean index and worktree; unrelated local content is not substituted
for committed content. JSON parsing rejects non-standard constants such as `NaN`
and `Infinity`, and governed file declarations require regular files.
Focused checks and exact-revision certification use the same entrypoint:

```sh
./scripts/validate --check SCF-JSON-001
./scripts/validate --mode certify
```

See [`docs/VALIDATION.md`](docs/VALIDATION.md) for mode semantics, machine
output, exit statuses, registry integrity, and the boundaries between
validation, diff review, CI evidence, and acceptance.

### Continuous integration

GitHub Actions runs the accepted complete-work gate through
[`.github/workflows/repository-validation.yml`](.github/workflows/repository-validation.yml).
The stable check name is `repository-validation`. See
[`docs/VALIDATION.md`](docs/VALIDATION.md) for exact tested-revision semantics,
local-to-CI responsibility boundaries, and branch-protection expectations.
