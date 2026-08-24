# Battle Reverse Current State

## Scope

- Workspace: `D:\HSR_Battle_Agent\hsr-battle-agent`.
- Current game version: `4.4.54`.
- GameAssembly provenance still points at the versioned client input recorded by the normalized manifest.
- Unpack pipeline: `V1_STATIC_COMPLETE`.
- Evidence ladder is unchanged: CONFIRMED, SUPPORTED, UNKNOWN.
- Native behavior requires dataflow, writes, branches, and consumers; names are supporting discovery evidence only.
- This document is the compact session entry point.
- Do not reread historical batch reports unless this file or a source artifact points to one.

## Latest semantic frontier

- HealHP content status: `NATASHA_HEALHP_CONTENT_24_PARTIAL`. The local
  archive contains `Avatar_Natasha_00_Skill02_Phase02`
  (`0xBC995F`–`0xBC9BC8`) as the bounded Natasha heal-bearing record, with
  `Heal`, `SkillTargetEntityList`, `TargetEntity`, `HPByMaxHP`, and `MaxHP`
  tokens present. The exact HealHP polymorphic config tag and amount fields
  are not yet decoded. See
  `docs/agent/handoffs/natasha_healhp_content_24.md` and
  `data/raw/4.4.54/natasha_healhp_content_24.json`.

- Stage 1 of the Core Sandbox Closure is **BLOCKED** with
  `RUNTIME_INSTANCE_OBSERVATION_REQUIRED`. The required live
  `PGOOHIHKHNJ` executor instance at M507304 cannot be obtained by the
  approved read-only readers: they follow only known static-derived chains and
  have neither an executor-instance locator nor execution-context capture.
  The existing in-process probe requires forbidden DLL injection/remote
  threading. See
  `docs/agent/handoffs/pgoo_live_dispatch_observation_stage1_blocker_20.md`
  and
  `data/raw/4.4.54/pgoo_live_dispatch_observation_stage1_blocker_20.json`.
- Therefore the unresolved pointer `F = [[PGOOHIHKHNJ instance]+0x0+0x120]`,
  its exact target, B identity, and `B[+0x2D8]` producer remain UNKNOWN; do
  not enter any candidate callee or later Core Sandbox Closure stage until an
  approved code-guided instance observation is available.

- Completed capabilities: Handoff 09 `MODIFIER_PROPERTY_EFFECT_09_PROOF`,
  Handoff 10 `GENERIC_PROPERTY_SOURCE_SLOT_MATERIALIZATION_10_PROOF`, and
  Handoff 11 `GENERIC_PROPERTY_MUTATION_SOURCE0_11_PROOF`.
- Completed: Handoff 12 `DIRECT_DAMAGE_HP_TRANSITION_12_PROOF` (scoped
  HP-transition contract, not damage-system semantics).
- Completed: Handoff 13 `DAMAGE_VALUE_TO_HP_BRIDGE_13_PROOF` (scoped
  generated-executor -> TargetDamageHP -> DirectDamageHP bridge; still not a
  damage formula).
- Completed: Handoff 14 `DAMAGE_EVALUATOR_Q_14_PROOF` (Q is a selected ratio
  or FixPoint(0); only global 0x95B1E18 concrete value remains UNKNOWN).
- Current frontier: HP transition for `DirectDamageHP(damage_kind=100,
  mode=0)` is CLOSED; modes 4/5/6 and post-transition consumers remain
  UNKNOWN.
- Session state: DirectDamageHP intercept at `0xE7333E0` is resolved as
  M506532 `TryGetLockHP`; both sides of the decision, the shared source-0
  CurrentHP write, and the bounded NegativeHP policy are recovered.
  `K_INITIALIZED_VALUE = FixPoint(2)` remains CONFIRMED, with lifetime
  immutability UNKNOWN. The reusable global/static writer classifier and its
  K probe output remain at
  `data/raw/4.4.54/current_hp_bound_global_writer_probe.json`.
