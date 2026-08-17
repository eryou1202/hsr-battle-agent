# Semantic Handoff 12 — Partial

`CAPABILITY_STATUS = PARTIAL`

This is a checkpoint only. It does **not** publish a generic HP clamp, DirtyHP,
NegativeHP, damage-intercept, event, or damage-resolution contract.

## Proven SetHP config/runtime chain

- Config runtime type: `RPG.GameCore.SetHP`, type index `22351`.
- Declared config fields: `TargetType`, `AttackType`, `DamageType`,
  `ModifyRatio`, `ModifyValue`, `ClearNegativeHP`, `ShowText`, `DisplayData`,
  `SourceType`.
- Serializer M124663 and generated executor constructor M508869 use the same
  config type reference `431384`. This confirms the config/runtime pairing;
  a separate factory edge has not been recovered.
- Generated executor: `ONECLKJPNJP`, type index `55652`.

| Primitive | Native identity | Confirmed subset |
| --- | --- | --- |
| Construct SetHP task | M508869, `0xC03AC20`, len `0x4F`, SHA-256 `64419fd610627c8b2c4d741a201b5cbc303907360ebc904fbb276a682ef6d73e` | Stores task context at `+0x18`, SetHP config at `+0x20`, marker `0x7777` at `+0x10`. |
| Execute SetHP task | M508871 `OnTaskBegin`, `0xC03AC70`, len `0x622`, SHA-256 `0477388bc0ec64253a57cdfa9ce73b19035451cad603e6e97686513fe1e9f2a9` | Reads selector from config `+0x18`; evaluates refs at `+0x28` and `+0x30`; resolves targets; calls M506500 per target with `mode=1`; writes completion marker `0x9999`. |

Native dataflow supports the following field mapping (metadata supplies the
field names): `TargetType -> +0x18`, `ModifyRatio -> +0x28`,
`ModifyValue -> +0x30`, `ClearNegativeHP -> +0x38`.

For the general arithmetic path, M508871 computes:

```text
target_value = ModifyValue + fp_mul(GetProperty(target, MaxHP /* 1 */), ModifyRatio)
```

`ClearNegativeHP` selects an additional native branch. Its policy is UNKNOWN.

## Proven HP primitives

| Primitive | Native identity | Reads | Writes / result |
| --- | --- | --- | --- |
| Get materialized property | M506504 `GetProperty`, `0xE72C6F0`, len `0x171`, SHA-256 `bcfc71bf3e4a4351e4062c12ad3a5d76a6292bb2779541e2b46cec218ccfa20c` | component `+0x2B0`, property table `+0xA0`, entry `+0x78` | For ordinary IDs other than native-special IDs 18/23, returns `entry[+0x78]`. |
| Change HP | M506500 `DirectChangeHP`, `0xE733830`, len `0x7FE`, SHA-256 `39c1918c671212e07f6351d861661a874dbe5fb9c5a27f5208b5890de6ec75c1` | CurrentHP entry/value | `mode=1` computes `input_value - CurrentHP`; `mode=2` uses `input_value` as delta. Negative result enters M506499. Other mode values take native error path. |
| Direct HP damage path | M506499 `DirectDamageHP`, `0xE732180`, len `0xF86`, SHA-256 `7f712493e35452e66166f1bcca4c51f2b8b3eecf5f65df54c1a85c00526e887a` | CurrentHP, MaxHP, DirtyHPRatio; in-method intercept decision | Default mode forms `CurrentHP + damage_delta`. The ordinary branch at `0xE732C6B` calls stable source-slot update at `0xE732C73`. |
| CurrentHP source update | unregistered helper `0x1957559D0`, len `0x6D`, SHA-256 `1a5105a81b2a52842ed0a55399d4cf288956750914ade1b912c8904e38db5843` | selected entry, source index, candidate | Updates stable source value, then rebuilds materialized `entry[+0x78]`; reused from Handoff 10. |

M506500 calls M506499 with `damage_kind=100` and `mode=0` only for its
negative-delta path. This is a native call shape, not a recovered damage
formula or request contract.

## AbilityProperty identities and mutation functions

