# R14 Real Combat Corpus and Capability Discovery

CR `CR-R14-REAL-COMBAT-CORPUS-CAPABILITY-DISCOVERY-20261008-001`. Verdict **REAL_COMBAT_CORPUS_EXPANDED**. Starting HEAD `ddd2739ae16daf88b70087b8b82c822036e5461d`, branch `terra/implementation`. No Git writes; frozen M10-M15, ScenarioCompiler, preexisting dirty files and R13 runtime are preserved.

The reusable pipeline verifies the immutable 4.6.51 manifest and shard hashes, reads the recovered DesignV index, walks exact ConfigBakeLayoutInfo directories, dispatches known readers, requires bounded full body consumption, and compiles through the existing R12/R13 Behavior IR. It discovers candidate ability assets from all decoded Avatar.JsonPath values and the proven common path. Candidate path transforms never supply accepted owner/root edges: those use numeric SkillList ownership, level-consistent SkillTriggerKey, SkillConfig.Name, EntryAbility, and unique serialized directory identity. Source SHA256 plus body start/end defines deduplication.

Baseline: 210 roots; 8 ability, 6 modifier, 196 alias; 1 owner/root join.

Expanded: 901 roots; 566 ability, 7 passive, 59 modifier, 231 alias, 38 other runtime configs. Ability plus passive = 573; combat = 632. SKILL_JOINED_CORPUS is a subset view (160 roots), not another exclusive stratum. The original 196 global aliases are retained with frozen archive hashes; they contribute no combat ranking weight. All 901 graphs compile, preserve unknown fields and unsupported tasks, round-trip through the same canonical IR, and have recorded IR hashes.

The pinned tables contain 95 Avatars, 7161 Skill level rows, and 730 unique SkillIDs. All 660 canonical Avatar.SkillList ownership rows were examined; the request's approximate 620 denominator is not used. 309 exact owner/config joins and 306 exact directory root joins were found. 161 rows have decoded/compiled roots, representing 160 unique roots. One shared root explains the row/root difference. 58 complete CharacterConfig roots qualify for joins; the remaining 37 are explicit structural gaps.

Exact root joins are identity joins even when a graph body is undecoded. Join statuses and graph decoding are separate columns. Synthetic R13 reference probes reach a prefix in 1 joined roots; 0 joined root probes complete. Required real actor state/policies are unavailable: **REFERENCE_TRANSITION_EXECUTABLE = 0**, full reference transitions = 0, native correctness is not claimed. All adapter failures are retained as explicit failed probes. The compiler's only production change preserves obfuscated concrete task names under their proven dispatcher family as UnsupportedSemanticIR, avoiding an untyped dictionary in task continuations.

Systematic enumeration: 2672 trusted directory entries across the discoverable player/common paths. 1722 unique record attempts: 705 accepted, 1017 reader gaps, 0 record framing gaps, 0 unsupported root types. Every reachable non-modifier entry is attempted; modifiers are decoded only if directly referenced or part of the baseline. Opaque outer hashes without decoded paths are outside this bounded phase. No whole-game archive or provider discovery was repeated.

The parent TurnBasedAbilityConfigList grammar is significant: modifier/target/camera dictionaries serialize keys before the next body, and group transitions serialize counts. The pipeline computes body ends before decoding, validates every exact key and cardinality against trusted directory identities, and rejects unexplained bytes. R13's next-start-only bound had rejected structurally valid dictionary bodies; R14 resolves this through the already-proven native list/dictionary grammar, not plausible trailing-byte acceptance.

A narrow reader exception was used for high-frequency first gaps (at least 20 failed attempts), directly reachable concrete dependencies, and parent/root framing needed across the corpus. The existing R10.2 schema/metadata machinery produced 119 local schemas; 132 native method spans were examined under a hard 180-method bound. No new registration, provider, DesignV, directory or global TaskConfig discovery was performed. Cached native schema extraction remains conservative: unsupported custom readers/active branches reject records. Source schemas, byte-span revalidations, local native citations, pins and explicit gap families are retained in audit.

Combat instances: task 4555, target 3141, predicate 327, expression 3227. These count actual serialized spans once per source shard/type/family, not duplicate IR payload occurrences. Type and instance support metrics distinguish IR representation, registered conditional reference support, structure-only, unsupported, oracle-pending and structural reader gaps. Literal target aliases do not inflate missing-handler scores; registered support is excluded from implementation-gap scoring.

Damage checkpoint: YES, `DamageByAttackProperty` 207 combat instances. The configs prove structural damage content; no damage settlement evaluator was added. Toughness/break: NO / NOT YET DECODED as proven task families. Shield: NO / NOT YET DECODED. Action-order/AV: NO / NOT YET DECODED. Resource: `ModifySPNew` 39 instances. Anonymous AttackData fields are not named as break/shield semantics by inference.

New serialized task types (28):

