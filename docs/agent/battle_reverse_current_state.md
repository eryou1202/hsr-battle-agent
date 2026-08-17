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

- Completed capabilities: Handoff 09 `MODIFIER_PROPERTY_EFFECT_09_PROOF`,
  Handoff 10 `GENERIC_PROPERTY_SOURCE_SLOT_MATERIALIZATION_10_PROOF`, and
  Handoff 11 `GENERIC_PROPERTY_MUTATION_SOURCE0_11_PROOF`.
- Partial checkpoint: Handoff 12 `SET_HP_CURRENT_HP_TRANSITION_12_PARTIAL`.
- Current frontier: `CurrentHP / DirtyHP / DirectDamageHP`.
- Session stop state: `STOP_HARD_BUDGET`; CurrentHP symbolic control flow is
  checkpointed, but global threshold `K` remains unresolved.
- Artifact: `data/semantics/4.4.54/generic_property_mutation_11.json`.
- Topology artifact: `data/raw/4.4.54/modifier_effect_topology_09.json`.
- Handoffs: `docs/agent/handoffs/semantic_handoff_09.md`, `docs/agent/handoffs/semantic_handoff_10.md`, `docs/agent/handoffs/semantic_handoff_11.md`, `docs/agent/handoffs/semantic_handoff_12_partial.md`.
- Handoff 10 refines 09's opaque contribution key to a stable PropertyEntry `source_index`.
- The capability includes source-slot lifecycle and materialization framework.
- Per-kind fixed-point operator names/formulas are still not accepted.
- It is not a damage formula.
- It adds a persistent, Modifier-owned contribution record and reverses it through the same stable source index.
- Handoff 11 adds the scoped mutable/base path: source slot `0` supports fixed-point `Set/Add/Mul/Min/Max`, rebuild, then a post-change bridge call.
- This mutation capability deliberately excludes non-null post-transform context and the native special-property IDs.
- Handoff 12 is deliberately partial: it records SetHP -> DirectChangeHP ->
  DirectDamageHP -> CurrentHP source-0 evidence, but it does not publish a
  complete HP or damage contract.
- Handoff 12 additionally records the CurrentHP bound branch's exact symbolic
  control flow. It remains partial because global threshold `K` at data RVA
  `0x95B1E80` has no recovered initialization/semantic identity.

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
- Partial SetHP-to-CurrentHP source-0 transition evidence.

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
- Partial HP handoff: `docs/agent/handoffs/semantic_handoff_12_partial.md`.
- Reusable evidence helpers: `tools/reverse/scripts/semantic_batch_evidence.py`.
- Reusable bounded xrefs: `tools/reverse/scripts/semantic_method_xrefs.py`.

## Current direct dependency frontier

- `0x19B4485C0` is now classified as a large tag-dispatch runtime rather than a small property formula; do not collapse it into arithmetic.
- Resume at M506503's CurrentHP branch `0xE72E162`: it reads MaxHP index `1`,
  M506511 `GetDirtyHP`, and branches around the common source-0 tail.
- M506511 `GetDirtyHP` at `0xE734050` has confirmed
  `MaxHP * DirtyHPRatio + DirtyHPDelta` arithmetic, but the CurrentHP bound
  policy is only symbolically confirmed: candidate `< bound` writes candidate;
  candidate `>= bound` uses fixed-point min/max against unrecovered runtime
  threshold `K` at data RVA `0x95B1E80` before the same source-0 write.
- M506499 `DirectDamageHP` needs its `0xE7333E0` intercept split and its
  `0xE73231C -> 0xE7327B4 -> 0xE732C6B` ordinary branch reconciled before a
  general HP/damage contract is accepted.
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
- CurrentHP/NegativeHP special mutation and DirtyHP policy.
- CurrentHP bound threshold `K` global initializer/semantic identity.
- DirectDamageHP intercept decision and modes 4/5/6.
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

- Next session: resolve the initializer/semantic identity of CurrentHP global
  threshold data `0x95B1E80`, used at M506503 `0xE72E1B9/E72E1D0/E72E1E7`.
- Only after that closes the bound primitive, resume DirectDamageHP M506499 at
  `0xE7333E0` / `0xE73231C`; treat `0x195C6D120` as generated tag-dispatch
  evidence, not a settled DamageRequest.
- Do not implement HP policy from Handoff 12 Partial.
