# Repository validation

Issue #4 establishes the initial read-only content validator for the current SCF
bootstrap repository.

## Run validation

Run from the repository root:

```sh
./scripts/validate
```

Runtime requirements are Python 3.11 or newer, Git, and the Python standard
library. The command performs no network access and does not modify repository
content.

The default JSON scope is every Git-tracked path ending in `.json`. Validation
reads each tracked file from the current working tree, so edits can be checked
before commit and a clean worktree is not required.

## Exit statuses

- `0`: all selected checks passed;
- `1`: repository content failed one or more checks;
- `2`: invalid invocation or an unexpected internal validator failure.

Repository-content diagnostics are controlled validation results. Internal
failures indicate that the validator could not reliably complete its work.

## Check inspection

List registered checks:

```sh
./scripts/validate --list-checks
```

Run one or more registered checks:

```sh
./scripts/validate --check SCF-JSON-001
./scripts/validate --check SCF-JSON-001 --check SCF-MANIFEST-001
./scripts/validate --check SCF-LEVEL0-001
```

This selection interface is developer feedback only. It is not the governed
focused-validation, complete-work-validation, or lifecycle-certification gate
assigned to Issue #8.

Use `--debug` only when diagnosing an unexpected internal failure.

## Initial checks

The validator checks:

- tracked JSON UTF-8, syntax, and duplicate keys;
- the current canonical checksum record;
- bootstrap manifest structure, identity, metadata, path, and digest consistency;
- durable Level 0 identity, provenance, hierarchy, semantic paths, manifest,
  checksum, canonical path, and digest consistency;
- declared descriptive and normative semantic paths and their disjointness;
- current required repository artifacts and narrow historical bootstrap-record
  consistency.

The validator intentionally does not implement schemas, authority graphs,
lifecycle state, CI enforcement, runtime architecture, or product validation.

## Adding a check

A later governed change that adds accepted repository authority or metadata may
extend validation as follows:

1. define the accepted rule and stable check and diagnostic identifiers;
2. implement the rule in a focused module under
   `src/scf_validation/checks/`;
3. register the check explicitly in
   `src/scf_validation/checks/__init__.py`;
4. return structured diagnostics rather than printing from the check;
5. add positive and negative tests;
6. update this documentation when user-visible behavior changes.

Do not infer unsupported authority, add dynamic plugin discovery, or encode
future architecture merely to make the validator appear general.

### Level 0 schema validation

`SCF-LEVEL0-001` also validates the canonical Level 0 document against
`authority/level-0/SCF-LEVEL-0.schema.json`. Validation is deterministic,
offline, and standard-library-only. The supported vocabulary is deliberately
bounded to the keywords used by the canonical schema; unsupported keywords are
errors. Schema identity, dialect, authority `$schema` reference, checksum,
manifest digest, and exact-byte consistency are validated separately from
authority semantic and cross-field rules.
