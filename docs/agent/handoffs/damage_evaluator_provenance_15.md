# Damage Evaluator Provenance 15

`STATUS = PREPROCESS / PROVENANCE`

This is **not** `semantic_handoff_15`. It records mechanical provenance for the
`JCKKNDFIFLM` evaluator consumed by M530155 / M504579.

Artifact: `data/raw/4.4.54/damage_evaluator_provenance_15.json`

---

## Field provenance

`JCKKNDFIFLM`, type index `57813`, has two declared normalized fields and nine
methods.

| Offset | Normalized field | Writer(s) | Source |
| --- | --- | --- | --- |
| `+0x10` | `<MainTarget>k__BackingField` | M530152 `set_MainTarget` (`0x154B9720`); M504579 direct write `0xE46D90B` | setter arg; `[[0x967A0C8+0x98]][0]` |
| `+0x18` | fallback numerator slot | M530156 (`0x154B7F29`); M530157 (`0x154B98F3`); M530158 (`0x154B99F7`) | constructor arg `rdx`; generated runtime value |
| `+0x20` | fallback denominator slot | M530156 (`0x154B7F2D`) | constructor arg `r8` |

No serializer/deserializer method was found in the normalized method set for
this type. M530156 is the closest initializer: it stores two FixPoint
arguments into `+0x18` and `+0x20`.

## M530155 instance origin (inside M504579)

1. M504579 obtains/materializes an evaluator object via
   `0xE46D8DC call 0x183C736B0` using type token global `0x967A0C8`.
2. It writes `[e+0x10] = [[0x967A0C8+0x98]][0]` at `0xE46D90B`.
3. It integrates that object with container `[r14+0x48]` through
   `0x1983C5DF0`.
4. The stored evaluator slot is `[r14+0x48][+0x10]`; M504579 loads it into
   `[rbp+0x6A8]` at `0xE46D949` and later calls M530155 with it.

This evaluator is shared across the target loop and does not change per target.

## Component identity test

- Evaluator component `A = resolve(e[+0x10])` with resolver `0x18B429D40`,
  token `0x96B72E8`.
- Target component `B = resolve(r13)` with the same resolver/token, where
  `r13` comes from target list `[r14+0x48][+0x28]`.

Because both use the same resolver/token, `A == B` exactly when
`e[+0x10] == r13`. `e[+0x10]` is set once from a global main-target slot, so:

- `SAME_COMPONENT_CONFIRMED` for iterations where current target is the main
  target.
- `DISTINCT_COMPONENT_CONFIRMED` for iterations where current target is not the
  main target.
- Overall result: **`MAY_ALIAS`**.

## Fallback value provenance

- `e[+0x18]` and `e[+0x20]` are initialized by M530156 from two FixPoint
  constructor arguments.
- M530157/M530158 can overwrite `e[+0x18]` with a generated runtime value when
  `e[+0x10] == null`.
- No serializer/config field mapping was found in the current normalized data.

## DamageByAttackProperty shapes

- `COMPONENT_RATIO_PATH`: available and observed as the normal M504579 native
  path because M504579 itself sets `e[+0x10]` from the global main-target slot.
- `LITERAL_RATIO_PATH`: structurally available through M530156 constructor
  fields, but no representative DesignData record was found in the current
  extracted set.
- Conclusion: **BOTH structurally possible; component-ratio is the observed
  normal path in M504579.**

## Remaining UNKNOWN

- Concrete source/lifetime of global `0x967A0C8` main-target slot.
- Indirect/virtual callers of M530156 that would prove literal-ratio evaluator
  construction in real configs.
- Whether the target list always contains the main target for representative
  DamageByAttackProperty records.

## Recommended next step

Resolve global `0x967A0C8` main-target provenance and locate indirect/virtual
callers of M530156. That will narrow `MAY_ALIAS` and confirm which evaluator
shape real DamageByAttackProperty configs use.
