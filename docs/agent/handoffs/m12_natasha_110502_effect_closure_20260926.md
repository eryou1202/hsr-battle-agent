# M12 Natasha 110502 effect-body closure audit — CR-M12-NATASHA-110502-EFFECT-CLOSURE-20260926-001

Mechanical evidence audit only. No production code, no runtime binder, no
TriggerAbility execution or traversal, no semantic inference, no M10/M11 change,
no existing M12 record change, no Git write.

- **Starting HEAD:** `090004039dff087217b4fa56b9d29fd8dedba4d0`
- **Branch:** `terra/implementation`
- **Machine-readable output:** `data/content_binding/4.4.54/natasha_110502_effect_closure_001.json`
- **Closure verdict:** `A. NO_REF02_CLOSURE`
- **Next executor:** DS

## 0. Content root

| Field | Value |
| --- | --- |
| AvatarID / SkillID | `1105` / `110502` |
| trigger key | `Skill02` |
| EntryAbility (root) | `Avatar_Natasha_00_Skill02_Phase01` |
| binding strength | `BEHAVIOR_ROOT_BOUND` (per `content_binding_reentry_review_001.json`) |

The owner-scoped join was **not** reconsidered, per the brief.

## 1. Question A — the named edge is exact

The pinned compiler artifact records the edge with exact fields:

- **Source:** `data/semantics/4.4.54/full_reconstruction/behavior_compiler_report_001.json` → `/records[31]`, `behavior_id …:Avatar_Natasha_00_Skill02_Phase01`
- **Operation:** `…Avatar_Natasha_00_Skill02_Phase01:ONSTART:0`, index **0**
- **Type / kind:** `RPG.GameCore.TriggerAbility` / `INVOKE_BEHAVIOR`
- **Exact target field:** `arguments.AbilityName.Value`
- **Exact target value:** **`Avatar_Natasha_00_Skill02_Phase02`**
- **Target exists:** yes — the ability container records ordinal 3 at `0xBC9960–0xBC9BC9`
- **Ordering:** index 0 of 4 root operations (1: PredicateTaskList, 2–3: presentation, omitted by existing policy)
- **Not executable:** `entrypoint executable_reference: false`, `event_boundary: UNKNOWN`, dependency `KERNEL-EVENT-001`

Classification: **`EXPLICIT_NAMED_CONTENT_EDGE`** — and nothing more. This is **not** an
executable TriggerAbility edge, not native continuation, not action completion.
The root's own `dynamic_value_definitions` is empty, so the root supplies no
dynamic values to the body.

## 2. Question B — the Phase02 body, in exact order

`compile_status: **REJECTED**` · 8 operations · **3 execution blockers** · `executable_reference: false`

| # | op | source type | compiler kind | status | disposition |
| --- | --- | --- | --- | --- | --- |
| 0 | ONSTART:0 | `WaitAnimState` | PRESENTATION_WAIT | PRESENTATION | **REJECT_NOT_NOOP** |
| 1 | ONSTART:1 | `TriggerEffect` | PRESENTATION | PRESENTATION | HEADLESS_PRESENTATION_OMITTED |
| 2 | ONSTART:2 | `WaitAnimState` | PRESENTATION_WAIT | PRESENTATION | **REJECT_NOT_NOOP** |
| 3 | ONSTART:3 | `PredicateTaskList` | CONDITIONAL | REQUIRES_PACKET | EXECUTABLE_REFERENCE |
| 4 | ONSTART:4 | **`HealHP`** | **HEAL_REQUEST** | **MODELLED** | **EXECUTABLE_REFERENCE** |
| 5 | ONSTART:5 | `PredicateTaskList` | CONDITIONAL | REQUIRES_PACKET | EXECUTABLE_REFERENCE |
| 6 | ONSTART:6 | `AddModifier` | ADD_MODIFIER | REQUIRES_PACKET | **BOUND_UNEXECUTABLE_PACKET** |
| 7 | ONSTART:7 | `WaitAnimState` | PRESENTATION_WAIT | PRESENTATION | **REJECT_NOT_NOOP** |
| 8 | ONSTART:8 | `ModifySPNew` | MODIFY_TEAM_SP | MODELLED | EXECUTABLE_REFERENCE |
| 9 | ONSTART:9 | `Retarget` | RETARGET | REQUIRES_PACKET | **BOUND_UNEXECUTABLE_PACKET** |
| 10 | ONSTART:10 | `SkillPerformFinish` | ACTION_COMPLETION_MARKER | REQUIRES_PACKET | EXECUTABLE_REFERENCE |

