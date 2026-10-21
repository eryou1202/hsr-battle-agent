# R20 Actor State + Resource / Progression

CR `CR-R20-ACTOR-STATE-RESOURCE-PROGRESSION-20261010-001`. Verdict **GENERIC_ACTOR_RESOURCE_REFERENCE_ENGINE_ESTABLISHED**. Starting HEAD `ddd2739ae16daf88b70087b8b82c822036e5461d`, branch `terra/implementation`. Git writes NONE; frozen M10–M15, ScenarioCompiler and strict admission unchanged. All inherited/unrelated files are hash-checked against the start gate.

R20 adds ActorRuntimeBinding and explicit resource transactions to the existing BehaviorRuntime/BehaviorBattleState. Actor/team stores and progression are reused; entity/ability-local reference stores and records live under opt-in mechanics. R15 schedules owned work, R17 dispatches modifiers/listeners, R19 evaluates properties/rank, and the existing R18 checkpoint stack protects atomic nested effects. There is no second BattleState, ScenarioCompiler, property evaluator, event bus or process-global cache.

## Actor authority and versions

REAL_CONTENT_STATIC, REAL_CONTENT_RECONSTRUCTED, REFERENCE_MODEL, EXPLICIT_SCENARIO_INPUT and EFFECTIVE_RUNTIME_UNKNOWN remain distinct. Absent fields, explicit zero, explicit false and unknown values remain distinct. Fields are never silently completed into native legality. Existing reference fixture values are preserved as inherited reference inputs rather than upgraded to native state.

Actor identity comes from the exact pinned 4.6.51 AvatarConfig decoded row, source pointer/hash and version manifest/source-shard pin. Levels, promotions, ranks, activation booleans, HP/property/resources and overrides are caller fixture inputs. Definition existence does not imply an active modifier. Initial instances require explicit activation evidence, exact definitions/owners, listener/provider policy, dynamic/snapshot state and unique IDs. Base/effective differences are checked with the R19 contribution evaluator to prevent double counting.

Research baseline is **4.6.51**; product ContentDatabase remains **4.4.54**. Shared types are version-independent abstractions. Static values are not merged across versions. Incompatible or relabelled source versions return VERSIONED_CONTENT_GAP. Exact native initialized actor legality and unprovided static/property/progression/resource values remain unknown. See version_compatibility.json.

## Resources, progression and callbacks

The trusted 632-root census has 39 ModifySPNew instances, 45 ByRankActivated predicates and 44 BySkillPointActivated predicates. The 31 SetEnergyBarState records remain structure-only candidate operations; they are not asserted to mutate a numeric resource.

Existing same-version R11 evidence identifies a related unpatched actor property path at 0xB/0xC/0x8A, a distinct team BP path, and a partial AddRatio → SPBase/rate/cap chain. Effective resource identity/formula, IFix/Lua/task mapping, event dispatch and capacities remain unproved. The label SP establishes none of those. Execution uses a hash-bound, caller-authored field mapping, exact target/owner/resource domain and explicit serialized-operand-as-delta policy. This is not native AddRatio formula equivalence.

ACTOR_RESOURCE, TEAM_RESOURCE, ENTITY_RESOURCE and ABILITY_LOCAL_RESOURCE are independent; UNKNOWN_NATIVE_RESOURCE rejects. READ, SET, ADD, SUBTRACT, CLAMP and COMPARE use the existing R12 fixed-point contract (signed int64 raw, scale 2^33, step2 toward-zero). Bounds, initial overcap, overflow, event order and complete active R17 listener registrations are explicit. Pre/change/post events drain owned R15 callbacks. Source costs require explicit source/authority, nonnegative subtraction and sufficient balance above the minimum; this does not establish native availability, turn ownership, ultimate thresholds or M15 admission.

