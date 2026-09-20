# Astra semantic freeze — Terra handoff (2026-09-20)

Goal: HSR 4.4.54 full-content deterministic battle sandbox. The Astra semantic sprint is complete (10/10); Domains 1–9 remain frozen. Full native reconstruction is **incomplete**. This handoff authorizes no runtime work in the final audit.

The authoritative [freeze manifest](../../data/semantics/4.4.54/full_reconstruction/astra_semantic_freeze_v1.json) records the four readiness classes, exact operation-family frontier, all original blocker questions, BattleState field contract, identity/order/RNG rules and detailed implementation tickets. [Master](../../data/semantics/4.4.54/full_reconstruction/astra_reverse_master_v1.json) records closure and every changed bookkeeping value. All domain documents and historical reports remain unchanged.

| Class | Terra boundary |
|---|---|
| SAFE_TO_IMPLEMENT | Typed identities, lossless schemas, exact registries, bound pure modifier queries/target consumers, strict gates, atomic transactions, snapshot/clone/hash infrastructure. |
| SAFE_TO_REPRESENT_ONLY | Invocation/lifecycle, topology/formation, AI policy/state, damage components, target bindings, progression activation and official scenario/mode descriptors. |
| SAFE_REFERENCE_MODEL_ONLY | Exact named ordinary damage/heal/value/resource/task-marker/timeline components with explicit contexts and packet exclusions. |
| STRICT_REJECT_UNTIL_NEW_EVIDENCE | Unproved invocation, source-driven modifier lifecycle, scheduler arbitration, AI winner/commit, special damage, retarget/randomness, native loadout activation and official wave/terminal semantics. |

BattleState is an aggregate of separately owned stores: content/progression input; immutable scenario/behavior definitions; entity/team/typed topology and formation; invocation/task/continuation state; modifier and property ownership; ordered nullable targets; separate scheduler request families; AI sequence/use/variable state; damage/survival/resources; events; wave/global/environment/mode/terminal state; RNG; opaque unresolved lifecycle handles. Actor, owner, caster, provider, receiver, equipment instance, target context and global service are distinct references. New runtime tokens are LOCAL_DESIGN_IDENTITY.

Every field is IMMUTABLE_INPUT, MUTABLE_STATE, DERIVED_CACHE or OPAQUE_UNRESOLVED_STATE. Snapshot/hash includes all decision-affecting pending and opaque state, source/profile/rule versions, allocator and RNG state. Preserve order, duplicate/null entries and field presence: [] != [null]. A hash of unresolved state does not make it executable. See freeze sections battle_state_contract and identity_contract.

Before step writes anything or draws RNG, preflight the entire reachable dependency closure, including secondary targets, callbacks, resource debit, completion and terminal/transition policies. Unknown random branches gate all possible effects before any draw. Stage only a closed plan; publish all state/queue/RNG writes atomically. On rejection, state/hash/RNG/queues/IDs stay unchanged. This is a local transaction design, not native rollback evidence. legal_actions() requires a supported decision context and returns BLOCKED on uncertainty; scheduler candidates and AI leaves are not player choices.

The minimum native-evidenced core currently supplies storage, gates and bounded pure primitives; no complete native-faithful battle action is established by this audit. The optional reference/ordinary-explicit/v1 profile accepts explicit ordinary membership, supplied actor/skill/targets, exact packet formulas and successful matching task boundaries. It excludes TriggerAbility, source-driven modifier creation, native AI selection, special action arbitration, random targets/crit and native official scenario transitions. See minimum_viable_faithful_core and implementation_frontier for exact payload gates; a compiler EXECUTABLE_REFERENCE flag alone is insufficient.

Custom free scenarios may omit official StageID. Preserve selected character/loadout/enemy definitions and explicit participant specs now; their native activation is still gated. A caller-selected namespaced/versioned SANDBOX_EXTENSION may define initial state or terminal rules, including selected-enemies-defeated with explicit empty-set and simultaneous-result policy. It cannot silently replace a blocked official rule or omit unknown source effects. Native-faithful official scenarios and custom extensions must remain separate in snapshots, outputs and coverage.

Start Terra with these ordered tickets from terra_roadmap:

1. TERRA-F01: evidence modes, lossless values, presence and provenance.
2. TERRA-F02: typed local identities and complete state/snapshot/clone/hash contracts.
3. TERRA-R01: registry and cross-domain descriptors without activation.
4. TERRA-G01/G02: transitive preflight/atomicity, then bounded pure lookup/consumer primitives.
5. TERRA-REF01/02/03: independently qualify existing reference components and ordinary schedule/legality.
6. TERRA-C01/C02: explicit custom scenario rules and existing exact followup edges.
7. TERRA-V01/V02/V03: source-backed requalification, deterministic integration, then independent oracles.