- `AbilityProperty[9] = NegativeHP` and `AbilityProperty[10] = CurrentHP`.
  Both identities have enum metadata support and direct native table accesses:
  `+0x68` for index 9 and `+0x70` for index 10.
- `CurrentHP` is native-special in M506503; do not route it through Handoff
  11's generic untransformed mutation contract.
- Apply-property-function helper: `0xE4410D0`, len `0x1C0`, SHA-256
  `aa8775d71b41bb6b9112630c4cba3892cdf6db8a41fbaef9ff604e5f1b337dc3`.
  Function IDs are confirmed: `1=Set`, `2=Add`, `3=Mul`, `4=Min`, `5=Max`.
  Out-of-range IDs take the helper's Set fallthrough.
- M506503 `ModifyProperty`: `0xE72DCE0`, len `0x8E6`, SHA-256
  `dc83a97417b6fd89d9a9c640b7caf916c5d9e1de6bfdd98d6237060c63fdacd9`.

## MaxHP / DirtyHP branch evidence

- In the CurrentHP-specific M506503 branch at `0xE72E162`, native code reads
  MaxHP (property 1), calls M506511 `GetDirtyHP`, computes
  `MaxHP - DirtyHP`, and compares the proposed candidate against that bound.
- M506511 `GetDirtyHP`: `0xE734050`, len `0xB0`, SHA-256
  `6afb98d5032558a2e893dbf600f979f5d58abceffdd3dfee6679e9dad2a5cc10`.
  It reads MaxHP (1), DirtyHPDelta (6), and DirtyHPRatio (7), with proven
  arithmetic:

```text
DirtyHP = fp_add(fp_mul(MaxHP, DirtyHPRatio), DirtyHPDelta)
```

- If the CurrentHP candidate is below the checked bound, M506503 reaches the
  common source-0 write tail. The equal/over-bound policy is UNKNOWN.

## CurrentHP special bound branch — PARTIAL

`SUBSECTION_STATUS = PARTIAL_SYMBOLIC_CONTROL_FLOW_CONFIRMED`

Definitions for the post-transform candidate at this point in M506503:

```text
C = candidate after 0x19CAF14A0
B = fp_sub(MaxHP, GetDirtyHP(component))
K = runtime global loaded from data RVA 0x95B1E80
```

The single global `K` is loaded at `0xE72E1B9`, `0xE72E1D0`, and
`0xE72E1E7`. Its runtime semantic value/initializer is not recovered here.
It must not be named or assumed to be zero.

| Helper | Native identity | Exact operation |
| --- | --- | --- |
| `fp_ge` | `0x19D660C50`, len `0x90`, SHA-256 `927ce232af90a197938433fff3c904fa43ac27ff7bc6874f20d7e6e27b4c9573` | `left >= right` |
| `fp_gt` | `0x19D6645B0`, len `0x90`, SHA-256 `93587ee19a0b623341ca4c341c52676f312c7b3225e84f6463473bf2880c58c0` | `left > right` |
| `fp_max` | `0x19D669330`, len `0xB9`, SHA-256 `83dbebb797696eb2c760601e0c0306f0dcd6358e1e7fab45dfd1e8b412600213` | `max(left, right)` |
| `fp_min` | `0x19D6693F0`, len `0xB9`, SHA-256 `e4cb86eeddaf038f03b8daca6dbf17005aedf85549d466728f82a8fb9e405e61` | `min(left, right)` |

Confirmed branch results:

| Candidate relation to B | Native result supplied to common tail | Source-0 write | Other property access |
| --- | --- | --- | --- |
| `C < B` | `C` | Yes, CurrentHP selected entry through `0xE72E8F9 -> 0x1957559D0(entry, 0, C)` | Reads MaxHP and GetDirtyHP inputs only; no NegativeHP access in this branch. |
| `C == B` | Enters the `C >= B` path. If `C >= K && MaxHP > K`, result is `max(B, K)`; otherwise `min(B, MaxHP)`. | Yes, same source-0 call. | Same reads; no second property write before the common tail. |
| `C > B` | If `C >= K && MaxHP > K`, result is `max(B, K)`; otherwise `min(C, MaxHP)`. | Yes, same source-0 call. | Same reads; no second property write before the common tail. |

