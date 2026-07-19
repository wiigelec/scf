# Session Continuity Framework

This repository contains the **Session Continuity Framework (SCF)**.

Its nested foundational specification set is **SCF Contract Foundations**.
The Contract Foundations define the generic architecture, authority model,
construction constraints, and minimum conformance rules from which governed
SCF applications are developed.

## Repository state

This repository is at bootstrap. It contains foundational authority and the
minimum process needed to begin governed top-down design. It contains no
product implementation, runtime architecture, speculative lower-level schema,
or continuous-integration system.

## Authority

`authority/core/SCF-CORE.json` is the Level-0 foundational authority.
Its integrity can be checked from the repository root with:

```sh
sha256sum -c authority/core/SCF-CORE.sha256
```

## Development sequence

Future work begins with a high-level Session Continuity Framework design scope.
That scope is then decomposed into milestones, phases, and bounded implementation
batches under the rules recorded in
`bootstrap/INITIAL-DEVELOPMENT-PROCESS.md`.