Skill-tree predicates bind the actual serialized TriggerKey and explicit boolean activation input. TriggerKey activation dictionaries in the cohort are reference state; they do not prove native PointID/activation legality. Rank reuses R19 KEYED_THRESHOLD_GE_REFERENCE with exact actor rank and keyed threshold. TriggerKey is not treated as rank. Missing rank, threshold, activation or comparison policy returns a gap.

Unsupported atomic resource effects restore resource/HP values, listeners/modifiers, RNG, queues and transaction records, including nested damage. Earlier committed source tasks persist and retry resumes the original source. Actors, policies, progression, resources and pending transactions serialize through existing snapshot/clone/hash/replay. Runtime hashes include behavior-changing policies; committed resource records include exact policy hashes. Actor binding policies also live in state.

## Measured boundaries

| Scope | Result |
|---|---|
| Frozen combat roots / joined roots / joined rows | 632 / 160 / 161 |
| Frozen combat tasks reached/completed | 1025 / 494 → 1025 / 494 |
| Frozen joined tasks reached/completed | 300 / 121 → 300 / 121 |
| Frozen HP commits / complete joined transitions | 0 / 0; state hash drift 0 |
| Same 15 R19 roots, finish-only lifecycle closures | 10 / 15 → 10 / 15 |
| Same 15 R19 roots, continuation-expression closures | 14 / 15 → 14 / 15 |
| Same 15 R19 roots, separate explicit-rank closures | 15 / 15 → 15 / 15 |
| Same 15 R19 roots reaching HP with expression/rank | 15 / 15 → 15 / 15 |
| Complete joined skills, all R19 comparison cohorts | 0 / 15 → 0 / 15 |
| R20 explicit contexts / real Avatar identities / exact source owner joins | 83 / 25 / 28 |
| Explicit activation entries / completed skill-tree / rank predicates | 249 / 15 / 13 |
| R20 original graph tasks reached/completed | 763 / 670 |
| Original graph resource attempted/committed / prefix roots | 7 / 7 / 7 |
| Original graph HP-mutating roots / settlements | 25 / 43 |
| Isolated original resource primitives | 38 commits / 39 probes, excluded from original graph/full-skill totals |
| Explicit modifier listener invoking real resource task | 3 callbacks / 3 commits, separate reference probes |
| Real graph resource callbacks | 0; separate listener probes do not inflate this count |
| Complete joined skill transitions / native validated | 0 / 0 |

Three original nonjoined ability-root reference actions complete under explicit scenario owner contexts: `Avatar_Anaxa_00_Skill01_Phase02`, `Avatar_Lingsha_00_Skill01_Phase02`, `Avatar_Sparkle_00_Skill01_Phase02`. All use their original source completion nodes and drained work. They are not joined complete skills and do not prove native actor ownership/legality. The 55 unjoined contexts use explicitly supplied ability owners rather than inferred character identities.

Seven original resource-prefix roots pass independent replay, clone and snapshot/resume comparisons, including all three completed ability actions. All 39 isolated source-resource probes pass checkpoint determinism; Local_SPAdd retains an exact-target-owner gap because the unchanged alias resolves multiple targets. No missing SkillPerformFinish is inserted. The paired damage/resource probe and existing reference Heal FormulaType2/resource probe mutate HP/resources; those pairings are explicitly synthetic. Original real heal FormulaType2/target mapping remains SOURCE_COMPATIBILITY_GAP in the paired probe and is not fabricated.

Natasha Skill02 Phase01/Phase02 retain their original progression blocker under unchanged fixtures. With separately labelled explicit activation state, both progress to the next original DispelStatus task and stop there. No Natasha keys or AvatarID branches exist in production.

## Whole battle capability matrix

