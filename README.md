# Session Continuity Framework

This repository contains the **Session Continuity Framework (SCF)**.

Its nested foundational specification is **SCF Contract Foundation**.
The Contract Foundation defines the generic architecture, authority model,
construction constraints, and minimum conformance rules from which governed
SCF applications are developed.

## Repository state

This repository is at bootstrap. It contains foundational authority and the
minimum process needed to begin governed top-down design. It contains no
product implementation, runtime architecture, speculative lower-level schema,
or continuous-integration system.

## Authority

`authority/core/SCF-CORE.json` is the bootstrap foundational authority.
Its integrity can be checked from the repository root with:

```sh
sha256sum -c authority/core/SCF-CORE.sha256
```

## Development process

Future work is governed through GitHub issues, isolated working branches, pull
requests, review, and merge to `main` under the rules recorded in
`bootstrap/INITIAL-DEVELOPMENT-PROCESS.md`.
