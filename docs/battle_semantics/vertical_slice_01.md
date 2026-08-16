# Battle Semantic Vertical Slice 01 — DynamicValue.Equals

> Final status: **`BATTLE_SEMANTIC = VERTICAL_SLICE_PROOF`**
> Game version: `4.4.54` (20260731-0529-BetaLive-15953205-OSBETAWin4.4.54-OSCb)
> Evidence level: `E4_STATIC_MACHINE_CODE`

## 1. Scope

This session recovers one small, generic, battle-relevant runtime primitive and
does not build a Sandbox, a full DynamicValue system, or any character skill
semantics. The recovered slice is the complete chain:

Serialized/Config runtime type `RPG.GameCore.DynamicValue`
→ FieldDefinition / MethodDefinition identity
→ native RVA
→ bounded native dataflow
→ semantic pseudocode
→ canonical Battle IR candidate `DynamicValueEquals`.

## 2. Candidate selection

Registry query (read-only, normalized 4.4.54 registries):

- battle-keyword flagged types: `14958`
- `RPG.GameCore` types / methods: `12433` /
  `45886`
- DynamicValue-family types: `160`

`ByCompareDynamicValue`, `ByDynamicValueDefined`, `SetDynamicValueBy*` etc.
were inspected first: their extra methods (`OJNNBEJLDIJ` /
`MGMEGEDLMAK`, `LJACLBNEEEB` / `EOJLPDGNHEK`) are wrapper/impl
**serialization** pairs, so those types cannot provide a battle-semantic
vertical slice by themselves. `DynamicValue.FromByteBinary` / `ToBinary` were
rejected for the same reason.

Shortlist:

| # | Status | Candidate | method_index | native_rva | size(B) | callees | complexity |
|---:|---|---|---:|---:|---:|---:|---|
| 1 | PRIMARY_CANDIDATE | RPG.GameCore.DynamicValue.Equals | 74632 | 0x1CFBE9E0 | 240 | 2 | LOW_MEDIUM |
| 2 | BACKUP_CANDIDATE | RPG.GameCore.DynamicValue.get_IntValue | 74637 | 0x1CFBF070 | 80 | 1 | LOW |
| 3 | BACKUP_CANDIDATE | RPG.GameCore.DynamicValue.get_FloatValue | 74633 | 0x1CFBED90 | 96 | 1 | LOW |
| 4 | CONSIDERED | RPG.GameCore.DynamicValue.get_BoolValue | 74636 | 0x1CFBF010 | 96 | 2 | LOW |
| 5 | CONSIDERED | RPG.GameCore.DynamicValue.Equals | 74630 | 0x1CFBE8F0 | 240 | 1 | LOW_MEDIUM |
| 6 | CONSIDERED | RPG.GameCore.DynamicValue.get_FixPointValue | 74635 | 0x1CFBEEA0 | 368 | 1 | MEDIUM |
| 7 | CONSIDERED | RPG.GameCore.DynamicValue.get_LongValue | 74639 | 0x1CFBF110 | 128 | 3 | LOW |

PRIMARY = `DynamicValue.Equals(DynamicValue)`.

Why: it is not serialization; it is a complete tag-aware compare helper with a
six-way switch, one normal-path callee, zero writes, no external battle state,
and its only deeper callee (`System.String.EqualsHelper`) is already identified
by the method registry.

## 3. Source identity (4.4.54)

| Item | Value |
|---|---|
| Runtime type | `RPG.GameCore.DynamicValue` (type_index `10822`) |
| Method | `Equals` (method_index `74632`) |
| Parameter relation | 1 parameter, parameter_index `85717`, type_reference `25310` = DynamicValue |
| Return | type_reference `424` = System.Boolean |
| native RVA | `0x1CFBE9E0` |
| mapping_kind | `DIRECT_NATIVE` |

Provenance:

- GameAssembly: `D:\StarRail_4.4.53\GameAssembly.dll`
  - sha256 `7b44379bf69352022cb3437b03431ddc558ffb34e3d98e7144200f37e8c837cc`
- global-metadata: sha256 `4bfdd6eaed092c1a70431cf32946903e41f716beeb1322291fa1ab1c6dbb33a7`
- Version source: sha256 `ebee1005eb0b18bf33dbbc3e6f05448649b86371d460bd523d9f1df48cbf161a`

## 4. Field map

`RPG.GameCore.DynamicValue` layout recovered from the normalized field
registry plus native accessor evidence:

| Offset | Width | Registry name | Role in Equals | Evidence |
|---|---:|---|---|---|
| +0x10 | 8 | mapValue | mapValue payload (pointer identity in Equals) | CONFIRMED |
| +0x18 | 8 | stringValue | stringValue payload (content equality in Equals) | CONFIRMED |
| +0x20 | 8 | arrayValue | arrayValue payload (pointer identity in Equals) | CONFIRMED |
| +0x28 | 8 | unionValue | unionValue numeric/bool payload | CONFIRMED |
| +0x30 | 1 | (registry row missing) | ValueType tag byte | SUPPORTED |

