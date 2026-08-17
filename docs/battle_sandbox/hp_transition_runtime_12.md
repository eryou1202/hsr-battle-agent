# HP Transition Runtime 12

Status: `BATTLE_SANDBOX = HP_TRANSITION_RUNTIME_12_PROOF`

This is the implementation note for the completed Handoff 12 HP-transition
contract. It is **not** a damage runtime. Reverse evidence is in
`docs/agent/handoffs/semantic_handoff_12.md` and the machine artifact is
`data/semantics/4.4.54/direct_damage_hp_transition_12.json`.

## Implemented scope

- `battle.ir.hp.try_get_lock_hp` — exact M506532 scan semantics.
- `battle.ir.hp.direct_damage.transition` — DirectDamageHP mode 0 for normal
  finite FixPoint values.
- SetHP negative-delta composition:
  `target = ModifyValue + fp_mul(MaxHP, ModifyRatio)`,
  `delta = target - CurrentHP`, negative delta lowers into DirectDamageHP
  with `damage_kind=100`.

## State model

- CurrentHP remains `PropertyEntry` property 10, materialized via source index 0.
- NegativeHP remains `PropertyEntry` property 9, materialized via source index 0
  only on the proven lock-overflow gate.
- Lock records are the smallest persistent representation required by the
  native `component[+0x50]`: `BattleState.component_lock_hp_records` keyed by
  entity runtime id. Each record is `{action_ref, kind, value}`. No lifecycle
  add/remove API is invented.
- No `entity.hp`, `DamageState`, `HitState`, `EventState`, or `EntityStats`
  field is introduced.

## TryGetLockHP

Scans records descending, skips `kind < damage_kind`, selects the first
accepted value, extends best index across equal values, stops at a non-equal
accepted value, and returns forward actions from best to end. Empty/no-match
returns `false` with lock value `0`.

## DirectDamageHP mode 0

The runtime implements the artifact's exact `O/D/C/M/R/L/K/Z/B` transition,
shared clamp, source-0 CurrentHP write, `Y <= 0` record boundary, bounded
NegativeHP write, and output `applied_delta`.

Unsupported modes 4/5/6 raise explicitly. Positive DirectChangeHP raises
instead of guessing. Special native NaN/Infinity FixPoint encodings are not
constructible by the current sandbox arithmetic; non-qword/non-int inputs are
rejected explicitly.

## Boundaries

- `_AfterPropertyChanged` M506625: represented by existing deterministic
  `PropertyChangeBoundary` records; consumers not implemented.
- `0x18DA9CFF0` negative record submit: represented by
  `NegativeHPRecordBoundary` trace when `Y <= 0`; consumer not followed.
- Lock action-list submission: represented by `LockActionBoundary` trace with
  the selected ordered opaque action refs; consumer not followed.
- `0x18B429F50` tail call: not implemented.
- NegativeHP gate native fields are exposed as a deterministic
  `negative_hp_gate` primitive input; no speculative component fields are
  added.

## Registry / Executor

The two HP primitives are loaded from the Handoff 12 artifact through the
semantic catalog and bound in the formal `PrimitiveRegistry`. The cross-layer
test executes SetHP composition via registered fixed-point primitives, then
`try_get_lock_hp` and `direct_damage.transition` through `Sandbox.execute`.
