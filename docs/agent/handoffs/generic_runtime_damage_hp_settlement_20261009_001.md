# R18 Generic Damage + HP Settlement

CR `CR-R18-DAMAGE-HP-SETTLEMENT-20261009-001`. Verdict **GENERIC_DAMAGE_HP_REFERENCE_PIPELINE_ESTABLISHED**.

Starting HEAD `ddd2739ae16daf88b70087b8b82c822036e5461d`, branch `terra/implementation`. Git writes NONE. SHA-256 preservation covers frozen M10–M15, ScenarioCompiler, strict admission, approved R12–R17 and unrelated dirty files. R17 archive CRC/member-set/member-hash verification PASS.

The existing generic runtime now executes the original decoded damage task through DamageRequestIR, explicit reference formula evaluation, R17 dispatch/R15 owned callback drain and persistent HP property settlement. Source tasks remain unchanged, including their UnsupportedSemanticIR envelope; R18 admits them only under exact caller-authored source-hash/mask policies. No character-specific handler or second runtime/event bus is introduced.

All **207** unique frozen DamageByAttackProperty instances have bounded decoded TaskConfig/target/AttackData records, covering **9** task bitmap shapes. No new reader was needed. The audit retains exact shard/record/artifact SHA-256, version, span, reader references, expressions, flags, nested structures and unknown fields. Native AttackData formula roles remain unknown. Masks selected by fixtures are explicitly sandbox roles, not semantic names inferred from numerical values. Unknown DynamicFloat programs are never replaced with literals.

The numeric contract reuses R12 mode0 raw signed int64 arithmetic, scale 2^33, representable step 2. Binary AST order is explicit; multiply/divide quantize toward zero after each operation. Tagged/mixed domains, overflow and division by zero return typed gaps. Negative behavior and final raw/whole-HP rounding require explicit reference policies. Historical 4.4.54 evidence is architectural background only; no historical damage formula/constants are transferred into native 4.6.51 claims.

The six configurable stages are BEFORE_DAMAGE, DAMAGE_AMOUNT_MODIFICATION, BEFORE_HP_MUTATION, HP_MUTATION, AFTER_HP_MUTATION and AFTER_DAMAGE. Native IDs/order and effective listeners remain unknown. Fixtures declare every event stage and the active reference listener scope. Exact callback targets, event payloads, callback hashes and serialized R17 listener aggregation permit pending amount changes. All callbacks, child abilities and continuations stay under R15 ActionExecutionRoot.

A source-task transaction snapshots before TaskFrame creation and executes only its descendant work until commit. A SemanticGap restores HP, modifier/listener effects, event registration, RNG, scheduler additions and damage histories together; earlier committed tasks remain. Retry re-enters the original source task. Budget-suspended requests/callbacks/checkpoints remain cloneable, hashable and resumable. Ordered targets, explicitly allowed duplicates and separately serialized source requests produce per-target settlement records.

HP settlement validates entity/property identities and initial HP/max HP, caps applied damage at current HP and records effective amount, pre/post HP, applied delta and overkill. Life state changes only under explicit policy. Shield bypass, no toughness mutation, no break processing and no resource/death/battle-end processing are individually declared sandbox boundaries. Missing/unknown policies are typed gaps. No shield amount is inferred as HP and no toughness is inferred from HP damage.

DamagePerformFinish has 118 unique frozen structural instances. Native signal meaning remains unknown. An exact reference local damage-drain assertion is available, and tests prove it does not request ability/action completion. Source graph probes receive no fabricated SkillPerformFinish.

| Completion category | Result |
|---|---:|
| ISOLATED_REAL_DAMAGE_PRIMITIVE | 6 / 6 (7 target settlements) |
| Explicit real damage + R17 amount callback checkpoint | 1 / 1 |
| REAL_GRAPH_PREFIX_HP_MUTATION — selected ability graphs | 3 / 6 |
| REAL_GRAPH_PREFIX_HP_MUTATION — actual joined skill roots | 11 / 15 (22 settlements) |
| FULL_REAL_SKILL_REFERENCE_TRANSITION — actual joined probes | 0 / 15 |
| Native skill correctness | NOT CLAIMED |

The isolated wrappers contain an explicitly synthetic completion node; this does not change real source graphs or count as whole-skill completion. Selected ability-graph probes and joined skill probes retain their own denominators. The joined tests exercise real Skill01/Skill02 roots and child ability invocation where source provides it, and all 15 still return SemanticGap: ten DamagePerformFinish blockers, four unknown DynamicFloat programs and one ByRankActivated progression predicate.

