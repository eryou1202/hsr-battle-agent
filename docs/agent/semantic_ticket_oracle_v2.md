# Semantic Ticket Impact — Nanoka Content Database

This is the local-ticket update after adopting a version-aligned external
oracle.  It changes the static-data route only: Nanoka content is a reference
oracle, never a local dynamic semantic proof.

## Status changes

| Old ticket family | New status | Reason / next boundary |
| --- | --- | --- |
| `CT-SRC-01..02` | `DEFER_VALIDATION` | Local framing is useful for C2/C3 validation, but not a prerequisite for usable static content.  CT-SRC-02 directory evidence remains valid. |
| `CT-AVA-01..09` | `CLOSED_EXTERNAL_RECONSTRUCTION_READY` where the 4.4.54 detail covers identity, stats, skill, trace, and Rank 1–6; otherwise `NEEDS_STATIC_RECOVERY` | Import first; use local data only for joins/schema scoring. |
| `CT-LC-01..04` | `CLOSED_EXTERNAL_RECONSTRUCTION_READY` or `DEFER_VALIDATION` | LightCone identity, promotion and refinement facts are static oracle data.  Effect execution remains dynamic. |
| `CT-REL-01..05` | `CLOSED_EXTERNAL_RECONSTRUCTION_READY` for RelicSet/piece/effect facts; `NEEDS_STATIC_RECOVERY` for unexposed affix/roll schema | No blind parser work unless a generated gap demands it. |
| `CT-STAT-01..03` | `DEFER_VALIDATION` | Base/promotion values are imported; local transforms are a later C3 quality task. |
| Monster entity/stat/weakness tickets | `CLOSED_EXTERNAL_RECONSTRUCTION_READY` or `DEFER_VALIDATION` | Use Monster details and group auxiliary data. |
| Monster AI / boss sequencing tickets | `NEEDS_DYNAMIC_SEMANTICS` | Static skill lists do not establish decision order. |
| Static Stage/Wave/Monster/Buff tickets | `CLOSED_EXTERNAL_RECONSTRUCTION_READY` only with a preserved package; otherwise `NEEDS_STATIC_RECOVERY` | Boss/Maze source details are imported without flattening waves. |
| Stage runtime tickets | `NEEDS_DYNAMIC_SEMANTICS` | Spawn timing, transitions, victory/failure event order stay outside the database. |
| Damage / Heal / SP / Energy / Turn / Event / Death / Target legality tickets | `NEEDS_DYNAMIC_SEMANTICS` | External values may guide searches but cannot prove runtime mutation order. |

## Operating rule

For every remaining static ticket, first consult the generated
`nanoka_static_gaps.json`.  Only a gap with a concrete reconstruction impact
may enter the static reverse queue.  For every dynamic ticket, write a
Semantic Packet that labels each claim `EXTERNAL_HINT`, `LOCAL_SUPPORTED`, or
`LOCAL_PROVEN`; no external description may be upgraded to proof.

## Freeze-MVP-01 gate

Static content may enter FREEZE-MVP-01 at C0/C1 when it is version-locked,
provenance-bearing, ID-preserving, and `RECONSTRUCTION_READY`; key corpus
joins should advance to C2/C3 as mismatch evidence warrants.  Dynamic core
semantics still require sufficient local evidence for Damage, Heal, SP,
Energy, Turn/AV, Death/Victory, Target, action legality, and critical Event
ordering before DSH consumes the frozen packet set.
