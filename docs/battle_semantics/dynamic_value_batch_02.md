# Battle Semantic DynamicValue Batch 02

> Final status: **`BATTLE_SEMANTIC = DYNAMIC_VALUE_BATCH_02_PROOF`**
> Game version: `4.4.54` (20260731-0529-BetaLive-15953205-OSBETAWin4.4.54-OSCb)
> Evidence level: `E4_STATIC_MACHINE_CODE` (all accepted primitives)
> Artifact schema: `battle_semantics_batch/1`

## 1. Scope

This batch recovers eleven small tag-aware DynamicValue scalar coercions,
tag/payload queries and the raw tag accessor.  It does **not** recover the
DynamicValue resolve system, BattleContext evaluation, FixPoint framework,
serialization, logging helpers, or any non-value method.

## 2. Candidate table (all 51 methods of `RPG.GameCore.DynamicValue`)

| method_index | name | native_rva | slot(B) | insn | branch | callees | classification | reason |
|---:|---|---|---:|---:|---:|---:|---|---|
| 74611 | .ctor | 0x1CFBDA60 | 16 | 1 | 0 | 0 | SKIP_WRAPPER | parameterless constructor wrapper |
| 74612 | .ctor | 0x1CFBDA70 | 16 | 4 | 0 | 0 | SKIP_WRAPPER | bool constructor wrapper |
| 74613 | .ctor | 0x1CFBDA80 | 16 | 4 | 0 | 0 | SKIP_WRAPPER | float32 constructor wrapper |
| 74614 | .ctor | 0x1CFBDA90 | 16 | 3 | 0 | 0 | SKIP_WRAPPER | float64 constructor wrapper |
| 74615 | .ctor | 0x1CFBDAA0 | 16 | 3 | 0 | 0 | SKIP_WRAPPER | string constructor wrapper |
| 74616 | .ctor | 0x1CFBDAB0 | 16 | 4 | 0 | 0 | SKIP_WRAPPER | int32 constructor wrapper |
| 74617 | .ctor | 0x1CFBDAC0 | 16 | 3 | 0 | 0 | SKIP_WRAPPER | int64 constructor wrapper |
| 74618 | .ctor | 0x1CFBDAD0 | 16 | 3 | 0 | 0 | SKIP_WRAPPER | array payload constructor wrapper |
| 74619 | .ctor | 0x1CFBDAE0 | 16 | 3 | 0 | 0 | SKIP_WRAPPER | map payload constructor wrapper |
| 74620 | .cctor | 0x1CFBFD60 | None | 1908 | 281 | 251 | SKIP_COMPLEX | static class initializer; 251 calls / 88 jumps, runtime infrastructure |
| 74621 | op_Implicit | 0x1CFBDAF0 | 48 | 10 | 0 | 1 | SKIP_WRAPPER | op_Implicit(string) allocates a DynamicValue cell; allocation-shaped wrapper |
| 74622 | op_Implicit | 0x1CFBDB20 | 48 | 11 | 0 | 1 | SKIP_WRAPPER | op_Implicit(int32) allocates a DynamicValue cell; allocation-shaped wrapper |
| 74623 | op_Implicit | 0x1CFBDB50 | 48 | 10 | 0 | 1 | SKIP_WRAPPER | op_Implicit(int64) allocates a DynamicValue cell; allocation-shaped wrapper |
| 74624 | op_Implicit | 0x1CFBDB80 | 64 | 12 | 0 | 1 | SKIP_WRAPPER | op_Implicit(float32) allocates a DynamicValue cell; allocation-shaped wrapper |
| 74625 | op_Implicit | 0x1CFBDBC0 | 48 | 10 | 0 | 1 | SKIP_WRAPPER | op_Implicit(float64) allocates a DynamicValue cell; allocation-shaped wrapper |
| 74626 | op_Implicit | 0x1CFBDBF0 | 48 | 11 | 0 | 1 | SKIP_WRAPPER | op_Implicit(bool) allocates a DynamicValue cell; allocation-shaped wrapper |
| 74627 | op_Implicit | 0x1CFBDC20 | 48 | 10 | 0 | 1 | SKIP_WRAPPER | op_Implicit(map) allocates a DynamicValue cell; allocation-shaped wrapper |
| 74628 | op_Implicit | 0x1CFBDC50 | 48 | 10 | 0 | 1 | SKIP_WRAPPER | op_Implicit(array) allocates a DynamicValue cell; allocation-shaped wrapper |
| 74629 | ToString | 0x1CFBDC80 | 2512 | 639 | 75 | 57 | SKIP_COMPLEX | ToString formatting dispatcher; 639 instructions, 57 calls, 33 jumps |
| 74630 | Equals | 0x1CFBE8F0 | 240 | 60 | 10 | 0 | SKIP_WRAPPER | Equals(object) adds IL2CPP runtime type identity check then duplicates the recovered Equals(DynamicValue) switch; no new battle semantic |
| 74631 | GetHashCode | 0x1CFBEAD0 | 672 | 195 | 15 | 6 | SKIP_COMPLEX | GetHashCode dispatcher; 195 instructions, 15 branches, 6 calls |
| 74632 | Equals | 0x1CFBE9E0 | 240 | 68 | 7 | 1 | SKIP_WRAPPER | already recovered as battle.ir.value.dynamic_value_equals in vertical_slice_01.json |
| 74633 | get_FloatValue | 0x1CFBED90 | 96 | 25 | 4 | 1 | ACCEPT | selected Batch 02 primitive |
| 74634 | get_DoubleValue | 0x1CFBEE20 | 128 | 39 | 6 | 2 | ACCEPT | selected Batch 02 primitive |
| 74635 | get_FixPointValue | 0x1CFBEEA0 | 368 | 89 | 14 | 1 | SKIP_COMPLEX | FixPoint framework: 89 instructions, 14 branches, range/shift encoding and two FixPoint global constants (0x95B1E00 / 0x95B1E60); exceeds single-callee batch budget |
| 74636 | get_BoolValue | 0x1CFBF010 | 96 | 29 | 3 | 2 | ACCEPT | selected Batch 02 primitive |
| 74637 | get_IntValue | 0x1CFBF070 | 80 | 24 | 3 | 1 | ACCEPT | selected Batch 02 primitive |
| 74638 | get_UintValue | 0x1CFBF0C0 | 80 | 24 | 3 | 1 | ACCEPT | selected Batch 02 primitive |
| 74639 | get_LongValue | 0x1CFBF110 | 128 | 39 | 5 | 2 | ACCEPT | selected Batch 02 primitive |
| 74640 | get_StringValue | 0x1CFBF190 | 48 | 11 | 1 | 1 | ACCEPT | selected Batch 02 primitive |
| 74641 | get_ArrayValue | 0x1CFBF1D0 | 48 | 13 | 2 | 1 | SKIP_WRAPPER | get_ArrayValue returns ObjectRef; current scalar-only trace contract would need a reference-result summary, deferred instead of special-cased |
| 74642 | get_MapValue | 0x1CFBF220 | 48 | 13 | 2 | 1 | SKIP_WRAPPER | get_MapValue returns ObjectRef; current scalar-only trace contract would need a reference-result summary, deferred instead of special-cased |
| 74643 | _LogError | 0x1CFBF270 | 80 | 17 | 1 | 2 | SKIP_COMPLEX | private logging helper; no value semantic |
| 74644 | _LogError | 0x1CFBF2C0 | 80 | 21 | 1 | 2 | SKIP_COMPLEX | private logging helper; no value semantic |
| 74645 | _LogTypeMismatch | 0x1CFBF310 | 352 | 90 | 15 | 10 | SKIP_COMPLEX | private logging helper; no value semantic |
| 74646 | _LogInvalidValue | 0x1CFBF470 | 432 | 115 | 21 | 12 | SKIP_COMPLEX | private logging helper; no value semantic |
| 74647 | _EscapeString | 0x1CFBE660 | 640 | 148 | 19 | 15 | SKIP_COMPLEX | string escaping helper; 150 instructions, 15 calls, not a gameplay value semantic |
| 74648 | get_ValueType | 0x1CFBE650 | 16 | 2 | 0 | 0 | ACCEPT | selected Batch 02 primitive |
| 74649 | get_IsInt | 0x1CFBEE00 | 16 | 3 | 0 | 0 | SKIP_WRAPPER | single tag comparison already covered by get_ValueType + selected tag predicates; excluded to respect batch value budget |
| 74650 | get_IsFloat | 0x1CFBEDF0 | 16 | 3 | 0 | 0 | SKIP_WRAPPER | single tag comparison already covered by get_ValueType + selected tag predicates; excluded to respect batch value budget |
| 74651 | get_IsBool | 0x1CFBEE10 | 16 | 3 | 0 | 0 | SKIP_WRAPPER | single tag comparison already covered by get_ValueType + selected tag predicates; excluded to respect batch value budget |
| 74652 | get_IsString | 0x1CFBF1C0 | 16 | 3 | 0 | 0 | SKIP_WRAPPER | single tag comparison already covered by get_ValueType + selected tag predicates; excluded to respect batch value budget |
| 74653 | get_IsNull | 0x1CFBF620 | 16 | 3 | 0 | 0 | ACCEPT | selected Batch 02 primitive |
| 74654 | get_IsArray | 0x1CFBF200 | 32 | 7 | 1 | 0 | ACCEPT | selected Batch 02 primitive |
| 74655 | get_IsMap | 0x1CFBF250 | 32 | 7 | 1 | 0 | ACCEPT | selected Batch 02 primitive |
| 74656 | get_longValue | 0x1CFBED70 | 16 | 2 | 0 | 0 | SKIP_WRAPPER | raw unionValue reinterpreter without tag check; canonical representation is tag-typed and cannot expose stale union bytes for ARRAY/MAP/STRING cells |
| 74657 | get_doubleValue | 0x1CFBED80 | 16 | 2 | 0 | 0 | SKIP_WRAPPER | raw unionValue reinterpreter without tag check; canonical representation is tag-typed and cannot expose stale union bytes for ARRAY/MAP/STRING cells |
| 74658 | get_boolValue | 0x1CFBE8E0 | 16 | 3 | 0 | 0 | SKIP_WRAPPER | raw unionValue reinterpreter without tag check; canonical representation is tag-typed and cannot expose stale union bytes for ARRAY/MAP/STRING cells |
| 74659 | FromByteBinary | 0x1CFBF630 | 720 | 156 | 18 | 23 | SKIP_SERIALIZATION | explicitly excluded FromByteBinary serialization semantic |
| 74660 | ToBinary | 0x1CFBF900 | 976 | 212 | 23 | 20 | SKIP_SERIALIZATION | explicitly excluded ToBinary serialization semantic |
| 74661 | get__DebuggerDisplay | 0x1CFBFCD0 | 144 | 33 | 1 | 4 | SKIP_COMPLEX | debugger-display formatter; 34 instructions, 4 calls, allocates debug string |