Notable exact facts: `AddModifier` carries
`reference_execution_blocker = EXECUTABLE_REFERENCE_ADD_MODIFIER_ARGUMENTS_UNSUPPORTED`;
`Retarget` carries **`ByRandom: true`** — a randomness surface inside the body;
the three `WaitAnimState` blockers use `REJECT_NOT_NOOP` /
`BEHAVIOR_AFFECTING_NODE_NOT_COMPILED` with `POSSIBLE_STATE_COMMIT` gating risk.

**Cross-source divergence (recorded, not resolved):** the compiler (close-4.4.0)
puts `DispelStatus` alone inside ONSTART:3 and `HealHP` as a separate top-level
operation at ONSTART:4; the pinned 4.4.53 archive puts `DispelStatus` (ordinal 0)
and `HealHP` (ordinal 1) as two success tasks of one `PredicateTaskList`.
Deciding which attribution is native would be an inference, so it was not done.

## 3. REF02 field matrix (13 required keys)

Authority: `reference_damage_adapters.py :: OrdinaryReferencePacket / PacketKind /
apply_reference_packet`, with `tests/game_data/test_reference_damage_v2.py`.

| Field | Status | Basis |
| --- | --- | --- |
| `packet_schema` | **EXACT_CLOSED** | contract constant `ordinary_reference_packet/1` |
| `kind` | **PRESENT_BUT_SEMANTICS_UNMAPPED** | compiler says `HEAL_REQUEST`/MODELLED, but no artifact maps `HealHP` to a REF02 kind |
| `source_id` | RUNTIME_SCENARIO_INPUT | caster token; REF02 gate takes an explicit owner |
| `targets` | RUNTIME_SCENARIO_INPUT | REF02 accepts an explicit single-id list |
| `base_value` | RUNTIME_SCENARIO_INPUT | existing `heal_formula_type4_ordinary` + two dynamic values |
| `factors` | LOCAL_ORCHESTRATION_ONLY | ordinary factor already folded by the existing formula |
| `resource_cost` | RUNTIME_SCENARIO_INPUT | REF02 requires it; content supplies a *contribution*, not a cost |
| `resource_owner` | RUNTIME_SCENARIO_INPUT | must equal the combat state owner |
| `toughness_delta` | **EXACT_CLOSED** | REF02 forces `0` for a heal |
| `survival_closed` | LOCAL_ORCHESTRATION_ONLY | demanded as an input, never derived |
| `events_closed` | LOCAL_ORCHESTRATION_ONLY | demanded as an input, never derived |
| `task_id` | **EXACT_CLOSED** | must be `None` for a combat packet |
| `task_owner` | **EXACT_CLOSED** | must be `None` for a combat packet |

**4 EXACT_CLOSED · 5 RUNTIME_SCENARIO_INPUT · 3 LOCAL_ORCHESTRATION_ONLY · 1 unmapped.**
`kind` is the only settlement-driving field with no existing mapping. No field was
marked `EXACT_CLOSED` merely because a plausible number existed.

## 4. DynamicFloat — the finding that changes the picture

**Result: `RUNTIME_VALUE_REQUIRED`** — and the representation is not opaque.

