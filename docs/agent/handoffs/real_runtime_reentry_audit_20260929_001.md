# Real Runtime Re-Entry Audit — HSR Battle Agent

Change request: `CR-REAL-RUNTIME-REENTRY-AUDIT-20260929-001`
Task type: **READ_ONLY architecture + implementation audit** (no implementation, no redesign, no frontend work)
Repository: `D:\HSR_Battle_Agent\hsr-battle-agent`
Branch: `terra/implementation`
Machine artifact: `data/control/real_runtime_reentry_audit_20260929_001.json`

Production files modified: **NONE**
Tests modified: **NONE**
Git writes: **NONE**

---

## 0. Start gate

| item | value |
|---|---|
| `git rev-parse HEAD` | `7eb82ec2400b050e6b915bbfb2d834bbfe0fae3d` |
| `git branch --show-current` | `terra/implementation` |
| Working tree | dirty, **preserved and read, never staged** |

The tree carries two independent uncommitted workstreams on top of HEAD:

1. **Frontend P5 product UX** — `frontend/*` (adapters, models, panels, `fe1/`, `fe3/`, `ui/`, styles, new fixtures).
2. **Reverse-engineering / semantic reconstruction probes** — `data/raw/4.4.54/*` (disassembly, TaskConfig/Predicate registries, damage-dispatch probes), `data/semantics/4.4.54/full_reconstruction/astra_*.json` + `.cjs`, and `docs/agent/handoffs/{astra_*,damage_*,natasha_*,direct_hp_*,semantic_handoff_*,turn_av_*}.md`.

HEAD is **8 commits after** the `24ccb9b` backend freeze. All 8 are P-series (`P0`→`P5B`). **No commit in that range touches the runtime, the compiler, the sandbox, the planners, or the loadout materializer.**

---

## 1. Original project goal

The target architecture is:

```
real client / extracted content
    → canonical static + behavior data
    → generic semantic / behavior representation
    → real-content BattleState
    → generic deterministic executor
    → run_until_decision()
    → DecisionPoint
    → legal_actions()
    → state clone / canonical hash
    → baseline / greedy / beam planner
    → recommendation
    → later: live client state reader
    → real-time battle advisor
```

The five **explicit non-goals** (content browser, M14 registry viewer, static Scenario builder, support-report viewer, admin console) are all implemented and healthy. The actual end goal has **zero realized steps**.

---

## 2–3. Source of truth and control artifacts

Current source was treated as authoritative; control artifacts were used as historical/context evidence only. Artifacts read (with their recorded verdicts):

| artifact | verdict |
|---|---|
| `backend_freeze_audit_20260927_001.json` | `BACKEND_CONTRACT_STACK_FREEZE_READY` (A); M10/M11 DELIVERED, M12 BLOCKED_BY_EVIDENCE, M13/M14/M15 DONE (at head `8a4dcb0`) |
| `scenario_entity_resolution_parity_20260927_001.json` | P0 IDENTICAL over 1459 stages; 420101 `COMPILES_STATICALLY`; real execution DENIED |
| `scenario_contract_conformance_20260927_001.json` | P1 `scenario_package/2`; F2/F3/F4 closed; **F5/F7 UNTOUCHED** |
| `content_product_projection_20260928_001.json` | P2 static product done; F5/F7 out of scope |
| `stage_encounter_product_projection_20260928_001.json` | P3 static product done |
| `scenario_support_report_20260929_001.json` | P4 static aggregation; `real_content_execution_performed: false` |
| `product_frontend_contract_20260929_001.json` | P5A done |
| `local_scenario_bridge_20260929_001.json` | P5B done; `battle_execution_exposed: false` |
| `full_action_closure_census_001.json` (M12) | `C. WAIT_PLUS_ONE_TRUE_FULL_ACTION_FRONTIER_FOUND`; minimum residual **1** class |
| `content_support_summary_v1.json` (M13) | **`CONTENT_ACTION_EXECUTABLE_REFERENCE = 0`** |
| `astra_semantic_freeze_v1.json` | `SEMANTIC_SPRINT_COMPLETE` but `native_reconstruction_status = INCOMPLETE_EVIDENCE_AND_CONTENT_BLOCKED`; `battle_state_contract.status = ARCHITECTURE_ONLY_NO_METHOD_IMPLEMENTATIONS` |
| `astra_reverse_master_v1.json` | `full_native_behavior_reconstruction_complete: false`; `production_implementation_started: false` |
| `astra_triggerability_v1.json` | `PASS_4_COMPLETE_BLOCKED_BY_EVIDENCE`; `execution_readiness: NO`; `expected_new_executable_coverage: 0` |
| `astra_sphitratio_targeted_evidence_v1.json` | `BLOCKED_BY_EVIDENCE` — "Do not recommend SOL policy reentry from this result" |
| `astra_monster_ai_v1.json` / `_pass2_` | `ai_policy_binding: PARTIAL`; coverage `PARTIAL`; runtime admission UNKNOWN |
| `astra_stage_environment_mode_v1.json` | wave advance `BLOCKED_BY_EVIDENCE_AND_GRAPH_CONTENT`; spawn `EXECUTION_BLOCKED`; terminal `EXECUTION_BLOCKED` |

---

## 4. Architecture inventory

```
src/hsr_battle_agent/
  battle_ir/         31 files   8,132 loc  REPRESENTATION (descriptors) + primitive types
  battle_runtime/    10 files   3,733 loc  REFERENCE_MODEL generic client-method primitives
  battle_runtime_v2/  1 file      168 loc  bound modifier queries
  battle_sandbox/    39 files  11,949 loc  state/executor/law/evidence/gate/trace/hash infra
  reference_sandbox/  4 files     734 loc  M10 LOCAL_ACTION_ENVELOPE session
  game_data/         28 files  14,426 loc  static + reconstruction + reference models
  content_support/    4 files   1,422 loc  M13 read-only query (descriptive only)
  content_planner/    3 files     630 loc  M15 fail-closed admission (REJECTED only)
  product_support/    2 files   1,147 loc  P4 support report
  frontend_adapter/   5 files     562 loc  offline static generation
  frontend_bridge/    4 files     353 loc  loopback HTTP transport
  planner/            5 files   1,214 loc  M8 exhaustive enumeration
  planner_search/     7 files     881 loc  M9 bounded DFS + objective
  reference_battle_planner/ 5 files 672 loc M11 bounded DFS over M10
  validation/         1 file      176 loc  golden promotion gate
```

**Runtime core is small.** Of `battle_sandbox`'s 11,949 lines, only **1,519** form state + executor + legal actions (`executor.py` 124, `state.py` 600, `state_v2.py` 381, `legal_actions.py` 129, `sandbox.py` 121, `strict_executor.py` 164). The rest is evidence/certificate/trace/snapshot/migration/boundary scaffolding.

**Category classification (not blurred):**