ABI-independent pseudocode for the exact proven subset:

```text
candidate = post_transform(apply_modify_function(...))
max_hp = property[MaxHP /* 1 */].materialized
dirty_hp = fp_add(fp_mul(max_hp, property[DirtyHPRatio /* 7 */]),
                  property[DirtyHPDelta /* 6 */])
bound = fp_sub(max_hp, dirty_hp)

if candidate < bound:
    result = candidate
elif candidate >= K and max_hp > K:
    result = fp_max(bound, K)
else:
    result = fp_min(candidate, max_hp)

update_property_source_slot(current_hp_entry, source_index=0, source_value=result)
```

All normal relations above reach the common tail and issue the source-index-0
update; no normal no-op/rejection exists in this bounded control-flow slice.
Malformed component/property-table guards instead enter native error paths.
After the update, M506503 calls its existing post-change bridge; that edge is
recorded but not followed.

This is not yet a coding-ready CurrentHP-bound primitive: the value and
initialization contract of `K` are UNKNOWN. In particular, do **not** simplify
this code to a conventional `clamp(C, 0, MaxHP - DirtyHP)`.

## Confirmed subset pseudocode

```text
execute_set_hp(task):
    ratio = evaluate_dynamic(task.config.ModifyRatio, task.context)
    value = evaluate_dynamic(task.config.ModifyValue, task.context)
    for target in select_targets(task.config.TargetType, task.context):
        target_value = fp_add(value, fp_mul(get_property(target, 1), ratio))
        direct_change_hp(target, mode=1, input_value=target_value, context)
    task.marker = 0x9999

direct_change_hp(component, mode, input_value, context):
    current = get_property(component, 10)
    if mode == 1:
        delta = fp_sub(input_value, current)
    elif mode == 2:
        delta = input_value
    else:
        native_error()
    if delta < 0:
        direct_damage_hp(component, delta, damage_kind=100, context, mode=0)
    else:
        native_positive_or_special_path()

direct_damage_hp_ordinary_subset(component, delta):
    old = get_property(component, 10)
    candidate = fp_add(old, delta)
    # only after the native intercept/bound policy has selected the ordinary branch
    update_property_source_slot(current_hp_entry, source_index=0, candidate)
```

The final source-slot line is CONFIRMED only as the concrete ordinary branch
at `0xE732C6B -> 0xE732C73`; it is not an unconditional HP semantic.

## Persistent State Requirements

- Reuse Handoff 10 `entity_property_entries` and stable source slots.
- `CurrentHP` persists as property ID 10 and is written through source index 0
  on the scoped M506499 branch.
- Do not invent a separate HP field that bypasses PropertyEntry materialization.
- No independent `NegativeHP` state contract is ready to implement.

## Existing primitives to reuse

- DynamicValue, Target selector, fixed-point add/subtract/multiply.
- Handoff 10 source allocation/update/materialization.
- Handoff 11 mutation function helper only for its ordinary non-special IDs;
  **not** for CurrentHP.

## UNKNOWN / MUST NOT IMPLEMENT

- HP clamp, full CurrentHP range policy, DirtyHP policy, or NegativeHP policy.
- DirectDamageHP in-method interceptor around `0xE7333E0` and its true/false
  semantic meaning.
- DirectDamageHP modes 4, 5, 6; all M506500 positive-delta paths.
- `_AfterPropertyChanged` event/listener behavior after HP writes.
- DamageRequest, hit resolution, damage formula, or UI/presentation fields.
- `ClearNegativeHP`, `AttackType`, `DamageType`, `ShowText`, `DisplayData`,
  `SourceType` semantics outside the reads listed above.

## Exact next native entry points

1. Resolve the initializer/semantic identity of CurrentHP branch global data
   `0x95B1E80`, loaded at `0xE72E1B9`, `0xE72E1D0`, and `0xE72E1E7`.
2. Only after that closes `K`, resume M506499 intercept decision `0xE7333E0`
   and its `0xE73231C -> 0xE7327B4` split; it remains out of scope here.