All three formulas serialise as `opcodes [1, 0, 17]` = `01 00 11`, i.e. base64
`"AQAR"`. Running the **existing** decoder (`decode_postfix_program`, whose
constants are `OPERAND_DYNAMIC = 0x01`, `OPERAND_FIXED = 0x00`, `END = 0x11`)
gives, for every one of them:

```
tokens = DYNAMIC[0], END     infix = DYNAMIC[0]
operand_count = 1   dynamic_hashes = (<one hash>,)   fixed_values = ()
```

So each DynamicFloat is **exactly one unresolved single-value reference**:

| Field | hash | resolved anywhere? |
| --- | --- | --- |
| `DispelStatus.Numbers` | `-2124210825` | no |
| `HealHP.HealPercentage` | `-1544075911` | no |
| `HealHP.ModifyValue` | `-203632277` | no |

The existing code already has the consumption path: `PostfixProgram.evaluate(resolver)`
(verified: it requests exactly that hash) and
`battle_ir.healing.RealSkillExternalBindings.dynamic_values` carrying
`ResolvedDynamicFloat(formula_operand, value_raw, provenance)` — the code says
"**evaluation is external**". Phase02's own compiler node defines **one** dynamic
value (`-1087299341`, `ReadInfo{Index:0, Type:"None"}`), referenced only by the
`AddModifier` Lifetime operand; **none** of the three heal/dispel hashes is defined
there. No ParamList index semantics were inferred.

## 5. Heal consumer

- Operation representation: **exists** — `kind = HEAL_REQUEST`, `semantic_status =
  MODELLED`, `disposition = EXECUTABLE_REFERENCE`, dependency
  `dynamic_mvp_v1:HEAL_STATE_TRANSITION`.
- Authorized formula adapter: **exists** — `heal_formula_type4_ordinary` (six
  integer inputs → one amount), plus `NatashaSkill02HealConfig` /
  `load_natasha_skill02_heal_config` projecting the content artifact.
- Authorized adapter to a **REF02 packet**: **does not exist.**
- The real-skill path deliberately terminates at `HealRequestBoundary` with
  `consumer_status = POSITIVE_HEAL_EVENT_CONSUMER_NOT_RECOVERED` and
  `persistent_effect_policy.current_hp_mutation: NOT_PERFORMED`.
- REF02's `EXPLICIT_HEAL` *does* mutate target HP — but only from a
  caller-declared packet, as a `REFERENCE_MODEL` settlement.

**Representation exists ≠ an authorized adapter exists.** Bridging them would
require a new mapping.

## 6. Target

All seven target-bearing fields recorded. Every heal/dispel/modifier target is the
alias `AbilityTargetEntity`; `ModifySPNew` targets `Caster`; `Retarget` targets
`SkillTargetEntityList` and carries `ByRandom: true`.

**`TARGET = LOCAL_OR_RUNTIME_SCENARIO_INPUT`** — REF02 already accepts an explicit
target id list, so native target selection and cardinality were neither needed nor
inferred.

## 7. Resource cost

**`REF02_SETTLEMENT_REQUIRED`.** REF02 requires the field, validates `>= 0`, and
**subtracts** it from the state's resource pool (verified against
`test_hand_computed_ordinary_damage`: 5 → 3 for cost 2).

The content supplies **no cost** — and this is a genuinely new exact finding:
`reference_operation_adapters._ADD_RATIO_SOURCES` **already contains
`"Avatar_Natasha_00_Skill02_Phase02"`**, and `apply_named_team_sp_contribution`
documents the `ModifySPNew` operation as a *"post-commit contribution"* whose
non-positive values *"are never treated as a cost"*. So the content SP operation
must **not** be used as `resource_cost`; a runtime scenario input must supply it.
No Skill Point cost was fabricated and `SPBase`/`BPNeed` were not mapped.

## 8. DispelStatus

Present in both sources (`Numbers` hash `-2124210825`, `Order` 2 / `"LastAdded"`,
target `AbilityTargetEntity`). It is **not** declared required for the heal, and
**not** declared independent of it — it is a **sibling effect in the same behavior**.

