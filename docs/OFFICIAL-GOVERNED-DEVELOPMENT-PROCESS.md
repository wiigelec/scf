# Official Governed Development Process

## Status, role, and governing parent

This document is the official repository-wide development process for governed
Session Continuity Framework (SCF) repository work after its acceptance and merge
to `main`.

It is a durable development-process specification. It governs how proposed
repository changes are authorized, planned, implemented, validated, reviewed,
corrected, accepted, merged, closed, and superseded. It does not itself define
SCF product runtime architecture or replace the accepted SCF authority hierarchy.

This process is governed by the accepted SCF authority hierarchy rooted in the
durable Level 0 authority. It must be interpreted consistently with that
hierarchy. A development-process rule may control repository work without
becoming semantic product authority. No issue, comment, branch, commit, pull
request, validation result, CI run, review, chat instruction, or automation may
silently contradict or replace accepted repository authority.

## Scope

This process applies to every proposed modification of governed repository state,
including authority, bootstrap, planning, validation, documentation, tests,
automation, and implementation artifacts.

Repository-wide process changes become effective only when accepted and merged
to `main`. Branch-local methods may organize bounded work, but they do not alter
this official process unless separately governed, reviewed, accepted, and merged.

## Core record and evidence boundaries

Governed development uses distinct records and evidence surfaces. Each answers a
different question and none silently substitutes for another.

### Accepted repository authority

Accepted authority defines semantic precedence, constraints, and permitted
interpretation. Authority discovery begins from the repository's documented root
and proceeds through explicit parent and precedence relationships.

### Governing issue

A GitHub issue identifies a bounded work item and records its stable high-level
objective, scope, constraints, exclusions, dependencies, deliverables, and
acceptance criteria.

Issue existence alone is not authorization to implement. Issue open or closed
state identifies lifecycle state but is not by itself evidence of acceptance,
merge, or successor authorization.

### Designated planning records

The governed detailed-scope comment refines the implementation boundary and
semantic decisions within the issue body.

The governed work-breakdown and patch-plan comment defines ordered execution,
patch boundaries, validation, commit strategy, correction strategy, and expected
completion evidence.

Planning records may refine but may not silently expand the issue body. A material
change to objective, high-level scope, exclusions, dependencies, deliverables, or
acceptance criteria requires a corresponding issue-body revision before the
expanded work proceeds.

### Working branch

An isolated branch is the provisional implementation domain for one governed
issue. Branch contents, temporary methods, and unaccepted commits are proposed
work, not accepted repository state.

### Commits

A commit is an immutable implementation record for a specific tree. It can
provide reviewable evidence, but it is not acceptance. A later commit creates a
different proposed revision and invalidates earlier exact-revision certification
or CI evidence as completion evidence for the new head.

### Local validation and certification

Focused validation provides intentionally incomplete edit-time feedback.

Complete-work validation evaluates the full resulting repository state.

Certification applies the complete gate to an exact clean revision and records
that revision. Certification is mechanical evidence for that commit. It is not
semantic review, acceptance, merge, closure, or authorization for other work.

### Continuous-integration evidence

CI independently tests an identified proposed commit through the accepted
repository validation workflow. CI evidence is exact-revision evidence. A passing
run for one SHA is not evidence for a later SHA.

A passing CI result does not approve, accept, merge, or close work. A failing CI
result blocks technical readiness until corrected or explicitly resolved under
applicable authority; deterministic failures must not be silently masked.

### Diff and semantic review

Full-diff review evaluates the complete proposed change against accepted
authority, governing scope, designated planning records, quality expectations,
security and safety concerns, and the issue acceptance criteria.

Mechanical checks establish properties they are designed to test. Passing
validation is not semantic review. Human review is responsible for intent, scope,
semantic consistency, omissions, misleading claims, and whether the evidence
justifies acceptance.

### Acceptance, merge, and closure

Acceptance is an explicit decision that the exact proposed revision satisfies the
governing issue and applicable authority.

