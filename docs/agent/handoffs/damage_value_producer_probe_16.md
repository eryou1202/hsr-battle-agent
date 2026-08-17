# Damage Value Producer Probe 16

`STATUS = PREPROCESS ONLY`

This is **not** `semantic_handoff_16`. It records mechanical provenance for
`request[+0x2D8]`, the FixPoint slot read by M507308.

Artifact: `data/raw/4.4.54/damage_value_producer_probe_16.json`

---

## Request object identity

- Evidence level: `SUPPORTED` / `UNKNOWN` for exact runtime type.
- M507296 `OnTaskBegin` materializes a request-like object at `0xC30EC14`
  via `0x183C736B0` with type token global `0x962F8E0`.
- No normalized type named `DamageRequest`/`DamageResult` matched.
- `+0x2D8` is treated as a native/runtime slot; it is also used by unrelated
  object families, so only request-chain methods are treated as strong
  evidence.

## Total +0x2D8 writers / pre-postprocess count

- Raw mechanical scan found many `+0x2D8` writes across the binary (many are
  stack locals or other object types).
- Request-chain relevant writers:
  - Pre-postprocess: `1` confirmed (`M508236 OnTaskBegin`)
  - Post-process: `2` (`M504557 RecomputeShieldCost`, `M504598 _MortallyWondedProcess`)
  - Other/unclassified: `3+` (`M504550 DamageFormula`, `M504576 SnapshotDamageMod`, `M504500 ModifyEntitiesActionDelay`)

## Writer clusters

1. **PROCESS_STORED_DAMAGE_ACCUMULATOR**
   - `M508236 OnTaskBegin` reads `[r12+0x2D8]`, adds via `0x19D661A00`, writes back at `0xB3DC80C`, then calls `M508237 -> M507308`.
2. **ABILITY_STATIC_POSTPROCESS**
   - `M504557` and `M504598` write `+0x2D8` after the original value exists.
3. **STACK_LOCAL_OR_OTHER_OBJECT_FAMILY**
   - `M504550`, `M504576`, `M504500`; not proven to target the same request FixPoint slot.

## Top candidates

| Rank | Classification | Method / RVA | Instruction | Why |
| --- | --- | --- | --- | --- |
| 1 | DAMAGE_VALUE_ACCUMULATOR_CANDIDATE | M508236 `0xB3DC5B0` | `0xB3DC80C` | Only confirmed pre-postprocess writer before M507308 |
| 2 | REQUEST_INITIALIZER | M507296 `0xC30D850` | `0xC30EC14` | DamageByAttackProperty request materialization site; +0x2D8 source unresolved |
| 3 | POSTPROCESS_ONLY | M504557 `0xE464D20` | `0xE4650B9` | Shield/post-process writer |
| 4 | POSTPROCESS_ONLY | M504598 `0xE465660` | `0xE465C77` | Explicit post-process writer |
| 5 | UNKNOWN | M504550 `0xE460BE0` | `0xE462D51` | Likely stack-local, not proven request slot |
| 6 | UNKNOWN | M504576 `0xE468AC0` | `0xE46AB2A` | Writes a pointer, likely different object family |

## Recommended V4P entry

- **Primary:** M508236 `OnTaskBegin` `0xB3DC5B0`, instruction `0xB3DC80C`
  - ProcessStoredDamage accumulator path.
- **Alternates:** M507296 `0xC30D850`, M504557 `0xE464D20`, M504598 `0xE465660`.
- **Minimal unresolved contract:** For DamageByAttackProperty, find the actual
  `+0x2D8` initialization before M507308; trace the object allocated at
  `0xC30EC14` (type token `0x962F8E0`).

## Shortest upstream generated-executor path

- ProcessStoredDamage:
  `M508236 OnTaskBegin -> accumulate request[+0x2D8] -> M508237 -> M507308`
- DamageByAttackProperty:
  `M507296 OnTaskBegin -> materialize request (0xC30EC14) -> M507304 -> M507308`
  - Direct `+0x2D8` write not yet found in this chain.

## Remaining ambiguity

- No direct `+0x2D8` writer found inside M507296/M507304/M507308 for
  DamageByAttackProperty; the request may be populated before OnTaskBegin or
  via an indirect helper.
- M504550/M504500 writes are on stack frames and not proven to target the
  request object.
- M504576 writes a pointer into `+0x2D8` and is likely a different object
  family.
