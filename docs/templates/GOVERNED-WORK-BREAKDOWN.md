## Governed work breakdown and patch plan

**Record role:** Ordered implementation and validation plan for this issue.

**Governing issue:** #

## Accepted base

- Branch: `main`
- Commit: `<commit>`
- Required predecessor state:
- Working branch:

## Planned repository structure

List the expected files or repository areas. Update this comment before
implementation if the structure changes materially.

## Work breakdown

1.
2.
3.

## Patch boundaries

### Patch 1 — <title>

**Purpose**

Describe the independently reviewable outcome.

**Expected files**

-

**Mechanical validation**

-

**Semantic review**

-

**Commit subject**

`<subject>`

### Patch 2 — <title>

**Purpose**

Describe the independently reviewable outcome.

**Expected files**

-

**Mechanical validation**

-

**Semantic review**

-

**Commit subject**

`<subject>`

Add further patches only when they represent distinct, independently reviewable
changes.

## Validation plan

- focused tests;
- complete repository validation;
- documentation consistency checks;
- scope-diff audit;
- protected-artifact checks;
- post-push branch and pull-request audit.

## Commit strategy

Use focused commits matching the patch boundaries. Make corrections as explicit
follow-up commits rather than silently rewriting reviewed history.

## Correction and revision strategy

- Edit the issue body for high-level scope changes.
- Edit the designated detailed-scope comment for implementation-boundary changes.
- Edit this comment for work order, files, patches, validation, or commit-plan
  changes.
- Preserve the exact designated headings.
- Do not create replacement planning comments unless the original cannot be
  edited.

## Pull-request plan

- Target branch:
- Head branch:
- Initial state: draft
- Required description content:
- Issue-closing reference:
- Evidence required before review transition:

## Completion evidence

Identify the expected base commit, branch head, focused commits, changed-file
inventory, tests, repository validation, semantic and scope audits, review,
merge commit, and completed acceptance checklist.

Issue state alone is not completion evidence.
