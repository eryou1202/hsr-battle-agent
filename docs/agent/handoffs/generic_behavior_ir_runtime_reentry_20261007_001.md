# R12 Generic Behavior IR and runtime re-entry

Change request: `CR-R12-GENERIC-BEHAVIOR-IR-RUNTIME-REENTRY-20261007-001`. Verdict: **GENERIC_RUNTIME_REENTRY_ESTABLISHED**.
Starting HEAD `17750b300eace78b9d2895d0fec4ad54572b96ff`; branch `terra/implementation`.
No Git writes. Every preexisting non-cache source/test/control/handoff file in the start baseline is hash-preserved.
M10-M15, strict admission and existing ScenarioCompiler remain frozen. Unrelated dirty files are preserved.

The pipeline is decoded real content -> evidence-aware binding -> canonical IR -> generic reference executor -> generic battle state -> local decision/actions -> future planner adapter. Native client remains a separate reference oracle and eventual live-state source. R11 live capture and reverse work were not reopened.

Existing architecture decisions are in `tmp/audit/r12_runtime_reentry_20261007_001/existing_runtime_inventory.json`.
New code extends the existing `battle_ir` and `battle_runtime` packages. It does not create a scenario compiler, DB, strict-executor facade or M11 admission adapter.

IR v1 defines all 15 requested node concepts. Every node retains evidence level, source version/path/hash/pointer, native method references, ledger IDs, semantic status and oracle status. Frozen payload JSON gives copy isolation and deterministic round trips. Original source authority is retained; execution authority is always REFERENCE_MODEL. Structural records and unavailable semantics are never upgraded.

Expressions support literals, explicitly scoped lookups, arithmetic, min/max/clamp, comparisons, lazy conditionals and unknown opcodes. R11 DynamicFloat opcodes 0/1/2/17 compile through generic stack decoding; operand hashes are content data. Mode0 signed raw/2^33 arithmetic is bounded with explicit toward-zero quantization at raw step2. Tagged/mixed/overflow and missing-provider domains block. This policy is not native arithmetic equivalence.

Targets use explicit caster/ability target/skill target list/param entity/modifier owner context, configured aliases, sequence/map/filter/compare/random operations. No effective alias winner is assumed. Predicates include progression row presence (any content key), entity-state tests, comparisons and logical composition. The primitive ledger (176 entries, 156 named types including metadata) is consumed for per-type evidence/native refs and coverage classification.

State separates entities, properties, actor/team resources, progression, modifier instances, dynamic providers, target context, scheduler, pending events and RNG. Mechanics can hold position/summon/phase state; presentation is separate. Clone, equality, canonical snapshots, hashes, registry-qualified runtime restore and local action replay are implemented. Identity is serialized IDs, never Unity/Python object identity.

SplitMix64 reference RNG stores algorithm, state and draw count; selection uses rejection sampling. It is not the client stream. Scheduler retains serialized continuations, barriers, tick/sequence ordered callbacks and event queues. Completion request becomes COMPLETED only after owned queues drain. Unknown native waits/effects/movement/VO remain blockers. No ordinary AV/turn rules or native action completion are invented.

Registry families are task, predicate, target, expression and event. Generic local operations include sequencing, conditional branches, explicit invocation policy, dynamic write, direct property/resource storage mutation, modifier instance insert/remove, event queue dispatch with configured callbacks, barrier/callback scheduling, random choice and completion drain. Property/modifier operations are explicit storage reference policies; native hooks/activation/renew rules are not simulated. Local legal_actions lists only caller-bound idle actions; native costs/target legality/turn ownership are not claimed. Beam/MCTS and live advising are future consumers, not integrated by R12.

The generic heal FormulaType2 core is amount-only, requires all operands and cap flag, and exposes pre-heal, effective amount modifiers, settlement, HP property hooks, post-heal and resource-listener extension points. HealHP remains a typed blocker. SetDynamicValue has a safe explicit-provider primitive, but recovered provider visibility remains blocked. Native actor ModifySPNew is not mapped into team BP or energy by inference. AddModifier and HOT renewal/activation remain oracle pending.

