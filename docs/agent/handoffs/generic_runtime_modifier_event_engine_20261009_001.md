# R17 Generic Modifier + Event Reference Engine

CR `CR-R17-MODIFIER-EVENT-ENGINE-20261009-001`. Verdict **GENERIC_MODIFIER_EVENT_REFERENCE_ENGINE_ESTABLISHED**.
Starting HEAD `ddd2739ae16daf88b70087b8b82c822036e5461d`, branch `terra/implementation`. Git writes NONE. Frozen M10–M15, ScenarioCompiler, strict M15 admission, previous R12–R16 artifacts/tests and unrelated dirty files are SHA-256 preserved. The five R17 production edits extend the same BehaviorRuntime/state and R15 scheduler.

The exact unique modifier definition census is **296**, with **153 directory definitions and 143 inline bodies**. A preliminary 439 typed graph-node count included 143 reader envelopes; those are excluded from the final definition count. The 94 R16 newly decoded directory graphs are inherited, never added to the corpus count a second time. R17 decodes zero new structural roots. Definitions retain source version, pinned artifact/hash, exact span, graph hash, config identity, native reader references, compiled callback tasks, decoded fields and unknown fields. All 296 are exercised by state binding/clone tests. Binding creates no active instance.

The reference AddModifier pipeline resolves an exact source-backed definition and explicit operands, then applies insert, refresh, replace, increment-stack or reject-duplicate policy. Numeric native policies remain raw data. Match identities explicitly preserve owner, caster, original caster, source ability and target; cross-source updates require a preservation policy. Activation and refresh callbacks need explicit policies. Dynamic initialization uses the caller-selected source provider; callbacks use explicit modifier-local/snapshot/source precedence. Refresh provider preservation/rebinding is explicit. Selected property snapshots and reversible additive reference contributions persist in instance state. This aggregation model claims no native equivalence.

Listener IDs, priority, owner/caster/source context, predicates, callback targets and exact compiled callback IR are serialized in each instance. Numeric callback flags remain opaque explicit reference data and are never mistaken for predicates. Dispatch constructs context-rich wrappers and uses the existing R15 event queue, CallbackFrame, task sequences, budgets and ActionExecutionRoot. Nested callbacks retain current action ownership. Logical expiry and opaque event expiry are explicit reference policies; real battle turn/AV mechanics are absent. Removal updates the active store, listeners, reversible contributions and tombstones; pending callbacks explicitly retain dispatch snapshots or cancel work that has not started. Running continuations remain resumable.

Every R15 transition executes on a cloned candidate state. A SemanticGap discards that primitive's state/RNG/listener/stack changes and keeps the earlier committed continuation. Retrying a suspended unsupported callback neither loses it nor repeats committed tasks or RNG draws. Callback-depth, task-depth, repeated-path cycle and WorkBudget guards remain in R15. Installed future-lifetime modifiers do not hold their originating action open; callbacks currently owned by that action do until drained. Definitions, instances, dynamic/snapshot stores, listeners, contribution records, pending callback IDs and reference policy identities all participate in clone/snapshot/restore/hash/replay.

Explicit heal stages can dispatch and drain callbacks in caller-declared pre-heal, effective amount, settlement, HP mutation and post-heal order. Damage has generic explicitly configured event points only. Native event IDs/order and complete damage formulas remain unresolved.

| Unchanged frozen fixture | R16 | R17 |
|---|---:|---:|
| Combat roots | 632 | 632 |
| Joined decoded skill roots / rows | 160 / 161 | 160 / 161 |
| Combat Modifier/Event first gaps | 181 | 181 |
| Joined Modifier/Event first gaps | 43 | 43 |
| Combat tasks reached | 1025 | 1025 |
| Combat tasks completed | 494 | 494 |
| Child abilities invoked / completed | 44 / 0 | 44 / 0 |
| Whole action reference completions | 0 | 0 |
| Joined task_list/0 AddModifier inputs | 41 | 41 |
| Joined task_list/0 dynamic provider inputs | 3 | 3 |

No modifier application input is fabricated in the frozen fixture. Exact first-gap and metric drift is empty. Frozen clone/restore checkpoints pass. The inherited R16 expanded-only 149 roots are rechecked separately under `NEW_EXPANDED_CORPUS`; they are never counted in the 632/160 denominators.

Each of the 41 joined AddModifier input roots has a detailed source/target/owner/caster/provider/policy/listener row. **40** have an exact definition and complete application/activation/registration in an independently labelled explicit sandbox fixture. **1** (`Avatar_Aventurine_00_PassiveSkill01`) lacks the exact config in current decoded files. **0** frozen roots are genuinely unblocked and all **41** remain native-effective unknown. Giving only the first application policy to their original full roots produces **38 WAITING_SCHEDULER** outcomes (ability bodies complete without a serialized finish request), **2 SemanticGaps**, and no whole-skill completion. No finish node is inserted in those full roots.