## 3. Accepted primitives

### DynamicValueToInt32 (`get_IntValue`, method_index 74637)

- Primitive: `battle.ir.value.dynamic_value_to_int`; result `int32`
- RVA `0x1CFBF070`; body 74 bytes /
  24 instructions / 3
  conditional branches / 1 calls
- Body sha256 `70cac298ed6a33948152745cd33ac47951a72f864214fb34dbe5659e7ecbe597`
- Tag behavior:

- INT(0): read signed 32-bit low dword of unionValue
- FLOAT(1): cvttsd2si eax (truncate toward zero; out-of-range/NaN -> 0x80000000)
- BOOL(2): unionValue == 1 -> 1, otherwise 0 (silent)
- any other tag: error-log callee, return 0

- Branch conditions: tag == 2 -> BOOL path, tag == 1 -> FLOAT path, tag == 0 -> INT path, tag not in {0,1,2} -> mismatch path
- Required callees:

- 0x1CFD2950 (type-mismatch log helper (error path only), UNKNOWN_HELPER_NOT_NEEDED)

- Pseudocode:

```
    int32 DynamicValueToInt32(DynamicValue this):
        t = this.ValueType                 # byte @ +0x30
        if t == BOOL(2): return this.unionValue == 1 ? 1 : 0
        if t == FLOAT(1): return cvttsd2si32(this.unionValue)
        if t == INT(0): return (int32)(uint32)low32(this.unionValue)
        _LogTypeMismatch(this); return 0   # CONFIRMED default, helper internals not followed
```