- Artifact: `data/semantics/4.4.54/generic_property_mutation_11.json`.
- Topology artifact: `data/raw/4.4.54/modifier_effect_topology_09.json`.
- Handoffs: `docs/agent/handoffs/semantic_handoff_09.md`, `docs/agent/handoffs/semantic_handoff_10.md`, `docs/agent/handoffs/semantic_handoff_11.md`, `docs/agent/handoffs/semantic_handoff_12.md`, `docs/agent/handoffs/semantic_handoff_13.md`, `docs/agent/handoffs/semantic_handoff_14.md`.
- Handoff 10 refines 09's opaque contribution key to a stable PropertyEntry `source_index`.
- The capability includes source-slot lifecycle and materialization framework.
- Per-kind fixed-point operator names/formulas are still not accepted.
- It is not a damage formula.
- It adds a persistent, Modifier-owned contribution record and reverses it through the same stable source index.
- Handoff 11 adds the scoped mutable/base path: source slot `0` supports fixed-point `Set/Add/Mul/Min/Max`, rebuild, then a post-change bridge call.
- This mutation capability deliberately excludes non-null post-transform context and the native special-property IDs.
- Handoff 12 is now a completed, scoped HP-transition contract: SetHP ->
  DirectChangeHP -> DirectDamageHP(damage_kind=100, mode=0) -> CurrentHP
  source-0, with the `TryGetLockHP` intercept, lock threshold, DirtyHP-ratio
  bound, and bounded NegativeHP policy. It is not a damage contract.
- Handoff 12 additionally records the CurrentHP bound branch's exact control
  flow with a confirmed initial value: `K` at `.data` RVA `0x95B1E80` is
  initialized to `FixPoint(2)` by `RPG.GameCore.FixPoint..cctor` (M68145,
  RVA `0x1D66A320`, direct store `0x1D66A34E`). Lifetime immutability is
  UNKNOWN.

## Confirmed reusable runtime chain

- DynamicValue.
- Fixed-point arithmetic.
- Comparison.
- Predicate/evaluator.
- Target selector.
- Generated task executor.
- Modifier application.
- Modifier lifecycle.
- Persistent modifier BattleState.
- Generic Modifier property-contribution ownership.
- Generic property contribution removal boundary.
- Generic PropertyEntry source-slot lifecycle and materialized-value write boundary.
- Generic untransformed source-0 Property mutation.
- Fixed-point Add/Subtract/Multiply helpers used by Property mutation.
- SetHP-to-CurrentHP source-0 transition evidence.
- DirectDamageHP HP transition: `TryGetLockHP` intercept, lock threshold,
  DirtyHP-ratio bound, shared source-0 CurrentHP write, bounded NegativeHP
  policy.
- Coding-ready CurrentHP bound initial-value contract (`K = FixPoint(2)`).

## Baseline commits that MUST remain intact

- `04dc482 sandbox: add modifier lifecycle runtime`.
- `a15df00 reverse: recover modifier lifecycle bridge`.
- `f3476d9 sandbox: add modifier application runtime`.
- `33cf283 reverse: recover modifier application bridge`.
- `b62910f sandbox: add action execution runtime`.
- `1ec6983 reverse: recover action execution bridge`.
- `74c5a59 sandbox: add target selector runtime batch`.
- `7ae767f reverse: recover target selector semantic batch`.
- `dc668d7 sandbox: add predicate evaluation runtime`.
- `8d4319e reverse: recover predicate evaluation bridge`.
- `e1b2668 sandbox: add fixpoint comparison runtime batch`.
- `11a6019 reverse: recover fixpoint comparison semantic batch`.
- `c66451f sandbox: add DynamicValue runtime batch`.
- `a2ea2d1 reverse: recover DynamicValue semantic batch`.
- `410ea94 reverse: recover first battle semantic vertical slice`.
- `ca98440 unpack: add versioned reverse pipeline v1`.

## Modifier lifecycle contract already sealed

- `TryAddModifierInstance` decision tree is recovered.
- `ModifierConfig.Stacking` behavior is recovered for the accepted cases.
- Duplicate-match identity is recovered.
- `Multiple`, `RetainGlobalLatest`, and `RetainGlobalLatestUnique` are recovered.
- Refresh/replace paths are recovered at their published scope.
- `Destroy` transitions State to `ToBeRemoved`.
- `RemoveDirtyModifiers` performs shift-left removal.
- Modifier State values: `ToBeAdded`, `Alive`, `ToBeRemoved`, `Removed`.
- Base virtual slot 13 is `OnAdded`.
- Base virtual slot 14 is `OnActivate`.
- Do not rediscover any of those facts.

