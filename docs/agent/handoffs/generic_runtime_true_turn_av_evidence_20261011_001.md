# R21 True Battle Turn / Action Value Evidence and Generic Runtime Contract

CR `CR-R21-TRUE-TURN-AV-CONTRACT-20261011-001`. Verdict **TRUE_TURN_AV_CONTRACT_READY**. Starting HEAD `ddd2739ae16daf88b70087b8b82c822036e5461d`, branch `terra/implementation`. Git writes NONE. Optional production turn engine implemented **NO**. Native-equivalent Turn/AV **NOT CLAIMED**.

R21 makes R22 reference execution possible while retaining exact native uncertainty. The global controller selects who may act; R15 schedules work inside the chosen action. These clocks and queues remain separate. No production runtime, test file, frozen M10–M15 file, ScenarioCompiler or strict admission code was edited.

## Start gate and authority

Read-only Git HEAD/branch/status/staged receipts and 1,520 starting-file SHA-256 values are in start_gate.json. R12–R20 approved handoff manifests were checked for file presence; later phase changes can supersede earlier file hashes. The current starting files are the R21 preservation authority. R12/R13 committed architecture and approved R14–R20 working-tree changes remain distinct from unrelated frontend/.workbuddy/old reverse changes. No inherited files are overwritten.

Research source is immutable `OSBETAWin4.6.51_20260924-0600_16677734`. Manifest SHA-256 `b702762039368badf25c1e2c0a3a4eea79d7b8ada79c6ce98a448492a97378ec`; GameAssembly SHA-256 `5177de36bc0961beb550aaa514056d00445969d80f660a1d3ad90833196aa40f`; global metadata SHA-256 `a8884e3850a676fb25b1a3734d10388cdf8b51e4782d2e0025b5199e0dbcbab2`. These pins were recomputed. Product ContentDatabase stays frozen 4.4.54. Astra 4.4.54 saved scheduler packets/body excerpts are identity candidates; every new core claim uses 4.6.51 body excerpts. No old RVA/property constant/comparator rule was promoted without same-build inspection.

Known type/field declarations, native base machine-code behavior, effective patch dispatch, initialized actor inputs and reference policy are separate columns in the A–H matrix. IFix guards exist on selected paths; no effective runtime oracle was acquired. Missing task types in the current corpus do not prove missing native initiative mechanics.

## Bounded native investigation

Budget: at most 3 subsystem paths, 120 selected method bodies, normal maximum 2 dependency hops. Actual: **3 paths, 48 bodies**. One permitted high-value third-hop join inspects M523327 → M522868 OnTurnEnd for modifier lifetime/event ownership. It is recorded with its exact path and reason. All other selected methods remain within the bounded controller/component families and at most 2 call/type joins. No registration/provider/archive rediscovery, live attach, game launch or patching occurred. Native research stopped after these paths; remaining joins become specific tickets.

Paths: initiative/controller selection/comparison/completion; directly reached actor delay/speed property behavior; insertion and turn/lifecycle boundaries. Inventory has per-method identity/RVA/span/body SHA-256, exact call sites, dependency path, review depth and patch uncertainty. Unresolved configuration field values, speed rebase notification, captured list-advance callback, packed key producers, effective insertion accounting, duration/event enum joins and initialization are explicitly listed.