| category | modules |
|---|---|
| STATIC DATA | `game_data.nanoka_content`, SQLite + JSONL content |
| PRODUCT PROJECTION | `game_data.content_product`, `game_data.scenario_compiler`, `product_support.scenario_report`, `frontend_adapter`, `frontend_bridge` |
| REFERENCE MODEL | `game_data.{reference_execution,reference_*_adapters,damage_survival_reference,dynamic_value_reference,predicate_semantics_reference,scheduler_semantics_reference,rng_semantics_reference,target_semantics_reference,toughness_break_reference,modifier_lifecycle_reference,property_contribution_reference,cross_family_execution_reference}`, `battle_runtime/*` |
| LOCAL/SYNTHETIC RUNTIME | `battle_sandbox` (legacy `PrimitiveExecutor`), `reference_sandbox`, `sandbox_transition` |
| REAL-CONTENT SEMANTIC RECONSTRUCTION | `game_data.{external_behavior,behavior_compiler,content_behavior_mapping,full_content_behavior_ingestion,behavior_descriptor_adapter,real_skill,followup_ledger}` |
| REAL-CONTENT EXECUTION | **NONE** |
| PLANNER | `planner`, `planner_search`, `reference_battle_planner` |
| PRESENTATION / TRANSPORT | `frontend_adapter.*`, `frontend_bridge.*`, `frontend/*` |

**Import direction is clean (verified by grep):**

- `battle_sandbox/` and `battle_runtime/` import **zero** `game_data` modules.
- `reference_boundary.py:61-69` mentions quarantined module *names* as strings, not imports.
- Only `reference_sandbox/session.py` (outside `STRICT_PATH_PACKAGES`) imports the quarantined reference modules.
- No planner package imports `content_support`/`content_planner`. Their only "content" references are the string literal `CONTENT_TARGET = "HSR-4.4.54"`.

---

## 5. Static content readiness

Counts read from the current SQLite (80 MB, verified by `COUNT(*)`) and canonical JSONL:

| entity | count | product/API coverage |
|---|---|---|
| Avatars | 97 | `character_product/1` + M14 capability index |
| Avatar skills (static rows) | 664 | M13 registry (620 canonical `AvatarID:SkillID`) |
| Traces | 5,018 | inside character product + loadout |
| Eidolons | 582 | inside character product |
| LightCones | 169 | referenced in character product + loadout |
| LightCone promotions / superimpositions | 1,183 / 845 | loadout |
| Relic sets / items | 60 / 184 | loadout (set_id counts) |
| Relic affixes / templates | 165 / 742 | loadout (external reconstruction only) |
| Monsters | 628 | `monster_product/1` |
| MonsterVariants | 2,648 | **no accessor** |
| MonsterSkills | 12,873 | **no accessor** |
| Encounters / Stages | 1,543 / 1,459 | `encounter_product/1`, `stage_product/1` |
| Waves / wave placements | 1,459 / 6,717 | only inside `stage_package` |
| Stage Buffs | 18 | `stage_package` (17 resolvable; `3110018` missing) |
| mode_metadata | 92 | **no accessor** |

**Product-ready:** Avatars, LightCones, Trace/Eidolon, Monsters, Stages, Encounters, Waves (via stage package), Stage Buffs.
**Exists without typed API:** MonsterSkills, MonsterVariants, Waves, mode_metadata, relic_items.
**Incomplete/ambiguous:** `RELIC_AFFIX_SCHEMA` (external-only, `SOURCE_CONFLICT` 80 exact / 37 non-exact), `STAGE_BUFF_DETAIL` partial, `AUXILIARY_ELITE/HARDLEVELGROUP` external-missing, `MONSTER_VARIANT_LIST:4034020` partial.

### F5 and F7 — verified still open in current source

**F5 (loadout completeness) — STILL UNRESOLVED.**
`game_data/scenario_compiler.py:25-26` still states verbatim: *"Audit F5 (loadout completeness) is explicitly NOT addressed by this change: no relic-slot, set_id, initial_state, skill_level or rank validation was added."* `_compile_players` (`:202-261`) copies `skill_levels`, `trace_state` and `initial_state` through unchanged.

**F7 (relic slot vocabulary) — STILL UNRESOLVED.**
The contract text `free_scenario_assembly_contract_v1.json:10` still declares slots `HEAD|HAND|BODY|FOOT|PLANAR_SPHERE|LINK_ROPE` while the data uses `HEAD|HAND|BODY|FOOT|NECK|OBJECT`. Affix identity is still composite (`main:21:1`), not a game affix id.

**What BattleState initialization actually needs:** identity + numeric survival (`entity_id`, `hp`, `max_hp`, `speed`). Static content **can** supply these numbers, but **no code path materializes them into any BattleState**. `free_scenario_assembly_contract_v1.json:54` lists "production BattleState construction" under `not_yet_claimed`.

---

## 6. Loadout / initial character state audit

Materializer: `ReferenceEvaluator.materialize_loadout` (`game_data/external_reconstruction.py:1132`), output schema `hsr_battle_agent.static_loadout/1`, `reconstruction_status: PARTIAL`.
**Sole caller:** `scenario_compiler.py:248` (static assembly). No runtime, sandbox or planner calls it.

| field | classification | evidence |
|---|---|---|
| avatar_id | VALIDATED | `KeyError` if absent (`1140-1143`) |
| avatar level | STATICALLY_MATERIALIZED | `base + add*(level-1)`; **no range validation** |
| avatar promotion | VALIDATED (existence) | `ValueError` if promotion row absent; no explicit 0..6 bound |
| eidolon rank | VALIDATED (0..6) but CONTEXTUAL_EFFECT_UNAPPLIED | recorded into `unapplied_contextual_effects` only |
| skill levels | UNREPRESENTED in materializer; CARRIED_UNVALIDATED by compiler | `scenario_compiler.py:257` |
| trace / rank state | PARTIAL: `unlocked_trace_ids` validated; `rank_state` CARRIED_UNVALIDATED | `1187-1193`, `scenario_compiler.py:231,237,258` |
| initial state | CARRIED_UNVALIDATED | `scenario_compiler.py:259` |
| LightCone existence / path compat | VALIDATED | `KeyError` / `ValueError` on `base_type` mismatch |
| LightCone level | STATICALLY_MATERIALIZED | no range validation |
| LightCone promotion | VALIDATED (existence) | `promotion == 0` special case |
| LightCone superimposition | CARRIED_UNVALIDATED | written to `lightcone_context` only |
| six relic slots | **UNREPRESENTED** | no six-slot rule at all |
| duplicate slots | VALIDATED | only when a template slot resolves |
| missing slots | **UNREPRESENTED** | no completeness check |
| relic slot identity | PARTIAL | derived from template, used only for duplicate detection |
| relic set_id | CARRIED_UNVALIDATED — **caller value IGNORED** | re-derived from template; surfaced as unapplied `relic_set_effect` |
| main affix | VALIDATED | must exist, `affix_kind == "main"`, group must match |
| sub affixes | VALIDATED | group match + `roll_tiers` within `0..step_num` |
| relic level | VALIDATED | `0 <= level <= template.max_level` |
| dynamic equipment effects | CONTEXTUAL_EFFECT_UNAPPLIED | `status: UNAPPLIED_CONTEXTUAL` |

