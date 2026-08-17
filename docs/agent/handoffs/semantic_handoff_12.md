# Semantic Handoff 12 - DirectDamageHP HP Transition

`CAPABILITY_STATUS = COMPLETED_SCOPED_DIRECT_DAMAGE_HP_TRANSITION`

This contract closes the HP-state transition for the proven caller shape:

```text
SetHP negative delta
  -> DirectChangeHP M506500(mode=1)
  -> DirectDamageHP M506499(damage_kind=100, mode=0)
  -> persistent CurrentHP source slot 0
```

It is an HP-transition semantic contract. It is **not** a damage formula,
DamageRequest, hit, event, or NegativeHP-general contract. Modes 4/5/6 of
DirectDamageHP remain UNKNOWN.

## Primitive identities

| Primitive | Method / RVA | Evidence |
| --- | --- | --- |
| DirectDamageHP | M506499, `0xE732180`, len `0xF86`, SHA-256 `7f712493e35452e66166f1bcca4c51f2b8b3eecf5f65df54c1a85c00526e887a` | CONFIRMED |
| TryGetLockHP (intercept helper) | M506532, `0xE7333E0`, len `0x38B`, SHA-256 `8fbd0e438355b720eb98c765e4703a6168addb7e9c183830f0a21832d60bc86d` | CONFIRMED |
| CurrentHP source-slot updater | unregistered `0x1957559D0`, len `0x6D`, SHA-256 `1a5105a81b2a52842ed0a55399d4cf288956750914ade1b912c8904e38db5843` | CONFIRMED (Handoff 10) |
| `fp_add` | `0x19D65EF80` | CONFIRMED |
| `fp_mul` | `0x19D661A00` | CONFIRMED |
| `fp_sub` | `0x19D661B60` | CONFIRMED |
| `_AfterPropertyChanged` boundary | M506625, `0xE72EFC0` | CONFIRMED identity; semantics NOT recovered here |

All identities are exact native-machine-code facts, not name-only guesses.

## Exact native input/output mapping for the proven caller shape

Windows x64 register/stack mapping of M506499:

| Native slot | Value | Status |
| --- | --- | --- |
| rcx | `TurnBasedAbilityComponent` component | CONFIRMED |
| rdx | HP delta `D` (negative for the proven path) | CONFIRMED |
| r8d | `damage_kind` = `100` | CONFIRMED from M506500 call |
| r9 | context pointer | CONFIRMED |
| stack arg 5 | pointer to output applied-delta slot | CONFIRMED |
| stack arg 6 | pointer to input record `{value@+0, flag_byte@+8}` | CONFIRMED |
| stack arg 7 | `mode` = `0` | CONFIRMED |

`damage_kind` is consumed only by `TryGetLockHP` in this mode-0 path.
`mode=0` takes the default candidate path; modes 4/5/6 branch earlier and
remain UNKNOWN.

Outputs:

- `arg5` is written `0` at entry.
- Ordinary no-NegativeHP path: `arg5` is overwritten with the applied
  CurrentHP delta `new_current - old_current` (CONFIRMED).
- NegativeHP property path (normal finite values): `arg5` is overwritten
  with `-D` (CONFIRMED).
- Persistent writes are listed below.

## Intercept decision at 0xE7333E0 - CONFIRMED

`TryGetLockHP(component, damage_kind, out lock_value, out action_list)`
is the intercept at `0xE7333E0`. The call at `0xE732317` passes
`damage_kind`; `test al,al; je 0xE7327B4` makes `false` the ordinary
no-interception side and `true` the lock-HP interception side.

Normal finite FixPoint semantics (special NaN/Infinity encoding branches are
NOT part of this contract):

