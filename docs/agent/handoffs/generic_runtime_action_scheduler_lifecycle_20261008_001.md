# R15 Action Execution Scheduler + Lifecycle

CR `CR-R15-ACTION-EXECUTION-SCHEDULER-LIFECYCLE-20261008-001`. Verdict **ACTION_SCHEDULER_REFERENCE_MODEL_ESTABLISHED**.
Starting HEAD `ddd2739ae16daf88b70087b8b82c822036e5461d`; branch `terra/implementation`. Git writes: NONE. M10–M15, ScenarioCompiler, R14 controls and unrelated tracked dirty files preserved (hash audit PASS).

ACTIONS are planner-visible invocations in the existing evidence-aware BehaviorRuntime. ACTION_EXECUTION_SCHEDULER is REFERENCE_MODEL; BATTLE_TURN_SCHEDULER remains NOT_YET_BOUND_FROM_REAL_CONTENT. No turn/AV/insertion mechanics or character execution subclasses were added.

Frozen R14 baseline: 632 combat roots, 4555 tasks; 1579 scheduler/lifecycle instances across 406 roots, 114 joined roots containing those tasks, 45 joined roots first blocked at a scheduler primitive. Counts: {'SkillPerformFinish': 111, 'TriggerAbility': 444, 'WaitAnimState': 762, 'WaitSecond': 226, 'WaitTimelineFinish': 36}. This union includes TriggerAbility, whereas the old SCHEDULER taxonomy has 1,137 instances/373 graphs; neither count replaces the other.

The frames are JSON value records with monotonic explicit IDs, snapshot/clone/stable_hash APIs and replay through the same engine. Sequence cursors wait for primitive completion. TriggerAbility creates a scheduled child with explicit inherited context and FIRE_AND_CONTINUE_REFERENCE / WAIT_CHILD_REFERENCE / WAIT_CHILD_TREE_REFERENCE relationships. Controller, owner/caster, targets, ParamEntity stack, dynamic provider parent, RNG sharing, event scope and resume policy are serialized and hashed. Unknown masks/child references remain typed gaps.

Ready task continuations run before owned events/callbacks, then child activation, then the next logical-time continuation. Enqueue ordinals break ties. Event expansion is resumable and budgeted. Callback children retain action ownership and source event; modifier callback owner/caster and nested callbacks are tested. Other actions’ queued work does not keep this action open.

WaitSecond evaluates an executable duration under SERIALIZED_RAW_REFERENCE_UNITS. Logical time is a nonnegative arbitrary-precision integer; serialized fixed-point tagged/overflow operands retain the existing numeric gaps. WaitAnimState/WaitTimelineFinish are explicit barrier fences, logical delays, external barriers, or gaps. No sleep/FPS conversion/native unit claim. Presentation classifications are authored synthetic scenario assumptions, backed only by structural identity, not native irrelevance proof. Movement requires integer modeled position and continuation. STATE_RELEVANT tasks retain generic dispatch.

SkillPerformFinish records COMPLETION_REQUEST. Task, ability and action completion are distinct. Root requests do not skip suffix tasks or settlement callbacks; all same-action owned work must drain. Persisted future-turn modifiers do not keep an action open. DamagePerformFinish remains structure-only: its empty serialized bitmap and R14 census do not prove native settlement. Unsupported primitives atomically discard candidate state, preserving scheduler cursor, context, RNG and prior successful work.

Deterministic budgets bound total/frame/task transitions, callback enqueue/activation, child invocations and time advances. Ability/template/task/callback paths have cycle/depth guards; repeated zero-delay event/schedule ancestry returns a typed gap. Budget exhaustion is EXECUTION_BUDGET_EXHAUSTED and resumes from snapshots.

| Combat probe metric | R14 rerun | R15 |
|---|---:|---:|
| tasks_reached | 332 | 1006 |
| tasks_completed | 17 | 484 |
| abilities_invoked | 0 | 28 |
| child_abilities_completed | 0 | 0 |
| barriers_encountered | 0 | 231 |
| callbacks_completed | 0 | 0 |
| logical_time_advances | 0 | 231 |
| ACTION_REFERENCE_COMPLETE | 0 | 0 |

All 632 roots rerun from hash-checked frozen R14 IR. Adapter crashes: 0. R15 reaches damage in 72 roots; no damage evaluator. {'SEMANTIC_GAP': 581, 'WAITING_SCHEDULER': 51}. The 51 drained roots without a root finish request stay WAITING_SCHEDULER, not false completion. Timings: {'after': 115.84800600000017, 'before': 17.076787300000433}; catalog verification is outside drive timing. Full raw per-root results and frozen first-gap distribution are in audit. Reach/completion counts are execution occurrences; static serialized census deduplicates physical spans. R14 completed task counts exclude absent handler attempts, while R15 adds failed task attempts to reach counts.

