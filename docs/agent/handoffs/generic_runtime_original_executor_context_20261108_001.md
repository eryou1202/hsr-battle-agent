# R29 original executor context investigation

CR `CR-R29-ORIGINAL-TASK-CONTEXT-CLOSURE-20261108-001`. Starting HEAD `61e12bb4aa7fc515d1762ce9d6597e182252d9a4`; branch `terra/implementation`. Investigation and handoff complete; **preferred executor/context execution success is NOT established**. Verdict: **EXECUTOR_EVIDENCE_ADVANCED_REFERENCE_PREFIXES_ONLY**. No full joined character skill, original Monster action, source-backed executable AI rule or native-effective outcome is claimed.

Forty same-build method bodies were acquired and hashed under the pinned 4.6.51 snapshot. These establish partial operations and exact executor factory/class mappings; they do not establish forty complete executor semantics. Frozen 4.4.54 product authority remains separate. All inherited production and historical controls remain byte-identical. M10-M15, ScenarioCompiler and strict admission changed: **no**. Git writes: **none**.

| Parent | R28 completed | R29 reference completed | Actual next task |
| --- | ---: | ---: | --- |
| Avatar_Fugue_00 | 2 | 12 | RPG.GameCore.AddModifier |
| Avatar_Herta | 2 | 2 | RPG.GameCore.AddModifier |
| Avatar_Jade_00 | 2 | 8 | RPG.GameCore.ByCompareTarget |
| Avatar_Kafka_00 | 4 | 4 | RPG.GameCore.DamageByAttackProperty |
| Avatar_Lynx_00 | 1 | 1 | RPG.GameCore.SetDynamicValueByProperty |
| Avatar_Sampo_00 | 1 | 1 | RPG.GameCore.FireProjectile |
| Avatar_Klara_00 | 0 | 0 | RPG.GameCore.SetDynamicValueByCharacterCount |

The R28 report text incorrectly described Fugue/Jade's blockers as AddModifier. Their exact gap hashes and serialized bodies identify further RemoveModifier tasks. R29 preserves those historical artifacts, records the correction, and applies the already existing R17 bridge only to exact subsequent removals. Every new removal has an explicit CANCEL_NOT_STARTED_REFERENCE callback policy and empty identity filter. No instance is created. New reference completions: **16**, new executable task families: **0**, new source-native parent task completions: **0**. These are reference inputs, not recovered native removal semantics.

The new method evidence is:

`DYN_PROPERTY_FACTORY` — `0x160A9DD0`: Exact config cast and constructor call 0x1270FFF0 -> .DNOPKLPLACJ.

`DYN_COUNT_FACTORY` — `0x160A9F40`: Exact config cast and constructor call 0x163ECA00 -> .FFCLKNPNDCE.

`DYN_PROPERTY_FLOW` — `0x127100D0`: Context/scope/key lookup; target evaluation mask 0x3f; first result; TurnBasedAbilityComponent.GetProperty; dynamic lookup writer. Empty selection reaches ThrowArgumentOutOfRange_IndexException, not zero.

`DYN_COUNT_FLOW` — `0x163ECB70`: AliveOnly selects evaluation masks 1 or 15. Per-candidate context assigned before predicate; 0x9999 result increments count; signed count encoded using shifts 33/26 and writer tail call. Mask bits and status lifecycle are not fully mapped.

`DYN_SCOPE_PROVIDER` — `0xEDF6E30`: Scopes 0/9 have special lookup paths; scope 0 traverses owner/parent stores and further fallbacks. Scopes 1..8 dispatch through native table. A single supplied scope is insufficient.

`DYN_PROPERTY_PROVIDER` — `0xF124690`: Property indices 18/23 have computed branches, general path reads indexed property object +0x48. Native property object is not an R19 base-property assertion.

`DYN_WRITER` — `0x1DCA0FD0`: Writer locates keyed entry and invokes interface methods on stored object; not proved equivalent to dictionary assignment.

`MODIFIER_FACTORY` — `0x160A9440`: Exact AddModifier cast -> .JAJPDPAHFOA constructor 0xB758240. OnTaskBegin 0xB7585A0 calls source/target evaluation and TryAddModifierInstance 0xF1290A0; full lifecycle not reconstructed.

`DAMAGE_EXECUTOR` — `0xC9C5070`: Direct calls include GetActualOwner, BeginAttack, StoreDamage, FireEvent, split-ratio helper and deferred modifier params. Exact serialized expression-to-stage mapping remains incomplete.

`PROJECTILE_EXECUTOR` — `0x16E74CA0`: Original FireProjectile config cast found by exact type load. Executor calls Retarget and HasBegunDyingProcess; callback builder 0x16E75370 constructs child task chain. No immediate completion/no-op equivalence.

`FORMATION_EXECUTOR` — `0x161A94C0`: Config/context fields packed into application argument block for 0x16A8CC50. Helper evaluates targets; native formation state still absent. Shared RVA call names are candidates, not disambiguated identities.

`DISTANCE_EXECUTOR` — `0xB628010`: From/To predicate selectors; fallback GetMovementTargetPos; vector differences and sqrtss; float-to-native numeric conversion; radius sum adjustment. Unit, conversion constants, final comparator and scene authority not fully closed.

