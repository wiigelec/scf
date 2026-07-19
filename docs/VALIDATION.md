# Repository validation

Issue #8 establishes the repository development validation gate by extending the
read-only content validator introduced by Issue #4.

## One repository-root entrypoint

Run all validation modes from the repository root through:

```sh
./scripts/validate
```

Runtime requirements are Python 3.11 or newer, Git, and the Python standard
library. Validation performs no network access and does not modify repository
content.

## Modes

The gate has three modes with distinct evidence claims.

### Focused validation

Focused mode runs one or more explicitly selected registered checks against the
current working-tree state:

```sh
./scripts/validate --check SCF-JSON-001
./scripts/validate --mode focused --check SCF-JSON-001
./scripts/validate --check SCF-JSON-001 --check SCF-MANIFEST-001
```

Using `--check` without `--mode` selects focused mode for backward
compatibility. Explicit focused mode requires at least one `--check`.

Focused validation is edit-time feedback. It is intentionally incomplete and
does not claim that the complete required validator inventory passed.

### Complete-work validation

Complete mode runs the entire required explicit validator registry against the
full resulting repository state:

```sh
./scripts/validate
./scripts/validate --mode complete
```

Running without `--mode` or `--check` selects complete mode for backward
compatibility.

Complete mode may run with uncommitted changes. Its result applies to the full
working-tree state read by the validators, not only to changed lines and not
only to a Git diff. When edits exist, machine output classifies the repository
as `working-tree` and reports the current `HEAD` separately.

### Certification validation

Certification runs the complete required registry only when the repository has
an existing `HEAD` and the working tree and index are clean:

```sh
./scripts/validate --mode certify
./scripts/validate --mode certify --format json
```

Successful human output includes:

```text
CERTIFIED <exact-commit-sha>
```

Successful machine output records the same exact revision, `clean: true`, and
repository classification `clean-revision`.

Certification means only that the exact clean revision passed the complete
validation gate. It does not approve, accept, merge, close, authorize,
supersede, or release work.

A dirty repository fails certification before content checks run. Complete mode
remains the correct mode for validating uncommitted bounded work.

## Explicit validator registry

List the required registered checks:

```sh
./scripts/validate --list-checks
./scripts/validate --list-checks --format json
```

The registry is explicit in `src/scf_validation/checks/__init__.py`. Its ordered
registered checks must exactly match `REQUIRED_CHECK_IDS`.

Validation fails rather than silently passing when registry composition is
missing, duplicated, malformed, unexpected, or reordered. The gate does not use
runtime filesystem scanning, third-party plugins, or dynamic validator
discovery.

## Result formats

Human-readable output is the default:

```sh
./scripts/validate --mode complete --format human
```

Machine-readable output is deterministic compact JSON:

```sh
./scripts/validate --mode complete --format json
```

Validation-result JSON uses `schema_version` 1 and contains:

- `mode`: `focused`, `complete`, or `certify`;
- `outcome`: `pass` or `fail`;
- `repository`: classification, exact revision where available, and cleanliness;
- `checks`: ordered check identifiers, names, outcomes, and diagnostics;
- `diagnostics`: gate-level diagnostics such as certification precondition
  failures;
- `summary`: error and warning counts.

Human and JSON output are rendered from the same immutable validation result.
Selecting JSON does not change which checks run or how success is determined.

Check-list JSON is a discovery result with `schema_version` and the ordered
`checks` inventory.

## Repository-state classifications

The machine result reports one of:

- `working-tree`: an existing `HEAD` with tracked, staged, or untracked changes;
- `clean-revision`: an existing `HEAD` with a clean worktree and index;
- `unborn-working-tree`: a valid Git repository without an initial commit.

Focused and complete validation support all three states. Certification requires
`clean-revision`.

## Exit statuses

- `0`: all selected or required checks passed and any mode preconditions passed;
- `1`: repository content or a controlled mode precondition failed;
- `2`: invalid invocation, invalid registry composition, unavailable repository
  tooling, or an unexpected internal validator failure.

Repository-content and certification-precondition diagnostics are controlled
validation results. Internal failures mean the gate could not reliably complete
its work.

## Current required checks

The current inventory is:

- `SCF-JSON-001` — tracked JSON integrity;
- `SCF-CHECKSUM-001` — canonical checksum;
- `SCF-MANIFEST-001` — authority manifest;
- `SCF-SEMANTIC-001` — authority semantic paths;
- `SCF-LEVEL0-001` — durable Level 0 authority;
- `SCF-REPO-001` — required repository artifacts.

