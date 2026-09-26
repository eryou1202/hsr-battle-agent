# M12 residual blocker frontier — CR-M12-RESIDUAL-BLOCKER-FRONTIER-20260926-001

Counterfactual analysis only. **WaitAnimState policy was not changed, no compiler
code was changed, no candidate is called executable, no semantics were inferred,
no existing M12 record was modified, no Git write was issued.**
`COUNTERFACTUAL_WAIT_GATE_CLOSED` is an analytical view, not an executable state.

- **Starting HEAD:** `c8b7672aa31a968af37f2311422695408cfbe729`
- **Machine-readable output:** `data/content_binding/4.4.54/content_residual_blocker_frontier_001.json`
- **Recommendation:** `SOL_REVIEW_WAIT_PLUS_ONE_DAMAGE_SHAPE`
- **Next executor:** SOL

## 1. Population and the counterfactual

241 settlement bodies. The counterfactual removes **only** diagnostics where
`origin=record` **and** `source_type=RPG.GameCore.WaitAnimState` **and**
`policy=REJECT_NOT_NOOP` **and**
`reason=BEHAVIOR_AFFECTING_NODE_NOT_COMPILED`. Nothing else is removed; a
`BEHAVIOR_AFFECTING_NODE_NOT_COMPILED` from any other operation is retained.
Both `original_blockers` and `residual_blockers` are preserved for every body.

## 2. Residual distribution

| Residual blockers | Bodies |
| --- | --- |
| 0 | **0** |
| 1 | **34** |
| 2 | 33 |
| 3 | 47 |
| 4 or more | 127 |

**Bodies unlocked by WaitAnimState alone: 0.**

## 3. Most common residual signatures

| Bodies | Residual signature |
| --- | --- |
| **49** | `DAMAGE_MIXED_STATE_FIELDS` |
| 38 | `BEHAVIOR_AFFECTING_NODE_NOT_COMPILED` + `DAMAGE_MIXED_STATE_FIELDS` |
| 17 | `ADD_MODIFIER_ARGUMENTS_UNSUPPORTED` + `DAMAGE_MIXED_STATE_FIELDS` |
| 11 | `BEHAVIOR_AFFECTING_NODE_NOT_COMPILED` + `DAMAGE_MIXED_STATE_FIELDS` + `MODIFIER_DEFINITION_UNRESOLVED` |
| 10 | `BEHAVIOR_AFFECTING_NODE_NOT_COMPILED` + `ADD_MODIFIER_ARGUMENTS_UNSUPPORTED` + `DAMAGE_MIXED_STATE_FIELDS` |

Residual class frequency: `DAMAGE_MIXED_STATE_FIELDS` 185 ·
`BEHAVIOR_AFFECTING_NODE_NOT_COMPILED` 152 (non-Wait sources: `TargetTimeSlow` 40,
`RadialBlurEffect` 36, `WaitSecond` 35, `SetEnergyBarState` 26, `WaitTimelineFinish`
14, `LAJIKDENEOO` 14, …) · `ADD_MODIFIER_ARGUMENTS_UNSUPPORTED` 83 ·
`MODIFIER_DEFINITION_UNRESOLVED` 54 · `RETARGET_TARGET_UNSUPPORTED` 39 ·
`DAMAGE_ATTACK_TYPE_UNSUPPORTED` 37 · `PROPERTY_VALUE_TYPE_UNSUPPORTED` 21 ·
`DAMAGE_PERCENTAGE_MISSING` 17 · `HEAL_VALUE_MISSING` 8 ·
`UNSUPPORTED_HEAL_FORMULA` 7.

## 4. Current accepted damage baseline (from actual code)

Authority: `behavior_compiler.py::_reference_payload_problem` lines 406–444;
`reference_execution.py::SemanticExecutor._execute_damage` (line 1476+);
`toughness_break_reference.py::apply_toughness_damage` +
`reference_execution.py::ToughnessCommitContext`; `tests/game_data/test_reference_damage_v2.py`.

