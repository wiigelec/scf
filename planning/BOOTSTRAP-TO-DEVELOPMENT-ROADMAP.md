# Bootstrap-to-Development Roadmap

## Document status

This document is a non-normative planning and coordination artifact produced
under GitHub issue #6.

It records the dependency-aware work required to move the Session Continuity
Framework (SCF) repository from bootstrap initialization into normal governed
development. It does not create, replace, supersede, or reinterpret repository
authority. The accepted authority and development process governing each issue
remain controlling.

## Governing context

The repository currently operates under:

- `authority/core/SCF-CORE.json`, the bootstrap foundational authority;
- `bootstrap/INITIAL-DEVELOPMENT-PROCESS.md`, the provisional issue, branch,
  pull-request, review, and merge process;
- the requirement that lower-level work remain traceable to higher-level
  authority;
- the requirement that bounded synthesis tasks have explicit objectives,
  authority references, context, scopes, requirements, and acceptance
  criteria.

The one-time bootstrap exception has expired. The repository is performing
governed post-bootstrap development, but the durable foundation needed for
scalable normal feature work is not yet complete.

## Roadmap objective

Establish the minimum durable capabilities needed so SCF development can:

- preserve an explicit authority hierarchy;
- plan work as bounded, dependency-aware units;
- validate complete proposed repository states;
- enforce validation through continuous integration;
- operate under an official governed development process;
- restore development context across independent sessions;
- explicitly complete the bootstrap-to-development transition; and
- begin routine governed specification and feature development without
  inventing missing authority or process.

## Scope boundary

This roadmap coordinates development-foundation work. It does not itself:

- establish or modify normative SCF authority;
- implement repository validation;
- implement continuous integration;
- define the official development process;
- supersede the provisional process;
- implement runtime architecture;
- create speculative lower-level schemas;
- implement functional SCF features; or
- authorize any roadmap issue to begin.

Each implementation change remains separately governed by its GitHub issue and
the development process authoritative when that issue begins.

## Roadmap issue register

The issue state recorded here is a planning snapshot, not lifecycle authority.
GitHub issue state and accepted repository evidence remain authoritative.

| Capability | Issue | Initial state | Strict predecessors |
|---|---:|---|---|
| Repository validation foundation | #4 | Complete | None |
| Initial durable Level 0 authority | #5 | In progress | #4 |
| Governed planning and bounded work records | #7 | Open | #4 |
| Repository development validation gate | #8 | Open | #7 |
| Continuous-integration enforcement | #9 | Open | #8 |
| Official governed development process | #10 | Open | #5, #7, #8, #9 |
| Governed development session restoration | #11 | Open | #7, #10 |
| Bootstrap-to-development transition | #12 | Open | #4, #5, #7, #8, #9, #10, #11 |

Issue #7 preferably follows #5 even though #5 is not a strict predecessor.
Establishing Level 0 first gives later planning records a durable authority root
and reduces transitional references to bootstrap authority.

## Foundational capability inventory

### F1 — Repository validation foundation

**Issue:** #4, **Add basic repository validation**

**Purpose:** Establish a small, repeatable repository-root command that verifies
the integrity and internal consistency of current authority and metadata files.

**Boundary:** Validate current repository content without defining the complete
development gate, CI policy, final authority hierarchy, or runtime architecture.

### F2 — Initial durable authority hierarchy

**Issue:** #5, **Create the Level 0 SCF specification**

**Purpose:** Create the first canonical Level 0 SCF authority derived from the
bootstrap foundational authority while preserving the bootstrap document as
historical foundational authority.

**Boundary:** Establish the durable authority root without introducing
product-specific runtime architecture or speculative lower-level
specifications.

### F3 — Reproducible governed work planning

**Issue:** #7, **Establish governed planning and bounded work records**

**Purpose:** Define durable planning records and bounded work units that make
scope, dependencies, authorization, lifecycle state, and acceptance criteria
recoverable without prior chat history.

**Boundary:** Define planning and execution records without replacing repository
authority, implementing product features, or determining domain semantics.

### F4 — Development validation gate

**Issue:** #8, **Establish the repository development validation gate**

**Purpose:** Define one documented validation interface for focused checks,
complete bounded-work validation, and explicitly authorized lifecycle-boundary
certification.

**Boundary:** Compose and report validation without silently modifying
repository content, replacing human review, or making acceptance decisions.