**Verdict:** a numeric materializer with a validated relic-affix arithmetic layer. It validates shape where a row exists, validates **nothing** about completeness or application, and has **no runtime consumer**.

---

## 7. Real-content binding / behavior audit

Population model (M13 corrective terminology):

| quantity | value |
|---|---|
| STATIC_SKILL_ROWS | 620 |
| EMPTY_TRIGGER_ROWS | 92 |
| TRIGGER_NAME_JOINED_ROWS | 528 |
| TRIGGER_JOINED_WITHOUT_ENTRY_ABILITY | 4 |
| **ACTUAL_BEHAVIOR_ROOT_BOUND_OR_BETTER** | **524** |
| TOTAL_STATIC_WITHOUT_BEHAVIOR_ROOT | 96 |

Binding / support / readiness distributions:

| binding_level | n |
|---|---|
| STATIC_ONLY | 96 |
| BEHAVIOR_ROOT_BOUND | 200 |
| FULL_ACTION_REPRESENTED | 324 |
| REFERENCE_SETTLEMENT_BOUND | **0** |
| **CONTENT_ACTION_EXECUTABLE_REFERENCE** | **0** |

| support_status | n | | readiness | n |
|---|---|---|---|---|
| REPRESENTABLE_BLOCKED | 336 | | SAFE_TO_REPRESENT_ONLY | 258 |
| BLOCKED_BY_EVIDENCE | 5 | | SAFE_REFERENCE_MODEL_ONLY | 337 |
| BLOCKED_BY_REFERENCE_SUPPORT | 1 | | STRICT_REJECT_UNTIL_NEW_EVIDENCE | 25 |
| BLOCKED_BY_CONTINUATION | 20 | | | |
| NO_SETTLEMENT | 162 | | | |
| UNBOUND_STATIC_SKILL | 96 | | | |

Settlement: **293** settlement-reaching bound roots; 65 root-record-only; 358 with any observed settlement; 166 with none. Kinds: DAMAGE_REQUEST 269, HEAL_REQUEST 28, MODIFY_TEAM_SP 110.

Full-closure census over 324 rows:

| status | n |
|---|---|
| ACTION_A_CURRENTLY_CLOSED | **0** |
| ACTION_B_WAIT_ONLY | **0** |
| ACTION_C_WAIT_PLUS_ONE_POLICY_CLASS | 5 |
| ACTION_D_SMALL_FRONTIER | 162 |
| ACTION_E_BROADLY_BLOCKED | 126 |
| ACTION_F_NO_SETTLEMENT | 31 |

Minimum true full-action residual: **1 blocker class** (`DAMAGE_PACKET` / `EXECUTABLE_REFERENCE_DAMAGE_MIXED_STATE_FIELDS`).

### Pipeline stage status

| stage | status |
|---|---|
| static Skill ID | PRESENT (620 rows) |
| behavior root | PARTIALLY BOUND (524/620) — a **string** join, not cross-validated against the compiler corpus |
| EntryAbility | PRESENT as a name |
| operations | compiled for the whole corpus (captured 14,042 / behavior-bearing 10,685) with **29,086** `BEHAVIOR_AFFECTING_NODE_NOT_COMPILED` failures; `REJECT_NOT_NOOP` rejects the entire record |
| continuations | **named edge only** — `execution_readiness: NO` |
| settlement | represented; executability refused for 100% of avatar settlement cases |
| runtime semantics | **NOT REACHED for any real avatar skill** |

**Executable real-content skills: 0. Independent oracle coverage: 0. Native validation evidence: 0.**

### Blocker families → classification