```text
list = component[+0x50]
if list is null: native throw
if list.count == 0: lock_value = 0; return false

lock_value = SENTINEL
  # global 0x95B1E00, initialized by RPG.GameCore.FixPoint..cctor to
  # raw 0xA2DE246004000001; semantic name not claimed.
best = -1
for i from list.count - 1 down to 0:
    record = list.items[i]           # stride 0x18
    kind   = record[+0x28]           # int32
    value  = record[+0x30]           # FixPoint
    action = record[+0x20]           # pointer, appended to action_list
    if kind < damage_kind:
        continue                     # scan lower index
    if lock_value == SENTINEL:
        lock_value = value           # first qualifying record accepted
        best = i
    elif lock_value == value:        # normal fp equality
        best = i                     # keep lock_value, prefer lower index
    else:
        break                        # stop; use current best
if best < 0:
    lock_value = 0
    return false                     # action_list is NOT cleared on false

action_list.Clear()
for i from best .. list.count - 1:
    action_list.Append(list.items[i][+0x20])
return true
```

Control-flow reconciliation:

- `0xE73231C` tests the helper result.
- `false` -> `0xE7327B4`: no lock-HP interception; computes the DirtyHP-ratio
  bound and reaches the stable source-0 write at `0xE732C6B`.
- `true` -> `0xE732324` lock-HP clamp. If the candidate does not violate the
  lock threshold, it converges into the same `0xE7327B4` bound logic. If it
  does violate the lock threshold, it records the lock overflow, uses MaxHP
  as the temporary upper bound, and still converges to `0xE732C6B`.
- `0xE732C6B` is the single persistent CurrentHP source-index-0 update for
  every normal path.

## DirectDamageHP mode=0 transition - CONFIRMED for normal finite values

Definitions:

```text
O = CurrentHP entry[+0x78] materialized value (property 10)
D = input delta (negative on the proven path)
C = fp_add(O, D)                    # mode 0 default candidate
M = MaxHP (property 1 via M506504)
R = DirtyHPRatio entry[+0x78]       # property 7; DirtyHPDelta is NOT read
L = TryGetLockHP lock_value         # 0 and false when no matching record
K = FixPoint(2)                     # initialized value; lifetime immutability UNKNOWN
Z = FixPoint(0)                     # global 0x95B1DE0, FixPoint..cctor initialized
B = fp_sub(M, fp_mul(M, R))         # no-lock upper bound
```

Interception side selection (normal finite values, `M > 0`):

```text
if TryGetLockHP(component, damage_kind, &L, &actions) == false:
    X = C
    bound = B
    P = 0
    flag = 0
else:
    T = fp_min(O, fp_max(fp_min(K, M), fp_mul(M, L)))
    if C < T:
        X = T
        bound = M                    # MaxHP temporary bound
        P = fp_sub(T, C)             # lock overflow, > 0
        flag = 1
    else:
        X = C
        bound = B
        P = 0
        flag = 0
```

Shared clamp and persistent CurrentHP write:

```text
if X < bound:
    Y = X
elif X >= Z and M > Z:
    Y = bound if bound > Z else Z
else:
    Y = fp_min(X, M)                 # decoded normal fallthrough

if Y <= 0:
    maybe_submit_negative_hp_record(component)   # bounded policy below

update_property_source_slot(CurrentHP_entry, source_index=0, Y)
```

- The source-0 write is CONFIRMED at `0xE732C6B -> 0x1957559D0`.
- The update rebuilds materialized `entry[+0x78]` through the existing
  materialization runtime.
- On the ordinary no-lock path, `L = 0` and `P = 0`. With
  `0 < C < B` this reduces exactly to the previously published simple-range
  contract: `Y = C`.

## NegativeHP policy - bounded, exact for this path

Pre-write record path (`maybe_submit_negative_hp_record`, entry `0xE732BDF`):

- Reached when `Y <= 0`.
- CONFIRMED gate: `component[+0x10] != null`,
  `[component[+0x10] + 0xD4] == 1`, and
  `[[component[+0x10] + 0x80] + 0xD0] != null`.