### F5 — Continuous-integration enforcement

**Issue:** #9, **Add continuous-integration enforcement**

**Purpose:** Execute the repository validation contract automatically against
an identifiable proposed commit and report a failing status when validation
fails.

**Boundary:** Provide independent mechanical evidence without repairing files,
creating authority, approving changes, or substituting for review and
acceptance.

### F6 — Official governed development process

**Issue:** #10, **Establish the official governed development process**

**Purpose:** Establish the durable process governing authority discovery,
planning, implementation, validation, review, correction, acceptance, closure,
and supersession.

**Boundary:** Govern development operations without supplying missing
architecture, approving a particular change, or collapsing technical readiness,
certification, acceptance, and closure into one event.

### F7 — Session-context restoration

**Issue:** #11, **Establish governed development session restoration**

**Purpose:** Allow a new assistant-user session to recover the current governed
development state from repository, branch, planning, validation, and local
evidence without relying on prior conversation history.

**Boundary:** Retrieve and report authority and state without inferring missing
authority, silently altering plans, or treating transient session state as
committed state.

### F8 — Bootstrap completion and transition

**Issue:** #12, **Complete the bootstrap-to-development transition**

**Purpose:** Verify that the complete development foundation exists, explicitly
supersede the provisional bootstrap process through accepted authority, and
record entry into normal governed development.

**Boundary:** Verify and record transition readiness without implementing a
missing predecessor capability or waiving an unmet criterion.

## Dependency model

### Dependency types

- **Strict dependency:** the predecessor must be accepted before the dependent
  issue can be completed correctly.
- **Preferred ordering:** work could proceed earlier, but the recommended order
  reduces rework, transitional language, or premature policy choices.
- **Parallelizable work:** work may proceed concurrently after all shared strict
  predecessors are satisfied.

### Strict dependencies

1. **#4 precedes #5.**
   Level 0 authority must be introduced only after repository identity,
   checksums, metadata, and semantic paths can be mechanically checked.

2. **#4 precedes #7.**
   Durable planning structures require a validation base capable of rejecting
   malformed tracked records.

3. **#7 precedes #8.**
   Complete bounded-work validation depends on defined work boundaries,
   requirements, and acceptance records.

4. **#8 precedes #9.**
   CI must enforce an established local validation contract rather than create
   an independent and divergent validation path.

5. **#5, #7, #8, and #9 precede #10.**
   The official process must govern an existing authority hierarchy, planning
   model, validation interface, and CI mechanism with stable responsibilities.

6. **#7 and #10 precede #11.**
   Session restoration must recover the actual durable planning and development
   process rather than a temporary bootstrap convention.

7. **#4, #5, #7, #8, #9, #10, and #11 precede #12.**
   The transition issue verifies the complete foundation and must not implement
   a missing predecessor.

### Preferred ordering

Issue #5 should normally be completed before #7 even though both become
available after #4. Establishing Level 0 first gives later planning records a
durable authority root and reduces transitional language.

Issue #10 should be finalized only after #9 establishes the actual CI contract.

### Parallelizable work

After #4 is accepted:

- #5 and #7 may proceed in parallel;
- conceptual design for #8 may begin while #5 is underway, provided it does not
  assume unresolved authority structure;
- requirements for #11 may be collected early, but implementation and
  acceptance require #7 and #10.

## Dependency graph

```text
#4  Basic repository validation
 │
 ├──────────────► #5  Level 0 SCF specification
 │
 └──────────────► #7  Governed planning and bounded work
                       │
                       └──────────► #8  Development validation gate
                                      │
                                      └──────────► #9  CI enforcement

#5 ───────────────────────────────────┐
#7 ───────────────────────────────────┤
#8 ───────────────────────────────────┼──► #10 Official development process
#9 ───────────────────────────────────┘
                                             │
#7 ──────────────────────────────────────────┤
#10 ─────────────────────────────────────────┴──► #11 Session restoration

#4, #5, #7, #8, #9, #10, #11 ─────────────────► #12 Bootstrap transition
```

## Recommended implementation sequence

1. Complete #4 — **Add basic repository validation**.
2. Complete #5 — **Create the Level 0 SCF specification**.
3. Complete #7 — **Establish governed planning and bounded work records**.
4. Complete #8 — **Establish the repository development validation gate**.
5. Complete #9 — **Add continuous-integration enforcement**.
6. Complete #10 — **Establish the official governed development process**.
7. Complete #11 — **Establish governed development session restoration**.
8. Complete #12 — **Complete the bootstrap-to-development transition**.

