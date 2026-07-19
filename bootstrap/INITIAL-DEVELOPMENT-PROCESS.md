# Initial Development Process

## Purpose

This provisional process governs development after repository bootstrap and
before a more specific approved process supersedes it.

## Authority hierarchy

1. The **Session Continuity Framework (SCF)** is the overall framework.
2. **SCF Contract Foundation** is its nested foundational specification.
3. `authority/core/SCF-CORE.json` is the bootstrap foundational authority for
   governed development.
4. Lower-level artifacts may refine that authority but may not silently
   contradict, rename, or replace it.

## Development flow

1. Create a GitHub issue defining the high-level work scope, governing
   constraints, and acceptance criteria.
2. Create a working branch from `main` associated with that issue.
3. Perform the work entirely within the working branch.
4. Open a pull request linking the proposed changes to the governing issue.
5. Review the pull request against the issue scope and applicable repository
   authority.
6. Merge the pull request into `main` only after it is accepted.

## Authority boundaries

GitHub issues define approved high-level work scope but do not themselves
modify repository authority.

Working branches are provisional implementation domains. Development methods,
planning structures, commits, temporary artifacts, and other branch-local
processes remain implementation concerns unless separately accepted as
repository authority.

Pull requests are proposed authority transitions.

Only reviewed and accepted changes merged into `main` become authoritative
repository state.

## Constraints

Every pull request must identify its governing issue, remain within the
approved high-level scope, and demonstrate satisfaction of the applicable
acceptance criteria.

Work that materially exceeds or changes the governing issue scope requires the
issue to be revised or a new issue to be created before that work is merged.

## Bootstrap exception

This change is the final bootstrap exception. It establishes the issue-based
development process used for all subsequent repository changes.

After this change is merged, every repository modification shall originate
from a GitHub issue and proceed through an isolated working branch and pull
request before entering `main`.