## Modifier effect topology 09

- Battle-reachable callback root is `RPG.GameCore.TurnBasedModifierInstance`.
- `OnAdded`: M506175, slot 13, RVA `0xE781890`.
- `OnActivate`: M506176, slot 14, RVA `0xE781C40`.
- Metadata name matches outside this rooted chain are not automatically Modifier overrides.
- Topology has two battle-reachable callback bodies, not hundreds of proven subclass bodies.
- `OnAdded` is classified `LIFECYCLE_ONLY` at current scope.
- `OnActivate` is classified `COMPOSITE`.
- High-value shared paths include property callbacks, stack cleanup, and event dispatch.
- Property contribution was selected first because its task-to-persistent-write chain is bounded and reusable.

## Property contribution contract 09

- Config runtime type: `RPG.GameCore.StackProperty`, type index 23267.
- Declared fields: `TargetType`, `Property`, `PropertyValue`, `Silence`, `IsRefresh`.
- Serializer M127753 proves used slots `+0x18`, `+0x20`, `+0x28`, `+0x30`, `+0x31`.
- Config-to-executor association is SUPPORTED, not CONFIRMED by a direct factory edge.
- Generated executor runtime type: `LEIHMEGJNME`, type index 54986.
- Executor constructor M506081 stores task context at `+0x18` and config at `+0x20`.
- Executor `OnTaskBegin` M506082 reads config `+0x18/+0x20/+0x28`.
- M506082 selects targets in forward order.
- M506082 evaluates the DynamicValue once in task context.
- M506082 invokes Modifier `StackProperty` M506199 per target.
- M506199 no-ops when Modifier State is beyond Alive.
- Normal M506199 path calls component `StackProperty` M506495.
- M506495 allocates a stable target PropertyEntry `source_index`.
- M506199 appends `{property_id, source_index, target_component}` at Modifier `+0x240`.
- Refresh uses a forward matching scan and M506497.
- Source of refresh flag for every config path is UNKNOWN.
- `_PopStackedProperties` M506312 walks `+0x240` in forward order.
- M506312 calls component `UnStackProperty` M506496 with the recorded source index.
- M506312 consumes/clears its contribution records.
- Source allocation/update/removal marks slots active/inactive without shifting indices.
- Each mutation rebuilds PropertyEntry `+0x78` before `_AfterPropertyChanged` notification.
- PropertyEntry materialization kind `+0x58` has seven native modes; only reducer topology is accepted.
- The adapter `0x15C6E450` sits between raw StackProperty input and source-slot value; it is not yet canonical.

## Generic Property mutation 11

- `M506503 ModifyProperty` is a generic source-0 mutation API on `TurnBasedAbilityComponent`.
- Native function IDs are proven: `1 Set`, `2 Add`, `3 Mul`, `4 Min`, `5 Max`; unsupported IDs use the native Set fallthrough.
- The helper reads old `entry[+0x78]`, computes fixed-point candidate, then calls `0x19CAF14A0` before the common source-0 update.
- The exact coding-ready scope requires `entry[+0x40] == null`; `0x19CAF14A0` then returns without changing the candidate.
- For property IDs outside `{10,12,14,16,18,20,22,24,26,28,30,32}`, M506503 reaches common tail `0xE72E8F9`.
- The tail calls Handoff 10 `UpdatePropertySourceSlot(entry, 0, candidate)`, rebuilds `+0x78`, and calls M506625 with old/new values.
- Source index `0` is a native mutable/base path, not a Modifier-owned contribution allocation.

## Current BattleState requirements

- Existing: `modifier_state_by_entity`.
- New required: `modifier_property_contributions` keyed by logical ModifierRef.
- A contribution record keeps target identity, property ID, and stable source index.
- New required: `entity_property_entries` keyed by `(entity, property_id)`.
- Each entry owns source generation, active flags, source values, materialization kind/base/post-transform inputs, and materialized value.
- Contribution sources and materialized values must remain separate representations.
- Ordered records are part of the contract.
- Key removal is part of the contract.
- Preserve source index `0` separately from modifier contribution ownership.
- Persist post-transform context so the scoped mutation runtime can reject non-null contexts.

## Source-of-truth files