Each ticket specifies inputs, outputs, reads, writes, rejection gates, tests, consumed artifacts, blockers and coverage effect. No ticket requires guessing unresolved native semantics. Golden promotion remains blocked on an independent oracle.

Never reuse these outdated conclusions:

- LightCone “165 exact joins”: these are numeric-token candidates; strict complete joins remain 0/169.
- AI “zero policy bodies/content blocked”: four policies and five configs are recovered; 11 exact IDs bind 15 sequence occurrences. Native admission, precedence, DefaultDSE, target handoff and commit remain unknown.
- D8 “acquisition pending”: 4696 Trace raw joins, 546 rank rows, 136 combined Trace/Eidolon behavior-name candidates and 488 level-override edges are available. There are still 322 missing Trace rows, 36 rank rows and 48 missing skill IDs; candidates are not activation.
- “1459 executable native waves”: these are adapter containers, with 2743 source groups. StageCommonTemplate.json is ABSENT_AT_PINNED_COMMIT; D9-Q1 remains blocked.
- Refresh=Replace/Count/OnReplace; provider=caster; refresh overwrites all dynamics: superseded/quarantined by D2.
- Target entity-ID ties, row adjacency, center=first, native stable AV ties, callback FIFO, automatic wave victory and task SUCCESS=ability/wait release: no native promotion.
- Static assembly/golden_eligible, singleton AI, real content IDs or self-generated replay: none proves native correctness.

Historical baseline: 14042 canonical records, 10685 behavior-bearing; 19715 report entrypoints, 4738 historically executable; 59595 historical executable-bound operations; 1528 executable-reference records; four source-backed executed records and 27 components. These are retained historical measurements, **not post-Astra native readiness**. No new execution was measured. Golden remains **0**.

Use blocker_registry in the freeze for exact evidence requests and current content corrections. Original question groups remain separate; inherited activation, event/RNG/state/version and oracle blockers are explicit. Tests must distinguish structural, reference-model, source-backed, native-trace and Golden evidence. Replay tests prove determinism, not an independent oracle.

Artifact pointers:

- [D1 TriggerAbility](../../data/semantics/4.4.54/full_reconstruction/astra_triggerability_v1.json) · [D2 Modifier](../../data/semantics/4.4.54/full_reconstruction/astra_modifier_v1.json) · [D3 Formation](../../data/semantics/4.4.54/full_reconstruction/astra_formation_boss_v1.json)
- [D4 Scheduler](../../data/semantics/4.4.54/full_reconstruction/astra_scheduler_arbitration_v1.json) · [D5 AI](../../data/semantics/4.4.54/full_reconstruction/astra_monster_ai_v1.json) · [D6 Damage](../../data/semantics/4.4.54/full_reconstruction/astra_damage_survival_v1.json)
- [D7 Target](../../data/semantics/4.4.54/full_reconstruction/astra_target_retarget_v1.json) · [D8 Progression](../../data/semantics/4.4.54/full_reconstruction/astra_equipment_trace_eidolon_v1.json) · [D9 Scenario](../../data/semantics/4.4.54/full_reconstruction/astra_stage_environment_mode_v1.json)
- [AI acquisition](../../data/semantics/4.4.54/full_reconstruction/monster_ai_content_acquisition_001.json) · [AI binding ledger](../../data/semantics/4.4.54/full_reconstruction/monster_ai_binding_ledger_001.json) · [AI sequence closure](../../data/semantics/4.4.54/full_reconstruction/monster_ai_sequence_id_binding_001.json)
- [D8 content followup](../../data/semantics/4.4.54/full_reconstruction/equipment_trace_eidolon_content_followup_001.json) · [D9 absent-graph followup](../../data/semantics/4.4.54/full_reconstruction/stage_environment_mode_content_followup_001.json)
- [Historical compiler report](../../data/semantics/4.4.54/full_reconstruction/full_content_behavior_compiler_report_001.json) · [Historical coverage](../../data/semantics/4.4.54/full_reconstruction/full_content_behavior_coverage_census_001.json)

Reopen only for concrete, version/hash-qualified new evidence answering an existing blocker, or a demonstrated bookkeeping defect. UNKNOWN alone, implementation convenience and repeated same-source searches are insufficient. No saved RVA may be applied to an unverified live binary. Native bodies/content acquisition require separately authorized work. Consume the concise do_not_reason_again registry and explicit superseded_claims in the freeze before changing a gate.

Stop after validated freeze. Runtime implementation is a separate Terra phase.
