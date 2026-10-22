# R24 Toughness / Weakness Break / Shield

CR: CR-R24-TOUGHNESS-BREAK-SHIELD-20261021-001. Starting HEAD: `1ab66b4d907bd97116d6cd0a8cea19d6a1212ca0`. Branch: `terra/implementation`. Git writes: **NONE**.

Verdict: **GENERIC_DEFENSE_BREAK_REFERENCE_ENGINE_ESTABLISHED**. Native correctness: **NOT CLAIMED**. Frozen M10-M15, ScenarioCompiler, strict admission, historical tests and approved R12-R23 artifacts are preserved.

## Evidence and coverage

The native research authority is pinned 4.6.51; the product baseline remains frozen 4.4.54. The four required R23 controls and handoff were read and hash-pinned. Their actual denominators remain 632 combat roots, 160 unique joined roots and 161 joined rows. The archived R23 explicit controls record 73 nonempty real prefixes, 18 reference HP roots, 15 roots completing original child finish tasks, and **0 complete source-closed joined transitions**. A stable reexecution count discrepancy is explained below.

The rescan covers all 854 decoded records among the 1817 existing catalog records, plus existing decoded owner/CharacterConfig and global target-alias context. It finds 4 defense-related structural candidates: **ByCompareStanceCount (1 predicate)** and **ModifierStancePreshowConfig (3 configs)**. These are not executable defense settlement tasks. There are 262 structurally decoded damage candidates across this larger catalog; the frozen 632-root R18 cohort has a different denominator and remains unchanged. Selectors and metadata names are listed separately in the evidence control. No hypothetical ReduceToughness, BreakShield or ApplyBreak family is assumed present.

Each imported observation records source version, artifact/body hashes, JSON pointer or line span, original byte spans when available, field masks, exact record identity and uncertainty. Anonymous operands remain unknown. Exact canonical owner joins are retained where available; missing joins are not inferred from names. Monster defensive initialization is not claimed. Source-backed executable defense operations: **0**; cohort C: **0**.

Bounded native examination: **1 existing subsystem path, 1 existing method body, 0 new selected bodies, 1 dependency hop**. The saved unpatched body at RVA 0xF145660 calls ExitBreakState at 0xF1414E0 and contains IFix guards. This proves a static call, not recovery timing or effective behavior. Metadata has shield-property candidates but no executable rule promotion. Existing 4.4.54 damage/stance evidence is background only. No game launch, live attach, memory patch, provider/archive/registration campaign or R23 Camera/Phase campaign was performed.

## Runtime contract

Defense actors, policy snapshots, active requests, histories, break generation, shield identities and counters live inside **BehaviorBattleState.mechanics[r24_defense_break_reference_v1]**. The existing state serializer/clone/hash includes them without adding default fields to old snapshots. Frozen non-turn state hashes remain unchanged when R24 is absent; R22 implementation identity is discussed below. R20 ActorRuntimeBinding accepts an optional provenance-tagged `defense` field on its atomic candidate state; direct `defense_break.bind` supports scenario initialization on an exact existing entity. There is no character-specific branch.

MISSING, KNOWN_ZERO, KNOWN_NONZERO, UNKNOWN_NATIVE_VALUE and EXPLICIT_REFERENCE_VALUE remain distinct. Unknown current toughness, weakness sets, shield state or capacity cannot become zero or known absence. A catalog definition never creates an instance. Source observations without a proven operand binder reject as DEFENSE_SOURCE_OPERAND_NOT_BOUND; separate explicit reference values are executable.

HP damage, shield absorption, toughness reduction, break trigger/state/effect/recovery are separate domains. ToughnessRequest, ToughnessEvaluation and ToughnessSettlement retain actor/target/source task/ability, elemental input, base operand, ordered modifiers, weakness authority, pre/post values, delta and generation. Reduction never comes from HP damage. Raw reference values use R12 checked fixed arithmetic, nonnegative state and rejection of overcap initialization/recovery.

Weakness matching uses explicit strings and temporary add/remove inputs, or explicit ignore/match override authority. Native element enums and special rules are unknown. A positive current value crossing to zero activates break only if explicitly eligible and not already active. Repeated zero attacks do not retrigger. Recovery and a new zero crossing increment the generation. Toughness zero is independent of life state.