`DynamicValueType` enum values (type_index 10824):

| Ordinal | Name |
|---:|---|
| 0 | INT |
| 1 | FLOAT |
| 2 | BOOL |
| 3 | ARRAY |
| 4 | MAP |
| 5 | STRING |
| 6 | NULL |

Note: the `+0x30` tag byte is read by every native accessor and written by
every constructor, but no normalized FieldDefinition row for type 10822
declares it. For this slice it is `SUPPORTED` from native evidence; its
metadata declaring-row provenance stays UNKNOWN.

## 5. Native evidence

- Body RVA `0x1CFBE9E0`, body bytes `213`
  (method slot estimate 0xF0), `66` instructions.
- Body sha256 `30fa402326b7420f4e4924c7bf65a4c5038f6bfd61c3b654826aa9cfaa860371`.
- Method code table slot `74632` =
  `0x19CFBE9E0` (image base `0x180000000`, matches body RVA).
- Jump table RVA `0x1CFBEAB8`:
  `-167, -144, -120, -97, -81, -65` for cases INT..STRING.
- ABI: `x64: this=rcx, other=rdx, bool return=al`.

Bounded disassembly (left column and RIP comments are RVAs; branch/call
operands are raw VAs with image base `0x180000000`):

```
    1CFBE9E0  48 83 ec 28               sub      rsp, 0x28
    1CFBE9E4  48 85 d2                  test     rdx, rdx
    1CFBE9E7  0f 84 c2 00 00 00         je       0x19cfbeaaf
    1CFBE9ED  0f b6 41 30               movzx    eax, byte ptr [rcx + 0x30]
    1CFBE9F1  3a 42 30                  cmp      al, byte ptr [rdx + 0x30]
    1CFBE9F4  75 2b                     jne      0x19cfbea21
    1CFBE9F6  83 f8 05                  cmp      eax, 5
    1CFBE9F9  0f 87 a2 00 00 00         ja       0x19cfbeaa1
    1CFBE9FF  89 c0                     mov      eax, eax
    1CFBEA01  4c 8d 05 b0 00 00 00      lea      r8, [rip + 0xb0] ; [rip]->0x19CFBEAB8 (rva 0x1CFBEAB8)
    1CFBEA08  49 63 04 80               movsxd   rax, dword ptr [r8 + rax*4]
    1CFBEA0C  4c 01 c0                  add      rax, r8
    1CFBEA0F  ff e0                     jmp      rax
    1CFBEA11  48 8b 41 28               mov      rax, qword ptr [rcx + 0x28]
    1CFBEA15  48 3b 42 28               cmp      rax, qword ptr [rdx + 0x28]
    1CFBEA19  0f 94 c0                  sete     al
    1CFBEA1C  48 83 c4 28               add      rsp, 0x28
    1CFBEA20  c3                        ret      
    1CFBEA21  31 c0                     xor      eax, eax
    1CFBEA23  48 83 c4 28               add      rsp, 0x28
    1CFBEA27  c3                        ret      
    1CFBEA28  f2 0f 10 42 28            movsd    xmm0, qword ptr [rdx + 0x28]
    1CFBEA2D  f2 0f c2 41 28 00         cmpeqsd  xmm0, qword ptr [rcx + 0x28]
    1CFBEA33  66 48 0f 7e c0            movq     rax, xmm0
    1CFBEA38  83 e0 01                  and      eax, 1
    1CFBEA3B  48 83 c4 28               add      rsp, 0x28
    1CFBEA3F  c3                        ret      
    1CFBEA40  48 83 79 28 01            cmp      qword ptr [rcx + 0x28], 1
    1CFBEA45  0f 95 c1                  setne    cl
    1CFBEA48  48 83 7a 28 01            cmp      qword ptr [rdx + 0x28], 1
    1CFBEA4D  0f 94 c0                  sete     al
    1CFBEA50  30 c8                     xor      al, cl
    1CFBEA52  48 83 c4 28               add      rsp, 0x28
    1CFBEA56  c3                        ret      
    1CFBEA57  48 8b 41 20               mov      rax, qword ptr [rcx + 0x20]
    1CFBEA5B  48 3b 42 20               cmp      rax, qword ptr [rdx + 0x20]
    1CFBEA5F  0f 94 c0                  sete     al
    1CFBEA62  48 83 c4 28               add      rsp, 0x28
    1CFBEA66  c3                        ret      
    1CFBEA67  48 8b 41 10               mov      rax, qword ptr [rcx + 0x10]
    1CFBEA6B  48 3b 42 10               cmp      rax, qword ptr [rdx + 0x10]
    1CFBEA6F  0f 94 c0                  sete     al
    1CFBEA72  48 83 c4 28               add      rsp, 0x28
    1CFBEA76  c3                        ret      
    1CFBEA77  48 8b 49 18               mov      rcx, qword ptr [rcx + 0x18]
    1CFBEA7B  48 8b 52 18               mov      rdx, qword ptr [rdx + 0x18]
    1CFBEA7F  48 39 d1                  cmp      rcx, rdx
    1CFBEA82  74 24                     je       0x19cfbeaa8
    1CFBEA84  31 c0                     xor      eax, eax
    1CFBEA86  48 85 c9                  test     rcx, rcx
    1CFBEA89  74 98                     je       0x19cfbea23
    1CFBEA8B  48 85 d2                  test     rdx, rdx
    1CFBEA8E  74 93                     je       0x19cfbea23
    1CFBEA90  8b 41 10                  mov      eax, dword ptr [rcx + 0x10]
    1CFBEA93  3b 42 10                  cmp      eax, dword ptr [rdx + 0x10]
    1CFBEA96  75 09                     jne      0x19cfbeaa1
    1CFBEA98  48 83 c4 28               add      rsp, 0x28
    1CFBEA9C  e9 ef 6e ba fe            jmp      0x19bb65990
    1CFBEAA1  31 c0                     xor      eax, eax
    1CFBEAA3  48 83 c4 28               add      rsp, 0x28
    1CFBEAA7  c3                        ret      
    1CFBEAA8  b0 01                     mov      al, 1
    1CFBEAAA  48 83 c4 28               add      rsp, 0x28
    1CFBEAAE  c3                        ret      
    1CFBEAAF  e8 8c 38 c4 e6            call     0x183c02340
    1CFBEAB4  cc                        int3     
```

