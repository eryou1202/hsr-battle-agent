# R13 Generic Primitive Expansion and Real Content Coverage

CR: `CR-R13-GENERIC-PRIMITIVE-COVERAGE-20261007-001`. Verdict: **GENERIC_RUNTIME_COVERAGE_EXPANDED**.
Starting HEAD `17750b300eace78b9d2895d0fec4ad54572b96ff`; branch `terra/implementation`. No Git writes.
Frozen M10-M15, strict admission and existing ScenarioCompiler are untouched. The preservation audit checks 478 starting files; only R13-owned runtime/tool files changed.

Coverage is actual isolated primitive execution with explicit synthetic reference inputs. Task probes count a successfully applied primitive that may return continuations; they do not claim those children or a legal battle executed. Alias bindings, enum mappings, category properties, relation lists and effective heal operands are declared reference fixture data. They are not native winners or native-equivalent semantics.

| Family | R12 baseline | R13 same corpus | R13 expanded corpus |
| --- | --- | --- | --- |
| task | 3/73 (4.1%) | 37/73 (50.7%) | 40/80 (50.0%) |
| target | 239/533 (44.8%) | 413/533 (77.5%) | 419/539 (77.7%) |
| predicate | 3/52 (5.8%) | 44/52 (84.6%) | 44/52 (84.6%) |
| expression | 79/79 (100.0%) | 79/79 (100.0%) | 83/83 (100.0%) |

Known task types remain 20. Mapped task types: 14 -> 17. Implemented conditionally reference-executable task types: 2 -> 13; actual passing task types: 1 -> 10. Unsupported mappings: 6 -> 3 (DebugLog, ModifyHealData, TargetTimeSlow). All 20 task types remain native-oracle pending.
Target passing types: 4 -> 31/91; predicate passing types: 2 -> 17/19. DynamicFloat IR representation/execution: 79/79 -> 83/83. Coverage iteration receipts retain the first batch and final rerun.

The R12 “4 graphs” were archived graph bundles. This phase reports those separately: 4 -> 5 bundles; distinct complete decoded behavior roots 207 -> 210. Expanded roots: 8 ability/config records, 6 modifier graphs, 196 alias graphs. Proven skill owner/root joins remain 1; no executable-skill count is claimed. The three new distinct roots are the insertion phase and two common ability records.

The batch decoder uses the same externally pinned 4.6.51 shard and already proven selected/common ConfigBakeLayoutInfo directories. Cached native schemas and previously decoded reader shapes are reused with archived byte-span/type validation. Unknown readers, active slots and unmatched framing remain STRUCTURAL_CORPUS_GAP. 9 records passed complete bounded consumption, including records already present in R12. 21 unsuccessful attempts are excluded from new coverage. No registration/provider/archive archaeology or live capture was reopened.

Ranking uses decoded frequency, observed subtree descendants, fan-out, confidence and semantic-invention risk. The top initial candidates were:

- `RPG.GameCore.TargetSequence`: frequency 89, score 300.38, observed mean descendants 2.82.
- `RPG.GameCore.PredicateTaskList`: frequency 22, score 107.74, observed mean descendants 9.05.
- `RPG.GameCore.TargetConcat`: frequency 29, score 97.88, observed mean descendants 2.31.
- `RPG.GameCore.TargetFilter`: frequency 13, score 30.71, observed mean descendants 3.85.
- `RPG.GameCore.ByCharacterDamageType`: frequency 14, score 28.35, observed mean descendants 1.00.
- `RPG.GameCore.ByAnd`: frequency 4, score 19.57, observed mean descendants 6.25.

Target algebra now implements pipelined sequence, sibling concat, stable filter/sort/index/take/query, explicit relation maps and context fetches. All outputs are ordered lists. Duplicates remain; empty outputs remain empty; null/unresolved entities block. Direction/index/category enums require serialized caller mappings; missing serialized sort defaults need explicit reference policies. Filter/map traversal preserves parameter context and RNG order. Unknown anonymous options remain recorded, never renamed as recovered native fields.