- Native evidence:

```
    1CFBF070  48 83 ec 28               sub      rsp, 0x28
    1CFBF074  0f b6 41 30               movzx    eax, byte ptr [rcx + 0x30]
    1CFBF078  83 f8 02                  cmp      eax, 2
    1CFBF07B  74 11                     je       0x19cfbf08e
    1CFBF07D  83 f8 01                  cmp      eax, 1
    1CFBF080  74 1b                     je       0x19cfbf09d
    1CFBF082  85 c0                     test     eax, eax
    1CFBF084  75 21                     jne      0x19cfbf0a7
    1CFBF086  8b 41 28                  mov      eax, dword ptr [rcx + 0x28]
    1CFBF089  48 83 c4 28               add      rsp, 0x28
    1CFBF08D  c3                        ret      
    1CFBF08E  31 c0                     xor      eax, eax
    1CFBF090  48 83 79 28 01            cmp      qword ptr [rcx + 0x28], 1
    1CFBF095  0f 94 c0                  sete     al
    1CFBF098  48 83 c4 28               add      rsp, 0x28
    1CFBF09C  c3                        ret      
    1CFBF09D  f2 0f 2c 41 28            cvttsd2si eax, qword ptr [rcx + 0x28]
    1CFBF0A2  48 83 c4 28               add      rsp, 0x28
    1CFBF0A6  c3                        ret      
    1CFBF0A7  48 8b 15 f2 a9 98 ec      mov      rdx, qword ptr [rip - 0x1367560e] ; [rip]->0x189949AA0 (rva 0x9949AA0)
    1CFBF0AE  e8 9d 38 01 00            call     0x19cfd2950
    1CFBF0B3  31 c0                     xor      eax, eax
    1CFBF0B5  48 83 c4 28               add      rsp, 0x28
    1CFBF0B9  c3                        ret      
```

### DynamicValueToUInt32 (`get_UintValue`, method_index 74638)

- Primitive: `battle.ir.value.dynamic_value_to_uint`; result `uint32`
- RVA `0x1CFBF0C0`; body 75 bytes /
  24 instructions / 3
  conditional branches / 1 calls
- Body sha256 `3aacb020b2a70b8a96a6a7330efec92540ada2548f23d29b279e66a8b742dcca`
- Tag behavior:

- INT(0): bit-preserving read of signed 32-bit low dword of unionValue
- FLOAT(1): cvttsd2si rax (64-bit truncation) then return low 32 bits
- BOOL(2): unionValue == 1 -> 1, otherwise 0 (silent)
- any other tag: error-log callee, return 0

- Branch conditions: tag == 2 -> BOOL path, tag == 1 -> FLOAT path, tag == 0 -> INT path, tag not in {0,1,2} -> mismatch path
- Required callees:

- 0x1CFD2950 (type-mismatch log helper (error path only), UNKNOWN_HELPER_NOT_NEEDED)

- Pseudocode:

```
    uint32 DynamicValueToUInt32(DynamicValue this):
        t = this.ValueType                 # byte @ +0x30
        if t == BOOL(2): return this.unionValue == 1 ? 1 : 0
        if t == FLOAT(1): return (uint32)(int64)cvttsd2si64(this.unionValue)
        if t == INT(0): return (uint32)low32(this.unionValue)
        _LogTypeMismatch(this); return 0   # CONFIRMED default, helper internals not followed
```

- Native evidence:

```
    1CFBF0C0  48 83 ec 28               sub      rsp, 0x28
    1CFBF0C4  0f b6 41 30               movzx    eax, byte ptr [rcx + 0x30]
    1CFBF0C8  83 f8 02                  cmp      eax, 2
    1CFBF0CB  74 11                     je       0x19cfbf0de
    1CFBF0CD  83 f8 01                  cmp      eax, 1
    1CFBF0D0  74 1b                     je       0x19cfbf0ed
    1CFBF0D2  85 c0                     test     eax, eax
    1CFBF0D4  75 22                     jne      0x19cfbf0f8
    1CFBF0D6  8b 41 28                  mov      eax, dword ptr [rcx + 0x28]
    1CFBF0D9  48 83 c4 28               add      rsp, 0x28
    1CFBF0DD  c3                        ret      
    1CFBF0DE  31 c0                     xor      eax, eax
    1CFBF0E0  48 83 79 28 01            cmp      qword ptr [rcx + 0x28], 1
    1CFBF0E5  0f 94 c0                  sete     al
    1CFBF0E8  48 83 c4 28               add      rsp, 0x28
    1CFBF0EC  c3                        ret      
    1CFBF0ED  f2 48 0f 2c 41 28         cvttsd2si rax, qword ptr [rcx + 0x28]
    1CFBF0F3  48 83 c4 28               add      rsp, 0x28
    1CFBF0F7  c3                        ret      
    1CFBF0F8  48 8b 15 41 09 9c ec      mov      rdx, qword ptr [rip - 0x1363f6bf] ; [rip]->0x18997FA40 (rva 0x997FA40)
    1CFBF0FF  e8 4c 38 01 00            call     0x19cfd2950
    1CFBF104  31 c0                     xor      eax, eax
    1CFBF106  48 83 c4 28               add      rsp, 0x28
    1CFBF10A  c3                        ret      
```

### DynamicValueToInt64 (`get_LongValue`, method_index 74639)

- Primitive: `battle.ir.value.dynamic_value_to_long`; result `int64`
- RVA `0x1CFBF110`; body 122 bytes /
  39 instructions / 5
  conditional branches / 2 calls
