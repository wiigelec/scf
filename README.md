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

## Repository validation

Run the initial read-only repository content validator from the repository root:

```sh
./scripts/validate
```

The validator checks current tracked JSON, authority checksums and metadata,
declared semantic paths, and required bootstrap artifacts. See
[`docs/VALIDATION.md`](docs/VALIDATION.md) for scope, exit statuses, check
selection, and contributor guidance.