Predicates cover logical composition, damage/team/category comparisons, HP and HP-ratio comparisons, grid/stance/character properties, target membership, modifier presence, team relationships, alive-mask and behavior-flag membership. Logical operators short circuit under their explicit reference contract. Anonymous bitmap fields stay in canonical IR with CONDITIONAL_REFERENCE role metadata; meanings are not inferred from field order.

Template/ability invocation uses generic catalogs, cycle checks, depth bounds, explicit owner/caster/target/parameter/provider relationships and resumable context-return frames. Policies and catalogs participate in snapshots/hashes. Recovered template parameter dictionaries remain invocation gaps; callers may provide explicit replacement contexts. Deferred child callback/event ownership blocks pending a scheduler subsystem. Additional ability lifecycle task-list slots are retained and block rather than being silently dropped.

Modifiers have explicit storage insertion/refresh/replace policies, numeric stacking data left uninterpreted, duration binding, dynamic-value checks, removal and property-stack reference operations. Event listener IDs/order/callback/owner/caster/conditions/mutation result are represented; native event IDs and activation rules are not globally simulated. HealHP requires decoded FormulaType2 plus all explicit effective operands, settlement policy and six hook declarations; missing hooks block atomically. SetDynamicValue requires a caller-bound existing provider. ModifySPNew remains separate and unmapped to team SP or energy. Presentation nodes require explicit presentation/barrier/position classifications.

Natasha Skill02 remains REFERENCE_VERTICAL_SLICE: compile **PASS_WITH_STRUCTURE_ONLY_NODES**; 0 completed top-level tasks, 1 accepted top-level invocation, 1 nested task reached under the generic synthetic policy; first gap `explicit reference input:WaitAnimState`. A child blocked at its animation barrier leaves the caller's invocation pending, so accepting it is not counted as call completion. Without R13 invocation policy the original controller-inheritance gap is preserved by all 30 unchanged R12 tests. No native post-state is claimed.

Additional named regressions: Local_SPAdd, TriggerStanceCountDown_Test, MAvatar_Common_TriggerDeparted, Avatar_Common_PassiveSkill, Avatar_Common_SkillMazeInLevel, AllTeammate, AvatarNextTurnOwnerEntity and AllEnemy. The three alias fixtures exercise real filter/logical-membership, query/sort/take and composed relation-map graphs with clone/snapshot checks. Modifier root installation remains a typed lifecycle gap. No fixture-specific production branches were added.

Determinism: **PASS** for clone, snapshot, hash, replay, nested continuation restore and RNG rollback. Architecture AST scan: **PASS**. Focused R12/R13 tests: **64 PASS**. FAST_UNIT: battle_ir 586 PASS, battle_runtime 258 PASS, battle_sandbox 918 PASS; **1762 total PASS**. Logs and test receipts are in the R13 audit directory. Tests do not perform native validation.

Highest remaining coverage family: template parameter/catalog binding and anonymous target/predicate options, followed by modifier/event lifecycle and child scheduler ownership. Recommend **R14 MORE GENERIC PRIMITIVE COVERAGE**, using the exact targeted oracle questions and affected decoded pointers in ledger v2. Each ticket states frequency, affected content and minimum evidence. Do not automatically return to a character mainline.

Production files: src/hsr_battle_agent/battle_ir/behavior_expansion_binding.py, src/hsr_battle_agent/battle_runtime/behavior.py, src/hsr_battle_agent/battle_runtime/behavior_expansion.py.
Test file: `tests/battle_runtime/test_behavior_r13.py`; existing R12/frozen tests unchanged.
Reproduce with repository-resolved Python running `tools/runtime/r13_coverage.py`, then `tools/runtime/r13_finalize.py`. Package only R13-owned files using `--package`; native payloads and old reverse trees are excluded. The external archive is `D:\HSR_Battle_Agent\agent_handoffs\CR-R13-GENERIC-PRIMITIVE-COVERAGE-20261007-001_changed_files.zip`; CRC, member set, sizes and SHA-256 are recorded in `tmp/audit/r13_generic_coverage_20261007_001/handoff_verification.json`.