Merge changes accepted repository state by integrating the accepted revision into
`main`.

Issue closure records closeout of the bounded work item. Merge and closure are
related but distinct facts. Neither closure alone nor merge alone authorizes
unrelated successor work.

## Governed lifecycle

### 1. Discover authority and current process

Before planning or implementation:

1. identify the accepted authority root and applicable descendants;
2. read this official process;
3. inspect the governing issue and explicit dependencies;
4. inspect accepted predecessor evidence when dependency correctness matters;
5. report conflicts or missing authority instead of silently choosing a
   convenient interpretation.

Transient conversation context may assist work but cannot override durable
accepted records.

### 2. Establish bounded authorization

Work may begin only when a governing issue exists and the applicable process
permits the bounded work to proceed.

Authorization is bounded by the issue body and accepted authority. It does not
extend to unrelated cleanup, speculative architecture, future issues, or
repository-wide policy changes absent explicit scope.

Strict dependencies must be satisfied before dependent work is completed.
Dependency closure alone is insufficient when accepted repository evidence does
not support satisfaction.

### 3. Record governed planning

Before substantive implementation, create or confirm exactly one designated
detailed-scope comment and one designated work-breakdown and patch-plan comment.

The planning records must identify the accepted base and working branch, define
implementation boundaries and non-goals, establish patch and validation strategy,
and state expected completion evidence.

Discrepancies among issue body, designated comments, repository authority, and
branch state must be reported and corrected in the proper source of truth. They
must not be reconciled by silent inference.

### 4. Create the isolated branch

Create the issue branch from the accepted `main` revision recorded in the plan.
Confirm the base, branch identity, and clean repository state before modifying
files.

Do not mix unrelated work into the branch. When unrelated changes are present,
separate them or stop until their ownership is resolved.

### 5. Implement bounded patches

Implement work in reviewable patches consistent with the designated plan.

Each patch should have one coherent purpose, narrow file scope, appropriate
focused tests, and a terse intentional commit subject. Temporary artifacts must
not become durable repository state unless explicitly required.

A patch that materially exceeds scope must stop until the governing issue or
planning record is revised at the correct level.

### 6. Validate before commit

Before committing a patch:

1. inspect the patch's changed-file inventory;
2. run applicable focused tests;
3. run the permanent validation test suite when repository validation behavior or
   durable process contracts are affected;
4. run complete-work validation for the resulting repository state;
5. run whitespace and text-hygiene checks;
6. inspect the full patch diff for scope and semantic correctness.

A failing required check blocks commit as completed work. Incomplete validation
must be recorded as incomplete evidence, not described as a pass.

### 7. Commit intentionally

Commit only the files belonging to the bounded patch. The worktree and index must
be understood before staging.

A commit identifies an exact tree but does not establish acceptance. Commit
history should preserve meaningful patch boundaries and corrections rather than
conceal them.

### 8. Validate and certify the proposed branch head

Before publication for acceptance review:

1. run the full permanent validation suite;
2. run complete-work validation;
3. perform full-diff and scope audit from accepted base to branch head;
4. verify commit topology and file inventory;
5. run exact clean-revision certification where the governing plan requires it.

Certification evidence must identify the exact clean head SHA. Any later commit
requires fresh certification for completion.

### 9. Push and open the pull request

Push only after the branch is in a known, validated state consistent with the
governing plan.

Open a pull request that links the governing issue and identifies:

- purpose and rationale;
- accepted base and exact head;
- changed-file inventory and patch structure;
- validation and certification evidence;
- known limitations or incomplete evidence;
- acceptance-criteria audit.

A pull request is a proposed repository transition. It is not accepted authority.

### 10. Obtain CI and review evidence

Require CI evidence for the exact current PR head. A later push requires a new run
and makes prior run evidence stale for completion.

Review the entire diff, not merely the last correction. Review must cover
mechanical results, semantic correctness, authority consistency, scope, process
compliance, and acceptance criteria.

Repository settings may require stable checks, but documentation must not claim
that an operational setting exists unless it is independently verified.