This is a recommended sequence, not authorization to begin an issue. Every
issue must separately follow the development process applicable at the time it
begins.

## Transition milestones

### Milestone A — Mechanically protected authority

Satisfied when #4 and #5 are accepted and merged into `main`.

The repository then has a canonical durable authority root and a local
mechanism capable of checking its basic integrity.

### Milestone B — Reproducible governed work

Satisfied when #7 and #8 are accepted and merged into `main`.

The repository can represent bounded work durably and validate the complete
resulting state through one documented interface.

### Milestone C — Enforced governed development

Satisfied when #9 and #10 are accepted and merged into `main`.

Proposed commits receive independent CI evidence and development proceeds under
an official durable process.

### Milestone D — Recoverable normal-development foundation

Satisfied when #11 and #12 are accepted and merged into `main`.

A new session can recover the governed frontier, and the repository has
explicitly completed the transition from provisional bootstrap development to
normal governed development.

## Bootstrap completion criteria

The bootstrap-to-development foundation is complete only when all of the
following are objectively verifiable:

1. A canonical durable Level 0 authority exists outside the bootstrap artifact.
2. Authority identities, parent relationships, versions, statuses, manifests,
   checksums, and declared semantic paths are mechanically validated.
3. Work can be represented as bounded, dependency-aware, recoverable planning
   units with explicit authority, context, scopes, requirements, and acceptance
   criteria.
4. One documented local validation gate verifies the complete proposed
   repository state for the applicable work boundary.
5. CI executes the same validation contract against an identifiable commit and
   fails when the contract fails.
6. An accepted official process governs planning, implementation, validation,
   review, correction, acceptance, closure, and supersession.
7. A new session can reconstruct authority, active planning state, applicable
   validation, current lifecycle frontier, and next authorized work without
   prior chat history.
8. The provisional bootstrap development process has been explicitly
   superseded through an accepted authority transition.
9. Issues #4, #5, and #7 through #12 are accepted and merged into `main`.
10. No completion claim depends solely on an issue description, GitHub open or
    closed state, branch-local convention, unmerged artifact, or transient
    conversation.

Failure of any criterion leaves the transition incomplete.

## Normal-development entry criteria

Routine governed SCF specification or feature development may begin only when:

- all bootstrap completion criteria are satisfied;
- the official development process is authoritative on `main`;
- the authority hierarchy supports the proposed lower-level work;
- planning, validation, and CI mechanisms are operational;
- the proposed work cites its governing authority and dependencies;
- the work has explicit read scope, write scope, behavioral requirements, and
  acceptance criteria;
- a new session can recover the work and its current lifecycle state; and
- beginning the work does not require invention of missing authority, process,
  validation, or transition semantics.

Development-foundation corrections remain foundation work even after normal
development begins when they modify mechanisms governing all later work.

## Status maintenance

The issue register is a durable planning snapshot and may be updated as roadmap
work progresses. An update must follow the development process authoritative at
the time of the change.

Status maintenance must observe these rules:

1. GitHub issue state alone is not proof of implementation acceptance.
2. A roadmap entry may be marked **Complete** only when the issue's accepted
   changes are merged into `main` and any required validation, CI, review, and
   acceptance evidence is complete.
3. **In progress** indicates only that separately authorized work has begun.
4. **Blocked** must identify the unmet predecessor or external condition.
5. **Superseded** must identify the accepted replacement issue or authority.
6. Status changes do not authorize successors unless the applicable official
   process explicitly permits and records that transition.
7. The roadmap should record exact accepted commit references when the
   governing process establishes a durable format for that evidence.
8. Changes to dependencies, capability boundaries, completion criteria, or
   normal-development entry criteria require review against issue #6 scope and
   accepted repository authority.

## Issue scope authority

The detailed objectives, constraints, exclusions, deliverables, acceptance
criteria, and dependency references for each capability are recorded in GitHub
issues #4, #5, and #7 through #12.

This roadmap summarizes and coordinates those issues. Where a summary in this
document conflicts with a valid governing issue or accepted repository
authority, the valid governing source controls and the roadmap must be
corrected through governed development.