Shield selection uses priority ascending then input order. Selection freezes IDs before BEFORE callbacks and re-reads capacity after they drain. Explicit alternatives consume all shields or the first applicable shield; overflow reaches HP or is explicitly discarded; zero capacity removes the instance or retains an inactive one. Positive capacity is consumed one-for-one in raw units. After absorption callbacks drain, each depletion callback drains before cleanup. Linked R17 removal cleans listeners/contributions. Refresh preserves identity and input position; replacement removes and appends an explicitly supplied instance. Expiry is manual or an explicit owner-boundary countdown, including a matching creation-turn boundary. No native precedence or expiry rule is claimed.

Break effects use a caller-authored identity/tasks envelope, owned by the original R15 action/ability. Effect IR can use existing state/event/scheduler primitives. Missing native damage, DoT, delay and elemental effects are never synthesized; absence records BREAK_EFFECT_NOT_BOUND. Explicit recovery specifies a boundary/callback, count and bounded restore amount. Missing recovery remains BREAK_RECOVERY_POLICY_MISSING; no native boundary timing is assumed.

## Integration and atomicity

R17 modifier_event_dispatch and R15 ActionExecutionRoot own all reference event keys and callbacks; no native event ID is assigned. BEFORE/AFTER_SHIELD_ABSORPTION, SHIELD_DEPLETED/REMOVED, BEFORE/AFTER_TOUGHNESS_CHANGE, BREAK_TRIGGERED, BREAK_EFFECT_EXECUTION and BREAK_RECOVERY are reference labels. Required callbacks drain before the owning action and normal turn release.

R18/R19 keep the original decoded DamageByAttackProperty IR. An exact-task-hash `damage_hooks` entry with EXPLICIT_SCENARIO_INPUT authority supplies defense independently; the R18 task binding must explicitly select R24 defensive boundaries. The hook reads the already evaluated/modified R18 amount, applies R18 rounding once, routes shield overflow, then passes the remainder to the shared **settle_hp** operation. There is one HP mutation, no extra formula evaluation/RNG draw, and no duplicated callback engine. Generated defense envelopes use SANDBOX_EXTENSION/REFERENCE_MODEL authority, while the original damage task retains its original evidence.

Standalone defense requests and boundary/lifecycle operations reuse the existing R18 scheduler transaction checkpoint. For real source damage, the enclosing atomic boundary includes all ordered target requests, shield/toughness/break state, HP, callbacks, events, trace and RNG. Failure rolls back the outermost request. Earlier completed source requests remain committed. Budget/logical-wait suspension is snapshot-resumable with no duplicate settlement. Recovery and expiry run as existing R22 boundary roots on the same persistent state and battle clock.

## Functional scenarios

| Case | Executed scenario | Result |
| --- | --- | --- |
| 1 | 01_full_absorption | PASS |
| 2 | 02_partial_absorption_hp_overflow | PASS |
| 3 | 03_multiple_shields_stable_order | PASS |
| 4 | 04_depletion_listener_cleanup | PASS |
| 5 | 05_known_empty_shields | PASS |
| 6 | 06_unknown_shields_gap | PASS |
| 7 | 07_positive_toughness_reduction | PASS |
| 8 | 08_weakness_mismatch | PASS |
| 9 | 09_exact_zero_break_once | PASS |
| 10 | 10_repeated_hits_no_double_break | PASS |
| 11 | 11_explicit_recovery | PASS |
| 12 | 12_multi_hit_shield_break | PASS |
| 13 | 13_multi_target_independence | PASS |
| 14 | 14_absorption_clone_snapshot_replay | PASS |
| 15 | 15_break_callback_clone_snapshot_replay | PASS |
| 16 | 16_atomic_gap_rollback | PASS |
| 17 | 17_real_decoded_damage_reference_defense | PASS |
| 18 | 18_r22_turn_persistence_and_order | PASS |

Core cohorts: **A PURE_REFERENCE_MECHANIC = 17**, including R22; **B REAL_DAMAGE_PLUS_REFERENCE_DEFENSE = 1**; **C SOURCE_BACKED_DEFENSE_CONTENT = 0**. These are scenario counts, not native content coverage. The additional edge tests cover R20 identity/provenance initialization, refresh/replacement/removal, explicit precedence, temporary weakness/override, eligibility, numeric/unknown state gaps, post-HP failure rollback, callback ownership/order, re-break generation and unbound source-operand rejection. The real multi-target late failure restores earlier targets in the same source request.

