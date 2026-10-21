# R19 Generic Damage Continuation + Property

CR `CR-R19-DAMAGE-CONTINUATION-PROPERTY-20261010-001`. Verdict **GENERIC_DAMAGE_CONTINUATION_REFERENCE_ESTABLISHED**. Starting HEAD `ddd2739ae16daf88b70087b8b82c822036e5461d`, branch `terra/implementation`. Git writes NONE; no live capture/game launch. Frozen M10–M15 and ScenarioCompiler remain unchanged. Preservation verifies 4071 starting files; R18 controls, source pins and handoff CRC/member sizes/hashes PASS.

R19 extends the existing R12 ExpressionIR/evaluator, R15 action scheduler, R17 modifier/event engine and R18 damage transactions. It adds no second runtime, event bus or unsnapshotted property cache. Original real source graphs, unsupported IR envelopes and numeric operands remain intact. No SkillPerformFinish was inserted into real graphs.

## Damage lifecycle and native boundary

The six serialized REFERENCE_MODEL states are REQUEST_CREATED → AMOUNT_EVALUATED → SETTLEMENT_PENDING → HP_COMMITTED → CALLBACKS_PENDING → DAMAGE_REFERENCE_COMPLETE. HP_COMMITTED means provisional storage mutation inside the R18 source transaction; a later primitive gap restores HP, callbacks, modifiers, RNG, queues and lifecycle records together. Earlier committed source tasks persist. Snapshot/clone/hash/resume/replay include pending requests and checkpoints.

R18 ASSERT_OWNED_DAMAGE_DRAINED_REFERENCE is retained and strengthened. It checks current ability and descendants, settlements, owned callbacks/events/continuations, child completion and pending transaction/event mutations. It completes only the finish task/local reference boundary. TASK_COMPLETION, DAMAGE_REQUEST_COMPLETION, DAMAGE_SETTLEMENT_COMPLETION, ABILITY_COMPLETION and ACTION_COMPLETION are separate. Action completion still requires an original source completion request and drained owned work.

The pinned 4.6.51 metadata maps DamagePerformFinish to config type 23016, reader 0x1E5265C0, and fields SkipDeathSettlement/IsFakeAvatarAttack. All 118 selected instances have bitmap 0. Reader/config fields do not prove runtime executor semantics or defaults. Related TurnBasedAbilityComponent.CharmDamagePerformFinish@0xF1418A0 emits an event through 0xE26CD70 → EventManager.FireEvent@0xEF632B0; CharacterHudComponent._OnAbilityDamagePerformFinish@0xEEC5F80 is a related consumer. The exact config/task-to-method join remains UNPROVEN. IFix guard RVA 0x978E100 / patch ID 0x7FC20 and effective Lua Type.Name hook maps remain unbound. Request finalization, settlement waiting, callback/event effects, controller/barrier behavior, bookkeeping and death settlement are UNKNOWN for the effective task. **Native correctness NOT CLAIMED.** Exact blocker: DAMAGE_FINISH_EFFECTIVE_RUNTIME_ORACLE_REQUIRED.

## DynamicFloat and property sources

All four selected unknown programs share `[1,0,0,0,4,17]`: push int32-key lookup, push int64 raw literal, multiply, terminate. Native evaluator 0x1E196300 uses table 0x1E197720; opcode 4 table slot 0x1E197730 points to 0x1E196678 and calls FixPoint.op_Multiply@0x1EC1BCF0 at 0x1E1966B3. The generic family reuses 0/1/2/17 and expands opcode 4 only under explicit R19 policy. Unknown opcodes, malformed indices/stacks/termination and tagged/mixed/overflow domains reject. R12 signed raw int64, scale 2^33, step2 toward-zero quantization and AST evaluation order are preserved.

The four source spans are 10713432–10713452, 11037846–11037866, 11101005–11101025 and 11314173–11314193; source artifacts/hashes, decoded programs and expanded ASTs are in dynamic_program_evidence.json. Their provider key -1126825319 already has raw value 17179869184 in the unchanged R18 fixture. No value was injected or substituted. R19 explicitly binds that existing store. Same-version R11/R11C evidence describes partial unpatched callback/parent/override/scoped lookup order, but active IFix/source identities and initialized effective provider precedence remain unknown.

