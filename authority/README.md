# SCF authority

This directory contains Session Continuity Framework authority artifacts.

`level-0/SCF-LEVEL-0.json` is the durable Level 0 root proposed by Issue #5.
It defines the smallest indivisible architecture invariant set that constrains
all lower-level specifications and conforming implementations.

`core/SCF-CORE.json` remains historical bootstrap foundational authority. It is
the provenance source for Level 0, but it is not Level 0's normative parent and
is not the permanent Level 0 artifact.

Lower-level authority may refine accepted higher-level authority but may not
contradict, override, silently replace, or rename it.