- `.LAJIKDENEOO`
- `RPG.GameCore.AlignTargetToTeamCenter`
- `RPG.GameCore.DamageByAttackProperty`
- `RPG.GameCore.DamagePerformFinish`
- `RPG.GameCore.FireProjectile`
- `RPG.GameCore.GlobalMainIntensityEffect`
- `RPG.GameCore.HeadLookAt`
- `RPG.GameCore.HideLevelStage`
- `RPG.GameCore.LookAt`
- `RPG.GameCore.LoopExecuteTaskListWithInterval`
- `RPG.GameCore.MoveToTargetList`
- `RPG.GameCore.PlayTimeline`
- `RPG.GameCore.RadialBlurEffect`
- `RPG.GameCore.RemoveEffect`
- `RPG.GameCore.ScaleCharacterModel`
- `RPG.GameCore.SetDynamicValueByModifierValue`
- `RPG.GameCore.SetDynamicValueByProperty`
- `RPG.GameCore.SetEnergyBarState`
- `RPG.GameCore.SetEntityVisible`
- `RPG.GameCore.SetSkillTargetFormationByPos`
- `RPG.GameCore.SetTeamFormation`
- `RPG.GameCore.ShowBattleUI`
- `RPG.GameCore.ShowBonusUIEffect`
- `RPG.GameCore.SyncCharLightAndCameraDir`
- `RPG.GameCore.TriggerAnimStateWithMove`
- `RPG.GameCore.VCameraConfigChange`
- `RPG.GameCore.WaitSecond`
- `RPG.GameCore.WaitTimelineFinish`

Modifier references: 338, 73 call/reference edges resolve to decoded roots. Passive installation refs distinguish CONTENT_GRAPH_PRESENT from ACTIVE_IN_ANY_REAL_ACTOR_UNKNOWN. Template calls: 47, 2 resolve to decoded template roots. Template definition/call identity, mask-4 numeric dictionaries, mask-8 string dictionaries, mask-32 sequence dictionaries, caller-context fields and nested calls are structurally retained. Effective inheritance/replacement/provider precedence remains unresolved. No second TemplateIR or runtime was introduced: existing TaskIR and lossless fields carry the data; the audit is a join sidecar.

Scheduler evidence: {'SkillPerformFinish': 111, 'TriggerAbility': 444, 'WaitAnimState': 762, 'WaitSecond': 226, 'WaitTimelineFinish': 36}. Serialized invocation, delayed continuation and completion configurations are present. Native barrier release, callback ownership, inserted/extra actions and AV policies are unclosed. Monster corpus: MONSTER_BEHAVIOR_CORPUS_NOT_YET_BOUND; no exact decoded Monster owner/config path was recovered in the permitted player scope.

Combat planning ranking (authored estimates, not recovered semantics):

| Family | All combat instances | Missing reference support | Score |
|---|---:|---:|---:|
| SCHEDULER | 1137 | 375 | 855.4 |
| DAMAGE | 325 | 325 | 753.6 |
| TARGETING | 3236 | 131 | 431.2 |
| PREDICATE | 327 | 145 | 228.9 |
| PROPERTY | 3409 | 118 | 155.4 |
| RESOURCE | 39 | 39 | 99.0 |
| MODIFIER | 400 | 18 | 94.4 |
| HEAL | 21 | 4 | 19.2 |
| UNKNOWN | 4 | 4 | 2.6 |
| CONTROL_FLOW | 722 | 0 | 0.0 |
| PRESENTATION | 1630 | 1258 | 0.0 |

Formula: (instances with missing reference support + 2*graphs with missing support + static_suffix_nodes + 5*decoded_skill_roots_blocked) * centrality * confidence / native_evidence_cost; scores are authored planning estimates. Static suffix counts are an upper-bound estimate of downstream blocking, not scheduler reachability. Prefix first gaps come from actual synthetic reference probes, separately recorded. Taxonomy is for planning; presentation tasks are excluded from choosing a battle mechanics subsystem. Highest-value next subsystem: **SCHEDULER**. Recommended **R15 TURN / AV / ACTION SCHEDULER**. Targeted oracle questions include exact primitive/frequency/affected root coordinates, archived reader refs and minimum evidence in capability discovery and semantic-gap ledger v3.

Determinism: canonical compile/round-trip PASS; repeated full pinned batch and census hashes must match the final determinism receipt. Regression: 1783 FAST_UNIT tests PASS; R12/R13/R14 focused 85 PASS. Architecture/preservation PASS. New tests cover bounded/full framing, exact parent keys/counts, source-coordinate dedup, owner/skill/root joins, unknown and obfuscated tasks, canonical IR stability, template/modifier references, stratification and honest coverage. No frozen tests were modified.

Reproduce with repository Python: `python tools/runtime/r14_expand.py`, `python tools/runtime/r14_discovery.py`, `python tools/runtime/r14_finalize.py --package`. Final reader caches are CR-owned audit inputs. `r14_local_readers.cjs` is the optional bounded research command used to generate them and depends on the existing frozen R10.2 tooling; it is not required for normal corpus reproduction. Hand-off excludes source game payloads and old reverse trees, includes only CR-owned files plus manifest, and verifies CRC, exact members, sizes, each member SHA256 and archive SHA256.

Production changed: `src/hsr_battle_agent/battle_ir/behavior_binding.py`. Tests added: `tests/battle_runtime/test_behavior_r14.py`. No runtime semantics, RNG, snapshot, clone, rollback or scheduler policies changed. External requested handoff: `D:/HSR_Battle_Agent/agent_handoffs/CR-R14-REAL-COMBAT-CORPUS-CAPABILITY-DISCOVERY-20261008-001_changed_files.zip`.