- **Accepted `AttackProperty` fields (ordinary HP damage)**: `$type`, `AttackType`, `DamagePercentage`, `DamageType`, `FormulaType`, `HitAnimation`, `HitEffect`, `HitAngleVertical`, `HitEffectHeight`, `HitPosHeight`, `HitTimeSlowIntensity`, **`StanceValue`, `StanceDamageType`, `HitTimeSlowType`**
- **Bounded HP + stance path**: `StanceValue` and `StanceDamageType` are accepted and **executed** (`apply_toughness_damage`, break damage, `ToughnessCommitContext`) — so `StanceValue` is **not** an unresolved field
- **Accepted argument keys**: `AttackProperty`, `DisplayData`, `CanTriggerLastKill`, `SpecialHitSoundEvent`
- **Supported attack types**: `None`, `""`, `Normal`, `DOT` · **Formulas**: `ByAttack`, `ByMaxHP`, `ByDefence`
- **Explicitly rejected**: any extra `AttackProperty` key → `DAMAGE_MIXED_STATE_FIELDS`; any extra argument key → `DAMAGE_ARGUMENTS_UNSUPPORTED`; `AttackType` outside the set → `DAMAGE_ATTACK_TYPE_UNSUPPORTED`; `FormulaType` outside the set → `DAMAGE_FORMULA_UNSUPPORTED`; presence of `DamageValue` or `BreakDamagePercentage` → `DAMAGE_FORMULA_UNSUPPORTED`; `DOT` with stance fields → `DOT_MIXED_STATE_FIELDS`; missing `DamagePercentage` → `DAMAGE_PERCENTAGE_MISSING`
- **REF02 additionally refuses by name** (`OrdinaryReferencePacket._SPECIAL_KEYS`): `SPHitRatio`, `HitSplitRatio`, `DamageValue`, `DamageBehavior`, `Nonlethal`, `RandomCrit`, `SpecialFormula`, `UnknownTargetCardinality`, `UnknownEventCallback`

## 5. The 185 `DAMAGE_MIXED_STATE_FIELDS` bodies

| Extra-field signature | Bodies |
| --- | --- |
| `SPHitRatio` | **77** |
| `HitAngleHorizontal`, `SPHitRatio` | 32 |
| `HitAngleHorizontal`, `HitSplitRatio`, `SPHitRatio` | 22 |
| `HitSplitRatio`, `SPHitRatio` | 14 |
| `HitMotion`, `SPHitRatio` | 6 |
| `ExtraDamagePercentage`, `ExtraFormulaType`, `SPHitRatio` | 4 |

Per-field frequency: **`SPHitRatio` 182**, `HitAngleHorizontal` 67,
`HitSplitRatio` 50, `HitMotion` 15, `ExtraDamagePercentage` 7,
`ExtraFormulaType` 7, `CustomName` 4, `FrameHalt` 4, `HitEffectOffsetAngle` 4,
`HitSource` 3, `ScreenSpaceFloatMsg` 3.

**Delta from the accepted baseline:** 1 extra field → **80 bodies**
(`SPHitRatio` only 77, `HitSplitRatio` only 1, `HitAngleHorizontal` only 1,
`HitMotion` only 1); 2 extras → 58; 3 → 38; 4+ → 9. Offender attack types are
`None`/`Normal` and formulas `None`/`ByMaxHP`/`ByDefence` — **no unsupported
attack type or formula**. `DamageValue` 0, `BreakDamagePercentage` 0,
`StanceValue` 318 (accepted, so not counted), missing `DamagePercentage` 0.
Argument keys outside the allowlist: `TriggerHitSound` 8, `EqualSplitInTargets` 2.

Target presence is **proven present by control flow**: the `MIXED` branch is
unreachable unless the earlier `isinstance(target, Mapping)` check passed. The 45
operations whose `target` was not carried by the upstream census projection are
child operations and were not re-projected here; no inference was drawn from that.

## 6. Heal frontier (24 bodies)

Minimum residual **1**; three bodies reach it
(`RETARGET_TARGET_UNSUPPORTED` ×2, `UNSUPPORTED_HEAL_FORMULA` ×1). Classes:
`BEHAVIOR_AFFECTING_NODE_NOT_COMPILED` 17 · `ADD_MODIFIER_ARGUMENTS_UNSUPPORTED` 11 ·
`RETARGET_TARGET_UNSUPPORTED` 10 · `HEAL_VALUE_MISSING` 8 ·
`PROPERTY_VALUE_TYPE_UNSUPPORTED` 7 · `UNSUPPORTED_HEAL_FORMULA` 7 ·
`DAMAGE_MIXED_STATE_FIELDS` 7.

**No heal body is closer than the damage candidates**: 32 damage bodies reach
residual 1 with one repeated class, versus 3 heal bodies spread over two classes.
`HealHP ⇒ EXPLICIT_HEAL` was **not** inferred.

## 7. Wait positions (707 WaitAnimState operations across the 241 bodies)

Arguments observed: `AnimStateName` 706, `NormalizedTimeEnd` 706,
`WaitForFrameEnd` 1. `NormalizedTimeEnd` is always
`{"IsDynamic": false, "FixedValue": {"Value": <float>}}` — never dynamic.

Top-30 minimum-residual bodies: all 30 carry at least one wait (avg 1.6), and
every wait classifies as **`BEFORE_SETTLEMENT` (37)** or
**`BEFORE_COMPLETION` (10)** — no `AFTER_SETTLEMENT`, no `AFTER_COMPLETION`, no
`BETWEEN_SETTLEMENTS`. `AnimStateName` values: `Skill01` 41, `Skill03` 3,
`Skill02` 3. Per-wait ordinal, name, `NormalizedTimeEnd` and the ordinals of the
settlement / completion / resource / modifier / retarget operations are recorded in
the artifact. **No conclusion that the wait is safe to collapse is drawn.**

