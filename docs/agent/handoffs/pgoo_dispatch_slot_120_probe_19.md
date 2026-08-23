# PGOOHIHKHNJ Dispatch Slot +0x120 Probe 19

`STATUS = PREPROCESS / TOPOLOGY`

This is **not** `semantic_handoff_19`. It records the runtime class-header slot
probe for:

```text
qword[[PGOOHIHKHNJ instance] + 0x0 + 0x120]
```

Artifact: `data/raw/4.4.54/pgoo_dispatch_slot_120_probe_19.json`

---

## [instance] header classification

- `RUNTIME_TYPE_HEADER`
- `[PGOOHIHKHNJ instance + 0x0]` is the runtime class/header pointer used by
  M507304.
- It is compatible with an IL2CPP class pointer, but this binary's class
  descriptor is runtime-initialized/encrypted in the static image.

## PGOOHIHKHNJ TypeInfo/class root

- `UNKNOWN`
- Type-token globals such as `0x9788B90` are runtime/encrypted class-descriptor
  pointers, not statically readable TypeInfo roots.
- No static TypeInfo global was recovered for type index `55138`.

## +0x120 layout role

- `UNKNOWN`
- The only `+0x120` accesses in PGOOHIHKHNJ methods are:
  - Reads at M507304 `0xC30F033` / `0xC30F07D`
  - Stack-local writes in M507308/M507312/M507313/M507315
- No class-header write is present in the type's own methods.

## Initialization mechanism

- Classification: `METADATA_DRIVEN_RUNTIME_INIT` / `EXTERNAL_RUNTIME_INIT`
- No static GameAssembly writer was found in the type's method set.

## Writer/source table

- `NONE_FOUND_IN_PGOOHIHKHNJ_METHODS`
- Source table/metadata: `UNKNOWN`
- Concrete pointer: `UNKNOWN`

## Concrete target / method_index / RVA

- **None recovered.**
- `STATIC_TARGET_RESOLUTION = INSUFFICIENT`

## ABI result

- `NOT_APPLICABLE` (no concrete target to validate)

## Runtime observation contract

To reduce later observation to one known pointer read:

1. Obtain a live PGOOHIHKHNJ instance (e.g., `r15` at M507304 `0xC30F0BC`).
2. Read qword `[instance + 0x0]` → class/header pointer `C`.
3. Read qword `[C + 0x120]` → function pointer `F`.
4. Normalize `F` to RVA: `F - 0x180000000`.
5. Ensure class initialization has occurred; M507304 gates on
   `byte [C+0xCA] & 4` before the call.
6. Pointer width is 8 bytes.

## Remaining UNKNOWN

- Concrete class/header pointer `C`
- Layout role of `+0x120`
- Initialization writer/helper for `[C+0x120]`
- Concrete function pointer / method_index / RVA
- Whether B returned by that pointer is the request object consumed by M507308