- Environment rules: `docs/agent/dsh_windows_environment.md`.
- Modifier application bridge: `docs/battle_semantics/modifier_application_bridge_07.md`.
- Modifier lifecycle bridge: `docs/battle_semantics/modifier_lifecycle_bridge_08.md`.
- Modifier application artifact: `data/semantics/4.4.54/modifier_application_bridge_07.json`.
- Modifier lifecycle artifact: `data/semantics/4.4.54/modifier_lifecycle_bridge_08.json`.
- Lifecycle Sandbox report: `data/sandbox/modifier_lifecycle_runtime_08_report.json`.
- Topology 09: `data/raw/4.4.54/modifier_effect_topology_09.json`.
- Property capability 09: `data/semantics/4.4.54/modifier_property_effect_09.json`.
- Handoff 09: `docs/agent/handoffs/semantic_handoff_09.md`.
- Property materialization 10: `data/semantics/4.4.54/generic_property_materialization_10.json`.
- Handoff 10: `docs/agent/handoffs/semantic_handoff_10.md`.
- Property materialization builder: `tools/reverse/scripts/build_generic_property_materialization_10.py`.
- Property mutation 11: `data/semantics/4.4.54/generic_property_mutation_11.json`.
- Handoff 11: `docs/agent/handoffs/semantic_handoff_11.md`.
- Property mutation builder: `tools/reverse/scripts/build_generic_property_mutation_11.py`.
- DirectDamageHP HP-transition artifact:
  `data/semantics/4.4.54/direct_damage_hp_transition_12.json`.
- HP-transition handoff: `docs/agent/handoffs/semantic_handoff_12.md`.
- Damage value to HP bridge artifact:
  `data/semantics/4.4.54/damage_value_to_hp_bridge_13.json`.
- Damage value to HP bridge handoff:
  `docs/agent/handoffs/semantic_handoff_13.md`.
- Damage evaluator Q artifact:
  `data/semantics/4.4.54/damage_evaluator_q_14.json`.
- Damage evaluator Q handoff:
  `docs/agent/handoffs/semantic_handoff_14.md`.
- Reusable evidence helpers: `tools/reverse/scripts/semantic_batch_evidence.py`.
- Reusable bounded xrefs: `tools/reverse/scripts/semantic_method_xrefs.py`.
- Global/static writer classifier:
  `tools/reverse/scripts/global_static_writer_classifier.py`.
- K probe output: `data/raw/4.4.54/current_hp_bound_global_writer_probe.json`.

## Current direct dependency frontier

- `0x19B4485C0` is now classified as a large tag-dispatch runtime rather than a small property formula; do not collapse it into arithmetic.
- M506503's CurrentHP branch `0xE72E162` is now a coding-ready bound
  initial-value contract: it reads MaxHP index `1`, M506511 `GetDirtyHP`, and
  branches around the common source-0 tail.
- M506511 `GetDirtyHP` at `0xE734050` has confirmed
  `MaxHP * DirtyHPRatio + DirtyHPDelta` arithmetic, and the CurrentHP bound
  policy is confirmed with `K_INITIALIZED_VALUE = FixPoint(2)`: candidate `<
  bound` writes candidate; candidate `>= bound` uses fixed-point min/max
  against `K` before the same source-0 write. `K` lifetime immutability remains
  UNKNOWN.
- `M506499 DirectDamageHP(damage_kind=100, mode=0)` is now closed as an
  HP-transition contract: intercept `0xE7333E0` is M506532 `TryGetLockHP`;
  `0xE73231C -> 0xE7327B4 -> 0xE732C6B` is the no-lock path; the lock side
  converges through the same source-0 CurrentHP write. See Handoff 12 and
  `data/semantics/4.4.54/direct_damage_hp_transition_12.json`.
- `M507308 -> M504579 -> M506499` is now closed as a scoped bridge
  (`DAMAGE_VALUE_TO_HP_BRIDGE_13_PROOF`). Normal path:
  `DirectDamageHP(damage_kind=11, mode=0)` with delta
  `fp_mul(MaxHP, Q) - CurrentHP`; fallback path uses `-V` with
  damage_kind 10/0 and mode 0 (or a dynamic mode UNKNOWN).