- Body sha256 `2435cc35f00d1b30efe233d9dfe8be596a7bc6581e8480ed39f7de43db0f5422`
- Tag behavior:

- BOOL(2): unionValue == 1 -> 1, otherwise 0 (silent)
- FLOAT(1): cvttsd2si rax (truncate toward zero; out-of-range/NaN -> 0x8000000000000000)
- INT(0): full signed qword unionValue
- any other tag: error-log callee, return 0

- Branch conditions: IL2CPP class-init flag @ 0x9A5743C == 0 -> one-time init branch, tag == 2 -> BOOL path, tag == 1 -> FLOAT path, tag == 0 -> INT path, tag not in {0,1,2} -> mismatch path
- Required callees:

- 0x3C6D0E0 (IL2CPP runtime class-init helper (one-time branch only), UNKNOWN_HELPER_NOT_NEEDED)
- 0x1CFD2950 (type-mismatch log helper (error path only), UNKNOWN_HELPER_NOT_NEEDED)

- Pseudocode:

```
    int64 DynamicValueToInt64(DynamicValue this):
        if not il2cpp_class_initialized(0x1034C):   # one-time runtime infrastructure
            il2cpp_runtime_class_init(0x1034C)
        t = this.ValueType                 # byte @ +0x30
        if t == BOOL(2): return this.unionValue == 1 ? 1 : 0
        if t == FLOAT(1): return cvttsd2si64(this.unionValue)
        if t == INT(0): return this.unionValue
        _LogTypeMismatch(this); return 0   # CONFIRMED default, helper internals not followed
```

- Native evidence:

```
    1CFBF110  56                        push     rsi
    1CFBF111  48 83 ec 20               sub      rsp, 0x20
    1CFBF115  48 89 ce                  mov      rsi, rcx
    1CFBF118  80 3d 1d 83 a9 ec 00      cmp      byte ptr [rip - 0x13567ce3], 0 ; [rip]->0x189A5743C (rva 0x9A5743C)
    1CFBF11F  74 3f                     je       0x19cfbf160
    1CFBF121  0f b6 46 30               movzx    eax, byte ptr [rsi + 0x30]
    1CFBF125  83 f8 02                  cmp      eax, 2
    1CFBF128  74 50                     je       0x19cfbf17a
    1CFBF12A  83 f8 01                  cmp      eax, 1
    1CFBF12D  74 0e                     je       0x19cfbf13d
    1CFBF12F  85 c0                     test     eax, eax
    1CFBF131  75 16                     jne      0x19cfbf149
    1CFBF133  48 8b 46 28               mov      rax, qword ptr [rsi + 0x28]
    1CFBF137  48 83 c4 20               add      rsp, 0x20
    1CFBF13B  5e                        pop      rsi
    1CFBF13C  c3                        ret      
    1CFBF13D  f2 48 0f 2c 46 28         cvttsd2si rax, qword ptr [rsi + 0x28]
    1CFBF143  48 83 c4 20               add      rsp, 0x20
    1CFBF147  5e                        pop      rsi
    1CFBF148  c3                        ret      
    1CFBF149  48 8b 15 70 a9 98 ec      mov      rdx, qword ptr [rip - 0x13675690] ; [rip]->0x189949AC0 (rva 0x9949AC0)
    1CFBF150  48 89 f1                  mov      rcx, rsi
    1CFBF153  e8 f8 37 01 00            call     0x19cfd2950
    1CFBF158  31 c0                     xor      eax, eax
    1CFBF15A  48 83 c4 20               add      rsp, 0x20
    1CFBF15E  5e                        pop      rsi
    1CFBF15F  c3                        ret      
    1CFBF160  b9 4c 03 01 00            mov      ecx, 0x1034c
    1CFBF165  e8 76 df ca e6            call     0x183c6d0e0
    1CFBF16A  c6 05 cb 82 a9 ec 01      mov      byte ptr [rip - 0x13567d35], 1 ; [rip]->0x189A5743C (rva 0x9A5743C)
    1CFBF171  0f b6 46 30               movzx    eax, byte ptr [rsi + 0x30]
    1CFBF175  83 f8 02                  cmp      eax, 2
    1CFBF178  75 b0                     jne      0x19cfbf12a
    1CFBF17A  31 c0                     xor      eax, eax
    1CFBF17C  48 83 7e 28 01            cmp      qword ptr [rsi + 0x28], 1
    1CFBF181  0f 94 c0                  sete     al
    1CFBF184  48 83 c4 20               add      rsp, 0x20
    1CFBF188  5e                        pop      rsi
    1CFBF189  c3                        ret      
```

### DynamicValueToFloat32 (`get_FloatValue`, method_index 74633)

- Primitive: `battle.ir.value.dynamic_value_to_float`; result `float32`
- RVA `0x1CFBED90`; body 87 bytes /
  25 instructions / 4
  conditional branches / 1 calls
- Body sha256 `81d18a68cd7cf52739c9d7f7c0ffb539b73bb4bced3ad14bc0d5b407048dc4c0`
- Tag behavior:

- INT(0): cvtsi2ss signed int64 -> float32
- FLOAT(1): cvtsd2ss float64 -> float32 (payload is always a double in the union)
- BOOL(2): unionValue == 1 -> +1.0f, otherwise +0.0f (silent)
- any other tag: error-log callee, return +0.0f

- Branch conditions: tag == 0 -> INT path, tag == 2 -> BOOL path, tag == 1 -> FLOAT path, tag not in {0,1,2} -> mismatch path, BOOL path: unionValue != 1 -> zero-float path
- Required callees:

- 0x1CFD2950 (type-mismatch log helper (error path only), UNKNOWN_HELPER_NOT_NEEDED)

- Pseudocode:

```
    float32 DynamicValueToFloat32(DynamicValue this):
        t = this.ValueType                 # byte @ +0x30
        if t == INT(0): return cvtsi2ss64(this.unionValue)
        if t == BOOL(2): return this.unionValue == 1 ? 1.0f : 0.0f
        if t == FLOAT(1): return cvtsd2ss(this.unionValue)
        _LogTypeMismatch(this); return 0.0f  # CONFIRMED default, helper internals not followed
```

