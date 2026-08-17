# Semantic Handoff 14 - Damage Evaluator Q

`CAPABILITY_STATUS = CODING_READY_WITH_UNKNOWN_GLOBAL_THRESHOLD`

This contract closes the FixPoint value `Q` returned by M530155
`GOCKCOMLFEO`, the evaluator consumed by Handoff 13 as:

```text
S0 = fp_mul(MaxHP, Q)
```

It does not recover a gameplay stat name. `Q` is natively proven to be a
**selected ratio**, not a damage formula.

## Identity

| Field | Value |
| --- | --- |
| Method index | 530155 |
| Method name | `GOCKCOMLFEO` |
| Declaring type index | 57813 (`JCKKNDFIFLM`) |
| PE RVA | `0x154B9420` |
| VA | `0x1954B9420` |
| Body length | `0x1F8` |
| Body SHA-256 | `630349815c23a2180b414f4df59045a2074245907a9a24fd139b3504384693f6` |

## Inputs

`rcx` = evaluator object `e`. Only three fields are read on normal paths:

| Offset | Role | Status |
| --- | --- | --- |
| `e[+0x10]` | optional component-resolver key | CONFIRMED |
| `e[+0x18]` | fallback numerator FixPoint | CONFIRMED |
| `e[+0x20]` | fallback denominator FixPoint | CONFIRMED |

No other normal input exists. Initialization/patch branches read feature bytes
`0x9576579`, `0x957657A`, `0x957657B`; those paths are recorded boundaries.

## Normal algorithm - CONFIRMED

```text
U = load_global(0x95B1E18)            # denominator threshold; concrete value UNKNOWN

if feature(0x957657B):                # patch path, NOT normal
    return M723335(get_patch(), e)    # boundary, not followed

if e[+0x10] != null:
    component = resolve(e[+0x10])     # 0x18B429D40
    D = get_property(component, 1)    # MaxHP (sealed identity)
    if feature(0x957657A):
        D = M723335(get_patch(), e)   # patched denominator, boundary
else:
    D = e[+0x20]

if D > U:                             # ordinary finite FixPoint compare
    if e[+0x10] != null:
        component = resolve(e[+0x10])
        N = get_property(component, 10)   # CurrentHP (sealed identity)
        if feature(0x9576579):
            N = M723335(get_patch(), e)   # patched numerator, boundary
    else:
        N = e[+0x18]
    Q = fixpoint_divide(N, D)         # tail 0x1D65FD90, normal finite inputs
else:
    Q = FixPoint(0)                   # global 0x95B1DE0, sealed identity

return Q
```

Branch conditions are strict:

- `D > U` strictly selects the ratio path.
- `D == U` selects `Q = FixPoint(0)` (`0x154B9582 -> 0x154B9586`).
- `D < U` selects `Q = FixPoint(0)`.

For ordinary finite FixPoint operands the inlined blocks at `0x154B9499`,
`0x154B94B0`, `0x154B953D`, `0x154B9574`, `0x154B9582` reduce exactly to
the `D > U` test. The special-encoding (bit-0 set) variants at
`0x154B94B0`/`0x154B953D`/`0x154B9574` perform the same selection on
encoding-normalized forms; their concrete special-value semantics remain
UNKNOWN.

## Property 1 / property 10 usage

- Property 1 is used only as the **denominator** `D` when `e[+0x10]` is
  non-null. Existing sealed identity: property 1 = MaxHP.
- Property 10 is read only after `D > U` and only when `e[+0x10]` is
  non-null; it is the **numerator** `N`. Existing sealed identity:
  property 10 = CurrentHP.
- Consequence (CONFIRMED by composition with Handoff 13): on the component
  path with `D > U`, `Q = CurrentHP / MaxHP`, so
  `S0 = fp_mul(MaxHP, Q) = CurrentHP` and the M504579 delta is zero. When
  `D <= U`, `Q = 0`, so `S0 = 0` and M504579 computes a negative delta.

## Tail 0x1D65FD90 - CONFIRMED bounded role

| Field | Value |
| --- | --- |
| RVA | `0x1D65FD90` |
| Body length | `0x28E` |
| Body SHA-256 | `598c57671d7b27de3f821c1359b5fff2b436fb2389d2197228d2731d5354f5f2` |
| Inputs | `rcx = numerator`, `rdx = denominator` |
| Output | FixPoint quotient `rcx / rdx` |

Evidence: the prologue treats `rdx` as the denominator
(`cmp r8, 1; jbe` rejects denominator <= 1), normalizes it, and runs a
long-division loop over `rcx` as the dividend. Overflow/special operands
transfer to `0x19D6640B0` or return sentinel globals; those edges are not
part of the normal-finite contract.

## Global roles

| Global | Role | Status |
| --- | --- | --- |
| `0x95B1E18` | denominator threshold `U`; ratio selected only when `D > U` | CONFIRMED role; concrete runtime value UNKNOWN |
| `0x95B1DE0` | FixPoint(0) return value | CONFIRMED (Handoff 12) |
| `0x96B72E8` | resolver type token for `0x18B429D40` | CONFIRMED usage; semantic identity not needed |
| `0x9576579/0x957657A/0x957657B` | patch-path feature bytes | CONFIRMED usage; patch behavior UNKNOWN |

Do not assign a concrete value to `0x95B1E18` from its disk qword. The
algorithm is complete with `U` as an explicit external semantic parameter.

## ABI-independent pseudocode

```text
evaluate_q(e):
    U = GLOBAL_0x95B1E18                # external semantic input, UNKNOWN value
    if PATCH_FLAG_B:
        return PATCH_TAIL(e)            # boundary
    if e.component_key != null:
        D = get_property(resolve(e.component_key), 1)   # MaxHP
        if PATCH_FLAG_A:
            D = PATCH_TAIL(e)           # boundary
    else:
        D = e.denominator_fixpoint       # e[+0x20]
    if D > U:
        if e.component_key != null:
            N = get_property(resolve(e.component_key), 10)  # CurrentHP
            if PATCH_FLAG_N:
                N = PATCH_TAIL(e)       # boundary
        else:
            N = e.numerator_fixpoint     # e[+0x18]
        return fixpoint_divide(N, D)
    return FixPoint(0)
```

## UNKNOWN

- Concrete runtime value of global `0x95B1E18`.
- Special FixPoint encoding comparisons and division overflow paths.
- M723335 `0x15B8BB50` patch/initialization return semantics.
- Whether `U` is intended as a max, guard, or sentinel; only its threshold
  role in `D > U` is proven.

## Exact next frontier

Only the concrete runtime initialization/meaning of global `0x95B1E18`, or
the patch helper M723335 if patch paths are ever needed. No large subsystem
is required.