- M530155 `GOCKCOMLFEO` is now closed (`DAMAGE_EVALUATOR_Q_14_PROOF`):
  `Q = fp_div(N, D)` when `D > global 0x95B1E18`, else `Q = FixPoint(0)`.
  Component path uses `D = MaxHP` and `N = CurrentHP`; fallback fields are
  `e[+0x20]` / `e[+0x18]`.
- Next native frontier, only if promoted to a new task: concrete
  initialization/meaning of global `0x95B1E18`, or M723335 `0x15B8BB50`
  patch paths.
- `0x195C6D120` remains generated tag-dispatch evidence, not a DamageRequest.
- Event/listener and Turn/AV work remain deferred.

## Known UNKNOWN

- Per-property adapter semantics for raw StackProperty input.
- Exact fixed-point operator names/formulas for materialization kinds 3..7.
- Design-data initialization of PropertyEntry kind/base/post-transform fields.
- Exact semantics of `Silence` and `IsRefresh` in every StackProperty path.
- Universal lifecycle route from `Destroy` to property-pop cleanup.
- Minimal DamageRequest/HitContext runtime boundary.
- Damage resolution formula.
- Non-null `0x19CAF14A0` post-transform policy.
- DirectDamageHP modes 4/5/6 and special FixPoint NaN/Infinity encoding
  branches inside its inlined compare blocks.
- General DirtyHP policy beyond the M506499 mode-0 DirtyHPRatio bound
  (DirtyHPDelta remains M506511 `GetDirtyHP` only).
- General NegativeHP consumers beyond the scoped DirectDamageHP policy.
- M504598 `_MortallyWondedProcess` internal post-process formula.
- M530155 `GOCKCOMLFEO` evaluator algorithm is CONFIRMED; concrete runtime
  value of global `0x95B1E18` is UNKNOWN (threshold role only).
- M504557 `RecomputeShieldCost` and fallback global `0x95C1CC0`.
- M504579 dynamic fallback mode `record[+0x19C]` (may select DirectDamageHP
  modes 4/5/6; not reversed).
- `K` lifetime immutability (initialized value `FixPoint(2)` is CONFIRMED;
  absolute immutability UNKNOWN; probe census in
  `data/raw/4.4.54/current_hp_bound_global_writer_probe.json`).
- Event listener registration, order, and unregister identity.
- Action completion and next-turn scheduling.

## MUST NOT redo

- MHY metadata schema.
- Identifier resolver.
- TypeDefinition, MethodDefinition, FieldDefinition, ParameterDefinition.
- Method code registry.
- DesignData bridge.
- Generated polymorphic registry foundation.
- Target config runtime bridge.
- Action config runtime bridge.
- Modifier application/lifecycle identity.
- Any Batch 02 through 08 published contracts.

## Implementation prohibitions

- Do not turn contribution addition into `final += value` or bypass PropertyEntry rebuild.
- Do not turn contribution pop into `final -= value`, shift source keys, or clear stale value slots as a substitute for deactivation.
- Do not treat generic source `0` mutation as modifier contribution removal/rollback.
- Do not use generic untransformed mutation for CurrentHP or another native special property ID.
- Do not hardcode Black Swan.
- Do not build full EntityState speculatively.
- Do not implement planner, Beam, MCTS, model training, or frontend work.
- Do not use strings/names alone as gameplay proof.

## Environment and worktree constraints

- Use the project Python resolver only.
- Do not invoke bare `python`, `py.exe`, `where.exe`, or `vswhere.exe`.
- Prefer existing normalized data and reusable scripts.
- Keep `hsr_design_data_hashes.csv` untouched.
- Keep `hsr_design_data_inventory.csv` untouched.
- Keep `tools/reference/` untouched.
- Keep `tools/reverse/vendor/` untouched.
- Do not absorb unrelated worktree changes.

## Immediate next entry procedure

- The damage-evaluator Q contract is closed; implementation input is
  Handoff 14 and `data/semantics/4.4.54/damage_evaluator_q_14.json`.
- Do not reopen M530155 disassembly, Handoff 13, Handoff 12, or broad
  generated-executor topology scans.
- Only promote a new task for: concrete initialization/meaning of global
  `0x95B1E18`, or M723335 `0x15B8BB50` if patch paths are needed.
- Do not enter full damage formula, stance, display, or event subsystems.
