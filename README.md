# Session Continuity Framework

This repository contains the **Session Continuity Framework (SCF)**.

Its nested foundational specification is **SCF Contract Foundation**.
The Contract Foundation defines the generic architecture, authority model,
construction constraints, and minimum conformance rules from which governed
SCF applications are developed.

## Repository state

This repository is in governed post-bootstrap foundation development. It now
contains a proposed durable Level 0 authority and local repository validation,
but the bootstrap-to-development transition is not complete.

## Authority

`authority/level-0/SCF-LEVEL-0.json` is the proposed durable Level 0 root.
It is derived from `authority/core/SCF-CORE.json`, which remains historical
bootstrap foundational authority and is not the permanent Level 0 artifact.

Run `./scripts/validate` from the repository root and see
[`authority/README.md`](authority/README.md) for the hierarchy.

## Development process

Future work is governed through GitHub issues, isolated working branches, pull
requests, review, and merge to `main` under the rules recorded in
`bootstrap/INITIAL-DEVELOPMENT-PROCESS.md`.

The bounded-work planning convention is documented in
[`docs/GOVERNED-ISSUE-PLANNING.md`](docs/GOVERNED-ISSUE-PLANNING.md).

## Repository validation

Run the read-only development validation gate from the repository root:

```sh
./scripts/validate
```

The default complete-work mode validates the full resulting repository state.
Focused checks and clean-revision certification use the same entrypoint:

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