## 8. Unlock arithmetic (set arithmetic only)

Cumulative bodies whose entire residual set is a subset of the stated classes:

| Additional classes removed after Wait | Bodies |
| --- | --- |
| `{DAMAGE_MIXED_STATE_FIELDS}` | **49** |
| `{DAMAGE_MIXED_STATE_FIELDS, DAMAGE_ATTACK_TYPE_UNSUPPORTED}` | 50 |
| `{DAMAGE_MIXED_STATE_FIELDS, ADD_MODIFIER_ARGUMENTS_UNSUPPORTED}` | 66 |
| `{DAMAGE_MIXED_STATE_FIELDS, BEHAVIOR_AFFECTING_NODE_NOT_COMPILED}` | **87** |
| `+ ADD_MODIFIER_ARGUMENTS_UNSUPPORTED` | 114 |
| `+ MODIFIER_DEFINITION_UNRESOLVED` | 140 |
| `+ RETARGET_TARGET_UNSUPPORTED` | 159 |

- **Best single class after Wait: `EXECUTABLE_REFERENCE_DAMAGE_MIXED_STATE_FIELDS` → 49 bodies**
- **Best pair after Wait: `{BEHAVIOR_AFFECTING_NODE_NOT_COMPILED, EXECUTABLE_REFERENCE_DAMAGE_MIXED_STATE_FIELDS}` → 87 bodies**

## 9. Minimum-residual candidates

**Residual == 1: 34 bodies** — 32 with `DAMAGE_MIXED_STATE_FIELDS` alone, 1 with
`RETARGET_TARGET_UNSUPPORTED`, 1 with `UNSUPPORTED_HEAL_FORMULA`.
Residual ≤ 3: 114 bodies (all recorded in the artifact with AvatarID, SkillID,
trigger key, EntryAbility (naming root), effect body, settlement kinds, operation
count, original and residual blockers, and version relation).

All seven previously-named minimum-blocker candidates land at residual 1 with the
same single signature:

| SkillID | Effect body | Extra fields beyond baseline |
| --- | --- | --- |
| 110701 | `Avatar_Klara_00_Skill01_Phase02` | `FrameHalt`, `HitAngleHorizontal`, `SPHitRatio` |
| 111001 | `Avatar_Lynx_00_Skill01_Phase02` | `SPHitRatio` |
| 120801 | `Avatar_FuXuan_00_Skill01_Phase02` | `SPHitRatio` |
| 130301 | `Avatar_RuanMei_Skill01_Phase02` | `SPHitRatio` |
| 131001 | `Avatar_Sam_00_Skill01_Phase02` | `HitSource`, `IsFaceToHitDir`, `SPHitRatio` |
| 131201 | `Avatar_Misha_00_Skill01_Phase02` | `SPHitRatio` |
| 131401 | `Avatar_Jade_00_Skill01_Phase02` | `SPHitRatio` |

**Why the second blocker fires** (recorded per candidate with the source field set,
the compiler condition, the expected allowed set, the actual set and both set
differences): `behavior_compiler.py` line 441,
`if any(key not in allowed_attack_fields for key in attack): return
EXECUTABLE_REFERENCE_DAMAGE_MIXED_STATE_FIELDS`, with `attack =
arguments.AttackProperty`. It returns **before** any runtime input is considered.

## 10. Recommendation

**`SOL_REVIEW_WAIT_PLUS_ONE_DAMAGE_SHAPE`** — a narrow, repeated residual signature
exists: `DAMAGE_MIXED_STATE_FIELDS` alone accounts for 49 of 241 bodies, and 77 of
the 185 mixed-field bodies differ from the accepted baseline by exactly one field
(`SPHitRatio`, which REF02's own `_SPECIAL_KEYS` already refuses by name).

The next Sol task should decide **one** scope: whether an uninterpreted extra
`AttackProperty` field should be representable as an explicitly excluded field so
those 49 bodies can be assessed as a group. It should **not** redesign the compiler
globally, and it should **not** decide native animation timing or damage semantics.

## 11. Non-claims

WaitAnimState is **not** asserted safe to omit. Extra fields are **not** asserted
ignorable. No field semantics were inferred beyond existing authority. No candidate
is called executable. M12 is **not** declared unblocked.

## 12. Validation

Population 241 reproduced; all original blockers preserved; only WaitAnimState
attributable diagnostics removed; 185 mixed-field bodies reproduced; signatures
reproduce from the compiler report; the accepted baseline is quoted from current
code and tests; rankings deterministic; JSON parses and duplicate-key validation
PASS; no policy or source file changed.