These checks cover the current accepted repository authority and bootstrap
foundation. They do not define product-specific validators without separate
authority.

## Validation is not diff review

Validation and diff review answer different questions:

- full-state validation asks whether the complete resulting repository state
  satisfies the implemented mechanical and semantic checks;
- a Git diff shows what changed between revisions and supports human scope,
  intent, quality, and review judgments.

A passing gate does not prove that the diff is authorized, complete, desirable,
or correctly reviewed. A clean diff does not prove that the resulting state is
valid. Governed work requires both forms of evidence where applicable.

## Validation is not CI or acceptance

Issue #9 may run complete mode automatically in CI against an identified
proposed commit. CI must call this entrypoint rather than reimplementing its
rules.

CI evidence, local validation, certification, review, merge, acceptance, issue
closure, and successor authorization remain distinct facts. Issue #10 may define
their official process relationships.

## Adding a check

A governed change that adds accepted repository authority or metadata may extend
validation as follows:

1. define the accepted rule and stable check and diagnostic identifiers;
2. implement the rule in a focused module under `src/scf_validation/checks/`;
3. add the identifier to `REQUIRED_CHECK_IDS`;
4. register the check in the same order in `REGISTERED_CHECKS`;
5. return structured diagnostics rather than printing from the check;
6. add positive and negative tests;
7. update this documentation when user-visible behavior changes.

Do not infer unsupported authority, add dynamic plugin discovery, or encode
future architecture merely to make the validator appear general.

## Governed planning artifacts

`SCF-REPO-001` requires the governed issue-planning convention and its reusable
record templates:

- `.github/ISSUE_TEMPLATE/governed-work.md`
- `docs/GOVERNED-ISSUE-PLANNING.md`
- `docs/templates/GOVERNED-DETAILED-SCOPE.md`
- `docs/templates/GOVERNED-WORK-BREAKDOWN.md`

These checks protect discovery of the convention and reusable templates. They do
not fetch GitHub, validate live issue contents, interpret issue state, authorize
work, decide acceptance, or establish the official development process.

`docs/examples/GOVERNED-WORK-EXAMPLE.md` is illustrative and intentionally is
not a required repository artifact.
## Continuous integration evidence

Issue #9 adds GitHub Actions execution of this validation gate through
`.github/workflows/repository-validation.yml`.

The workflow uses the stable check name `repository-validation` and runs for:

- pull requests when they are opened, reopened, synchronized with a later commit,
  or marked ready for review;
- pushes to `main`;
- explicitly requested manual workflow dispatches.

### Exact tested revision

For a pull request, the workflow tests
`github.event.pull_request.head.sha`. It does not silently treat GitHub's
synthetic pull-request merge ref as the proposed source revision.

For other supported events, the workflow tests `github.sha`. The selected SHA is
passed explicitly to checkout, verified against `git rev-parse HEAD`, written to
the job log and step summary, and used in the validation-evidence artifact name.

CI evidence is commit-specific. A passing run for one SHA is not evidence for a
later SHA. A pull-request `synchronize` event creates a new run for the new head
commit.

### Commands and failure behavior

CI runs the permanent validation regression suite:

```sh
python -m unittest discover -s tests/validation -v
```

It then invokes the accepted complete-work gate without reimplementing its
registry or rules:

```sh
./scripts/validate --mode complete --format json
```

The JSON result is captured as `validation-result.json`. Shell `pipefail`
semantics preserve the validator's nonzero exit status when output is also sent
through `tee`, so validation failure fails the workflow check.

The workflow grants only read access to repository contents and disables
persisted checkout credentials. It does not repair files, commit changes, push
branches, or otherwise mutate repository content.

### Local and CI responsibilities

These evidence surfaces answer different questions:

- focused local validation gives intentionally incomplete edit-time feedback;
- complete local validation checks the full resulting working-tree state;
- local certification identifies an exact clean revision that passed the full
  gate;
- CI independently reports that the workflow tested an identified commit and
  that its tests and complete-work validation passed or failed;
- diff review evaluates scope, intent, quality, and authorization;
- acceptance, merge, issue closure, and successor authorization remain separate
  lifecycle decisions.

A successful CI run does not approve or accept a change. It also does not replace
local validation, certification where required, or human review.

### Branch-protection expectation

Repository settings may use the stable `repository-validation` check as a
required status check. This documentation identifies the intended check name but
does not claim that branch protection is configured. Branch-protection state is
an operational repository setting and must be verified independently.
