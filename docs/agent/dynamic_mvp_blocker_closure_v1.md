# Dynamic MVP Blocker Closure v1

Status: `DYNAMIC_MVP_BLOCKERS_CLOSED`
Game version: `4.4.54`
Freeze decision: `FREEZE_MVP_CANDIDATE = YES`

This document is the narrow handoff for a deterministic **standard ordinary
battle MVP**. It does not reopen static-content recovery and does not claim a
general client runtime. The active machine-readable authority is
`data/semantics/4.4.54/dynamic_mvp_v1/`.

## Boundary and closure rule

The supported model has a canonical boundary after an ordinary action's
effects have settled, and before the next ordinary actor is selected. A
mechanism can be reconstruction-closed when internal timing still unknown to
native reverse cannot alter the state visible at that boundary.

| Blocker | Status | Handoff rule |
| --- | --- | --- |
| Positive HealData | `CLOSED_RECONSTRUCTED` | Commit a settled positive heal as `min(max_hp, old_hp + amount)` at `HEAL_COMMIT_BOUNDARY`. |
| Team skill points (native BP) | `CLOSED_LOCAL` | Gate before use, deduct positive cost before effects, add positive gain after effects, clamp. |
| Actor energy (native SP) | `CLOSED_LOCAL` | Ultimate gates on max energy and spends before effects; normal energy gains settle after use and clamp. |
| Ordinary AV recharge | `CLOSED_RECONSTRUCTED` | Refill the acting entity with `UnitActionDelay`, advance/order the ordinary list, then select next actor. |
| HP zero to death | `CLOSED_LOCAL` | Derive ordinary `DEAD` from settled HP zero; exclude from ordinary target/action domains. |
| Target/action legality | `CLOSED_LOCAL` | Apply alive/faction/type filters and resource gates before starting tasks. |
| Wave/terminal | `CLOSED_LOCAL` | After death settlement, next exact wave or victory; all ordinary players dead is defeat. |

There are no `HARD_BLOCKED` standard-MVP blockers. `CLOSED_RECONSTRUCTED`
does not mean that the opaque native event callback has been pretended to be
known; the specific assumptions are in the packets.

## Local evidence used

This closure is based on targeted, bounded local evidence, not a new archive
or native census:

- `real_skill_heal_boundary_30.json` confirms the real Natasha Skill02 task
  path through `HealData` and `EventManager.FireEvent`.
- `mvp_skill_character_component_type_31.json` and its four pre/post xref
  artifacts show `UseSkill` owns the resource-gate and before/after mutation
  hooks.
- `mvp_get_unit_action_delay_31.txt`,
  `mvp_turn_based_game_mode_type_31.json`, and
  `mvp_reset_all_entity_delay_callback_31.txt` establish the local speed,
  delay, reset, and ordering objects.
- `mvp_target_alive_filter_evaluate_31.txt` establishes that configured
  alive-state filtering removes invalid candidates.
- `mvp_ability_component_type_31.json` and
  `mvp_turn_based_game_mode_type_31.json` expose the concrete local HP-change,
  dying, entity-death, wave, and battle-result surfaces.

## DSH implementation sequence

1. Read canonical content / `data/db/hsr_content_4.4.54.sqlite`; do not read
   Nanoka JSON, DesignData bytes, or archive offsets from runtime code.
2. Compile the supported static skills into descriptors following
   `legal_action_semantic_spec_v1.json`.
3. Implement the seven packets in listed order at these boundaries:
   `ACTION_GATE` → `RESOURCE_PRE_COMMIT` → effects / HP commit →
   `RESOURCE_POST_COMMIT` → `ORDINARY_ACTION_COMPLETED` →
   `DEATH_COMMIT` → `TERMINAL_CHECK`.
4. Run the state-diff fixture `semantic_e2e_mvp_v1.json` before expanding the
   supported skill or stage set.

## Explicitly post-MVP

Break, shields beyond supplied amount calculation, follow-up, extra action,
advance/delay, summon timeline, Ultimate insertion, all event-bus ordering,
dynamic target restrictions, revive, special resources, Monster AI selection,
special boss death, and score/mode terminal rules are out of this freeze.

## Historical documents

`data/semantics/4.4.54/dynamic_core/closure_v1.json` and
`docs/agent/handoffs/turn_av_semantics_29.md` remain useful historical proof.
Their old non-freeze/generic-recharge conclusion is superseded only for this
strict standard-MVP profile; do not reinterpret the change as a broad semantic
claim.