| Evidence | Same-build base path finding |
|---|---|
| E01 | Base selection walks the controller list, calls HasActionTurn and IsAnyLockActionDelay. _PickTurnActiveEntity calls selection, SetCurrentTurnActionEntity, writes controller+0x260, notifies owner change, reads property 0x26, then advances list delay. |
| E02 | PackActionDelayCompareData reads property 0x26 when requested and packs a qword plus flags and signed integer keys. Comparator orders unequal tagless qwords signed ascending; after equality +08 boolean true first; equal zero delay additionally +09 true first and +0c signed descending; remaining +10 and +14 signed ascending. Tagged paths use separate comparisons. |
| E03 | SetupActionDelayByUnitDistance reads property 0x20; multiplies config object field+0x190 by the argument, stores the result at component+0x2a0, divides by positive speed, then calls ModifyProperty for 0x26 with operation literal 1. get_UnitActionDelay returns config field+0x190 divided by positive property 0x20; nonpositive speed returns a static qword. |
| E04 | RefreshSpeed has a modifier-behavior-dependent branch and writes property 0x20; another branch uses ToSpeedOverrideLinearProperty plus fixed-point addition/multiplication/subtraction and writes 0xd4. ApplyDelayModifyWhenActionPhaseEnd drains stored entries through ModifyProperty 0x26 operation literal 2. |
| E05 | The base path clamps the supplied elapsed amount, calls ModifyEntitiesActionDelay on the controller list with a captured delegate, then adds elapsed amount into controller+0x348 through FixPoint.op_Addition. The delegate body and all filtering paths are not closed. |
| E06 | SetCurrentTurnActionEntity stores current action entity at controller+0x298. _PickTurnActiveEntity separately writes +0x260. Named current-turn-owner accessors and independent metadata fields corroborate distinct storage; ProcessTurnOwnerSwitch calls owner-change processing. |
| E07 | TryInsertAbility invokes a separate sort. _CompareByInsertAbilityInstance calls ENGBNDIPDJL.KGAFHLGGNHJ, which first compares signed +0xa8 ascending, then entity-related data. _TickInsertAbility changes current action entity and invokes UseAbility; _FinishInsertAbility calls ExecuteAllModifierEvent and a LevelInsertAbilityFinish initializer. |
| E08 | Action-finish controller paths check skill and limbo completion before OnAfterSkillPerform/RefreshCurrentSkillPerform. ProcessOnLevelTurnEnd iterates modifiers and calls OnTurnEnd; OnTurnEnd conditionally calls a helper for config literal 5, then calls event execution with literal 0x13. |
| E09 | Distinct death and revive handlers exist. Revive reads/modifies properties and calls SetupActionDelayByUnitDistance. This establishes queue-affecting lifecycle candidates, not a complete native participation rule. |

Speed behavior has a concrete distance/speed division join, with speed read at property 0x20 and output mutation at 0x26. The config field value, tagged AV scale/range, full rounding and effective initialization are unresolved. `10000 / speed` remains a declared reference candidate. RefreshSpeed has separate modifier-sensitive and override property paths; this does not close native mid-cycle rebase.

Action ordering includes signed tagless qword readiness comparison and packed auxiliary keys. Equal zero values have special +09/+0c ordering distinct from negative delay. These machine-code facts do not prove final equal-key stability, key producer meanings or effective dispatch. Turn-owner candidate storage and current action entity are distinct; a source skill owner does not establish native turn rights.

Insertion uses a separate sort/use/finish path. Ultimate/FUA/extra categories and AV/counter consumption remain unclosed. Modifier OnTurnEnd contains event literal 0x13 and a config-literal-5 branch; the reference event interface uses namespaced keys and does not transplant these literals as global native event IDs.

## Generic state and explicit policy

The exact Draft 2020-12 JSON schemas are embedded in the turn contract control. BattleTurnState resides under existing BehaviorBattleState.mechanics["battle_turn_v1"]. It contains rational BattleClock; ordered participant bindings; ActorInitiativeState; normal queue index; ActiveTurn stack; separate pending insertions/interrupts; fresh ActionPermissions; boundary work/cursors; decision/failure; stage/terminal state; all ID/order/revision/counter state and a command journal.

Actor HP/resources/progression/properties/modifiers remain in their current authoritative stores. Effective speed samples are revision/hash-bound scheduling caches. Absolute due_at is the readiness authority; remaining=max(0,due_at-now) is derived. Queue copies are checked against initiative revision/due, so they cannot diverge silently. Explicit participant generations invalidate stale entries/permissions. No process object identity or wall clock participates.