The only normal-path tail-call target is `System.String.EqualsHelper`
(method_index `3485`, RVA `0x1BB65990`), a
length-prefixed ordinal UTF-16 content equality helper:

```
    1BB65990  48 83 ec 28               sub      rsp, 0x28
    1BB65994  48 85 c9                  test     rcx, rcx
    1BB65997  0f 84 99 00 00 00         je       0x19bb65a36
    1BB6599D  48 85 d2                  test     rdx, rdx
    1BB659A0  0f 84 95 00 00 00         je       0x19bb65a3b
    1BB659A6  44 8b 49 10               mov      r9d, dword ptr [rcx + 0x10]
    1BB659AA  48 83 c1 14               add      rcx, 0x14
    1BB659AE  48 83 c2 14               add      rdx, 0x14
    1BB659B2  41 83 f9 0c               cmp      r9d, 0xc
    1BB659B6  7c 68                     jl       0x19bb65a20
    1BB659B8  0f 1f 84 00 00 00 00 00   nop      dword ptr [rax + rax]
    1BB659C0  48 8b 01                  mov      rax, qword ptr [rcx]
    1BB659C3  48 3b 02                  cmp      rax, qword ptr [rdx]
    1BB659C6  75 67                     jne      0x19bb65a2f
    1BB659C8  48 8b 41 08               mov      rax, qword ptr [rcx + 8]
    1BB659CC  48 3b 42 08               cmp      rax, qword ptr [rdx + 8]
    1BB659D0  75 5d                     jne      0x19bb65a2f
    1BB659D2  48 8b 41 10               mov      rax, qword ptr [rcx + 0x10]
    1BB659D6  48 3b 42 10               cmp      rax, qword ptr [rdx + 0x10]
    1BB659DA  75 53                     jne      0x19bb65a2f
    1BB659DC  48 83 c1 18               add      rcx, 0x18
    1BB659E0  48 83 c2 18               add      rdx, 0x18
    1BB659E4  45 8d 41 f4               lea      r8d, [r9 - 0xc]
    1BB659E8  41 83 f9 18               cmp      r9d, 0x18
    1BB659EC  45 89 c1                  mov      r9d, r8d
    1BB659EF  7d cf                     jge      0x19bb659c0
    1BB659F1  45 85 c0                  test     r8d, r8d
    1BB659F4  7e 32                     jle      0x19bb65a28
    1BB659F6  41 83 c0 02               add      r8d, 2
    1BB659FA  66 0f 1f 44 00 00         nop      word ptr [rax + rax]
    1BB65A00  8b 01                     mov      eax, dword ptr [rcx]
    1BB65A02  3b 02                     cmp      eax, dword ptr [rdx]
    1BB65A04  0f 94 c0                  sete     al
    1BB65A07  75 12                     jne      0x19bb65a1b
    1BB65A09  48 83 c1 04               add      rcx, 4
    1BB65A0D  48 83 c2 04               add      rdx, 4
    1BB65A11  41 83 c0 fe               add      r8d, -2
    1BB65A15  41 83 f8 03               cmp      r8d, 3
    1BB65A19  7d e5                     jge      0x19bb65a00
    1BB65A1B  48 83 c4 28               add      rsp, 0x28
    1BB65A1F  c3                        ret      
    1BB65A20  45 89 c8                  mov      r8d, r9d
    1BB65A23  45 85 c0                  test     r8d, r8d
    1BB65A26  7f ce                     jg       0x19bb659f6
    1BB65A28  b0 01                     mov      al, 1
    1BB65A2A  48 83 c4 28               add      rsp, 0x28
    1BB65A2E  c3                        ret      
    1BB65A2F  31 c0                     xor      eax, eax
    1BB65A31  48 83 c4 28               add      rsp, 0x28
    1BB65A35  c3                        ret      
    1BB65A36  e8 05 c9 09 e8            call     0x183c02340
    1BB65A3B  e8 00 c9 09 e8            call     0x183c02340
```

