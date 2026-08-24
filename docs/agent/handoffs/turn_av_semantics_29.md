# Turn / AV Semantics 29

Status: `TURN_AV_SEMANTICS_29_PROOF` — confirmed for the ordinary, eligible
action-list scope, with explicit completion/recharge and special-ordering
boundaries.

## Closed transition

`DoTurnPrepareStartWork` sorts the action-entity list, picks the first eligible
`HasActionTurn` entity, stores it as current actor/turn owner, reads that
entity's property `38`, and advances the list by the selected delay.

For every admitted action entity the advance callback writes:

`remaining_delay = max(remaining_delay - selected_delay, FixPoint(0))`

The game mode then writes:

`elapsed_action_delay += selected_delay`

Property `38` is therefore confirmed as the remaining action delay. Property
`32` is the speed input: `get_UnitActionDelay` returns zero for non-positive
speed, otherwise an unresolved unit-distance constant divided by speed.
`SetupActionDelayByUnitDistance` similarly sets property `38` from
`(unit_distance_constant * input_ratio) / speed` when speed is positive.

## Ordering

The native comparator is lexicographic: remaining delay ascending, then
continuation/current-actor priority, then zero-delay special/immediate keys,
then two additional integer keys. The runtime's ordinary scope rejects those
special modes. If all recovered keys are equal, the sandbox preserves prior
action-list order as its documented deterministic policy; native
`List<T>.Sort` stability is not claimed.

## Completion and recharge boundary

Task success is not sufficient to declare a turn complete. Native completion
also checks skill, limbo, add-buff, hold-frame, and cleanup state before the
FSM reaches `TurnEnd` (enum value `20`). The runtime therefore requires an
explicit settled-action acknowledgement.

The generic post-action write that recharges the acting entity's property
`38` for its next ordinary turn is not closed by this batch. Repeated-turn
runtime calls must supply a provenance-bearing `next_action_delay_raw` at the
completion boundary. No community `10000 / SPD` or `150 / SPD` formula is
used.

## Evidence

- Machine-readable capability:
  `data/semantics/4.4.54/turn_av_semantics_29.json`
- Bounded native census:
  `data/raw/4.4.54/turn_av_topology_census_29.json`
- Builder:
  `tools/reverse/scripts/build_turn_av_semantics_29.py`

The artifact records exact native RVAs and bounded-body SHA-256 hashes for the
completion, sorting, selection, advance callback, property, and comparator
methods.

## Runtime binding

`src/hsr_battle_agent/battle_runtime/turns.py` implements the ordinary-scope
transition over BattleState schema v4. `turn_timeline` stores ordered runtime
ids, current actor, elapsed delay, phase, and turn index; property `38` remains
the only source of truth for per-actor remaining delay. The catalog-backed
primitive is `battle.ir.turn.advance_to_next_actor`.

`ActionCompletionBoundary` is intentionally not inferred from task success.
It requires the current actor, an explicit next-delay raw value, and a
non-empty provenance label before another turn can be selected.

Focused tests cover sorting, selection, AV subtraction, elapsed AV, stable
equal-key policy, three sequential turns, completion validation, catalog
provenance, trace output, snapshot roundtrip, clone isolation, and stable
hashing.