- Native evidence:

```
    1CFBED90  48 83 ec 28               sub      rsp, 0x28
    1CFBED94  0f b6 41 30               movzx    eax, byte ptr [rcx + 0x30]
    1CFBED98  85 c0                     test     eax, eax
    1CFBED9A  74 18                     je       0x19cfbedb4
    1CFBED9C  83 f8 02                  cmp      eax, 2
    1CFBED9F  74 1e                     je       0x19cfbedbf
    1CFBEDA1  83 f8 01                  cmp      eax, 1
    1CFBEDA4  75 2d                     jne      0x19cfbedd3
    1CFBEDA6  f2 0f 10 41 28            movsd    xmm0, qword ptr [rcx + 0x28]
    1CFBEDAB  f2 0f 5a c0               cvtsd2ss xmm0, xmm0
    1CFBEDAF  48 83 c4 28               add      rsp, 0x28
    1CFBEDB3  c3                        ret      
    1CFBEDB4  f3 48 0f 2a 41 28         cvtsi2ss xmm0, qword ptr [rcx + 0x28]
    1CFBEDBA  48 83 c4 28               add      rsp, 0x28
    1CFBEDBE  c3                        ret      
    1CFBEDBF  48 83 79 28 01            cmp      qword ptr [rcx + 0x28], 1
    1CFBEDC4  75 19                     jne      0x19cfbeddf
    1CFBEDC6  f3 0f 10 05 32 a2 06 e7   movss    xmm0, dword ptr [rip - 0x18f95dce] ; [rip]->0x184029000 (rva 0x4029000)
    1CFBEDCE  48 83 c4 28               add      rsp, 0x28
    1CFBEDD2  c3                        ret      
    1CFBEDD3  48 8b 15 ee ac 98 ec      mov      rdx, qword ptr [rip - 0x13675312] ; [rip]->0x189949AC8 (rva 0x9949AC8)
    1CFBEDDA  e8 71 3b 01 00            call     0x19cfd2950
    1CFBEDDF  0f 57 c0                  xorps    xmm0, xmm0
    1CFBEDE2  48 83 c4 28               add      rsp, 0x28
    1CFBEDE6  c3                        ret      
```

### DynamicValueToFloat64 (`get_DoubleValue`, method_index 74634)

- Primitive: `battle.ir.value.dynamic_value_to_double`; result `float64`
- RVA `0x1CFBEE20`; body 128 bytes /
  39 instructions / 6
  conditional branches / 2 calls
- Body sha256 `117a9d58bdb6742994359db02cc0c99a4874436698642e1809a4b458ee0a2671`
- Tag behavior:

- INT(0): cvtsi2sd signed int64 -> float64
- BOOL(2): unionValue == 1 -> +1.0, otherwise +0.0 (silent)
- FLOAT(1): raw float64 union payload
- any other tag: error-log callee, return +0.0

- Branch conditions: IL2CPP class-init flag @ 0x9A57434 == 0 -> one-time init branch, tag == 0 -> INT path, tag == 2 -> BOOL path, tag == 1 -> FLOAT path, tag not in {0,1,2} -> mismatch path, BOOL path: unionValue != 1 -> zero-double path
- Required callees:

- 0x3C6D0E0 (IL2CPP runtime class-init helper (one-time branch only), UNKNOWN_HELPER_NOT_NEEDED)
- 0x1CFD2950 (type-mismatch log helper (error path only), UNKNOWN_HELPER_NOT_NEEDED)

- Pseudocode:

```
    float64 DynamicValueToFloat64(DynamicValue this):
        if not il2cpp_class_initialized(0x10344):   # one-time runtime infrastructure
            il2cpp_runtime_class_init(0x10344)
        t = this.ValueType                 # byte @ +0x30
        if t == INT(0): return cvtsi2sd64(this.unionValue)
        if t == BOOL(2): return this.unionValue == 1 ? 1.0 : 0.0
        if t == FLOAT(1): return this.unionValue
        _LogTypeMismatch(this); return 0.0   # CONFIRMED default, helper internals not followed
```

- Native evidence:

```
    1CFBEE20  56                        push     rsi
    1CFBEE21  48 83 ec 20               sub      rsp, 0x20
    1CFBEE25  48 89 ce                  mov      rsi, rcx
    1CFBEE28  80 3d 05 86 a9 ec 00      cmp      byte ptr [rip - 0x135679fb], 0 ; [rip]->0x189A57434 (rva 0x9A57434)
    1CFBEE2F  74 4a                     je       0x19cfbee7b
    1CFBEE31  0f b6 46 30               movzx    eax, byte ptr [rsi + 0x30]
    1CFBEE35  85 c0                     test     eax, eax
    1CFBEE37  74 5b                     je       0x19cfbee94
    1CFBEE39  83 f8 02                  cmp      eax, 2
    1CFBEE3C  74 10                     je       0x19cfbee4e
    1CFBEE3E  83 f8 01                  cmp      eax, 1
    1CFBEE41  75 20                     jne      0x19cfbee63
    1CFBEE43  f2 0f 10 46 28            movsd    xmm0, qword ptr [rsi + 0x28]
    1CFBEE48  48 83 c4 20               add      rsp, 0x20
    1CFBEE4C  5e                        pop      rsi
    1CFBEE4D  c3                        ret      
    1CFBEE4E  48 83 7e 28 01            cmp      qword ptr [rsi + 0x28], 1
    1CFBEE53  75 1d                     jne      0x19cfbee72
    1CFBEE55  f2 0f 10 05 8b a4 06 e7   movsd    xmm0, qword ptr [rip - 0x18f95b75] ; [rip]->0x1840292E8 (rva 0x40292E8)
    1CFBEE5D  48 83 c4 20               add      rsp, 0x20
    1CFBEE61  5e                        pop      rsi
    1CFBEE62  c3                        ret      
    1CFBEE63  48 8b 15 66 ac 98 ec      mov      rdx, qword ptr [rip - 0x1367539a] ; [rip]->0x189949AD0 (rva 0x9949AD0)
    1CFBEE6A  48 89 f1                  mov      rcx, rsi
    1CFBEE6D  e8 de 3a 01 00            call     0x19cfd2950
    1CFBEE72  0f 57 c0                  xorps    xmm0, xmm0
    1CFBEE75  48 83 c4 20               add      rsp, 0x20
    1CFBEE79  5e                        pop      rsi
    1CFBEE7A  c3                        ret      
    1CFBEE7B  b9 44 03 01 00            mov      ecx, 0x10344
    1CFBEE80  e8 5b e2 ca e6            call     0x183c6d0e0
    1CFBEE85  c6 05 a8 85 a9 ec 01      mov      byte ptr [rip - 0x13567a58], 1 ; [rip]->0x189A57434 (rva 0x9A57434)
    1CFBEE8C  0f b6 46 30               movzx    eax, byte ptr [rsi + 0x30]
    1CFBEE90  85 c0                     test     eax, eax
    1CFBEE92  75 a5                     jne      0x19cfbee39
    1CFBEE94  f2 48 0f 2a 46 28         cvtsi2sd xmm0, qword ptr [rsi + 0x28]
    1CFBEE9A  48 83 c4 20               add      rsp, 0x20
    1CFBEE9E  5e                        pop      rsi
    1CFBEE9F  c3                        ret      
```