BASE_PROPERTY, EFFECTIVE_PROPERTY, MODIFIER_CONTRIBUTION, ABILITY_DYNAMIC_VALUE, MODIFIER_LOCAL_DYNAMIC_VALUE, SNAPSHOT_VALUE, CONTEXT_OVERRIDE and UNKNOWN_PROVIDER are explicit runtime source abstractions. Ordered provider policies, missing behavior and evidence labels serialize/hash/replay. R17 already writes additive contributions into property storage: EFFECTIVE_PROPERTY reads once, BASE_PROPERTY subtracts documented contributions, and removal reuses R17 inverse mutation. Active reference modifier IDs/order and aggregation are explicit. The property checkpoint uses real decoded damage with an explicit R17 sandbox contribution: base attack 10 + contribution 3 = effective 13; coefficient 2 gives damage 26 and HP 100 → 74. It is separate from joined skill cohorts.

ByRankActivated's mask 8 decodes TriggerKey StringHash 2089636447, not an ordinal rank. Native comparison/runtime executor semantics remain unknown. Main R18 comparison inputs are preserved and return RANK_POLICY_MISSING; a separate explicit_rank cohort supplies actor rank 0 and keyed threshold 1 under KEYED_THRESHOLD_GE_REFERENCE. It closes that predicate by explicit policy and advances to the next source task. Missing actor rank/keyed threshold remains RANK_INPUT_MISSING. No AvatarID/SkillID dispatch exists.

## Measured results

| Scope | R18 | R19 |
|---|---:|---:|
| A. Isolated original damage primitive | 6/6 | 6/6 |
| B. Same joined roots reaching HP mutation | 11/15, 22 settlements | 15/15, 29 settlements |
| Selected unknown DynamicFloat first gaps | 4 | 0 |
| C. Joined damage lifecycle including original finish | 0/15 | 14/15; 15/15 with separately supplied rank |
| D. Complete joined whole-skill reference transition | 0/15 | 0/15, including rank cohort |
| E. Native validated transition | 0 | 0; NOT CLAIMED |
| Same six nonjoined real ability roots reaching HP | 3/6 | 3/6 |
| Complete original nonjoined ability-root reference actions | 0/6 | 2/6 |

C does not imply D; D does not imply E. Isolated damage wrappers retain R18's explicitly synthetic completion and are excluded from real graph completion claims. The two naturally complete actions are Avatar_AventurineW_00_Skill01_Phase02 and Avatar_TheHerta_00_Skill01_Phase02. Both retain their original real graph and original SkillPerformFinish, all owned work drains, no SemanticGap remains, and source-backed regressions verify snapshot/replay hashes. They are real ability-root actions, **not joined complete skill transitions**.

The three joined cohorts use exactly R18's selected 15 roots: finish-only gives 10 lifecycle closures and leaves four unknown programs; continuation_expression gives 14 closures with no additional state values; explicit_rank gives 15 closures with progression additions recorded separately. Main cohort next blockers: 12 missing Camera catalog entries, one template parameter/context mapping, one missing rank policy, and one skill-tree progression input. Rank cohort leaves 13 missing Camera entries, one template context and one skill-tree input. Per-root audit records HP, finish reach/completion, next task or drained sequence, next exact gap, ability completion, action status and final BattleState hash.

All 118 structurally decoded finish instances were probed. Original graph reach/context-ready/completed: 50. Remaining structure-only-in-original-graph: 68. All 118 pass separately labelled isolated real-finish local assertions in explicit contexts with no injected damage and no inserted completion task; those assertions do not count as damage lifecycle or full skill execution. Native oracle blocked: 118, an overlapping classification. The 116 distinct source roots include basic/skill/Skill03-related, child and maze patterns across many actors. Structural count is not original graph execution count.

Unchanged frozen inputs: 632 combat roots, 160 decoded joined roots, 161 joined rows. Combat tasks reached/completed 1025/494; joined 300/121. Damage attempts/commits 74/0. HP mutations, DamagePerformFinish completions and action completions all 0. First-gap distributions, task metrics and all 632 final BattleState hashes have zero drift from R18. No policies, progression rows or operands were injected into frozen inputs.

