# M12 clean content action census — CR-M12-CLEAN-ACTION-CENSUS-20260926-001

Mechanical discovery only. No production code, no runtime binder, no semantic
inference, no M10/M11 change, no existing M12 record change, no Git write.

- **Starting HEAD:** `fa657f200b615bf5575524d41237365e0196edcc`
- **Branch:** `terra/implementation`
- **Machine-readable output:** `data/content_binding/4.4.54/content_action_closure_census_001.json`
- **Stop condition:** `NO_CLEAN_CONTENT_BODY_FOUND`
- **Next executor:** DS

## Population (the approved join reproduced exactly)

| | |
| --- | --- |
| AvatarConfig skill rows examined | 620 |
| **behavior-root-bound skills** | **528** ✓ (matches the expected population) |
| empty-trigger-key rows excluded | 92 |
| distinct EntryAbilities | 521 |
| roots found in the compiler report | 519 |
| direct body candidates | 3 |
| one-named-edge candidates | 18 |
| ambiguous (multiple named targets → stop) | **305** |

Structural source: `full_content_behavior_compiler_report_001.json` (342 MB,
**14,042 records streamed** in bounded memory — the same schema as the 553-record
`behavior_compiler_report_001.json`, but covering all avatars; the 553-record file
turns out to cover only **two** avatar ability containers, Natasha and Black Swan).

## Classification result

| Class | Count |
| --- | --- |
| CLASS_A_DIRECT_CLEAN | **0** |
| CLASS_B_ONE_EDGE_CLEAN | **0** |
| CLASS_C_SETTLEMENT_SHAPE_PRESENT_BUT_RUNTIME_INPUTS_NEEDED | **0** |
| CLASS_D_STRUCTURALLY_BLOCKED | **7** |
| CLASS_E_NO_REF02_RELEVANT_BODY | **521** |

**At least one CLASS_A/B/C candidate exists: NO.**

## The decisive numbers

- **Only 7 of 528 behaviour-root-bound skills reach a body containing a REF02-relevant operation** — 1 `HEAL_REQUEST` (`HealHP`) and 6 `DAMAGE_REQUEST` (`DamageByAttackProperty`). All 7 are CLASS_D.
- **427 of 528 roots are `compile_status: REJECTED`**, and **429 of 528 bodies carry at least one `REJECT_NOT_NOOP` blocker**. The dominant constraint is compiler rejection, not the absence of a settlement shape.
- **94 bodies have zero blockers — and not one of them contains a REF02 settlement operation.** Cleanliness and settlement shape never co-occur in this population.
- Feature counts across the 528: `WaitAnimState REJECT_NOT_NOOP` **429**, additional top-level `TriggerAbility` **310**, `BOUND_UNEXECUTABLE_PACKET` **298**, `PredicateTaskList` **213**, `AddModifier` **182** (of which **181** carry a `reference_execution_blocker`), `SkillPerformFinish` **16**, `ModifySPNew` **12**, `DispelStatus` **7**, `ByRandom` retarget **7**, damage **6**, heal **1**, toughness-related **0**.
- Root compile-status distribution: `REJECTED` 427, `COMPILED_STRUCTURE_ONLY` 91, `STATIC_DOCUMENT_ONLY` 5, absent 5.
- CLASS_E sub-reasons: multiple named targets 305, root has neither settlement op nor named edge 197, body reached but no settlement op 14, root absent from report 5.

## Packet-kind mapping (§6)

**`NO_PACKET_KIND_MAPPING_FOUND`** — for every operation type and compiler kind.
All eight pairwise searches return zero non-audit files:

| Pair searched | Non-audit files |
| --- | --- |
| `PacketKind` + `DAMAGE_REQUEST` | 0 |
| `PacketKind` + `HEAL_REQUEST` | 0 |
| `ORDINARY_DAMAGE` + `DamageByAttackProperty` | 0 |
| `EXPLICIT_HEAL` + `HealHP` | 0 |
| `PacketKind` + `HealHP` | 0 |
| `PacketKind` + `DamageByAttackProperty` | 0 |
| `ORDINARY_DAMAGE` + `DAMAGE_REQUEST` | 0 |
| `EXPLICIT_HEAL` + `HEAL_REQUEST` | 0 |

`HealHP` was **not** inferred to mean `EXPLICIT_HEAL`, and `DamageByAttackProperty`
was **not** inferred to mean `ORDINARY_DAMAGE`.

## Top 20 shortlist

Ranking is `CLOSURE_ENGINEERING_PRIORITY`, not gameplay quality, and follows the
brief's order exactly: class → fewer blockers → fewer runtime inputs → stronger
version provenance → AvatarID → SkillID.

