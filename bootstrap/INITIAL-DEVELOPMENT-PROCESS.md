# Initial Development Process

## Purpose

This provisional process governs development after repository bootstrap and
before a more specific approved process supersedes it.

## Authority hierarchy

1. The **Session Continuity Framework (SCF)** is the overall framework.
2. **SCF Contract Foundations** is its nested foundational specification set.
3. `authority/core/SCF-CORE.json` is the Level-0 root authority for governed
   development.
4. Lower-level artifacts may refine that authority but may not silently
   contradict, rename, or replace it.

## Development flow

1. Create and approve a high-level SCF product design scope.
2. Integrate that scope into `main`.
3. Decompose the approved scope into milestones.
4. Decompose each milestone into phases.
5. Decompose each phase into bounded batches.
6. Implement each batch through a reviewable, reproducible patch.

## Constraints

Do not introduce implementation, runtime architecture, speculative schemas,
CI, milestones, phases, or batches during bootstrap. Every later artifact must
identify its governing authority and remain within its approved scope.

## Bootstrap exception

The existing root commit is a repository seed containing only the MIT license
and placeholder README. The SCF bootstrap commit is a one-time exception to the
milestone/phase/batch hierarchy because that hierarchy does not yet exist. The
exception expires when the bootstrap commit is created.