| Capability | Reference status | Native evidence |
|---|---|---|
| Actor state initialization | REFERENCE_EXECUTABLE | NATIVE_ORACLE_PENDING |
| Damage/HP | REFERENCE_EXECUTABLE | NATIVE_ORACLE_PENDING |
| Heal | REFERENCE_PARTIAL | NATIVE_ORACLE_PENDING |
| Modifier/Event | REFERENCE_EXECUTABLE | NATIVE_ORACLE_PENDING |
| Resources/Energy/SP | REFERENCE_EXECUTABLE | NATIVE_ORACLE_PENDING |
| Progression | REFERENCE_EXECUTABLE | NATIVE_ORACLE_PENDING |
| Shield | NOT_BOUND | NOT_BOUND |
| Toughness/Break | NOT_BOUND | NOT_BOUND |
| True Turn/AV | NOT_BOUND | NOT_BOUND |
| Action legality | REFERENCE_PARTIAL | NATIVE_ORACLE_PENDING |
| Monster AI | STRUCTURE_ONLY | NOT_BOUND |
| Stage/wave/mode | NOT_BOUND | NOT_BOUND |
| Planner integration | REFERENCE_PARTIAL | NOT_BOUND |

Top remaining gaps include missing decoded catalogs/template parameters, effective modifier/provider inputs, DispelStatus and other unbound primitives, native actor/resource initialization and formula/events, true turn/AV, shield/break, Monster decisions and stage progression. First-gap frequency does not measure unvisited subsystem absence.

**Recommended R21: TRUE BATTLE TURN / AV, starting with bounded evidence discovery.** Establish a source/effective-runtime contract for clock/initiative/tie-break/turn ownership/advance-delay/interrupt semantics before implementing native-like scheduling. R15 logical time is insufficient evidence. Catalog/character-root completion ranks second for concrete graph closure, followed by toughness/break/shield, Monster behavior, action legality/cost and targeted native oracle work. See next_phase_priority.json for impact, evidence availability, generic reuse, blockers, cost and uncertainty; another local property/resource phase is not the default.

## Validation and handoff

Determinism PASS; replay PASS; architecture PASS. R20 focused tests cover provenance/version relabelling, absent/zero/false/unknown, progression/rank gaps, all resource operations/domains, bounds/overcap/cost, event order/ownership, nested HP/resource/RNG/listener rollback, active initial modifiers/providers, base/effective contributions, checkpoint restoration and explicit replay.

Final lanes: R12_R20 **307 PASS**, battle_ir_FAST_UNIT **586 PASS**, battle_runtime_FAST_UNIT **501 PASS**, battle_sandbox_FAST_UNIT **918 PASS**. Frozen historical tests unchanged.

Production: `src/hsr_battle_agent/battle_runtime/behavior.py`, `src/hsr_battle_agent/battle_runtime/action_scheduler.py`, `src/hsr_battle_agent/battle_runtime/actor_binding.py`, `src/hsr_battle_agent/battle_runtime/resource_engine.py`. Tests: `tests/battle_runtime/test_behavior_r20.py` (42 focused tests). Five requested R20 controls and this report are generated by r20_finalize.py. Audit: `tmp/audit/r20_actor_resource_progression_20261010_001/`.

Reproduce: `python tools/runtime/r20_evidence.py`; `python tools/runtime/r20_probes.py --frozen`; `python tools/runtime/r20_probes.py --r19`; `python tools/runtime/r20_probes.py`; `python tools/runtime/r20_followups.py`; `python tools/runtime/r20_replay.py`; `python tools/runtime/r20_checks.py final`; `python tools/runtime/r20_finalize.py`; `python tools/runtime/r20_finalize.py --package`. The start gate must never be regenerated after edits.

Handoff: `D:/HSR_Battle_Agent/agent_handoffs/CR-R20-ACTOR-STATE-RESOURCE-PROGRESSION-20261010-001_changed_files.zip`. Archive includes only R20-owned source/tests/tools/controls/report/audits, baseline-relative patches and manifest. Inherited starting-file copies, binaries, native payloads/process dumps/old reverse trees and unrelated dirty files are excluded. CRC, exact members, sizes, per-member SHA-256 and ZIP SHA-256 are verified; ZIP receipt stays external to avoid a self-reference.

**Native correctness NOT CLAIMED. Git writes NONE.**