Natasha Skill02 trusted graph compilation: **PASS**. All 21 distinct selected task spans, 16 main-graph DynamicFloat ASTs, selectors, predicates and HOT config reference are retained. All 19 archived selected DynamicFloat ASTs (16 main plus 3 HOT callback expressions) compile as a separately pinned supplemental IR fixture. Supplemental expressions are not silently attached to an active modifier/execution path. Fixture IR canonical SHA-256: `05820ac210120c80669c664b6803550d4e04485b1d21e2979bb9d752b71285a0`.
Executable prefix: **PASS**, specifically the first TriggerAbility target and DynamicString operand evaluation; **0 completed top-level tasks**. Full transition: **SEMANTIC_GAP**.
First gap: `RPG.GameCore.TriggerAbility` requires `ability context/controller inheritance policy`. Phase02 is present in the catalog; invocation is deliberately not inferred to be synchronous or context-preserving. Supplying a catalog entry alone does not close controller inheritance. No deterministic Natasha post-state/native validation is claimed.

Census v2 inspects 4 hash-matching archived graph files only. Known task types: 20; IR-representable: 20 (unknown types retained as UnsupportedSemanticIR); mapped: 14; conditionally reference-executable: 2; oracle-pending: 20; unknown task mappings: 6. 18 types have no reference task execution yet. Actual deduplicated records: {'task': 73, 'target': 533, 'predicate': 52}; DynamicFloat expressions: {'decoded_expressions': 79, 'IR_representable': 79, 'unknown_programs': 0}. Anonymous bitmap fields in reader-chain archives remain explicitly unbound and blocking even where a type has a registered handler. Serialized references/copies are deduplicated by source coordinates. No claim that 620 skills were structurally decoded. Compiler encounter diagnostics and corpus frequencies remain separate from actual runtime attempts.

Tests: **30 PASS**, zero failures/errors. They cover IR/hash isolation, expressions, missing providers, target/predicate dispatch, scheduler resume/order/drain, events, RNG vector/clone/replay, modifiers, rollback on gap, heal core and real graph compilation/prefix. Architecture scan: PASS; no character/skill/name-specific execution branches in CR-owned code. Existing historical selected handlers are untouched and never used by R12.
Frozen FAST_UNIT regression: battle_ir 586 PASS, battle_sandbox 918 PASS, battle_runtime 224 PASS; total 1728 PASS, zero failures/errors/skips.

Controls: `data/control/generic_behavior_ir_v1_20261007_001.json`, `data/control/generic_runtime_semantic_gap_ledger_20261007_001.json`, `data/control/generic_runtime_support_census_v2_20261007_001.json`. Audit directory: `tmp/audit/r12_runtime_reentry_20261007_001/`.
Production additions: src/hsr_battle_agent/battle_ir/behavior.py, src/hsr_battle_agent/battle_ir/behavior_binding.py, src/hsr_battle_agent/battle_runtime/behavior.py, src/hsr_battle_agent/battle_runtime/behavior_state.py, src/hsr_battle_agent/battle_runtime/behavior_primitives.py.
Test addition: `tests/battle_runtime/test_behavior_r12.py`. Audit/reproduction tool: `tools/runtime/r12_runtime_reentry.py`.

Next phase: **R13 GENERIC PRIMITIVE EXPANSION + REAL CONTENT COVERAGE**. Rank gap primitives by actual corpus frequency, implement generic reference policies, re-run coverage, and use native oracle research only for the primitive joins that need it. Do not return automatically to a character-only reverse phase.

Handoff contains only CR-owned additions and manifest, no game payloads or old reverse trees. Its CRC, member sizes and SHA-256 are recorded in the external package receipt to avoid circular hashing. Reproduce controls/tests with repository-resolved Python running `tools/runtime/r12_runtime_reentry.py`; add `--package` for the explicitly requested handoff location.