### DynamicValueToBool (`get_BoolValue`, method_index 74636)

- Primitive: `battle.ir.value.dynamic_value_to_bool`; result `boolean`
- RVA `0x1CFBF010`; body 93 bytes /
  29 instructions / 3
  conditional branches / 2 calls
- Body sha256 `0174ef692e3616e143a1d3bb722362b97c4fd0fd66b899055bb946527ffb1403`
- Tag behavior:

- INT(0): unionValue in {0,1} -> value != 0; any other raw payload -> invalid-value log helper then false
- BOOL(2): unionValue == 1 (raw payloads other than 1 normalize to false, silently)
- any other tag: type-mismatch log helper, return false

- Branch conditions: tag == 0 -> INT path, tag == 2 -> BOOL path, tag not in {0,2} -> mismatch path, INT path: unsigned comparison raw < 2 bypasses the invalid-value helper, BOOL path: unionValue == 1
- Required callees:

- 0x1CFD2AB0 (invalid-value log helper (INT raw value >= 2; error path only), UNKNOWN_HELPER_NOT_NEEDED)
- 0x1CFD2950 (type-mismatch log helper (non INT/BOOL tags; error path only), UNKNOWN_HELPER_NOT_NEEDED)

- Pseudocode:

```
    bool DynamicValueToBool(DynamicValue this):
        t = this.ValueType                 # byte @ +0x30
        if t == INT(0):
            raw = this.unionValue
            if raw >= 2: _LogInvalidValue(this)   # negative/2+ raw payload
            return raw == 1
        if t == BOOL(2):
            return this.unionValue == 1
        _LogTypeMismatch(this); return false  # CONFIRMED default
```

- Native evidence:

```
    1CFBF010  56                        push     rsi
    1CFBF011  48 83 ec 20               sub      rsp, 0x20
    1CFBF015  48 89 ce                  mov      rsi, rcx
    1CFBF018  0f b6 41 30               movzx    eax, byte ptr [rcx + 0x30]
    1CFBF01C  85 c0                     test     eax, eax
    1CFBF01E  74 0c                     je       0x19cfbf02c
    1CFBF020  83 f8 02                  cmp      eax, 2
    1CFBF023  75 31                     jne      0x19cfbf056
    1CFBF025  48 83 7e 28 01            cmp      qword ptr [rsi + 0x28], 1
    1CFBF02A  eb 21                     jmp      0x19cfbf04d
    1CFBF02C  48 8b 46 28               mov      rax, qword ptr [rsi + 0x28]
    1CFBF030  48 83 f8 02               cmp      rax, 2
    1CFBF034  72 13                     jb       0x19cfbf049
    1CFBF036  48 8b 15 fb 09 9c ec      mov      rdx, qword ptr [rip - 0x1363f605] ; [rip]->0x18997FA38 (rva 0x997FA38)
    1CFBF03D  48 89 f1                  mov      rcx, rsi
    1CFBF040  e8 6b 3a 01 00            call     0x19cfd2ab0
    1CFBF045  48 8b 46 28               mov      rax, qword ptr [rsi + 0x28]
    1CFBF049  48 83 f8 01               cmp      rax, 1
    1CFBF04D  0f 94 c0                  sete     al
    1CFBF050  48 83 c4 20               add      rsp, 0x20
    1CFBF054  5e                        pop      rsi
    1CFBF055  c3                        ret      
    1CFBF056  48 8b 15 db 09 9c ec      mov      rdx, qword ptr [rip - 0x1363f625] ; [rip]->0x18997FA38 (rva 0x997FA38)
    1CFBF05D  48 89 f1                  mov      rcx, rsi
    1CFBF060  e8 eb 38 01 00            call     0x19cfd2950
    1CFBF065  31 c0                     xor      eax, eax
    1CFBF067  48 83 c4 20               add      rsp, 0x20
    1CFBF06B  5e                        pop      rsi
    1CFBF06C  c3                        ret      
```

### DynamicValueTypeTag (`get_ValueType`, method_index 74648)

- Primitive: `battle.ir.value.dynamic_value_type`; result `DynamicValueType`
- RVA `0x1CFBE650`; body 5 bytes /
  2 instructions / 0
  conditional branches / 0 calls
- Body sha256 `fbb856ed704e304243792b6e84415cff0e70781a5e34bdfce046ae9803ee913b`
- Tag behavior:

- Returns the raw +0x30 byte unchanged (0..6 for canonical cells; no validation and no coercion)

- Branch conditions: none
- Required callees:

- none

- Pseudocode:

```
    DynamicValueType DynamicValueTypeTag(DynamicValue this):
        return this.ValueType              # byte @ +0x30, zero-extended
```