### 11. Correct open work

While work remains open, correct defects with bounded later commits.

Corrections must:

- preserve the governing issue boundary;
- update designated planning records when implementation detail changes;
- update the issue body when high-level scope changes;
- receive fresh local validation;
- receive fresh certification when required;
- receive fresh CI for the new SHA;
- be included in renewed full-diff review.

Do not rewrite accepted `main` history to conceal corrections. Do not treat a
previously passing SHA as evidence for a corrected head.

### 12. Determine readiness and acceptance

The following states are distinct:

- **implementation readiness**: planned work can be performed;
- **technical readiness**: required tests and validation pass for the proposed
  state;
- **audit readiness**: scope, topology, inventory, evidence, and review records are
  complete enough to audit;
- **certified revision**: the exact clean revision passed certification where
  required;
- **accepted revision**: an explicit acceptance decision covers the exact
  revision.

Technical readiness, audit readiness, or certification does not automatically
establish acceptance.

Acceptance must identify the revision being accepted and must be supported by the
governing issue, applicable authority, completed review, and required evidence.

### 13. Merge accepted work

Merge only the accepted revision through the governed pull request.

If the PR head changes after acceptance, the earlier acceptance is stale unless
the change is explicitly reviewed and accepted under the applicable process.

The resulting `main` commit becomes accepted repository state subject to the
authority role of the merged artifacts.

### 14. Close out the issue

Before closing as completed, identify applicable evidence:

- accepted base;
- branch and accepted head;
- focused commit history;
- changed-file inventory;
- focused and full tests;
- complete validation and certification where required;
- exact CI result;
- full-diff review;
- acceptance-criteria audit;
- accepted merge commit on `main`.

Omitted evidence must be justified by the actual work boundary. Issue state alone
is never sufficient completion evidence.

Close the issue only after its accepted work is on `main` or the issue is
explicitly closed for another stated reason such as not planned or superseded.

### 15. Authorize successor work separately

Completion, merge, or closure does not automatically authorize the next issue.

Successor work requires its own governing issue, dependency interpretation,
bounded authorization, planning records, accepted base, and isolated branch.

## Failure and incomplete-evidence behavior

A deterministic validation, test, certification, or CI failure is evidence that
the tested revision is not technically ready under that check. It must not be
silently retried until a passing result is obtained without preserving the
relevant failure context.

Tooling failure, unavailable infrastructure, missing permissions, interrupted
execution, ambiguous logs, stale SHA evidence, or an unreviewed later commit
produces incomplete evidence. Incomplete evidence is not failure of the repository
unless the underlying check actually failed, but it is also not a pass.

When required evidence cannot be produced:

1. state exactly what is missing;
2. preserve known results without overstating them;
3. correct the cause or record an authorized exception;
4. rerun the applicable check against the exact proposed revision;
5. defer acceptance when the missing evidence is required.

Conflicting records, uncertain scope, or unresolved authority precedence must be
escalated for correction. Convenience is not permission to guess.

## Repository-wide process changes

A proposed change to this official process must itself follow this process.

Repository-wide process changes require:

- an explicit governing issue;
- clear authority role and parent;
- impact analysis for active and future work;
- explicit supersession or amendment semantics;
- consistent repository discovery updates;
- applicable validation and review;
- acceptance and merge to `main`.

A branch-local instruction may not silently amend this process.

## Supersession

This document supersedes
`bootstrap/INITIAL-DEVELOPMENT-PROCESS.md` prospectively upon acceptance and merge
to `main`.

The provisional file remains historical evidence of the bootstrap-to-development
transition. Supersession does not erase its history, retroactively invalidate work
properly governed by it, or convert its bootstrap exception into continuing
authority.

After this process becomes accepted repository state, new governed work uses this
document. Work already in progress continues under the process authoritative when
that work began unless an explicit governed decision migrates it.

A later official process may amend or supersede this one only through an accepted
repository-wide process change with explicit parent, scope, transition, and
supersession rules.