## 6. Semantic pseudocode (ABI-independent)

```
    bool Equals(DynamicValue other):
        if other == null:
            throw NullReferenceException            # CONFIRMED
        t = this.ValueType                         # byte @ +0x30, CONFIRMED
        if t != other.ValueType:
            return false                            # CONFIRMED
        if t > 5:                                   # NULL(6) or invalid tag
            return false                            # CONFIRMED
        switch t:                                   # jump table @ 0x1CFBEAB8
            case INT(0):
                return this.unionValue == other.unionValue   # CONFIRMED
            case FLOAT(1):
                return ieee_double_equal(this.unionValue, other.unionValue)
                # cmpeqsd -> false for NaN          # CONFIRMED
            case BOOL(2):
                return (this.unionValue == 1) == (other.unionValue == 1)
                # both sides normalized to bool      # CONFIRMED
            case ARRAY(3):
                return this.arrayValue == other.arrayValue
                # reference equality only             # CONFIRMED
            case MAP(4):
                return this.mapValue == other.mapValue
                # reference equality only             # CONFIRMED
            case STRING(5):
                a = this.stringValue
                b = other.stringValue
                if a == b: return true               # CONFIRMED
                if a == null or b == null: return false  # CONFIRMED
                if a.Length != b.Length: return false   # CONFIRMED
                return System.String.EqualsHelper(a, b)
                # ordinal content equality           # CONFIRMED
        return false                               # unreachable fallback
```

Labels: `CONFIRMED` = direct machine-code evidence plus registry identity;
`SUPPORTED` = native evidence without a matching metadata declaration row;
`UNKNOWN` = not followed/not needed.

## 7. State dependency model

- reads: the two `DynamicValue` operands only (and string content for STRING).
- writes: none.
- global state: none.
- return: `bool`.
- determinism: `DETERMINISTIC`.

## 8. Canonical Battle IR candidate (draft)

```json
{
  "primitive_id": "battle.ir.value.dynamic_value_equals",
  "semantic_name": "DynamicValueEquals",
  "description": "Tag-aware equality over two RPG.GameCore.DynamicValue cells",
  "inputs": [
    {
      "name": "lhs",
      "type": "DynamicValue"
    },
    {
      "name": "rhs",
      "type": "DynamicValue"
    }
  ],
  "context_reads": [
    "lhs",
    "rhs"
  ],
  "context_writes": [],
  "result": "boolean",
  "determinism": "DETERMINISTIC",
  "source_runtime_type": "RPG.GameCore.DynamicValue",
  "source_method": "Equals",
  "source_method_index": 74632,
  "source_native_rva": "0x1CFBE9E0",
  "evidence_level": "E4_STATIC_MACHINE_CODE",
  "provenance_note": "RVA is provenance only; runtime logic must not depend on it",
  "unknowns": [
    "FieldDefinition provenance for the +0x30 ValueType tag byte",
    "Generic IL2CPP null-check helper internals (error path only)",
    "No E5 client-side runtime observation yet (out of scope for this slice)"
  ]
}
```

`source_native_rva` is provenance/evidence only and must not be part of runtime
IR logic.

## 9. Unknowns

- FieldDefinition provenance for the +0x30 ValueType tag byte
- Generic IL2CPP null-check helper internals (error path only)
- No E5 client-side runtime observation yet (out of scope for this slice)

## 10. E4 success criteria

| Criterion | Status |
|---|---|
| A Runtime Type identity | PASS |
| B MethodDefinition identity | PASS |
| C native RVA | PASS |
| D native body dataflow | PASS |
| E inputs / outputs | PASS |
| F read / write set | PASS |
| G branches | PASS |
| H deterministic pseudocode | PASS |
| I generic IR primitive | PASS |

Machine-readable companion:
`data/semantics/4.4.54/vertical_slice_01.json`.