Separate explicit categories and denominators:

- 40 isolated real AddModifier wrappers: {'ACTION_REFERENCE_COMPLETE': 40}; committed target applications 40, instances created 40, listeners 52.
- 52 independently triggered listener event probes: {'SEMANTIC_GAP': 46, 'ACTION_REFERENCE_COMPLETE': 6}; modifier callbacks completed 6. The leading callback gaps are wave/maze predicates (29 probes), other predicate/progression/context operands, further AddModifier inputs, resource operations and retargeting. These are runtime/input gaps, not automatically missing readers.
- Four diverse real source-backed configuration/application fixtures: three initial complete lifecycles and one explicit scheduler/context gap. Their subsequent reference refresh/stack/replace/event/remove actions produce 18 reference action completions and 12 completed modifier callbacks. Bailu property buff, Acheron property contribution and Seele multi-event callback behavior pass. Silwolf dynamic write executes under exact caller-authored operand/provider policy, then stops at an anonymous TriggerAbility mask rather than silently skipping it. Argenti, Robin and Yukong definitions were also inspected but have no observed AddModifier site in the selected frozen graphs; no site is invented for them.

The sum of these distinctly labelled sandbox subcategories is **64 reference wrapper/event actions and 18 completed modifier callbacks**. This total is not a whole-real-skill coverage percentage or a frozen-corpus improvement.

Natasha remains a regression only: original source graphs and Skill02 child invocation are preserved; actor progression remains blocked without initialized real actor rows. Native actor supplied: false; progression blocker preserved: True.

The largest remaining raw family is CONTENT_CATALOG_BINDING (145 combat / 75 joined; weighted score 295). Modifier/Event (181 / 43) is now principally instance/reference-policy/native-effective context for these frozen fixtures. Recommend **R18 DAMAGE / HP SETTLEMENT** as the largest remaining unimplemented combat primitive (74 combat / 15 joined; weighted score 104), with targeted missing catalog/source/reader work kept as a separate backlog. This is authored phase planning, not native semantics. Wave/maze predicates and provider/resource gaps exposed by explicit event probes are retained in ledger v5; R17 stops before those major subsystems and before any real Turn/AV engine.

Tests: R12_R17: 185 PASS, battle_ir_FAST_UNIT: 586 PASS, battle_runtime_FAST_UNIT: 379 PASS, battle_sandbox_FAST_UNIT: 918 PASS. Architecture, determinism and replay PASS. Focused tests cover exact binding, policies, identities, refresh/replace/stack, explicit providers/snapshots, activation/listeners, priority/predicates, nested owned callbacks, removal/cancellation, persistence/current-action drain, atomic registration and RNG rollback, callback retries/cycles/depth bounds, mid-callback restore/hash/replay, real configurations, Natasha preservation, heal stages and damage extension boundaries. Frozen tests are unchanged.

Production files: ["src/hsr_battle_agent/battle_ir/content_catalog.py", "src/hsr_battle_agent/battle_runtime/behavior.py", "src/hsr_battle_agent/battle_runtime/behavior_state.py", "src/hsr_battle_agent/battle_runtime/action_scheduler.py", "src/hsr_battle_agent/battle_runtime/modifier_lifecycle.py"].
Tests: `tests/battle_runtime/test_behavior_r17.py`.
Controls: ["data/control/generic_runtime_modifier_event_engine_v1_20261009_001.json", "data/control/generic_runtime_modifier_lifecycle_census_v1_20261009_001.json", "data/control/generic_runtime_support_census_v7_20261009_001.json", "data/control/generic_runtime_semantic_gap_ledger_v5_20261009_001.json"].
Audit: `tmp/audit/r17_modifier_event_20261009_001/`.

Reproduce: `python tools/runtime/r17_checks.py gate` before new edits; `python tools/runtime/r17_checks.py baseline`; `python tools/runtime/r17_probes.py`; `python tools/runtime/r17_regressions.py`; `python tools/runtime/r17_checks.py final`; `python tools/runtime/r17_finalize.py --package`. `--reuse-frozen` reuses the already verified unchanged frozen result while regenerating only explicitly labelled probes. The pinned R14/R16 source artifacts and catalog remain prerequisites.

Handoff destination: `D:/HSR_Battle_Agent/agent_handoffs/CR-R17-MODIFIER-EVENT-ENGINE-20261009-001_changed_files.zip`. ZIP member set, CRC, sizes, per-member SHA-256 and archive SHA-256 are recorded in `handoff_verification.json`. Only R17-owned changes, parsed explicit fixture evidence, controls, logs, receipts and manifest are packaged; native binaries, whole source payloads, old audit trees and dumps are excluded.
