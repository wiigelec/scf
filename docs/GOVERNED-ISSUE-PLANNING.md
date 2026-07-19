# Governed Issue Planning

## Status and authority boundary

This document defines the current lightweight convention for planning bounded
Session Continuity Framework development work through GitHub Issues.

It is a development-planning document. It is not normative SCF authority and
does not replace, supersede, or reinterpret the accepted authority hierarchy.

The convention is governed by:

- the high-level scope recorded in the governing GitHub Issue;
- the detailed scope recorded in one designated issue comment;
- the work breakdown and patch plan recorded in one designated issue comment;
- the development process authoritative when the work begins.

GitHub Issues are the primary durable planning mechanism. Repository files
document the convention and provide reusable templates; they do not duplicate
live issue state.

## Three-record planning model

Each governed bounded work item uses exactly three durable planning records.

### 1. Issue body — high-level scope

The issue body is the stable high-level contract for the work. It records:

- objective;
- governing authority and constraints;
- high-level scope;
- explicit exclusions;
- dependencies;
- deliverables;
- acceptance criteria.

The issue body must remain concise enough to orient a new session without
embedding the full implementation design.

A material change to objective, scope, exclusions, dependencies, deliverables,
or acceptance criteria requires editing the issue body. Detailed comments must
not silently expand or replace it.

### 2. Governed detailed scope comment

One issue comment headed exactly:

```text
## Governed detailed scope
```

records the implementation boundary. It includes:

- governing issue and accepted base;
- governing authority and constraints;
- implementation boundary;
- required behavior;
- affected concepts and repository areas;
- semantic decisions;
- explicit non-goals;
- dependency interpretation;
- review concerns;
- completion boundary.

This comment refines the issue body. It may not authorize work outside the
issue body's high-level scope.

### 3. Governed work breakdown and patch plan comment

One issue comment headed exactly:

```text
## Governed work breakdown and patch plan
```

records the ordered execution plan. It includes:

- accepted base and working branch;
- planned repository structure;
- ordered work breakdown;
- patch boundaries;
- expected files or repository areas;
- validation plan;
- commit strategy;
- correction and revision strategy;
- pull-request plan;
- completion evidence.

This comment converts the detailed scope into reviewable implementation steps.
It does not replace the issue body or grant authority beyond it.

## Source-of-truth boundaries

The three records have distinct responsibilities:

- **GitHub issue identity and open/closed state** identify and track the work item.
- **Issue body** governs high-level scope and acceptance criteria.
- **Detailed-scope comment** governs implementation boundaries and semantic
  decisions within that scope.
- **Work-breakdown and patch-plan comment** governs execution order, patch
  boundaries, validation, and commit strategy.
- **Commits and pull requests** provide implementation evidence.
- **Repository validation** provides mechanical evidence.
- **Review and merge** provide acceptance evidence under the process applicable
  at that time.

No single state substitutes for another. In particular:

- an open issue is not authorization;
- a closed issue is not by itself acceptance evidence;
- passing validation is not review;
- review approval is not merge;
- merge is not permission to begin unrelated successor work.

## Dependencies

Dependencies are recorded through explicit GitHub issue references.

A governed issue should distinguish:

- **strict dependencies**, which must be satisfied before the work can be
  completed correctly;
- **preferred ordering**, which reduces rework but is not a hard blocker;
- **related work**, which supplies context but is not a predecessor.

Issue references must identify the actual predecessor or related issue. Prose
descriptions without a reference are insufficient when a GitHub issue exists.

Dependency state is recovered from the referenced issue and accepted repository
evidence. The governing issue must not silently treat issue closure alone as
proof that a dependency was accepted.

## Status distinctions

GitHub's open or closed issue state tracks the work item but does not collapse
the complete development lifecycle.

The planning convention keeps these facts distinct:

- issue state;
- authorization to begin;
- implementation readiness;
- validation result;
- review state;
- acceptance state;
- merge state;
- closure state.

Issue #10 may later establish the official process and vocabulary governing
these facts. This document records only the minimum distinctions needed to
avoid conflation during current foundation development.

## Identifying and revising the designated comments

The designated planning comments are identified by their exact top-level
headings:

- `## Governed detailed scope`
- `## Governed work breakdown and patch plan`

Each governed issue should contain one comment with each heading.

When planning detail changes:

- edit the original designated comment in place;
- preserve the exact heading;
- update only the affected detail;
- do not create a replacement comment unless the original cannot be edited;
- update the issue body instead when the change affects high-level scope.

GitHub comment-edit history preserves earlier versions. Repository history
preserves implementation changes. Corrections must not silently rewrite accepted
repository history.

## Session recovery

A new session recovers a bounded work item in this order:

1. Read the issue body for objective, high-level scope, exclusions,
   dependencies, deliverables, and acceptance criteria.
2. Read the `Governed detailed scope` comment for implementation boundaries,
   semantics, non-goals, and review concerns.
3. Read the `Governed work breakdown and patch plan` comment for accepted base,
   branch, patch sequence, validation, commit strategy, and completion evidence.
4. Inspect referenced predecessor issues and accepted repository evidence.
5. Inspect the working branch, commits, pull request, and validation evidence if
   implementation has begun.
6. Report discrepancies instead of inferring which record should silently win.

Transient conversation context may assist the session but is not required for
recovery and must not override durable records.

## Completion evidence

Before an issue is closed as completed, the applicable evidence should be
identifiable:

- accepted base commit;
- implementation branch and head commit;
- focused commit history;
- changed-file inventory;
- focused and complete test results;
- repository validation results;
- semantic and scope audit results;
- pull-request review state;
- merge commit on `main`;
- completed acceptance checklist.

Not every work item requires every evidence type, but omissions must be
justified by the work's actual boundary. Issue state alone is never sufficient
completion evidence.

## Boundary with later foundation work

This convention intentionally does not define:

- repository-local planning schemas or registries;
- a custom lifecycle engine;
- the final development validation gate;
- continuous-integration enforcement;
- the complete official development process;
- bootstrap completion;
- successor-work authorization.

Issue #8 may build the complete validation gate around the bounded-work
convention. Issue #10 may establish the official governed development process.
This document must not preempt either issue.
