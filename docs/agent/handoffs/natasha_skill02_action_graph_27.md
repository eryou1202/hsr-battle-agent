# Natasha Skill02 Action Graph 27

`STATUS = SKILL02_HEALHP_LINKAGE_NOT_FOUND`

This is a targeted content-graph / record-indirection task. It does **not**
recover gameplay semantics or implement Sandbox runtime.

Artifact: `data/raw/4.4.54/natasha_skill02_action_graph_27.json`

---

## Natasha Skill02 record family

| Name | Start | End | Length |
| --- | --- | --- | --- |
| `Avatar_Natasha_00_Skill02_Phase01` | `0xBC9855` | `0xBC995F` | 266 |
| `Avatar_Natasha_00_Skill02_Phase02` | `0xBC995F` | `0xBC9BC8` | 617 |
| `Avatar_Natasha_00_Skill02_Camera_Other` | `0xCCB1CD` | `0xCCB3FF` | 562 |
| `Avatar_Natasha_00_Skill02_Camera_Self` | `0xCCB3FF` | `0xCCB518` | 537 |
| `Avatar_Natasha_00_Rank01_InsertSkill_Phase02` | `0xBCA7E5` | `0xBCAB38` | 851 |

## Phase02 child/reference model

- `UNKNOWN`
- Phase02 contains string-like references and modifier names, but no
  structurally valid selector-7 HealHP action node was found in the bounded
  records.

## Structural selector-7 hits

- None valid.
- Raw `0x07` bytes exist as string lengths / false positives, not as
  structurally valid `HealHP` action nodes in the proven polymorphic family.

## Exact HealHP node location

- **Not found.**

## Parent → HealHP proof

- Not established.

## HealHP node boundary

- N/A.

## Populated field presence

- Not decoded.

## Target config status

- `NOT_DECODED`

## Amount-field structural status

- `NOT_DECODED`

## Remaining single blocker

- `SKILL02_HEALHP_LINKAGE_NOT_FOUND`

## Blocker boundary

Resolution stops at the Natasha Skill02 phase/action container encoding: the
phase records do not contain an inline selector-7 HealHP action node, and the
outer ability/action container that links Skill02 to a HealHP node is not yet
resolved.

## Recommended next step

Map the outer ability/action container for `Avatar_Natasha_00_Ability.json`
and its Skill02 action references (string-keyed or object-table indirection),
then follow the reference to the selector-7 HealHP node.