`DISTANCE_RADIUS` — `0xB628510`: Position from component +0x118/+0x120. IgnoreRadius flag +0x40 returns zero radius while retaining position. Otherwise component virtual radius getter; missing radius component also returns zero in this branch. This does not authorize zero position/distance.

`AI_SEQUENCE_AXIS` — `0xCB44EE0`: GetAISkillSequence or fallback config; (context field +1) modulo sequence length, then two search segments using candidate helper. Field ownership/reset and complete eligibility semantics not proved.

`AI_ACTION_DEPENDENCY` — `0xBAD72D0`: Action reads sequence and invokes 0xED36EA0 plus skill conversion helper. 0xED36EA0 delegates through virtual operation and increments stored/global counter; do not label this sequence cursor advancement without resolving provider.

The deepest dynamic-value blocker is the actual scope-0 TaskContext owner/parent/child/modifier graph plus keyed entry write/listener behavior, not a missing property dictionary. The property executor takes the first selected result and throws on empty selection; it does not justify unknown-to-zero. Klara's AliveOnly masks and candidate context are partly observed, while complete mask meanings, predicate status ownership and native numeric conversion remain unbound. A contract has therefore not been installed. Native methods contain IFix branches; these observations cover their unpatched paths and never establish patched effective parity.

AddModifier cohort A (exact source construction): **0**, blocked on exact definition joins and full application/instance/listener/lifetime inputs. Cohort B (explicit reference construction): **0**, no caller-supplied construction contract. Removal policy does not authorize construction. The R17 engine remains the sole modifier lifecycle.

Kafka is rerun with the unchanged R28 inputs and remains at DAMAGE_REFERENCE_INPUT_MISSING after four tasks. Its exact serialized operand tree is retained in the per-operand damage ledger. Dynamic property values, formula/stage mapping, split and settlement semantics remain unbound. R28 JsonEnum values are reused only as provider-role evidence. No new damage binding is fabricated.

Sampo's executor retargets and checks dying state; its child callback builder and Tick are retained. Native projectile world/collision/impact ownership is missing, so no immediate no-op or child callback is synthesized. SetTeamFormation now has an exact config-held executor and application helper, but no authoritative formation component state. FORMATION_PROVIDER_MISSING remains. ByDistance reads scene positions and a virtual radius provider, uses float vector length and converts native numeric representation before comparison. IgnoreRadius zeroes radius only, not distance or position. Spatial units, providers and exact numeric conversion remain incomplete.

Monster AI retains the original 140-byte decoded body. New axis/action bodies reveal sequence access, modulo-based search, candidate checks, virtual provider calls and counters. The selected action helper at 0xED36EA0 cannot be called cursor advancement solely from its name/use. Stepper/skill conversion, availability, result ownership and reset are incomplete. AI rules executed: **0**. Monster chains 1002013→100201301, 1002014→100201401, 1002040→100204001 retain exact snapshots and blockers; completed actions **0**.

Camera unresolved **68**. No concrete new provider artifact appeared; no Camera search, no-op or invented finish was attempted. Source-provider asset joins gained: **0**. Frozen denominators are copied from R28 and independently kept separate (632 combat roots, 160 joined roots, 161 joined rows, stable 72 versus historical 73).

Seven unchanged baseline parents and three Monster actions were freshly replayed from their original states/commands with exact final hashes, JSON snapshots and clones. Changed reference scenarios regenerate public command receipts (old command prehashes are intentionally invalid after policy changes), then replay them exactly; each stage is saved. Original IR hashes remain unchanged. Gap ownership remains with the scheduler; no failure is converted into completion.

Fresh tests: battle_ir **586**, battle_sandbox **918**, R21 **21**, R27 **8**, R28 **7**, all exit **0** (total **1540**). The inherited **651** runtime cases, including R12-R26 focused cases and R22/R24/R25/R26 trace contracts, have identical tested input hashes and remain **revalidated prior PASS**, not fresh full runtime execution. No production runtime or admission behavior changed, so the conditional fresh full-runtime release gate was not triggered. This is an explicit limitation against the request to freshly run every regression lane. Commands, exit codes, counts, input manifests and source fingerprints are in final_tests.json. No unfinished test is reported PASS.

Investigation budget: 40/40 new method bodies, at most three dependency hops from selected factory/executor paths; five grouped subsystem paths. The one justified broad static operation was an exact selected config-type reference scan over the pinned code section to locate obfuscated factories. No archive recrawl, registry initializer research, game launch, attachment or process/memory modification occurred. Raw disassembly acquisition is distinguished from full semantic decoding. Failed tool experiments (invalid RVA, descriptor diagnostic formatting, stale replay prehash, gap serialization) were corrected; no failed attempt counts as execution success.

Recommended R30: recover scope-0 ownership and dynamic keyed setter callback contract, native numeric conversion and selector mask meanings, then implement the generic opt-in R19/R20 binding and rerun Lynx/Klara. Follow actual reached modifier blockers with exact instance construction inputs. Keep Beam/MCTS deferred.

Production files changed: **none**. New tools: r29_sources.cjs, r29_assessment.py, r29_finalize.py. New test modules: none; existing source/provider regressions rerun. Seven new controls, this report, and curated per-root/native/test receipts form the handoff. The archive manifest records exact members, sizes and per-member SHA-256; external verification records CRC and ZIP SHA-256 without a self-referential archive hash.
