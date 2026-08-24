# External Reconstruction Rule Pack

The executable counterpart is
`ReferenceEvaluator` in
`src/hsr_battle_agent/game_data/external_reconstruction.py`.  This is a pure,
deterministic reference calculator—not a Battle Runtime and not local semantic
proof.

| Rule | Inputs materialized | Scope / guard | Excluded behavior |
| --- | --- | --- | --- |
| Static Loadout | Avatar promotion/level, compatible LightCone, selected Trace status additions, template-checked relic main/sub affixes, caller-supplied static modifiers | Uses ID-preserving records; validates LightCone path, relic slot/level/group, and sub-roll tiers | LightCone effect logic, RelicSet effect logic, Eidolon mechanics, conditional/passive activation |
| Normal damage | ATK/HP/DEF scaling, boosts, DEF/RES/PEN, vulnerability/final/true multipliers, crit mode | Selected optimizer implementation; attacker level must be 80 | skill payload interpretation, target selection, requests, events, HP write/order |
| Break / Super Break | external coefficient, break effect/boost, explicit toughness inputs, damage multipliers | amount-only | Weakness Break state transition/timing, DoT/event scheduling |
| Heal | ATK/HP/flat scaling, outgoing/heal boost | amount-only | HealData creation/consumer, heal cap and CurrentHP write order |
| Shield | DEF/HP/ATK/flat scaling, shield boost | amount-only | shield replacement, absorption, expiry, target timing |

Every result contains an evidence level, reconstruction status, component
values, and an explicit scope.  Do not import a result into `battle_runtime`
as a behavior proof.  Use it only as an external reference, a deterministic
numeric test oracle, or a future compiler input once a corresponding local
Semantic Packet proves the runtime behavior.

The exact source inventory and symbols are emitted to
`data/semantics/4.4.54/external_reconstruction/fribbels_rule_inventory.json`.