## Whole battle reassessment

- **damage_HP**: generic reference formula/HP settlement/lifecycle and transaction engine established; native formula, events, death and defensive rules unresolved.
- **heal**: FormulaType2 reference core and explicit R17 staged heal/event integration; native inputs/provider/listener/settlement still partial; frozen HEAL gaps=4.
- **shield**: full subsystem absent; explicit sandbox bypass only; missing native shield input remains a gap.
- **toughness_break**: full subsystem absent; no toughness mutation/break processing inferred from damage.
- **resources_energy**: explicit actor/team reference stores exist; actual energy/SP costs, gains, listeners, joins not closed; frozen RESOURCE gaps=4.
- **true_turn_AV**: not implemented; R15 logical scheduler is not native turn/AV initiative, ownership or speed engine.
- **modifier_event**: R17 generic reference instances/listeners/contributions/owned callbacks available; native effective instance/listener/provider state unknown; frozen gaps=181 combat/43 joined.
- **Monster_AI**: no independent real-content-driven behavior runtime closure; not investigated or implemented in R19.
- **stage_wave_mode**: full stage/wave/mode runtime not implemented; progression/termination remains separate precise blockers.

Largest raw catalog family remains 145 combat / 75 joined; modifier/event context/state gaps remain 181 / 43. These first-gap counts do not measure unvisited or absent battle subsystems. Recommended next phase is **R20 CORE PROPERTY / RESOURCE ENGINE**, followed by content catalog/reader expansion, true turn/AV foundation, toughness/break/shield, Monster behavior corpus, and targeted effective native oracle closure. See whole_battle_assessment.json for ranking/basis. R20 is not automatically another damage or Natasha follow-up.

## Validation and delivery

Determinism/replay/architecture/preservation PASS. Transaction tests cover post-HP expression/callback gaps, earlier task retention, RNG rollback, finish gaps, multi-target/child continuations, pending work, budget exhaustion and every lifecycle checkpoint. Provider/aggregation/rank tests include missing inputs, ordering/hash changes, R17 contribution and removal, overflow and malformed unknown programs. R12–R19 and FAST_UNIT lanes: R12_R19 265 PASS, battle_ir_FAST_UNIT 586 PASS, battle_runtime_FAST_UNIT 459 PASS, battle_sandbox_FAST_UNIT 918 PASS. Frozen tests remain unchanged.

Production: `src/hsr_battle_agent/battle_runtime/behavior.py`, `src/hsr_battle_agent/battle_runtime/action_scheduler.py`, `src/hsr_battle_agent/battle_runtime/damage_pipeline.py`, `src/hsr_battle_agent/battle_runtime/dynamic_property.py`. Tests: `tests/battle_runtime/test_behavior_r19.py` (32 tests). Controls: five R19 JSON controls listed in the change request. Audit: `tmp/audit/r19_damage_continuation_20261010_001/`.

Reproduce: `python tools/runtime/r19_probes.py`; `python tools/runtime/r19_probes.py --frozen-only`; `python tools/runtime/r19_probes.py --broader-only`; `python tools/runtime/r19_followups.py`; `python tools/runtime/r19_evidence.py`; `python tools/runtime/r19_checks.py final`; `python tools/runtime/r19_finalize.py --package`. The start gate is preserved and must not be regenerated after edits. Native text evidence is bounded to directly relevant pinned methods; no provider/archive/registration discovery or live observation occurred.

Handoff: `D:/HSR_Battle_Agent/agent_handoffs/CR-R19-DAMAGE-CONTINUATION-PROPERTY-20261010-001_changed_files.zip`. Only R19-owned changed production/tests/tools/controls/report/audits, diffs and manifest are included. No binaries/native payloads/dumps/old reverse trees/starting file copies. CRC/member sets/sizes/per-member SHA-256 and ZIP SHA-256 are verified; receipt is external to the ZIP to avoid self-reference. Git writes NONE. Native correctness NOT CLAIMED.