| Unchanged frozen input | R17 | R18 |
|---|---:|---:|
| Combat roots / decoded joined roots / joined rows | 632 / 160 / 161 | 632 / 160 / 161 |
| Combat tasks reached / completed | 1025 / 494 | 1025 / 494 |
| Joined tasks reached / completed | 300 / 121 | 300 / 121 |
| Combat / joined first DAMAGE blockers | 74 / 15 | 74 / 15 |
| Damage operations attempted / committed | 74 / 0 | 74 / 0 |
| Roots reaching HP mutation / action completions | 0 / 0 | 0 / 0 |

Frozen task counts, first-gap families, primitives and unrelated diagnostics have zero drift. The 74 DAMAGE capability strings now accurately identify missing explicit reference inputs instead of an absent implementation; 15 affect joined roots. No damage properties/policies were added to frozen inputs. Expanded corpora and synthetic wrappers are not merged into 632/160 denominators.

| Real source fixture | Amount (HP units) | HP before → after |
|---|---:|---|
| Avatar_AventurineW_00_Skill01_Phase02 → b | 20 | 100 → 80 |
| Avatar_Serval_Skill02_Phase02 → b | 30 | 100 → 70 |
| Avatar_Anaxa_00_Skill03_Phase02 → b | 40 | 100 → 60 |
| Avatar_Argenti_00_Skill01_Phase02 → b | 50 | 100 → 50 |
| Avatar_Argenti_00_Skill01_Phase02 → c | 50 | 100 → 50 |
| Avatar_Acheron_00_Skill01_Phase02 → b | 60 | 100 → 40 |
| Avatar_TheHerta_00_Skill01_Phase02 → b | 70 | 100 → 30 |

The explicit event checkpoint uses the unchanged AventurineW decoded task and an explicitly synthetic R17 active listener/callback. Base damage 20 becomes 25 by exact callback addition; HP 100 → 75, one owned modifier callback drains, and clone/restore/replay hashes match. The listener is never labelled as native or source-recovered.

Structured controls include first-gap distributions, task counts, raw input bindings, full settlement records, source pointers and narrowly scoped oracle tickets. Native operand roles, rounding, critical sampling, defensive ordering, event IDs/listeners, multi-hit splitting, death/overkill and DamagePerformFinish consumers remain ticketed.

Largest raw blocker: CONTENT_CATALOG_BINDING, **145 combat / 75 joined** (weighted score 295). Modifier/Event is largely missing reference/native state (181 / 43). Recommend **R19 DAMAGE FOLLOW-UP / PROPERTY PIPELINE** from measured explicit prefixes: resolve selected exact DynamicFloat programs and DamagePerformFinish local lifecycle evidence, with catalog reader closure as an independent content backlog. No automatic Natasha selection, resource engine, shield/break subsystem or invented Turn/AV model.

Tests: R12_R18: 233 PASS, battle_ir_FAST_UNIT: 586 PASS, battle_runtime_FAST_UNIT: 427 PASS, battle_sandbox_FAST_UNIT: 918 PASS. Determinism/replay/architecture/preservation PASS. R18 adds 48 focused tests; frozen tests are unchanged.

Production files: `src/hsr_battle_agent/battle_ir/behavior.py`, `src/hsr_battle_agent/battle_runtime/behavior.py`, `src/hsr_battle_agent/battle_runtime/behavior_state.py`, `src/hsr_battle_agent/battle_runtime/action_scheduler.py`, `src/hsr_battle_agent/battle_runtime/damage_pipeline.py`.
Tests: `tests/battle_runtime/test_behavior_r18.py`.
Controls: `data/control/generic_runtime_damage_pipeline_v1_20261009_001.json`, `data/control/generic_runtime_hp_settlement_v1_20261009_001.json`, `data/control/generic_runtime_damage_support_census_v1_20261009_001.json`, `data/control/generic_runtime_support_census_v8_20261009_001.json`, `data/control/generic_runtime_semantic_gap_ledger_v6_20261009_001.json`.
Audit: `tmp/audit/r18_damage_hp_settlement_20261009_001/`.

Reproduce: `python tools/runtime/r18_probes.py --explicit-only`; `python tools/runtime/r18_probes.py --frozen-only`; `python tools/runtime/r18_followups.py`; `python tools/runtime/r18_checks.py final`; `python tools/runtime/r18_finalize.py --package`. Start-gate hashes must already exist before edits. Scripts preserve R17 controls/audits and perform only read-only Git commands.

Handoff destination: `D:/HSR_Battle_Agent/agent_handoffs/CR-R18-DAMAGE-HP-SETTLEMENT-20261009-001_changed_files.zip`. Only R18-owned changed files, parsed selected-record/reference evidence, controls, receipts, diffs and manifest are packaged; binaries, whole raw payloads, dumps, previous audit trees and starting file copies are excluded. Verification records exact ZIP member set, CRC, sizes, every member SHA-256 and archive SHA-256.