Reference policy: reduced exact integer rationals, positive denominator, gcd normalization, zero=0/1, explicit 256-bit numeric bound, reject booleans/floats and unsupported tagged speed modes. Ordinary R12 mode0 speed raw is explicitly decoded using /2^33. Initial due=now+K/s; waiting speed changes preserve remaining distance, new_due=now+remaining*old_speed/new_speed; advance/delay uses a fraction of the full current interval; advance clamps to now. Every numeric choice is hash-bound REFERENCE_MODEL and injectable. Missing policy returns AV_REFERENCE_POLICY_MISSING.

Total queue order: due ascending, declared priority descending, participant registration ordinal ascending, enqueue ordinal ascending, then entry ID UTF-8 bytes ascending. Equal readiness acts at the same AV timestamp; no fabricated elapsed tick. Normal completion re-schedules only after end-boundary/duration/expiry callbacks drain, using final effective speed.

NORMAL_TURN, EXTRA_TURN, INSERTED_ACTION, FOLLOW_UP_ACTION, ULTIMATE_INTERRUPT and FORCED_ACTION are proposed reference categories. Each rule explicitly records placement, owner/parent, AV consumption, normal-turn count, start/end events and duration progression. The initial profile consumes AV/count only for NORMAL_TURN; EXTRA_TURN emits start/end but does not consume normal AV/count. Other insertions emit action boundaries only. Ultimate interruption remains a typed gap until a safe-point adapter exists. These choices are policy, not native categorization.

## R15, events and decision integration

Global select → caller player/Monster/forced decision → fresh permission and BEFORE_ACTION callbacks → existing ResourceEngine/context → R15 ActionExecutionRoot → tasks/events/resources/damage drain → exact completed/suspended/gap receipt → AFTER_ACTION/TURN_END/duration/expiry → final-speed interval → lifecycle/stage reconciliation. R15 logical time is never added to battle AV. Running/suspended work holds its normal turn.

Existing R15 start_action rejects while its current root is incomplete. R21 does not bypass that guard. A future interrupt adapter must save the parent root/context at an explicit safe point, retain all parent-owned queues/cursors, execute a distinct root, and restore parent current-root/context without restoring shared actor/resource/modifier state. Absent adapter/policy/token or an open damage/resource transaction returns INTERRUPT_POLICY_MISSING.

Reference turn events reuse R17 listeners and R15 frames through labeled boundary envelopes. They require complete explicit listener registration hashes, including an explicitly empty set. Event IDs/status/listener cursors and duration/expiry cursors prevent duplicate dispatch after snapshot/resume. Persistent modifiers survive skill completion; declared owner-normal-end duration policy skips creation turn, runs turn-end callbacks before duration progress and drains expiry callbacks before reset. Automatic energy/SP gains are not fabricated.

APIs: initialize_turns, run_until_decision, current_turn_owner, next_actor_preview, legal_action_candidates, submit_action, run_until_next_turn, is_terminal, notify_speed_change, adjust_readiness, request_insertion, plus existing clone/snapshot/hash/replay. Distinct boundary kinds are player normal, enemy AI, out-of-turn window, forced action, suspended input, terminal, SemanticGap and budget yield. Candidates are reference permissions; native legal_actions is not claimed.

MonsterDecisionProvider and lifecycle/stage interfaces specify input snapshot, exact candidate permission, stable provider/hash, deterministic RNG ownership and wave/terminal results. Full AI/stage/waves are not implemented. WAVE_PENDING does not imply victory. Defeat/removal removes waiting entries and cancels invalid insertions; active work has an explicit settlement rule; revival/new summons require new generation/registration and full binding.

Clone/canonical snapshot/hash reuse existing runtime methods and include policies/catalog/registry/provider identities plus every pending turn/action/event cursor. Canonical equality rejects unreduced rational alternatives. Replay stores prehash/arguments in the state journal; external receipts hold the posthash after journal append, avoiding a self-referential snapshot hash.

Typed failures: `INITIATIVE_INPUT_MISSING`, `SPEED_PROVIDER_MISSING`, `TURN_OWNER_UNKNOWN`, `AV_REFERENCE_POLICY_MISSING`, `NATIVE_ORDER_UNKNOWN`, `INTERRUPT_POLICY_MISSING`, `TURN_BOUNDARY_EVENT_UNKNOWN`, `ENTITY_STATE_UNRESOLVED`, `ACTION_NOT_COMPLETE`, `SEMANTIC_GAP`. Missing native behavior never becomes a silent no-op. Rejected commands preserve state/RNG; resumable action gaps preserve earlier committed task prefixes.

