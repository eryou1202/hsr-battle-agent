# Semantic Handoff 30: Real Natasha Skill to Heal Event Boundary

`STATUS = CORE_RUNTIME_READY_WITH_BOUNDED_EXTERNAL_BLOCKER`

This handoff composes the ordinary Turn/AV runtime with the real
`Avatar_Natasha_00_Skill02_Phase02` content recovered in Content Handoff 30.
It is the strongest honest core path currently available:

```text
BattleState property-38 timeline
  -> select Natasha as active actor
  -> load and validate committed real DesignData content
  -> accept provenance-bearing BySkillPointActivated resolution
  -> accept provenance-bearing AbilityTargetEntity resolution
  -> emit DispelStatus request boundary
  -> evaluate native FormulaType 4 using BattleState properties
  -> emit Heal request boundary with computed FixPoint amount
  -> preserve CurrentHP until the positive-heal consumer is recovered
  -> settle the turn with an explicit provenance-bearing next delay
```

Semantic artifact:
`data/semantics/4.4.54/real_skill_heal_boundary_30.json`.

Sandbox report:
`data/sandbox/core_real_skill_runtime_30_report.json`.

## Accepted runtime scope

- Active caster must match the Turn/AV timeline's current actor.
- Content must validate as the exact committed 4.4.54 Natasha artifact.
- The parent/task/predicate/target discriminators, field bitmaps, node
  boundary, DynamicFloat opcode shapes, operand keys, and archive provenance
  are validated before execution.
- Predicate, target alias, DynamicFloat values, and ordinary-healer branch are
  external bindings with mandatory non-empty provenance.
- Missing or duplicate DynamicFloat bindings fail explicitly.
- FormulaType 4 is implemented for the ordinary non-component-kind-225,
  non-rally branch only.
- MaxHP, CurrentHP, HealRatio, and HealTakenRatio must exist as materialized
  BattleState properties.
- Non-positive formula output clamps to zero as in the native body.

## Boundary semantics

The runtime returns two ordered typed values:

1. `DispelStatusRequestBoundary`
2. `HealRequestBoundary`

Neither is mislabeled as a persistent gameplay mutation. The Heal boundary
records the observed CurrentHP, computed amount, FormulaType, exact config
reference, and all dynamic/target/branch provenance.

The positive heal event consumer remains unknown. Consequently CurrentHP is
unchanged, and the E2E test asserts the entire BattleState hash is unchanged
across the two effect boundaries. This is intentional correctness, not a
placeholder success write.

## E2E result

The deterministic scenario selects Natasha at delay 10 before an ally at
delay 20, loads the real skill, resolves the three serialized DynamicFloat
keys externally, and computes:

```text
(MaxHP 1000 - CurrentHP 400) * HealPercentage 1 + ModifyValue 50
= FixPoint(650)
```

With HealRatio and HealTakenRatio both zero, the final amount remains
`FixPoint(650)`. The runtime emits the ordered boundaries, leaves the ally at
`FixPoint(400)` CurrentHP, settles Natasha with an explicit delay 30, and then
selects the ally.

## Verification

- Focused real-skill tests: 6 passed.
- Full `tests/battle_runtime`: 185 passed.
- Full `tests/battle_sandbox`: 170 passed.
- Full `tests/reverse`: 8 passed.

## Remaining blockers

1. `BySkillPointActivated` runtime-context semantics.
2. DynamicFloat opcode and hashed-operand evaluation.
3. TargetConfig discriminator 12 selector implementation join.
4. `DispelStatus` effect consumer.
5. Positive HealData event consumer and CurrentHP mutation.
6. Generic post-action recharge writer/formula.

The damage-request dispatch blocker is unchanged: no new evidence resolves
the live `PGOOHIHKHNJ` instance-dependent pointer. No damage formula or fake
positive-HP mutation is introduced by this handoff.
