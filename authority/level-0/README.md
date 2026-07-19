# SCF Level 0 authority

This directory contains the canonical Level 0 authority set:

- `SCF-LEVEL-0.json`
- `SCF-LEVEL-0.schema.json`
- `SCF-LEVEL-0.sha256`
- `SCF-LEVEL-0.schema.sha256`
- `manifest.json`

Level 0 is derived from `../core/SCF-CORE.json`, which remains historical
bootstrap foundational authority. Level 0 has no normative parent.

Run `./scripts/validate` from the repository root to validate the complete
authority set.

## Structural schema

`SCF-LEVEL-0.schema.json` is the repository-local structural contract for
`SCF-LEVEL-0.json`. The authority document remains the normative semantic
authority. The schema constrains representation, required fields, types, fixed
identity values, and additional-property policy without adding architecture
meaning.

The authority document declares the stable schema identity through `$schema`.
`SCF-LEVEL-0.schema.sha256` and the manifest schema entry protect the exact
schema bytes. Repository validation is offline and implements only the bounded
Draft 2020-12 vocabulary used by this schema; unsupported keywords fail
validation rather than being silently ignored.