| blocker | concrete occurrences | class |
|---|---|---|
| `SPHitRatio` / `HitSplitRatio` | every ACTION_C candidate (1208, 1303, 1401, 1501); refused by the REF02 packet adapter | **A** (parser/data extraction) + **D** (evidence: `astra_sphitratio` is `BLOCKED_BY_EVIDENCE`) |
| `WaitAnimState` | 320 roots / 2,597 occurrences — a presentation wait used as an implicit order barrier | **C** (missing runtime primitive: declared ordering barrier) |
| `TriggerAbility` / cross-behavior continuation | 324 roots with first-hop edges, 642 occurrences, 20 roots with second hop | **B** (semantic mapping: activation/context/registration contract missing) + **D** |
| Modifier definitions | 184 roots / 432 occurrences | **A**/**B** (definition catalog resolves only a subset; global/deferred/remove paths rejected) |
| Retarget | present but not a blocker in the ACTION_C set (only `ASTRA target` ordering is `ORDER_UNKNOWN`) | **B** |
| mixed-state damage requests | 231 roots / 507 occurrences | **C** (primitive for mixed-state packets) + **D** |
| formation change | `FORMATION_CHANGE` = `STRUCTURAL_PACKET_ONLY`; native `SetTeamFormation` strict-rejected | **C** |
| scheduler semantics | insert/one-more/immediate/arbitration strict-rejected | **B** + **D** |
| target selection | general selector/aggro/adjacency/invalidation `ORDER_UNKNOWN` | **D** |
| RNG-dependent semantics | client algorithm `UNKNOWN`; `retarget ByRandom` is `NATIVE_BLOCKED_TR_Q2` | **D** (evidence) |
| `BEHAVIOR_AFFECTING_NODE_NOT_COMPILED` | 431 roots / 1,673 occurrences (29,086 at operation level corpus-wide) | **A** (unmapped `RPG.GameCore.*` types) |
| presentation-only (`VCameraConfigChange` etc.) | classified `CURRENT_PRESENTATION_OMITTABLE` | **E** (product/presentation only) |

---

## 8. Behavior IR audit

Two layers, and they do not touch each other:

- **Descriptor layer** (`battle_ir/descriptors/*`, `descriptor_registry.py`) — **representation only**. `DescriptorOccurrence.execution_permitted()` and `DescriptorRegistry.execution_permitted()` both raise. Family enums expose only `REPRESENTED` / `UNRESOLVED`; there is no executable boolean. Neither `battle_runtime` nor `battle_sandbox` imports any descriptor class. 12 descriptor classes: `DescriptorOccurrence`, `InvocationDescriptor`, `ModifierDescriptor`, `FormationTopologyDescriptor`, `SchedulerDescriptor`, `MonsterAIDescriptor`, `DamageDescriptor`, `TargetIntent`, `ResolvedTargetSet`, `RetargetDescriptor`, `ProgressionActivationDescriptor`, `ScenarioDescriptor`.
- **Execution layer** (`battle_ir/model.py` `PrimitiveCall`/`PrimitiveSpec` + `battle_ir` value/state types) — this is what `PrimitiveExecutor` dispatches.

Compiler facts:

- Input is canonical `BehaviorRecord` only (**raw external payload is never consulted**).
- **52** primitive bindings: 17 `EXECUTABLE_REFERENCE`, 1 `STRUCTURAL_CALL_ONLY` (`INVOKE_BEHAVIOR`), 34 `STRUCTURAL_PACKET_ONLY`.
- Policy `REJECT_NOT_NOOP`: any diagnostic rejects the entire record.
- `OPERATION_MAP` (`external_behavior.py:43-163`) recognizes ~115 `RPG.GameCore.*` types. Anything else → `OPAQUE` → `BEHAVIOR_AFFECTING_NODE_NOT_COMPILED`.

Answers:

| question | answer |
|---|---|
| canonical cross-ability identity? | **NO** — "No concrete native token/element/equality key recovered" |
| continuation represented? | only as a named handle + boolean closure flag; never first-class |
| modifiers first-class? | YES for representation (catalog + 4 supported stacking names); partially executable (ADD/REMOVE only) |
| conditions represented? | YES (`CONDITIONAL` / `PREDICATE` are executable kinds) |
| target resolution represented? | PARTIAL (`RETARGET` executable; `TARGET_FILTER` structural; ordering UNKNOWN) |
| event subscription represented? | STRUCTURE ONLY |
| scheduler timing represented? | PARTIAL (markers + insert/delay executable; arbitration rejected) |
| RNG represented? | STRUCTURE ONLY; client algorithm `UNKNOWN` |

> **"record exists in IR" is true for 14,042 records. "BattleState transition exists" is true for ZERO real-content records.**

---

## 9. BattleState audit

| type | module | form | classification |
|---|---|---|---|
| `TerraBattleState` | `battle_sandbox/state_v2.py:108` | `__slots__`, schema `terra_battle_state/2` | ARCHITECTURAL_SHELL |
| `BattleState` | `battle_sandbox/state.py:73` | dataclass, schema v4 | LOCAL_SANDBOX / REFERENCE_MODEL |
| `ReferenceBattleState` | `game_data/reference_execution.py:227` | dataclass | REFERENCE_MODEL |
| `ReferenceCombatState` / `ReferenceEntityState` | `game_data` | dataclass | REFERENCE_MODEL |
| `SandboxResourceState` | `battle_sandbox/sandbox_transition.py:213` | dataclass | SYNTHETIC |
| `CustomScenario` | `battle_sandbox/custom_scenario.py:128` | `__slots__` | SYNTHETIC |

`TerraBattleState` has **no named HP / speed / resource field**. All **61** frozen field families exist exactly once as `TypedStore`s — ordered, duplicate-preserving containers that implement **no lifecycle behaviour and no transition logic**. Only `revision_sequence`, `allocator`, `rng_state` and 8 `OPAQUE_UNRESOLVED` families have structural components.

Concept matrix (see JSON for the full 25-row table):

| concept | terra | legacy/reference | mutated by an executor | real-content bound |
|---|---|---|---|---|
| actors | family name only | yes | yes (legacy/reference) | no |
| HP | no field | yes | yes (negative-delta path only) | no |
| max_hp | no field | yes | read only | no |
| toughness | family name only | yes (reference) | no | no |
| **energy** | ABSENT | ABSENT | no | no |
| SP | ABSENT | caller-declared resource | yes (synthetic) | no |
| speed / AV / turn order | family name / `ordinary_timeline` | yes (`turn_timeline`) | yes (ordinary advance) | no |
| statuses / buffs / debuffs | ABSENT | yes (modifier model) | partial | no |
| DOT, summons, weakness, resistance | ABSENT | absent or descriptor-only | no | no |
| shields | ABSENT | reference field | no | no |
| break state | family name, no logic | reference module | no | no |
| RNG / event queue / scheduler | partial family names | yes / partial | yes (ordinary) | no |
| wave state | ABSENT | ABSENT | no | no |
| stage state / terminal | families only | yes | custom terminal only | no |

`astra_semantic_freeze_v1.battle_state_contract.status = ARCHITECTURE_ONLY_NO_METHOD_IMPLEMENTATIONS`.

**Verdict:** no `REAL_CONTENT_CAPABLE` BattleState exists.

---

## 10. Executor audit

State-changing paths:

1. **`PrimitiveExecutor`** (`executor.py:37`) — registry dispatch, 92 generic client-method atoms, failures raise `UnsupportedPrimitiveError` (never a silent no-op). Loads `data/semantics/4.4.54/catalog.json`.
2. **`StrictExecutor`** (`strict_executor.py:118`) — supports **exactly one** operation, `terra.strict.no_op/1`; anything else → `UNSUPPORTED`.
3. **`sandbox_transition.py`** — the only path that mutates Terra state; caller-declared resource transition, explicitly not a client-native rule.
4. **`battle_runtime/*`** (3,733 loc) — reference primitive implementations.

Mutation sites are only five: `component_lock_hp_records`, `modifier_state_by_entity`, `entity_property_entries`, `modifier_property_contributions`, `turn_timeline`.

**Real-content executor: NONE.** `battle_runtime/healing.py` implements the real Natasha Skill02 FormulaType 4 slice, but it is **not registered as a primitive**, **not in the catalog**, and states of itself: *"This function performs no HP or dispel mutation. It returns the ordered request boundaries that a future recovered event consumer must apply."*

**M10 reference trace, end to end:** `action_id → session.step → envelope preflight → OrdinaryReferencePacket (REF02) exact-shape validation → reference settlement → SandboxResourceTransaction atomic commit → StagedTrace`. **COMPLETE** for caller-declared local envelopes. Scope limit: *"Explicit local action envelopes; never a recovered HSR skill catalogue."*

**First real action blocker chain (the central chain):**

1. static Skill ID (e.g. `120801`)
2. M13 registry row with `entry_ability = "Avatar_FuXuan_00_Skill01_Phase01"` (string join)
3. behavior root located; `root_compile_status = REJECTED`
4. **STOPS** — the settlement is blocked (`DAMAGE_PACKET` from `EXECUTABLE_REFERENCE_DAMAGE_MIXED_STATE_FIELDS`) and `DamageByAttackProperty` runtime dispatch is unresolved
5. even with a packet, **no binder exists** (`content_planner/__init__.py:17`)
6. even with an envelope, **no real-content BattleState/BattleActor initializer exists**

**Furthest real-content progress:** `Avatar_Natasha_00_Skill02_Phase02` reaches the **HEAL REQUEST BOUNDARY** with a computed `FixPoint(650)`, and deliberately leaves `CurrentHP` unchanged because the positive HealData consumer is unrecovered. Four explicit dependencies remain in that one bounded slice.

---

## 11. Monster runtime audit

**Classification: `FAMILY_LEVEL_ONLY`.**

| join | status |
|---|---|
| Monster static ID → Monster skill | YES at the static layer (12,873 skill rows, 2,648 variants, relations) |
| Monster skill → behavior | **NO** proven entity-exact join |
| behavior → runtime execution | **NO** |

Evidence:

- Compiler: Monster behavior-bearing 3,809 / captured 3,983 / `executable_reference` **48** / golden **0**.
- Failure cluster: `NO_EXECUTABLE_LOWERING`, operation `INVOKE_BEHAVIOR`, owner `Monster`, **2,863** operations (e.g. `Monster_AML_Boss_00_Skill01_Phase01` `ONSTART`).
- `astra_monster_ai_v1`: `ai_policy_binding` PARTIAL; `candidate_generation.status = DECLARED_LEAVES_RECOVERED_RUNTIME_ADMISSION_UNKNOWN`; `terra_contract.ready` PARTIAL with no runtime.
- `astra_monster_ai_pass2`: coverage PARTIAL; `MA-Q01.policy_precedence BLOCKED_BY_EVIDENCE`; 11 sequence IDs require `ExcelOutput/MonsterSkillConfig.json`; 19 child SkillList misses lack inheritance proof.
- No `get_monster_skill` / `get_monster_variant` accessor exists.
- M13 `content_support` covers **Avatar skills only**.

Sub-audit: AI config source availability is CLOSED for 9 paths but **runtime override/inheritance precedence is unproved**; skill choice has declared leaves but no proven runtime-eligible set or winner; turn behaviour, phase transitions, body parts and formation changes are all strict-rejected.

**No exact Monster ID → skill → behavior → runtime execution join is claimed, because none is mechanically proven.**

---

## 12. Stage runtime audit

**Classification: `STATIC_TOPOLOGY_ONLY`.** No implementation exists for wave spawn, wave clear, next-wave transition, enemy formation runtime, stage buff activation, win/lose conditions, score rules, special mode rules, boss phase transitions or terminal state. (grep for `wave_spawn`/`next_wave`/`advance_wave`/`spawn_wave` returns only a string literal in `followup_ledger.py:1876` and a label in `scenario_report.py:109`.)

Semantic evidence: wave model `ARCHITECTURE_CLOSED_NATIVE_DISPATCH_PARTIAL`; wave advance `BLOCKED_BY_EVIDENCE_AND_GRAPH_CONTENT` (every predicate family UNKNOWN); spawn `EXECUTION_BLOCKED`; stage buffs `STATIC_ACTIVATION_SOURCE_DISTINCT_BATTLE_BINDING_PARTIAL` (**exact behavior matches 0**, missing references 17); terminal `SOURCE_PREDICATE_SURFACES_EXACT_EXECUTION_BLOCKED` (1,297 empty win conditions, custom string `[CDT_WaitCustomString:Level_SpecialWin]`); defeat `OPAQUE_UNTIL_PREDICATE_AND_CONTEXT_BOUND`; special mode overrides `RECORDED_NOT_IMPLEMENTED`.

**Trace of stage 420101 (verified present in the current SQLite):**

- `stage_type: Challenge`, `level: 60`, `monster_list: [{monster0: 100401401, monster1: 100402601}]`
- `level_win_condition: ["[CDT_WaitCustomString:Level_SpecialWin]"]`, `level_lose_condition: ["[CDT_WaitCustomString:Level_SpecialLose]"]`
- `stage_config_data` includes `_Wave = 1`, `_IsEliteBattle = 1`, `_BindingMazeBuff = 3110001`
- wave record `420101:1` present

Chain: `Stage ID 420101 → ScenarioCompiler / get_stage_package static assembly → ScenarioPackage hsr_battle_agent.scenario_package/2 → STOP`.
**Stopping point:** the package is a deterministic static document; `scenario_compiler.py:1-31` states it *"deliberately does not ... construct a mutable BattleState"*. Nothing consumes a `ScenarioPackage` to initialize a battle, and the win condition is an opaque custom string so terminal semantics are not evaluable either.

---

## 13. DecisionPoint / legal action audit

- **`DecisionPoint` / `run_until_decision` do not exist at all** — zero grep matches anywhere in `src/`.
- `battle_sandbox/legal_actions.py`: `LegalActionProposal(action_id, candidate_occurrence_id, actor_id, target_ids, resource_cost, target_supported, terminal_supported)`. `query_player_legal_actions` **classifies caller-supplied proposals; it never generates actions.** Modelled constraints: candidate membership, target support flag, terminal support flag, resource sufficiency. **Not modelled:** skills, cooldowns, energy, target aliveness, speed order, ultimate timing, pending decisions, no-input/follow-up events.
- `Sandbox.legal_actions()`, `step()`, `is_terminal()` all raise `StubNotImplementedError("NOT_IMPLEMENTED: legal_actions needs recovered action semantics")`.
- `reference_sandbox/session.py:218` returns a view over caller-declared envelopes; candidate id hardcoded to `ordinary:{actor}`.
- `sandbox_transition.SandboxActionRule` lets the **caller** declare the action.

**Can a real Avatar Skill appear as a legal action today? NO.** Required dependencies, in order: a SkillID/EntryAbility → action binder; an execution model for the settlement family; a real-content BattleState/BattleActor initializer; a `DecisionPoint`/`run_until_decision` loop; real resource semantics (SP/energy/AV recharge).

Three independent guards also prevent it structurally: M15 admission can only return `REJECTED`; `frontend_adapter/render.py:106-117` raises `POSITIVE_REAL_CONTENT_PLANNER_NOT_IMPLEMENTED` on any non-REJECTED result; the re-enacted denial pass records 0 legal actions / 0 state mutations / 0 RNG draws for all 620 canonical skills.

---

## 14. Planner audit

| package | algorithm | objective | state source | classification |
|---|---|---|---|---|
| `planner` (M8) | exhaustive source-order DFS | **none** (horizon / custom terminal) | `CustomScenario` + `SandboxResourceContract` | not a goal-directed engine |
| `planner_search` (M9) | bounded source-order DFS | `RESOURCE_AT_HORIZON` / `REACH_RESOURCE_COMPARISON` / `MIN_STEPS` with LT/LE/EQ/GE/GT | synthetic caller resource | **SEARCH_ENGINE_READY**; adapter not ready |
| `reference_battle_planner` (M11) | bounded source-order DFS over immutable M10 sessions | ENTITY/RESOURCE × HORIZON/REACH/MIN | `ReferenceBattleSession` | **SEARCH_ENGINE_READY**; adapter not ready |

Shared infrastructure: state clone required and present; canonical hash `semantic_hash_v2(snapshot)`; `dedup_mode = ACCOUNT_ONLY` (counts, does not prune); limits `max_depth` / `node_limit` / `max_plans`; `search_rng_draws == 0` asserted everywhere; caller-state mutation asserted; terminal is horizon or caller custom terminal with **no official win/lose condition**.

**Baseline policies: random ABSENT, simple-auto ABSENT, greedy ABSENT, beam ABSENT.** Every object named "policy" in these packages is a frozen search/generation *config*, not a per-action decision policy.

**No reference planner imports any content module.** Reuse assessment:

- `SEARCH_ENGINE_READY`: `planner_search`, `reference_battle_planner`
- `REAL_CONTENT_ADAPTER_READY`: **none**

Both engines are algorithmically complete, deterministic, hash-based and replay-verified; reuse requires a **new real-content state+action adapter** and no engine rewrite.

---

## 15. Determinism / hash / replay audit

| surface | implementation | reusable |
|---|---|---|
| RNG | `SandboxRng` over `random.Random` (MT19937, state 625); `CLIENT_RNG_ALGORITHM = "UNKNOWN"`, `SANDBOX_RNG = "DETERMINISTIC_ABSTRACTION"` | yes (as a declared reference) |
| allocator | `IdentityAllocator` — deterministic, non-reusing, namespace-scoped, generation-aware, reserve/commit/abort/retire with tombstones; rejects `NATIVE_CLIENT_IDENTITY` | yes |
| scheduler ordering | sort by remaining delay; Python stable sort preserves prior order on ties (**a declared sandbox policy**) | only as a declared rule |
| event ordering | monotonic `event_id`, `PrimitiveStarted`/`PrimitiveFinished`, scalar summaries | yes |
| canonical hash | `stable_json_hash`, `logical_battle_hash` (excludes trace), `stable_f01_envelope_hash`, `semantic_hash_v2`, `canonical_v2_bytes` | yes |
| snapshot/clone | `SandboxSnapshot` deep copy; `TerraSnapshotV2` clones state + policy | yes |
| replay | re-step and byte-compare `canonical_v2_bytes`; `REPLAY_STEP_MISMATCH` on divergence; fault injection points | yes |

Assumptions tied only to synthetic/reference semantics: the entire resource model is caller-declared; the tie-break rule is declared, not recovered; the terminal rule is local max-committed-actions; the RNG is a declaration, not the client PRNG.

---

## 16. Validation / oracle audit

| item | value |
|---|---|
| golden fixtures | **0** |
| native traces | **0** (`data/traces/` contains only `.gitkeep`) |
| official-client trace | **NONE** |
| private-server trace | **NONE** (used only as static structure snapshots; four artifacts explicitly disclaim private-server truth) |
| independent oracle | **NONE** (`terra_golden_ledger_v1.json`: `qualifying_independent_native_oracles: []`, `m7_status: BLOCKED`) |
| current test baseline | **1,954 tests, 0 failures, 0 errors** (`python -m unittest discover -s tests -t . -p "test_*.py"`, 203.6 s, 146 test files) |

The baseline is **+79 tests** over the 1,875-test freeze-audit figure — the delta is entirely the 8 P-series commits.

**What is the strongest real-world evidence that any implemented action semantics match HSR? → NONE.** The strongest available tier is `DETERMINISTIC_REPLAY_ONLY` (self-consistency) plus static disassembly evidence. All 1,954 passing tests validate reference-model consistency, contract behaviour, determinism and denial boundaries — **zero** validate any operation against HSR itself.

Anti-promotion mechanisms (four independent lines, all type-identity based, not string equality): `validation/oracles.py` promotion gate; `battle_ir/evidence.py` three separate `_StrictVocabulary` enums where `CLOSE_4.4.0_TO_4.4.54` can never merge as `EXACT_NATIVE`; `evidence_boundary.py` module-private `_NATIVE_SEAL`; `reference_boundary.py` whose `promote_to_native()` unconditionally raises; plus `gate_certificate.py` requiring `NATIVE_EVIDENCED` closure.

---

## 17. Live reader audit

**Classification: `STATIC_ONLY`.** The live-battle-state sub-capability is `NONE`.

- Not `NONE` overall because real attach + `ReadProcessMemory` code exists under `tools/runtime_snapshot/*.py` (ctypes, `OpenProcess` with `PROCESS_QUERY_INFORMATION|PROCESS_VM_READ`, PSAPI enumeration) and `tools/runtime_probe/` (C++ `LoadLibraryW` via `CreateRemoteThread` + `DllMain`).
- Not `PARTIAL_LIVE` because those tools read only known UnityPlayer/GameAssembly ranges and static-derived pointer chains. `pgoo_live_dispatch_observation_stage1_blocker_20.md`: they *"do not locate managed task/executor instances, inspect execution registers, or enumerate heaps"*. `tools/runtime_probe/README.md`: it does **not** enter BattleInstance / Ability Execute / Modifier Runtime / Battle Sandbox.
- Absence checks: `pymem` 0, `frida` 0, `ptrace` 0, `.proto`/`.pcap` files 0, network protocol reader 0, OCR/screen capture 0, client hooks 0.
- `src/hsr_battle_agent/runtime/` contains only `.gitkeep` and a 3-line README placeholder.
- Frontend: `LiveBattleBackendAdapter.ts` is `kind='LIVE'` but every method throws `BackendNotConnectedError`, `contractStatus = NOT_CONNECTED`, `supportedMethods: []`. `BattleBackendAdapter.ts` states *"The real backend API does not exist yet"*.
- Probe status itself: experimental and blocked — `STATIC_TARGET_UNRESOLVED`; `runtime_probe` Phase A never launched and was blocked at `OpenProcess error 5`.

---

## 18. Product / frontend audit

| surface | status |
|---|---|
| static product browse | SOLVED (static) — FE1/FE2 M14 capability index + M15 rejection view over ~620 skill rows; FE3 product layer generated (97 characters / 628 monsters / 1459 stages / 1543 encounters, 30 detail chunks, 3727 complete details) but **not mounted** in any app/panel module |
| Scenario compilation | SOLVED (static) — P0 IDENTICAL over 1459 stages / 6717 placements / 0 unresolved; P1 `scenario_package/2`, team size 1..4 enforced, reachable rule states only `UNKNOWN`/`UNSPECIFIED` |
| Support Report | SOLVED (static aggregation) — `real_content_execution_performed false`, `planner_invoked false`, `battle_state_created false`, `m10_m11_invoked false` |
| browser → Python bridge | SOLVED (local transport) — single-threaded loopback HTTP on `127.0.0.1:8765`, routes `GET /info`, `POST /scenario/compile`, `POST /scenario/support`; capabilities `battle_execution false / planner false / native_execution false`; end-to-end PASS via a real FE3 client |

P-series: **P0 DONE, P1 DONE, P2 DONE, P3 DONE, P4 DONE, P5A DONE, P5B DONE** (all static or static-transport).

**None of these advance real execution directly.** The only product-layer code that runs anything is `frontend_adapter/render.py emit_planner_result()`, which can invoke the **reference** planner on caller-declared M10 envelopes.

---

## 19. Original-goal gap matrix

Full 34-row machine-readable matrix is in the JSON (`gap_matrix`). Condensed:

| row | CURRENT_STATUS | REAL_CONTENT | RUNTIME | PLANNER_READY | NATIVE_VALIDATED |
|---|---|---|---|---|---|
| Static Avatar content | PRESENT | YES | NO | N/A | NO |
| Static Monster content | PRESENT | YES | NO | N/A | NO |
| Static Stage content | PRESENT | YES | NO | N/A | NO |
| Loadout | PARTIAL | YES | NO | NO | NO |
| Behavior binding | PARTIAL | YES | NO | NO | NO |
| Behavior IR | REPRESENTATION_ONLY | YES | PARTIAL (generic atoms) | NO | NO |
| BattleState | ARCHITECTURAL_SHELL | NO | PARTIAL (legacy/ref) | NO | NO |
| Generic executor | PARTIAL | NO | PARTIAL | NO | NO |
| Damage | REFERENCE_MODEL_ONLY | NO | PARTIAL | NO | NO |
| Toughness / break | REFERENCE_MODEL_ONLY | NO | NO | NO | NO |
| Energy | ABSENT | NO | NO | NO | NO |
| SP | PARTIAL (declared) | NO | PARTIAL (synthetic) | NO | NO |
| Speed / action order | PARTIAL (declared) | NO | PARTIAL | NO | NO |
| Buff / Modifier | PARTIAL | NO | PARTIAL | NO | NO |
| DOT | REPRESENTATION_ONLY | NO | NO | NO | NO |
| Shield / Heal | PARTIAL (request boundary) | PARTIAL | NO mutation | NO | NO |
| Triggers | REPRESENTATION_ONLY | NO | NO | NO | NO |
| Follow-up | REPRESENTATION_ONLY | NO | NO | NO | NO |
| Summons / memosprite | ABSENT | NO | NO | NO | NO |
| RNG | REFERENCE_MODEL_ONLY | NO | PARTIAL | NO | NO |
| Scheduler | PARTIAL | NO | PARTIAL (ordinary) | NO | NO |
| Monster AI | FAMILY_LEVEL_ONLY | NO | NO | NO | NO |
| Stage runtime | STATIC_TOPOLOGY_ONLY | NO | NO | NO | NO |
| **DecisionPoint** | **ABSENT** | NO | NO | NO | NO |
| Legal actions | PARTIAL (classification only) | NO | NO | NO | NO |
| State clone / hash | **PRESENT** | N/A | YES | YES | NO |
| Replay | **PRESENT** | N/A | YES | YES | NO |
| Baseline policy | ABSENT | NO | NO | NO | NO |
| Greedy planner | ABSENT | NO | NO | NO | NO |
| Beam planner | ABSENT | NO | NO | NO | NO |
| Native validation | ABSENT | N/A | NO | NO | NO |
| Live reader | STATIC_ONLY | NO | NO | N/A | NO |
| Advisor | ABSENT | NO | NO | NO | NO |
| Frontend product plumbing | PRESENT | NO | NO | NO | NO |

---

## 20. First real action candidate census

Mechanical derivation from `per_skill_records` (n = 324) in `full_action_closure_census_001.json`, filtered to: settlement present, no second hop, zero target/resource/predicate/modifier blockers, no MODIFIER/RANDOM_TARGET/RETARGET/RESOURCE/HEAL_PACKET classes, no DOT/HEAL settlement kind. **98 rows** meet the filter; **10 enumerated** per the change request.

**This ordering is a mechanical sort key, NOT a ranking of merit. No candidate is selected. Selection is explicitly left to SOL.**

All 10 share: provenance `CLOSE_4.4.0_TO_4.4.54` @ `b11066be` with `source_version_unverified: true`; join rule `(AvatarConfig.AvatarID, AvatarSkillConfig.SkillTriggerKey) == same-owner CharacterConfig.SkillList[]`; M14 `FULL_ACTION_REPRESENTED` + `STRICT_REJECT_UNTIL_NEW_EVIDENCE`; settlement kind `DAMAGE_REQUEST`; target model `AbilityTargetEntity` (2 targets, 1 damage alias).

| # | avatar_id | skill_id | entry_ability | settlement body | closure ops | status | M14 support | residual classes | packet extras |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1208 | 120801 | `Avatar_FuXuan_00_Skill01_Phase01` | `..._Phase02` | 11 | ACTION_C | BLOCKED_BY_EVIDENCE | DAMAGE_PACKET | SPHitRatio |
| 2 | 1303 | 130301 | `Avatar_RuanMei_Skill01_Phase01` | `..._Phase02` | 11 | ACTION_C | BLOCKED_BY_EVIDENCE | DAMAGE_PACKET | SPHitRatio |
| 3 | 1501 | 150101 | `Avatar_Sparxie_00_Skill01_Phase01` | `..._Phase02` | 11 | ACTION_C | BLOCKED_BY_EVIDENCE | DAMAGE_PACKET | SPHitRatio |
| 4 | 1401 | 140101 | `Avatar_TheHerta_00_Skill01_Phase01` | `..._Phase02` | 11 | ACTION_C | BLOCKED_BY_EVIDENCE | DAMAGE_PACKET | SPHitRatio, HitEffectHeight, HitPosHeight |
| 5 | 1506 | 150601 | `Avatar_SilverWolf999_00_Skill01_Phase01` | `..._Phase02` | 14 | ACTION_C | BLOCKED_BY_EVIDENCE | DAMAGE_PACKET | HitMotion (+ missing damage percentage) |
| 6 | 1504 | 150401 | `Avatar_Ashveil_00_Skill01_Phase01` | `..._Phase02` | 8 | ACTION_D | REPRESENTABLE_BLOCKED | BANNC + DAMAGE_PACKET | — |
| 7 | 1310 | 131001 | `Avatar_Sam_00_Skill01_Phase01` | `..._Phase02` | 9 | ACTION_D | REPRESENTABLE_BLOCKED | BANNC + DAMAGE_PACKET | — |
| 8 | 1404 | 140401 | `Avatar_Mydeimos_00_Skill01_Phase01` | `..._Phase02` | 9 | ACTION_D | REPRESENTABLE_BLOCKED | BANNC + DAMAGE_PACKET | — |
| 9 | 1215 | 121501 | `Avatar_Hanya_00_Skill01_Phase01` | `..._Phase02` | 10 | ACTION_D | REPRESENTABLE_BLOCKED | BANNC + DAMAGE_PACKET | — |
| 10 | 1008 | 100801 | `Avatar_Arlan_Skill01_Phase01` | `..._Phase02` | 10 | ACTION_D | REPRESENTABLE_BLOCKED | BANNC + DAMAGE_PACKET | — |

(`BANNC` = `BEHAVIOR_AFFECTING_NODE_NOT_COMPILED`. Every candidate additionally carries `WAIT_ANIM_STATE` as a presentation wait; row 4's root is `COMPILED_STRUCTURE_ONLY` while the rest are `REJECTED`.)

Missing runtime primitives common to all 10: a damage-packet consumer for the mixed-state `DamageByAttackProperty` request; a wait/presentation barrier primitive with declared ordering semantics; a real-content BattleActor/BattleState initializer; a SkillID/EntryAbility → action binder.

**Explicitly not selected:** the M12 census's own previous SOL candidates (Phainon 1408/140, SilverWolf999 1506/150601 Skill02) were re-verified and their residual sets are recorded in the census; `1408/140801` appears in the further-named list.

**Two current artifacts contradict each other and the contradiction is left standing:** `simple_skill_candidate_index_21.md` claims the global serialized HealHP selector is 7 and that a heal path bypasses the PGOO blocker; `natasha_skill02_healhp_content_30.md` explicitly **retracts** that selector claim (global TaskConfig registry uses ULEB discriminators; HealHP = 1481) and `direct_hp_real_content_census_28.md` records `DIRECT_HP_AVATAR_SLICE_NOT_FOUND`.

---

## 21. Runtime foundation dependency graph

30 nodes and 30 edges are recorded in the JSON (`runtime_foundation_dependency_graph`). Key chains:

```
content_static → validated_loadout → initial_battle_actor → real_content_battlestate   [MISSING x2]
content_static → behavior_root_binding → behavior_ir → operation_lowering → skill_action_adapter
operation_lowering → damage_packet ← damage_dispatch_resolution (BLOCKING)
positive_heal_consumer → hp_mutation (BLOCKING for the heal path)
legal_action_generator → decisionpoint_loop → planner_search_engine
real_content_battlestate → real_content_adapter_for_planner → planner_search_engine
trace → native_validation_oracle → live_reader → advisor
```

Clean-layering constraint: `battle_sandbox` and `battle_runtime` import **zero** `game_data` modules and planners import **zero** content modules, so real-content work must add an **adapter layer** rather than modify the existing engines.

---

## 22. What should stop

| stream | sufficient? | on critical path? | why |
|---|---|---|---|
| P2/P3 product projection | yes | **no** | read-only projection; executes no behavior IR; supplies no input any runtime node needs |
| P4 support reporting | yes | **no** | declares `real_content_execution_performed false`; aggregates what already exists |
| P5A/P5B frontend adapters + visual frontend | yes | **no** | bridge capabilities pin battle/planner/native execution to false; Live adapter is a NOT_CONNECTED skeleton; FE3 not even mounted |
| M14 display enhancements / registry viewing | yes | **no** | the viewer displays data whose execution readiness is `STRICT_REJECT_UNTIL_NEW_EVIDENCE` for the bound population; better display of a denial does not move the denial |
| M15 admission expansion | yes | **no** | vocabulary is deliberately `{REJECTED}`; expansion depends on execution semantics that do not exist — downstream, not upstream |
| additional static product collections / missing accessors | yes | **no** | static tables are already sufficient for execution; missing accessors are conveniences |
| F7 relic vocabulary doc alignment | no | **marginal** | does not block execution by itself, but the loadout contract text cannot be used as a schema until aligned |
| F5 loadout completeness | no | **yes, conditional** | becomes a direct dependency of `initial_battle_actor` if the first real action needs initial character state |
| frontend visual polish / UX | user-owned | **no** | explicitly out of scope |

---

## 23. Audit verdict

## **C. `REAL_RUNTIME_BLOCKED_BY_MISSING_RECONSTRUCTION`**

Real HSR 4.4.54 content cannot yet produce a **single** BattleState transition, because the behavior reconstruction deliberately refuses 29,086 operation nodes and has recovered no runtime execution semantics for any of them. **Zero of 620 canonical skills is executable.**

Why C:

1. `binding_level_distribution` records `CONTENT_ACTION_EXECUTABLE_REFERENCE = 0` and `REFERENCE_SETTLEMENT_BOUND = 0` — every one of the 620 rows is `STATIC_ONLY`, `BEHAVIOR_ROOT_BOUND` or `FULL_ACTION_REPRESENTED`, and none is executable.
2. The compiler refuses 29,086 nodes with `BEHAVIOR_AFFECTING_NODE_NOT_COMPILED` under `REJECT_NOT_NOOP`, so a rejected record cannot be promoted piecewise.
3. `ACTION_A_CURRENTLY_CLOSED = 0` and `ACTION_B_WAIT_ONLY = 0` across all 324 censused rows; the minimum residual is still 1 blocker class.
4. The single skill with a recovered chain (Natasha Skill02, heal) reaches a request boundary and deliberately performs **no mutation**; four explicit dependencies remain in that one slice.
5. `DamageByAttackProperty` dispatch is `PARTIAL_RESOLUTION - TARGET_UNRESOLVED` and the `SPHitRatio` evidence artifact is itself `BLOCKED_BY_EVIDENCE` with an explicit instruction not to re-enter SOL on it.
6. `TriggerAbility` readiness is `NO` with expected new coverage 0; `full_native_behavior_reconstruction_complete: false`.
7. Monster runtime admission is UNKNOWN and Stage wave advance is blocked, so no non-avatar content can fill the gap.

**Why not D (missing state model):** D presupposes content sufficiency. Content is demonstrably insufficient. D-type work *is* also unfinished — TerraBattleState is a 61-empty-store shell, energy/DOT/summons/weakness/shields have no representation, `DecisionPoint` does not exist, `legal_actions` only classifies — and it will have to be done, but it is **not the binding constraint**; building the state model first would produce a runtime with nothing to run. It is recorded as the next-in-line co-blocker.

**Why not A or B:** no bounded fix set exists. The blocker set spans content extraction (11 monster sequence IDs, direct-HP node mapping, DynamicFloat operands, the `+0x120` dispatch), semantic mapping (TriggerAbility activation, AI precedence, wave advance, terminal predicates), runtime primitives (positive heal consumer, event trigger engine) and evidence (0 golden, 0 native trace, empty oracle ledger).

**Why not E:** the foundations do not conflict with the goal. The evidence-gated layering, frozen evidence vocabularies, deterministic hash/clone/replay infrastructure and two complete DFS search engines are all correct and reusable. The consistent finding across every module is **"denied, not wrong"**.

---

## 24. Output files

- `data/control/real_runtime_reentry_audit_20260929_001.json` (97 KB, 35 sections)
- `docs/agent/handoffs/real_runtime_reentry_audit_20260929_001.md` (this document)
- `D:\HSR_Battle_Agent\agent_handoffs\CR-REAL-RUNTIME-REENTRY-AUDIT-20260929-001_changed_files.zip` (contains the two files above + `HANDOFF_MANIFEST.json`)

No production code changes. No test changes.

---

## 25. Claim boundary

- No production code was modified; no test was modified.
- No git write of any kind was performed.
- No feature was implemented, no architecture was redesigned, no frontend visual work was done.
- No fix is proposed for any blocker identified.
- No first action was selected and no candidate is ranked by merit.
- No roadmap is written.
- No real-content execution is claimed anywhere.
- No source-backed reconstruction is upgraded into native validation.
- Counts from M12 census artifacts were produced at heads `311b6e9b` and `8a4dcb0`; SQLite counts, module inventory, grep results and the 1,954-test baseline were measured at HEAD `7eb82ec`.
- The dirty working tree was treated as authoritative current source and was preserved, never staged.

**NEXT: SOL.**
