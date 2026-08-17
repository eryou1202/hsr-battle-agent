# Damage Helper Preprocess 14

`STATUS = PREPROCESS_ONLY`

This is **not** `semantic_handoff_14`. It is a compact mechanical extraction for
the next V4P semantic pass. No gameplay semantics are assigned.

Machine-readable artifact:
`data/raw/4.4.54/damage_helper_preprocess_14.json`

---

## 1. M530155 `GOCKCOMLFEO` return-path summary

Identity (PE RVA / VA):

| Field | Value |
| --- | --- |
| Method index | 530155 |
| PE RVA | `0x154B9420` |
| VA (task spelling) | `0x1954B9420` |
| Body length | `0x1F8` |
| Body SHA-256 | `630349815c23a2180b414f4df59045a2074245907a9a24fd139b3504384693f6` |
| Declaring type index | 57813 |

Branches: `28` conditional/unconditional branch instructions in the extracted
body. Calls: `14` direct call sites. Globals referenced: `6`.

Return/transfer paths:

1. `0x154B95CB ret` — return value is loaded at `0x154B95BD` from global
   `0x95B1DE0`.
2. `0x154B9506 jmp 0x15B8BB50` — tail transfer after an alternate
   initialization path.
3. `0x154B95DA jmp 0x1D65FD90` — tail transfer into an unresolved
   fixed-point-like helper.

The main path reads:

- `[rbx+0x10]` or `[rbx+0x20]` (input object fields)
- global `0x95B1E18`
- global `0x96B72E8`
- calls `M506504 GetProperty` with property `1` and later property `0xA` (10)
- final return source is global `0x95B1DE0`

Inline fixed-point-like comparison blocks appear at `0x154B9499`,
`0x154B94B0`, `0x154B953D`, `0x154B9574`, and `0x154B9582`. These are
mechanical `sar 7` / `setg` / `cmov` patterns, not yet labeled.

## 2. M530155 exact unresolved decision points

- `0x154B9431` and `0x154B943E` — initialization-flag branches (globals
  `0x957657B`, `0x957657A`).
- `0x154B9499` / `0x154B94B0` / `0x154B953D` / `0x154B9574` / `0x154B9582` —
  selection between `0x95B1E18`-derived value, input property value, and
  `0x95B1DE0`.
- `0x154B9588` — flag branch controlling whether property `10` is read before
  the tail transfer at `0x154B95DA`.
- `0x154B95DA` — tail call into `0x1D65FD90`; exact semantics unresolved.

## 3. Global `0x95B1E18` writer result

Run with `global_static_writer_classifier.py --data-rva 0x95B1E18`:

- Storage: `.data`, writable, file offset `0x95AFC18`
- Disk raw qword: `0xCC0A1BA48763671C`
- Reads: `59`
- Direct writes: `0`
- Indirect writer candidates: `0`
- Static-constructor readers: `2`
  - `RPG.GameCore.FixVec2..cctor` M68317 `0x1D66D2E0`
  - `RPG.GameCore.FixVec3..cctor` M68378 `0x1D670BE0`
- Classification: `UNKNOWN`
- Initializer candidate: none found
- Mechanical note: disk image only; no direct writer recovered; no semantic
  meaning assigned.

Optional fallback global `0x95C1CC0`:

- Direct writes: `1`
- Writer: `FJNAOAEPNJF..cctor` M530122, method RVA `0x154B96E0`, direct store
  `0x154B96FD`
- Disk raw qword: `0x1C95E9C65A78289C`
- Classification: `DIRECT_RUNTIME_WRITTEN_GLOBAL`, `STATIC_FIELD_BACKING`

## 4. M504598 `_MortallyWondedProcess` three output-store formulas/dataflow

Identity:

| Field | Value |
| --- | --- |
| Method index | 504598 |
| RVA | `0xE465660` |
| Body length | `0x7EC` |
| Body SHA-256 | `6fac82d4e55bcdad1366184fdd1a133fce5b7f511e012d75c3226be2943efe0a` |

All three known stores write through `[r14]`, where `r14` is the second
argument (`rdx`) from the prologue — the damage FixPoint output pointer used by
Handoff 13.

### Store 1 — `0xE465931`

```text
[r14] = rax
rax = cmovg(rax, rbx) based on ecx
ecx = inline fixed-point compare result from rax/rbx inputs
```

Preceding window: `0xE4658A2` – `0xE465931`. Source operands: `rax`, `rbx`.
The compare block is the same `sar 7` / `setg` / `cmov` family.

### Store 2 — `0xE465A3F`

```text
[r14] = rax
rax = cmovg(rax, rsi) based on ecx
ecx = inline fixed-point compare result from rax/rsi inputs
```

Preceding window: `0xE4659D0` – `0xE465A3F`. Source operands: `rax`, `rsi`.

### Store 3 — `0xE465C61`

```text
[r14] = rax
rax = qword ptr [0x95B1DE0]
```

Reached only when an earlier call result `eax` is `1`, or `eax == 2` and
`byte ptr [rcx+0x18] == 0`. The value is a direct load from global `0x95B1DE0`.

Whether the three paths reconverge: after store 1, control jumps to
`0xE465A4B`; after store 2, it continues to `0xE465A42` / `0xE465A4B`; store 3
is in a later region. They are separate output-write sites; full reconvergence
is not yet proven.

## 5. Unresolved helper calls

M530155:

- `0xB429D40` (unregistered resolver, called twice)
- `0x15FE7450` (M732322, called twice)
- `0x15B8BB50` (M723335, called / tail-transferred)
- `0x1D65FD90` (tail transfer, unresolved fixed-point-like helper)
- `0x183C02340` (error/cold stub)

M504598:

- `0xB429D40` (unregistered resolver)
- `0x154B8FE0` (M530133)
- `0x1D661B60` (M68198, known fixed-point binary but exact operation unresolved)
- `0xE72B580` (M506478)
- `0xB42A0C0` (unregistered)
- `0xE7333E0` (M506532 `TryGetLockHP`, sealed by Handoff 12)
- `0xB429F50` (unregistered)
- `0xE72D9E0` (M506491)
- `0xE445DD0` (M504409)
- `0x15FE7450` (M732322)
- `0x15B3C8B0` (M723020)
- `0x15D456B0` (M726510)
- `0x15D45880` (M726511)
- `0x183C020B0` / `0x183C02340` (error/cold stubs)

## 6. Recommended V4P semantic-analysis order

1. Resolve M530155 `0x95B1E18` / `0x95B1DE0` roles and the inline compare
   selection; determine which return path feeds `Q`.
2. Resolve tail helper `0x1D65FD90` if it participates in M530155 return value.
3. Trace M504598 stores A/B/C and determine which store is reached for the
   Handoff 13 normal path.
4. Resolve the M504598 fixed-point binary call `0x1D661B60` and the unregistered
   resolver calls `0xB429D40`, `0xB42A0C0`, `0xB429F50`.
5. Reconnect the resolved `V` rewrite to M504579 / M507308 only after the
   helper internals above are bounded.

## 7. Exact RVAs for remaining ambiguous branches

M530155:

- `0x154B9431`, `0x154B943E`
- `0x154B9499`, `0x154B94B0`, `0x154B953D`, `0x154B9574`, `0x154B9582`
- `0x154B9588`, `0x154B95DA`

M504598:

- `0xE46592B`, `0xE465A39` (compare result gates before stores 1/2)
- `0xE465C3A`, `0xE465C42`, `0xE465C47`, `0xE465C50`, `0xE465C54`
  (store 3 gate)
- Stores: `0xE465931`, `0xE465A3F`, `0xE465C61`
