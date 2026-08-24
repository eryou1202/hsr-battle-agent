# HealHP Polymorphic Registry Entry 26

`STATUS = HEALHP_REGISTRY_ENTRY_26_PROOF`

This is a registry-entry recovery proof. It does **not** recover gameplay
semantics or implement Sandbox runtime.

Artifact: `data/raw/4.4.54/healhp_polymorphic_registry_entry_26.json`

---

## HealHP methods 124664-124666 identities

| Method | Name | Native RVA | Role |
| --- | --- | --- | --- |
| 124664 | `.ctor` | `0x1D0EBD50` | CONSTRUCTOR |
| 124665 | `OJNNBEJLDIJ` | `0x1D0EBBD0` | SERIALIZER_IMPL_OR_INIT |
| 124666 | `MGMEGEDLMAK` | `0x1D0EBEB0` | DESERIALIZER_IMPL |

## HealHP field map summary

Fields `97106`–`97116`:

`TargetType`, `HealerTargetType`, `AliveOnly`, `FormulaType`, `HealPercentage`,
`SPHitRatio`, `ModifyValue`, `IsHealRallyHP`, `ScreenSpaceFloatMsg`,
`DisplayData`, `PerformanceDelay`.

## Polymorphic dispatcher identity

- Factory thunk table: `0x49392E0`
- HealHP thunk: `0x1CC131D0`
- Table index: `7`
- HealHP thunk behavior:
  - Alloc type token `0x961AA08`
  - Calls `M124665 OJNNBEJLDIJ` `0x1D0EBBD0`
  - Calls `M124666 MGMEGEDLMAK` `0x1D0EBEB0`

## Exact 4.4.54 serialized selector / code

- **Selector value: `7`**
- Encoding: `ULEB/VLQ unsigned varint`
- Encoded bytes: `0x07`

## Selector encoding width

- Variable-length unsigned varint; `7` encodes as a single byte `0x07`.

## Selector -> HealHP proof

```text
serialized selector 7
→ factory thunk table 0x49392E0 index 7
→ thunk 0x1CC131D0
→ alloc type token 0x961AA08
→ M124665 OJNNBEJLDIJ 0x1D0EBBD0
→ M124666 MGMEGEDLMAK 0x1D0EBEB0
→ RPG.GameCore.HealHP type_index 22352
```

## Natasha HealHP node decoded?

- **No.**
- The bounded `Avatar_Natasha_00_Skill02_Phase02` record does not contain a
  standalone type_code `7` action node that parses as `heal_hp` in this
  window.
- The HealHP config may be reached through an outer table/index or another
  phase.

## HealHP populated field bitmap

- Not decoded from this record.

## Target config decoded?

- No.

## Amount inputs structurally decoded?

- No.

## Remaining single blocker

- `NATASHA_RECORD_HEALHP_NODE_INDIRECTION_OR_OTHER_PHASE`

## Status

- `HEALHP_REGISTRY_ENTRY_26_PROOF`
