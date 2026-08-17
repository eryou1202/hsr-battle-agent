# Damage Request Slot Origin 17

`STATUS = PREPROCESS ONLY`

This is **not** `semantic_handoff_17`. It records the bounded alias/dataflow
provenance for `request[+0x2D8]` on the DamageByAttackProperty path.

Artifact: `data/raw/4.4.54/damage_request_slot_origin_17.json`

---

## Request pointer alias chain

1. M507296 allocates object **A** at `0xC30DBFB` via `0x18B42A0C0` with type
   token global `0x9788B90`.
2. M507296 stores A in `rsi`, sets `[A+0x18]` and `[A+0x20]`.
3. M507296 calls M507304 at `0xC30DC87` with `rdx = A`; M507304 stores A in
   `rdi`.
4. M507304 reads fields from A (`+0x10`, `+0x18`, `+0x20`, `+0x38`).
5. M507304 performs an indirect call at `0xC30F0BC` through a function pointer
   loaded from `[rcx+0x120]`; the return value **B** is stored to `[rsp+0x60]`.
6. M507304 loads B into `r8` and calls M507308 at `0xC30F610`.

## Exact +0x2D8 origin

- **Result:** `UNKNOWN_INDIRECT_HELPER_BOUNDARY` / `SUCCESS_C`
- M507308 reads `request[+0x2D8]` from object B.
- No direct `+0x2D8` write was found in M507296, M507304, or M507308.
- B is produced by the indirect call at `0xC30F0BC`; the exact writer of
  `B[+0x2D8]` is inside or before that helper.

## Writer/helper identity

- The next helper to resolve is the **indirect call target at `0xC30F0BC`**,
  whose function pointer is loaded from `[rcx+0x120]`.
- Once that target is known, its body should contain or call the `+0x2D8`
  producer for the DamageByAttackProperty path.

## M504550 connection

- **`NO_BOUNDED_CONNECTION`**
- M507304 calls M504548 (`0xE460840`) and M504549 (`0xE460A80`), but does not
  call M504550 DamageFormula (`0xE460BE0`) directly.
- No wrapper path from M507296/M507304 to M504550 was found in this bounded
  check.

## Type token 0x962F8E0

- Global `0x962F8E0` is an opaque `.data` qword (`0x8BC167FB4108E6C6`).
- It is used at M507296 `0xC30EC14`, but that allocation occurs **after** the
  M507304 calls and is not proven to be the request object consumed by
  M507308.
- The request object entering M507304/M507308 is allocated earlier with token
  `0x9788B90` at `0xC30DBFB`.

## M508236 correction

- `0x19D65EF80 = fp_add`
- `0x19D661A00 = fp_mul`
- `0x19D661B60 = fp_sub`
- M508236 was previously described as adding via `0x19D661A00`; it is now
  corrected to **applying `fp_mul`** via `0x19D661A00`.
- The neutral classification is `STORED_DAMAGE_VALUE_TRANSFORM`.

## Recommended V4P entry

- **Primary:** indirect call site `0xC30F0BC` (function pointer from
  `[rcx+0x120]`), because it returns the object B whose `+0x2D8` is read by
  M507308.
- **Alternates:** M507304 `0xC30ED00`, M507296 `0xC30D850`.
- **Minimal unresolved contract:** identify the indirect call target and trace
  `B[+0x2D8]` initialization.

## Remaining UNKNOWN

- Whether B is the same object as A or a child/returned request object.
- Identity/body of the indirect helper called at `0xC30F0BC`.
- Exact `+0x2D8` write inside or before that helper.
- Role of the later `0x962F8E0` allocation at `0xC30EC14`.