No artifact authorizes excluding a declared sibling from a REF02 settlement, and
the existing whole-step discipline rejects rather than partially applies
(`_SPECIAL_KEYS` rejection; `test_late_special_field_rejects_whole_step_without_resource_debit`).
Classification: **`SIBLING_EFFECT_BLOCKS_ATOMIC_REPRESENTATION`** — option **D** of
the brief. Not decided from gameplay intuition.

## 9. Survival / events

REF02 **demands** `survival_closed` and `events_closed` as inputs; it neither
derives nor guarantees them. They are explicit runtime contract inputs that belong
to the local envelope, not content claims. Classified `LOCAL_ORCHESTRATION_ONLY`.

## 10. Local bridge

**`BLOCKED_BY_MISSING_SETTLEMENT_FIELDS`** — blocking field: `kind`. Plus four
blocking structural conditions: the unauthorised sibling exclusion, Phase02's own
`REJECTED` compile status with three `REJECT_NOT_NOOP` blockers, the two
`BOUND_UNEXECUTABLE_PACKET` operations (one with a declared blocker), and the
`ByRandom` retarget. No settlement value would have to be fabricated. This is
**not** permission to implement a bridge, and TriggerAbility is **not** called
executed.

## 11. Verdict

**A. NO_REF02_CLOSURE.**

- C, and the premise of D, both require the body to be closed with existing
  mappings — one required field (`kind`) is not.
- B requires the only blockers to be runtime scenario inputs — two are not.
- E requires a new exact mapping needing evidence judgment — the new exact findings
  are all established by existing code.

M12 is **not** declared unblocked. Golden remains 0, NATIVE_TRACE remains empty.

## 12. New exact evidence

1. **NE-1** The Phase01→Phase02 named edge with its exact argument field/value, from an existing compiler artifact.
2. **NE-2** All three DynamicFloats decode to a single unresolved value reference — a value-supply problem, not opaque bytecode.
3. **NE-3** An existing authorized adapter already names this behavior in its `AddRatio` allowlist; the SP operation is a contribution, never a cost.
4. **NE-4** Phase02's compiler node is `REJECTED` with three `REJECT_NOT_NOOP` waits, and two of eight operations are `BOUND_UNEXECUTABLE_PACKET`.
5. **NE-5** The two sources attribute `DispelStatus`/`HealHP` to different structural positions (recorded, not resolved).

## 13. Next executor and question

**DS.** Not all settlement-driving fields close, and no newly discovered exact
mapping requires evidence judgment.

**Next question:** mechanically resolve the two remaining non-runtime gaps without
inferring semantics: (1) enumerate every artifact and symbol that classifies a
`RPG.GameCore.HealHP` task and determine whether any declares a REF02 packet kind —
if none does, record the absence precisely so Sol can decide whether to authorize
one; and (2) test whether the three `REJECT_NOT_NOOP` `WaitAnimState` blockers and
the two `BOUND_UNEXECUTABLE_PACKET` operations are covered by any existing omission
or exclusion policy. Do not derive a formula, invent ParamList meaning, guess any
coefficient, cost, target type or Dispel semantics, and do not traverse or execute
the TriggerAbility edge.

## 14. Validation performed

- JSON parses; duplicate keys rejected (`validate_json_no_duplicate_keys.mjs` → PASS — it caught a real duplicate `git_writes` key, which was removed).
- All cited source paths exist; all reported SHA-256 digests recompute.
- Operation order reproduces from `/records[32]`.
- The `DYNAMIC[0]` decode was reproduced by **executing** the repository decoder.
- The `_ADD_RATIO_SOURCES` membership was read directly from module source.
- REF02 required keys and validate rules were read from the current implementation and tests.
- No inferred semantic mapping appears as exact evidence; no fuzzy or numeric-proximity join was used.