- Native evidence:

```
    1CFBE650  0f b6 41 30               movzx    eax, byte ptr [rcx + 0x30]
    1CFBE654  c3                        ret      
```

### DynamicValueStringPayload (`get_StringValue`, method_index 74640)

- Primitive: `battle.ir.value.dynamic_value_string`; result `string_or_null`
- RVA `0x1CFBF190`; body 38 bytes /
  11 instructions / 1
  conditional branches / 1 calls
- Body sha256 `694440a712d06707798f7e912fc878eaa48ad017332fcff82ecc1385dd3c2af6`
- Tag behavior:

- STRING(5): return stringValue pointer (null pointer is returned as-is)
- any other tag: type-mismatch log helper, return null

- Branch conditions: tag == 5 -> payload path, tag != 5 -> mismatch path
- Required callees:

- 0x1CFD2950 (type-mismatch log helper (error path only), UNKNOWN_HELPER_NOT_NEEDED)

- Pseudocode:

```
    string | null DynamicValueStringPayload(DynamicValue this):
        if this.ValueType == STRING(5):
            return this.stringValue          # may be null
        _LogTypeMismatch(this); return null  # CONFIRMED default
```

- Native evidence:

```
    1CFBF190  48 83 ec 28               sub      rsp, 0x28
    1CFBF194  80 79 30 05               cmp      byte ptr [rcx + 0x30], 5
    1CFBF198  75 09                     jne      0x19cfbf1a3
    1CFBF19A  48 8b 41 18               mov      rax, qword ptr [rcx + 0x18]
    1CFBF19E  48 83 c4 28               add      rsp, 0x28
    1CFBF1A2  c3                        ret      
    1CFBF1A3  48 8b 15 ce c0 98 ec      mov      rdx, qword ptr [rip - 0x13673f32] ; [rip]->0x18994B278 (rva 0x994B278)
    1CFBF1AA  e8 a1 37 01 00            call     0x19cfd2950
    1CFBF1AF  31 c0                     xor      eax, eax
    1CFBF1B1  48 83 c4 28               add      rsp, 0x28
    1CFBF1B5  c3                        ret      
```

### DynamicValueIsArray (`get_IsArray`, method_index 74654)

- Primitive: `battle.ir.value.dynamic_value_is_array`; result `boolean`
- RVA `0x1CFBF200`; body 18 bytes /
  7 instructions / 1
  conditional branches / 0 calls
- Body sha256 `24c53a6f0aa01b73c24dbccf93476c659c0c268320b625b13bdd7b8cd3846dfe`
- Tag behavior:

- ARRAY(3) with non-null arrayValue -> true
- ARRAY(3) with null arrayValue -> false (no log call)
- any other tag -> false (no log call)

- Branch conditions: tag == 3 -> payload-null check, payload != null
- Required callees:

- none

- Pseudocode:

```
    bool DynamicValueIsArray(DynamicValue this):
        return this.ValueType == ARRAY(3) and this.arrayValue != null
```

- Native evidence:

```
    1CFBF200  80 79 30 03               cmp      byte ptr [rcx + 0x30], 3
    1CFBF204  75 09                     jne      0x19cfbf20f
    1CFBF206  48 83 79 20 00            cmp      qword ptr [rcx + 0x20], 0
    1CFBF20B  0f 95 c0                  setne    al
    1CFBF20E  c3                        ret      
    1CFBF20F  31 c0                     xor      eax, eax
    1CFBF211  c3                        ret      
```

### DynamicValueIsMap (`get_IsMap`, method_index 74655)

- Primitive: `battle.ir.value.dynamic_value_is_map`; result `boolean`
- RVA `0x1CFBF250`; body 18 bytes /
  7 instructions / 1
  conditional branches / 0 calls
- Body sha256 `aaba88791efd49d810af7a9ffd8031de04d0bdae0ab0badfaa91bbe610147c17`
- Tag behavior:

- MAP(4) with non-null mapValue -> true
- MAP(4) with null mapValue -> false (no log call)
- any other tag -> false (no log call)

- Branch conditions: tag == 4 -> payload-null check, payload != null
- Required callees:

- none

- Pseudocode:

```
    bool DynamicValueIsMap(DynamicValue this):
        return this.ValueType == MAP(4) and this.mapValue != null
```

- Native evidence:

```
    1CFBF250  80 79 30 04               cmp      byte ptr [rcx + 0x30], 4
    1CFBF254  75 09                     jne      0x19cfbf25f
    1CFBF256  48 83 79 10 00            cmp      qword ptr [rcx + 0x10], 0
    1CFBF25B  0f 95 c0                  setne    al
    1CFBF25E  c3                        ret      
    1CFBF25F  31 c0                     xor      eax, eax
    1CFBF261  c3                        ret      
```

### DynamicValueIsNull (`get_IsNull`, method_index 74653)

- Primitive: `battle.ir.value.dynamic_value_is_null`; result `boolean`
- RVA `0x1CFBF620`; body 8 bytes /
  3 instructions / 0
  conditional branches / 0 calls
- Body sha256 `49adb1620f6a8421191f0be5e9ce9f8cd4c0eb49ddcf3024ae29ed0bbeecbb52`
- Tag behavior:

- NULL(6) -> true
- any other tag -> false

- Branch conditions: tag == 6
- Required callees:

- none

- Pseudocode:

```
    bool DynamicValueIsNull(DynamicValue this):
        return this.ValueType == NULL(6)
```

- Native evidence:

```
    1CFBF620  80 79 30 06               cmp      byte ptr [rcx + 0x30], 6
    1CFBF624  0f 94 c0                  sete     al
    1CFBF627  c3                        ret      
```


## 4. Skipped candidates

