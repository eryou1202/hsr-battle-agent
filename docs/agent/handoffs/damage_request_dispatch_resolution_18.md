# Damage Request Dispatch Resolution 18

`STATUS = PREPROCESS ONLY`

This is **not** `semantic_handoff_18`. It records the bounded indirect-dispatch
resolution for:

```text
M507304 0xC30F0BC call [rcx+0x120]
```

Artifact: `data/raw/4.4.54/damage_request_dispatch_resolution_18.json`

---

## rcx provenance

- `rcx` at the slot load is `[r15]`, where `r15` is the first argument of
  M507304.
- M507296 passed `r12` (its `this` = PGOOHIHKHNJ executor instance) as `rcx` to
  M507304.
- So the dispatch owner is the **PGOOHIHKHNJ executor instance**; the slot is
  loaded through its first qword (`[r15]`), which is likely a klass or
  dispatch-table-like pointer.

## +0x120 dispatch identity

- Classification: `UNKNOWN` / `BOUNDED_POLYMORPHIC_TARGET_SET`
- A .rdata method-pointer table at `0x4C1A880` contains PGOOHIHKHNJ methods in
  order.
- If that table is the base, `+0x120 = 0x4C1A9A0` points to M507328 `.ctor` of
  HIPAIGMJNOE, but that conflicts with the return-object contract.
- Therefore the exact vtable/dispatch-table base is not proven.

## Concrete target(s)

| Candidate | Method / RVA | Evidence |
| --- | --- | --- |
| M507307 | `COADOLBGKGK` `0xC310B10` | 6-param method; tail-calls `0x18B429F50`; strongest return-object candidate |
| M507309 | `CJFALFFMGLG` `0xC313A10` | exact call arity; calls M504421 `ApplyStanceDamage`; return-object contract weak |
| M507328 | `.ctor` `0x15997360` | table-slot candidate only if base is `0x4C1A880`; unlikely |

## Selected DamageByAttackProperty target

- **M507307 `COADOLBGKGK` `0xC310B10`**
- Confidence: `SUPPORTED_NOT_CONFIRMED`

## A/B alias result

- `UNKNOWN`
- A is the object allocated at M507296 `0xC30DBFB` (token `0x9788B90`).
- B is the return value of the indirect call at `0xC30F0BC`.
- If M507307 is the target, its tail-call to `0x18B429F50` may return B;
  whether B == A is not proven.

## Exact +0x2D8 writer

- `UNKNOWN`
- No `+0x2D8` write found inside M507296/M507304/M507308 or in the first layer
  of the shortlisted targets.
- Next layer to inspect:
  - M507307 tail helper `0x18B429F50`
  - M507309 callee M504421 `ApplyStanceDamage` `0xE4487C0`

## Source/helper feeding the write

- Not yet resolved.
- The tail helper `0x18B429F50` is the primary next layer if M507307 is
  confirmed.

## M504550 connection

- **`NO_BOUNDED_CONNECTION`**
- Neither M507307 nor M507309 directly calls M504550 DamageFormula.
- M507309 calls M504421 `ApplyStanceDamage`, not M504550.

## Recommended V4P entry

- **Primary:** M507307 `COADOLBGKGK` `0xC310B10`
- **Alternates:** M507309 `0xC313A10`, M507304 `0xC30ED00`
- **Minimal unresolved contract:** prove the PGOOHIHKHNJ dispatch-table base so
  the exact +0x120 target is confirmed, then trace `B[+0x2D8]` initialization
  inside the selected target or its single callee layer.

## Remaining UNKNOWN

- Exact vtable/dispatch-table base for PGOOHIHKHNJ
- Whether the +0x120 slot is M507307, M507309, M507328, or another interface
  slot
- Whether B == A or a different request object
- Exact `+0x2D8` writer inside the resolved target or its callee