## Policy-only traces and validation

Nine explicit traces: two speeds, three-way order, equal readiness, waiting speed change, advance/delay, inserted action, interrupted action, defeated-before-turn and turn-end callback. Arithmetic traces have independently handwritten expected rational results. Insertion/interrupt/event transcripts are declared protocol specifications, not executable global engine/native tests. The interrupt fixture explicitly expects the initial profile gap and documents a future adapter transcript.

R21 executable specification lane: **21 PASS**. It checks rational arithmetic, noncanonical/malformed/overflow inputs, deterministic order, policy hash mismatch, stale queue generations/revisions, all boundary kinds/active phases, existing BehaviorRuntime/state clone/snapshot/hash and an explicit replay command specification. A separate actual R15 compatibility probe verifies active-root rejection, callback drain, cloned/restored action completion and unchanged battle AV while its logical-time wait advances. No existing tests were edited.

| Regression lane | Baseline | Final |
|---|---|---|
| R12_R20 | 307 PASS | 307 PASS |
| battle_ir_FAST_UNIT | 586 PASS | 586 PASS |
| battle_runtime_FAST_UNIT | 501 PASS | 501 PASS |
| battle_sandbox_FAST_UNIT | 918 PASS | 918 PASS |

Validation: immutable source pin/body/hash references PASS; exact-vs-inferred joins and bounded inventory PASS; JSON schemas/policy/example serialization PASS; policy trace repeat/hash PASS; inherited file preservation PASS; architecture PASS. The tests do not establish native Turn/AV or an implemented full battle loop.

## R22 executable plan and independent tracks

Recommended **R22 GLOBAL TURN / AV REFERENCE ENGINE + DECISION BOUNDARY INTEGRATION**. Implement strict opt-in state/provider policy validation; rational queue/clock; actor-bound permissions/decisions; R15 ownership/completion; R17 reference boundary envelopes and duration cursors; lifecycle/stage/Monster request adapters; public-command replay and regression tests. The plan control provides proposed files, ordered deliverables, API/call graph links, and 19 acceptance rows.

Implement reference clock/order/decisions now. Require caller policy for speed/availability, source readiness effects, insertion/lifetimes/lifecycle/stage choices. Reserve structural tickets for exact native rounding/rebase/effect mappings and effective oracle tickets for initialized inputs/patch dispatch/native insertion/events/legality. No new broad evidence phase is a prerequisite.

Camera catalog gaps, unknown templates, modifier inputs, incomplete Heal, Shield, Toughness/Break, Monster AI content, stage/waves and adviser/search are independent tracks. R21 global subsystem readiness is not judged by completion of the 160 skill roots and does not upgrade that census.

## Deliverables and handoff

Five requested control JSONs and this report are accompanied by six R21 tooling/specification files and the R21 audit directory. Production files modified: NONE. Existing tests modified: NONE. Optional reference turn engine: NO. Native-equivalent Turn/AV: NOT CLAIMED. Git writes: NONE.

Reproduce: python tools/runtime/r21_evidence.py; python tools/runtime/r21_contract.py; python tools/runtime/r21_specs.py; python tools/runtime/r21_checks.py final; python tools/runtime/r21_finalize.py; python tools/runtime/r21_finalize.py --package. Never regenerate the start gate. Native extraction script uses only pinned static sources; previously selected bodies are retained.

Handoff target: `D:/HSR_Battle_Agent/agent_handoffs/CR-R21-TRUE-TURN-AV-CONTRACT-20261011-001_changed_files.zip`. Package includes only R21-owned files and manifest. Selected bounded text disassembly is included; game binaries/payloads, process dumps, prior reverse audit trees and unrelated work are excluded. External handoff_verification.json records CRC, exact members, sizes, member SHA-256, ZIP SHA-256 and archive size. The verification receipt is kept outside the archive to avoid self-reference.