- 74611 .ctor (SKIP_WRAPPER): parameterless constructor wrapper
- 74612 .ctor (SKIP_WRAPPER): bool constructor wrapper
- 74613 .ctor (SKIP_WRAPPER): float32 constructor wrapper
- 74614 .ctor (SKIP_WRAPPER): float64 constructor wrapper
- 74615 .ctor (SKIP_WRAPPER): string constructor wrapper
- 74616 .ctor (SKIP_WRAPPER): int32 constructor wrapper
- 74617 .ctor (SKIP_WRAPPER): int64 constructor wrapper
- 74618 .ctor (SKIP_WRAPPER): array payload constructor wrapper
- 74619 .ctor (SKIP_WRAPPER): map payload constructor wrapper
- 74620 .cctor (SKIP_COMPLEX): static class initializer; 251 calls / 88 jumps, runtime infrastructure
- 74621 op_Implicit (SKIP_WRAPPER): op_Implicit(string) allocates a DynamicValue cell; allocation-shaped wrapper
- 74622 op_Implicit (SKIP_WRAPPER): op_Implicit(int32) allocates a DynamicValue cell; allocation-shaped wrapper
- 74623 op_Implicit (SKIP_WRAPPER): op_Implicit(int64) allocates a DynamicValue cell; allocation-shaped wrapper
- 74624 op_Implicit (SKIP_WRAPPER): op_Implicit(float32) allocates a DynamicValue cell; allocation-shaped wrapper
- 74625 op_Implicit (SKIP_WRAPPER): op_Implicit(float64) allocates a DynamicValue cell; allocation-shaped wrapper
- 74626 op_Implicit (SKIP_WRAPPER): op_Implicit(bool) allocates a DynamicValue cell; allocation-shaped wrapper
- 74627 op_Implicit (SKIP_WRAPPER): op_Implicit(map) allocates a DynamicValue cell; allocation-shaped wrapper
- 74628 op_Implicit (SKIP_WRAPPER): op_Implicit(array) allocates a DynamicValue cell; allocation-shaped wrapper
- 74629 ToString (SKIP_COMPLEX): ToString formatting dispatcher; 639 instructions, 57 calls, 33 jumps
- 74630 Equals (SKIP_WRAPPER): Equals(object) adds IL2CPP runtime type identity check then duplicates the recovered Equals(DynamicValue) switch; no new battle semantic
- 74631 GetHashCode (SKIP_COMPLEX): GetHashCode dispatcher; 195 instructions, 15 branches, 6 calls
- 74632 Equals (SKIP_WRAPPER): already recovered as battle.ir.value.dynamic_value_equals in vertical_slice_01.json
- 74635 get_FixPointValue (SKIP_COMPLEX): FixPoint framework: 89 instructions, 14 branches, range/shift encoding and two FixPoint global constants (0x95B1E00 / 0x95B1E60); exceeds single-callee batch budget
- 74641 get_ArrayValue (SKIP_WRAPPER): get_ArrayValue returns ObjectRef; current scalar-only trace contract would need a reference-result summary, deferred instead of special-cased
- 74642 get_MapValue (SKIP_WRAPPER): get_MapValue returns ObjectRef; current scalar-only trace contract would need a reference-result summary, deferred instead of special-cased
- 74643 _LogError (SKIP_COMPLEX): private logging helper; no value semantic
- 74644 _LogError (SKIP_COMPLEX): private logging helper; no value semantic
- 74645 _LogTypeMismatch (SKIP_COMPLEX): private logging helper; no value semantic
- 74646 _LogInvalidValue (SKIP_COMPLEX): private logging helper; no value semantic
- 74647 _EscapeString (SKIP_COMPLEX): string escaping helper; 150 instructions, 15 calls, not a gameplay value semantic
- 74649 get_IsInt (SKIP_WRAPPER): single tag comparison already covered by get_ValueType + selected tag predicates; excluded to respect batch value budget
- 74650 get_IsFloat (SKIP_WRAPPER): single tag comparison already covered by get_ValueType + selected tag predicates; excluded to respect batch value budget
- 74651 get_IsBool (SKIP_WRAPPER): single tag comparison already covered by get_ValueType + selected tag predicates; excluded to respect batch value budget
- 74652 get_IsString (SKIP_WRAPPER): single tag comparison already covered by get_ValueType + selected tag predicates; excluded to respect batch value budget
- 74656 get_longValue (SKIP_WRAPPER): raw unionValue reinterpreter without tag check; canonical representation is tag-typed and cannot expose stale union bytes for ARRAY/MAP/STRING cells
- 74657 get_doubleValue (SKIP_WRAPPER): raw unionValue reinterpreter without tag check; canonical representation is tag-typed and cannot expose stale union bytes for ARRAY/MAP/STRING cells
- 74658 get_boolValue (SKIP_WRAPPER): raw unionValue reinterpreter without tag check; canonical representation is tag-typed and cannot expose stale union bytes for ARRAY/MAP/STRING cells
- 74659 FromByteBinary (SKIP_SERIALIZATION): explicitly excluded FromByteBinary serialization semantic
- 74660 ToBinary (SKIP_SERIALIZATION): explicitly excluded ToBinary serialization semantic
- 74661 get__DebuggerDisplay (SKIP_COMPLEX): debugger-display formatter; 34 instructions, 4 calls, allocates debug string

## 5. Representation conflicts

- REPRESENTATION_CONFLICT_RECORDED_NO_CHANGE: For every representable input the native and canonical results agree; the unreachable native null-payload case is kept as a defensive runtime check.  No representation change is justified yet.

## 6. Known unknowns

- FieldDefinition provenance for the +0x30 ValueType tag byte
- Type-mismatch / invalid-value log helper internals (0x1CFD2950 / 0x1CFD2AB0); error paths only and value-neutral
- IL2CPP runtime class-init helper internals (0x3C6D0E0); one-time infrastructure on get_LongValue / get_DoubleValue
- get_FloatValue cvtsd2ss assumes default MXCSR round-to-nearest-even
- No E5 client-side runtime observation for any Batch 02 primitive
- Canonical DynamicValue cannot represent ARRAY/MAP cells with null payload pointers; IsArray/IsMap keep the native null-check defensively (REPRESENTATION_CONFLICT recorded, no representation change)

Machine-readable companion:
`data/semantics/4.4.54/dynamic_value_batch_02.json`.