- CONFIRMED action: allocates an object through `0x18B42A0C0`, stores the
  `+0xD0` pointer at object `+0x10`, stores word `8` at object `+0x18`, then
  calls `0x18DA9CFF0(object, 1)`.
- This call is a **recorded boundary**. Its consumer semantics are NOT
  followed and do NOT block the CurrentHP source-0 write.
- If any gate fails, the record submit is skipped and the CurrentHP write
  still happens with `Y <= 0`.

Post-write NegativeHP property path (entry `0xE732CCC`):

- CONFIRMED gate: feature byte at `0x9570924 == 0`,
  `component[+0x20] != null`, `[component[+0x20] + 0x18] > 0`, and
  `P > 0`.
- `P > 0` only occurs when `TryGetLockHP` returned true and `C < T`.
  Therefore, on the ordinary no-lock path (`P == 0`) the
  **AbilityProperty NegativeHP entry is neither read nor written**.
- When the gate passes:
  - reads `N_old = NegativeHP entry[+0x78]` (property 9, table slot `+0x68`);
  - writes `N_new = fp_add(N_old, P)` to NegativeHP source slot 0 through
    `0x1957559D0`;
  - computes `applied = fp_sub(new_current, O)`;
  - if `applied != 0`, calls `_AfterPropertyChanged(component, 10, ...)`
    (M506625, boundary);
  - calls `_AfterPropertyChanged(component, 9, ...)` (M506625, boundary);
  - normal finite output: `*arg5 = -D`.
- When the gate does not pass:
  - `*arg5 = applied`;
  - calls `_AfterPropertyChanged(component, 10, ...)` (M506625, boundary).

When `flag == 1` (lock overflow path), the recovered action list is submitted
through the object/callee chain at `0xE7331A0`; that edge is recorded and not
followed. Every normal path ends with the tail call at `0xE733243 ->
0x18B429F50`; that edge is recorded and not followed.

## Persistent reads/writes

Persistent reads (property table `component[+0xA0]`, validated):

| Item | Property ID / slot | Status |
| --- | --- | --- |
| CurrentHP materialized `O` | 10, table `+0x70` | CONFIRMED |
| MaxHP materialized `M` | 1, via M506504 | CONFIRMED |
| DirtyHPRatio materialized `R` | 7, table `+0x58` | CONFIRMED no-lock path only |
| Lock-HP list `component[+0x50]` | not an AbilityProperty | CONFIRMED |
| NegativeHP materialized `N_old` | 9, table `+0x68` | CONFIRMED, only lock-overflow path |

Persistent writes:

| Item | Source index | Value | Condition |
| --- | --- | --- | --- |
| CurrentHP | 0 | `Y` | always on every normal path |
| NegativeHP | 0 | `fp_add(N_old, P)` | only `P > 0` gate above |

No DirtyHPDelta (property 6) read occurs inside M506499 mode-0 path.

## FixedPoint operations used

```text
C       = fp_add(O, D)
lockcap = fp_mul(M, L)                     # true intercept side only
T       = fp_min(O, fp_max(fp_min(K, M), lockcap))
B       = fp_sub(M, fp_mul(M, R))          # no-lock side only
P       = fp_sub(T, C)                     # lock overflow only
applied = fp_sub(new_current, O)
N_new   = fp_add(N_old, P)                 # NegativeHP path only
```

Inline fixed-point compares/min/max are compiled directly; `K = FixPoint(2)`
is only used on the true intercept side, and its lifetime immutability stays
UNKNOWN.

## ABI-independent pseudocode