Skill view: 160 unique decoded joined roots / 161 joined rows. Started 160; child reached 22; damage 14; heal 0; modifier operations 43; finish 0; action complete 0. Prefix tasks completed 4 → 114. These are synthetic probes, not executable native skills.

Natasha Skill02 Phase01: 0 top-level tasks completed under WAIT_CHILD_TREE, child invocations 1, nested abilities ['ability:Avatar_Natasha_00_Skill02_Phase02']; 3 descendant tasks completed, 2 waits; first remaining gap `explicit actor progression rows` at `RPG.GameCore.BySkillPointActivated`; action complete NO. Its parent TriggerAbility remains suspended rather than being prematurely counted complete.

Non-Natasha full-root fixtures and isolated exact real IR nodes are recorded separately. The isolated nodes use synthetic wrapper sequences and an explicit synthetic modifier registration; their completion is not added to whole-root corpus completion. No full joined root reaches WaitTimelineFinish in this probe, so its preserved real-node regression supplies coverage without inventing reachability.

| Isolated real-node pattern | Source root | Result |
|---|---|---|
| LINEAR_FINISH | Avatar_Acheron_00_Skill01_Phase02 | ACTION_REFERENCE_COMPLETE |
| TriggerAbility | Avatar_Ashveil_00_Skill01_Phase01 | SEMANTIC_GAP |
| WaitSecond | Avatar_Bailu_00_Skill02_Phase01 | ACTION_REFERENCE_COMPLETE |
| WaitAnimState | Avatar_Anaxa_00_Skill01_Phase01 | ACTION_REFERENCE_COMPLETE |
| WaitTimelineFinish | Bronya_00_Skill03_Phase01 | ACTION_REFERENCE_COMPLETE |
| MODIFIER_CALLBACK | MAvatar_Acheron_00_PointB3_DamageUp | SEMANTIC_GAP |
| DamageByAttackProperty | Avatar_Acheron_00_Skill01_Phase02 | SEMANTIC_GAP |

Post-R15 first-gap priority (combat + twice joined-root blockers):

- CONTENT_CATALOG_BINDING: combat 161, joined 83, score 327.
- MODIFIER_EVENT: combat 180, joined 43, score 266.
- OTHER_SEMANTICS: combat 103, joined 6, score 115.
- DAMAGE: combat 72, joined 14, score 100.
- PREDICATE_PROGRESSION: combat 25, joined 7, score 39.
- PROPERTY_DYNAMIC_PROVIDER: combat 23, joined 2, score 27.
- ACTION_EXECUTION_SCHEDULER: combat 6, joined 3, score 12.
- HEAL: combat 4, joined 0, score 4.
- RESOURCE: combat 4, joined 0, score 4.
- POSITION: combat 3, joined 0, score 3.

Recommended **R16 CORPUS READER EXPANSION**, targeted to exact missing referenced child abilities, with MODIFIER/EVENT ENGINE next. Missing catalog references dominate joined roots; modifier lifecycle is the largest combat family. Damage is now observable in 72 combat/14 joined roots but is not yet the dominant first gap. Do not choose turn/AV.

Six narrow oracle tickets cover invocation flags, animation release, duration units, timeline finish, finish after-end ownership and DamagePerformFinish; each records frequency, affected roots and minimum native evidence. No live capture or whole-character reverse request.

Validation: determinism PASS; replay PASS; architecture PASS. Full ExecutionResult including pending-frame journal and canonical snapshots/hashes are compared across clones/restores. Unit checks also cover RNG rollback, action-owned and child-owned callback drains, persistent modifiers, position rollback, external barrier release, budgets and zero-delay cycles.

- R12_R13_R14_R15: 121 tests, return code 0, PASS.
- battle_ir_FAST_UNIT: 586 tests, return code 0, PASS.
- battle_runtime_FAST_UNIT: 315 tests, return code 0, PASS.
- battle_sandbox_FAST_UNIT: 918 tests, return code 0, PASS.

The initial battle_ir baseline had five sandbox-temp permission errors; the workspace TMP/TEMP rerun passed all 586. Final FAST_UNIT uses that same workspace temp root.

Production files:

- `src/hsr_battle_agent/battle_runtime/behavior.py`
- `src/hsr_battle_agent/battle_runtime/behavior_state.py`
- `src/hsr_battle_agent/battle_runtime/action_scheduler.py`

New test: `tests/battle_runtime/test_behavior_r15.py`. Reproducible audit entry points: `tools/runtime/r15_scheduler_probes.py`, `r15_scheduler_regressions.py`, `r15_scheduler_finalize.py`. Required three controls accompany this report. Handoff contains only CR-owned files plus a manifest; no source game payloads or old reverse trees. ZIP CRC, exact members, uncompressed sizes, member SHA-256 and ZIP SHA-256 are verified by the finalizer.