## Verification and limits

R24 tests: **34 PASS**. All 18 required scenarios pass with observations and hashes in functional_scenarios.json. Clone/JSON snapshot suffix replay passes across shield mutation and a pending R17 break callback. Policies, counters, pending effects and transaction checkpoints participate in the existing runtime hash. No wall clock or global mutable mechanics cache is used.

Baseline: `{"R12_R23": {"returncode": 0, "tests": 363}, "R21": {"returncode": 0, "tests": 21}, "battle_ir_FAST_UNIT": {"returncode": 0, "tests": 586}, "battle_runtime_FAST_UNIT": {"returncode": 0, "tests": 557}, "battle_sandbox_FAST_UNIT": {"returncode": 0, "tests": 918}}`.

Final: `{"R12_R24": {"returncode": 0, "tests": 397}, "R21": {"returncode": 0, "tests": 21}, "battle_ir_FAST_UNIT": {"returncode": 0, "tests": 586}, "battle_runtime_FAST_UNIT": {"returncode": 0, "tests": 591}, "battle_sandbox_FAST_UNIT": {"returncode": 0, "tests": 918}}`.

The unchanged frozen 632/160 runner reports **no drift**, including original state hashes and first-gap/metric outputs. R22 A-L: 14 traces, 18 actions, 16 normal turns, 35 decisions; all scheduling/effect observables and same-version clone/snapshot/replay remain exact. R22 full hashes differ across versions because its policy deliberately hashes battle_turn.py implementation bytes; the R24 extension changes this identity.

The full 160-root R23 execution census is re-run. **159 archived semantic results match. One inherited census discrepancy is isolated**: the archived Avatar_Bailu_00_Skill01_Phase01 row halted at the implementation-binding guard before content admission, yet its two boundary tasks were counted as a real prefix. The exact starting R23 source and current R24 source both reach the original missing child source with zero real tasks completed. Thus the archived control remains **73** nonempty prefixes, while stable execution yields **72** (88 blocked entries). This is documented in r23_starting_code_diagnostic.json; historical controls remain untouched. HP roots remain 18, original child-finish roots remain 15 and complete source-closed transitions remain **0**. All old source and control files covered by the start gate remain unchanged except the four authorized production extensions. The CR-owned gate tool was also updated. Preservation checks cover 1561 starting files; architecture PASS.

The milestone establishes a reusable reference engine. It does not prove native shield formulas/order, native elemental IDs, effective IFix/Lua behavior, native break damage/DoT/delay or recovery timing. Source-backed defense content remains zero. A/B results do not inflate C or frozen source coverage.

Recommended R25: **STAGE / WAVE / TERMINATION**, with Monster content/AI as the next alternative based on exact evidence cost. Both move toward completing an encounter. Action legality, planner bridge and targeted defense/oracle follow-ups remain separate. Do not automatically open another broad defense reverse-engineering phase.

## Delivery and reproduction

Production files: src/hsr_battle_agent/battle_runtime/action_scheduler.py, src/hsr_battle_agent/battle_runtime/actor_binding.py, src/hsr_battle_agent/battle_runtime/battle_turn.py, src/hsr_battle_agent/battle_runtime/damage_pipeline.py, src/hsr_battle_agent/battle_runtime/defense_break.py. Tests: tests/battle_runtime/test_behavior_r24.py. Audit: tmp/audit/r24_defense_break_shield_20261021_001/.

Reproduce in order with Python: r24_checks.py gate (fresh audit only), baseline; r24_evidence.py; r24_scenarios.py; r24_regressions.py frozen/turns/skills; r24_checks.py final; r24_finalize.py --package. Historical runners are redirected into R24 audit only. Existing pinned snapshots and approved R12-R23 artifacts are prerequisites.

Handoff: D:/HSR_Battle_Agent/agent_handoffs/CR-R24-TOUGHNESS-BREAK-SHIELD-20261021-001_changed_files.zip. The archive includes CR-owned new files, patches against exact start-gate hashes, derived audit receipts and a member manifest. Existing source files must match their recorded baseline before patching. Game binaries, native bodies, source snapshots, process dumps, old reverse trees, starting backups and unrelated dirty files are excluded. handoff_verification.json separately records CRC, exact member set, sizes, member hashes and ZIP SHA-256.