| # | Class | Avatar/Skill | Trigger | Effect body | Blockers | Ops | REF02 ops |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | D | 1211 / 121101 | Skill01 | `Avatar_Bailu_00_Skill01_Phase02` | 2 | 4 | 1 damage |
| 2 | D | 1105 / 110502 | Skill02 | `Avatar_Natasha_00_Skill02_Phase02` | 3 | 8 | 1 heal |
| 3 | D | 1303 / 130304 | SkillP01 | `Avatar_RuanMei_PassiveSkill01` | 4 | 26 | 1 damage |
| 4 | D | 1413 / 141301 | Skill01 | `Avatar_Evernight_00_Skill01_Phase02` | 4 | 6 | 1 damage |
| 5 | D | 1415 / 141508 | Skill11 | `Avatar_Cyrene_00_Skill11_Phase02` | 8 | 11 | 2 damage |
| 6 | D | 1404 / 140409 | Skill21 | `Avatar_Mydeimos_00_Skill21_Ability` | 14 | 12 | 2 damage |
| 7 | D | 1212 / 121209 | Skill21 | `Avatar_Jingliu_00_PassiveAtkReady_Ability` | 30 | 27 | 1 damage |
| 8–20 | **E** | e.g. 1001/100101, 1002/100207, 1003/100307 … | — | zero-blocker bodies with **no** settlement operation | 0 | 2–5 | 0 |

**Ranks 8–20 are CLASS_E and are not settlement candidates.** They are listed only
because the brief asked for at least 20 rows and only 7 settlement-bearing bodies
exist; each is annotated in the JSON as `"Not a settlement candidate."`

No row is called safe to execute.

## Natasha 110502 reference position

**Rank 2 of 528, CLASS_D_STRUCTURALLY_BLOCKED** — ranked on mechanical merit, **not**
special-cased upward. Bailu 121101 outranks it on the brief's own second
criterion (2 blockers vs 3). Confirmed blockers: the three `WaitAnimState`
`REJECT_NOT_NOOP` waits, the `AddModifier` unsupported packet, the `ByRandom`
retarget, the `DispelStatus` sibling, `compile_status: REJECTED`, and the unmapped
`kind`. It remains the **only** `HEAL_REQUEST` body in the entire population, and
its heal operation is the only settlement operation anywhere that the compiler
marks `MODELLED` with an `EXECUTABLE_REFERENCE` disposition.

## Field precheck (§7)

There are no CLASS A/B/C candidates, so the precheck was built for the 7
settlement-bearing bodies anyway. Mechanical result per body: `kind` **UNMAPPED**;
`source_id`/`targets`/`resource_cost`/`resource_owner` **RUNTIME_INPUT**;
`base_value` **RUNTIME_INPUT** for the heal body (existing
`heal_formula_type4_ordinary`) and **UNSUPPORTED** for the 6 damage bodies because
no local damage formula exists; `factors`/`survival_closed`/`events_closed`/
`task_id`/`task_owner` **LOCAL_ORCHESTRATION**; `toughness_delta`
**LOCAL_ORCHESTRATION** for the heal and **UNMAPPED** for damage. No packet value
was synthesised.

## Version / provenance

Every selected body carries `version_relation: CLOSE_4.4.0_TO_4.4.54` from the
pinned TurnBasedGameData commit `b11066be…`; the static side is exact 4.4.54
(Nanoka SQLite) for all 528 rows. **No CLOSE_VERSION evidence was upgraded to
exact.** Note the archive path label caveat applies as before: the
`data/raw/4.4.54/*` reverse artifacts declare game version 4.4.54 while their
source archive path sits under `StarRail_4.4.53`.

## Why the census is not exhaustive

305 roots (58%) name **more than one** top-level `TriggerAbility` target, and the
brief's §3 stop rule requires the census to record ambiguity and stop. 288 of those
roots are already `REJECTED`, but the remainder were not explored further, so a
settlement-bearing body might exist behind a second named edge. This is recorded as
a scope limit, not as evidence of absence.

## Validation performed

JSON parses; duplicate-key validation PASS. The 528-row population reproduces. All
519 reported EntryAbilities exist in the report; all 20 named targets exist
(0 absent). Operation counts, compiler statuses and dispositions reproduce.
Class rules and the ranking key are deterministic and are published in
`classification_rules`. All cited hashes recompute. No production code, no existing
M12 record and no frozen authority was modified; read-only Git was used only for
`rev-parse`/`branch`/`status`/`log`.