```text
direct_damage_hp(component, D, damage_kind, context, out_applied, in_record, mode):
    assert mode == 0                     # scoped path; modes 4/5/6 UNKNOWN
    out_applied = 0

    current_entry = property_entry(component, 10)
    O = current_entry.materialized
    C = fp_add(O, D)                     # D < 0 for SetHP lowering

    M = get_property(component, 1)
    lock_hit = try_get_lock_hp(component, damage_kind, &L, &actions)

    if lock_hit and M > 0:
        T = fp_min(O, fp_max(fp_min(FixPoint(2), M), fp_mul(M, L)))
        if C < T:
            X = T
            bound = M
            P = fp_sub(T, C)
            flag = 1
        else:
            X = C
            R = get_property(component, 7)
            bound = fp_sub(M, fp_mul(M, R))
            P = 0
            flag = 0
    else:
        X = C
        R = get_property(component, 7)
        bound = fp_sub(M, fp_mul(M, R))
        P = 0
        flag = 0

    if X < bound:
        Y = X
    elif X >= 0 and M > 0:
        Y = bound if bound > 0 else 0
    else:
        Y = fp_min(X, M)

    if Y <= 0:
        maybe_submit_negative_hp_record(component)   # boundary; does not change Y

    update_property_source_slot(current_entry, 0, Y)
    new_current = current_entry.materialized
    applied = fp_sub(new_current, O)

    if feature_byte(0x9570924) == 0 and component[+0x20] is nonempty and P > 0:
        neg_entry = property_entry(component, 9)
        N_old = neg_entry.materialized
        update_property_source_slot(neg_entry, 0, fp_add(N_old, P))
        out_applied = -D
        if applied != 0:
            after_property_changed(component, 10, ...)   # boundary
        after_property_changed(component, 9, ...)        # boundary
    else:
        out_applied = applied
        after_property_changed(component, 10, ...)       # boundary

    if flag:
        submit_lock_action_list(actions)                # boundary
    native_tail(actions_or_placeholder)                 # boundary, not followed

try_get_lock_hp(component, damage_kind, &L, &actions):
    list = component[+0x50]
    if list is null: native_throw()
    if list.count == 0:
        L = 0
        return false
    L = SENTINEL
    best = -1
    for i from list.count - 1 down to 0:
        rec = list.items[i]
        if rec.kind < damage_kind: continue
        if L == SENTINEL:
            L = rec.value
            best = i
        elif L == rec.value:
            best = i
        else:
            break
    if best < 0:
        L = 0
        return false
    actions.Clear()
    for i from best .. list.count - 1:
        actions.Append(list.items[i].action_ptr)
    return true
```

## Dependencies

- `GENERIC_PROPERTY_SOURCE_SLOT_MATERIALIZATION_10_PROOF`
- `GENERIC_PROPERTY_MUTATION_SOURCE0_11_PROOF` (fixed-point ops, source-0 model)
- Handoff 12 partial evidence (SetHP -> DirectChangeHP -> DirectDamageHP)
- CurrentHP bound `K_INITIALIZED_VALUE = FixPoint(2)` evidence
- `TryGetLockHP` M506532 identity and bounded disassembly

## UNKNOWN / MUST NOT IMPLEMENT

- DirectDamageHP modes 4, 5, 6.
- Special FixPoint NaN/Infinity encodings inside the inlined compare blocks.
- `component[+0x50]` list record/action type identities beyond offsets
  (`+0x20`, `+0x28`, `+0x30`); the `_LockHPList` field-name link is
  SUPPORTED, not field-offset-proven.
- `_AfterPropertyChanged` consumer behavior, the `0x18DA9CFF0` submit
  consumer, and the `0x18B429F50` tail call.
- Full DirtyHP policy: M506499 mode-0 uses only DirtyHPRatio; DirtyHPDelta
  remains part of M506511 `GetDirtyHP`, not this transition.
- General NegativeHP consumers beyond this path.
- `K` lifetime immutability: initialized value is CONFIRMED; absolute
  immutability remains UNKNOWN.

## Exact next native entry points

1. DirectDamageHP modes 4/5/6: `0xE732235`, `0xE732288`, `0xE7322A6`.
2. Post-transition submit consumers: `0x18DA9CFF0`, `0x18B429F50`.
3. `_AfterPropertyChanged` dispatcher M506625 only if event semantics are
   promoted to a new task.
