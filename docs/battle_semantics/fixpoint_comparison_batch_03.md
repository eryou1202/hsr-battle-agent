# Battle Semantic FixPoint Comparison Batch 03

> Final status: **`BATTLE_SEMANTIC = FIXPOINT_COMPARISON_BATCH_03_PROOF`**
> Game version: `4.4.54` (20260731-0529-BetaLive-15953205-OSBETAWin4.4.54-OSCb)
> Evidence level: `E4_STATIC_MACHINE_CODE` (all accepted primitives)
> Artifact schema: `battle_semantics_batch/1`

## 1. Scope

This batch recovers the game's real comparison core: six mode-aware
`RPG.GameCore.FixPoint` comparison operators, one signed int32 -> FixPoint
raw-encoding bridge, and three boxed sign/zero predicate leaves.  It does
**not** recover the `TaskContext.Evaluate(bool)` predicate graph dispatcher,
FixPoint arithmetic, serializer wrappers, or any `ByCompareDynamicValue`
content pipeline.

Composition shape proven by this batch plus existing artifacts:

```text
DynamicValue (INT)
  -> DynamicValueToInt32        (Batch 02, reused)
  -> FixPointFromInt32          (Batch 03)
  -> FixPoint{Less,LessEqual,Equal,NotEqual,Greater,GreaterEqual}
  -> boolean
```

## 2. Candidate table

| method_index | candidate | native_rva | size(B) | insn | branch | callee | classification | reason |
|---:|---|---|---:|---:|---:|---:|---|---|
| 68214 | RPG.GameCore.FixPoint.op_Equality | 0x1D661340 | 144 | 48 | 3 | 0 | ACCEPT | exact bounded native body; no normal-path callees; no context reads beyond operands |
| 68215 | RPG.GameCore.FixPoint.op_Inequality | 0x1D664520 | 144 | 48 | 3 | 0 | ACCEPT | exact bounded native body; no normal-path callees; no context reads beyond operands |
| 68216 | RPG.GameCore.FixPoint.op_GreaterThan | 0x1D6645B0 | 144 | 48 | 3 | 0 | ACCEPT | exact bounded native body; no normal-path callees; no context reads beyond operands |
| 68217 | RPG.GameCore.FixPoint.op_LessThan | 0x1D6646D0 | 138 | 45 | 3 | 0 | ACCEPT | exact bounded native body; no normal-path callees; no context reads beyond operands |
| 68218 | RPG.GameCore.FixPoint.op_GreaterThanOrEqual | 0x1D660C50 | 144 | 48 | 3 | 0 | ACCEPT | exact bounded native body; no normal-path callees; no context reads beyond operands |
| 68219 | RPG.GameCore.FixPoint.op_LessThanOrEqual | 0x1D664760 | 144 | 48 | 3 | 0 | ACCEPT | exact bounded native body; no normal-path callees; no context reads beyond operands |
| 68256 | RPG.GameCore.FixPoint.op_Implicit | 0x1D664F30 | 40 | 11 | 0 | 0 | ACCEPT | exact bounded native body; no normal-path callees; no context reads beyond operands |
| 68173 | RPG.GameCore.FixPoint.get_IsZero | 0x1D663050 | 8 | 3 | 0 | 0 | ACCEPT | exact bounded native body; no normal-path callees; no context reads beyond operands |
| 68174 | RPG.GameCore.FixPoint.get_IsNegative | 0x1D663060 | 8 | 3 | 0 | 0 | ACCEPT | exact bounded native body; no normal-path callees; no context reads beyond operands |
| 68175 | RPG.GameCore.FixPoint.get_IsPositive | 0x1D663070 | 11 | 3 | 0 | 0 | ACCEPT | exact bounded native body; no normal-path callees; no context reads beyond operands |
| 133350 | RPG.GameCore.ByCompareDynamicValue..ctor | 0x1CE2F1C0 | 57 | 15 | 1 | 2 | SKIP_SERIALIZATION | all five declared methods are ctor/serializer wrapper shapes; no Check/Evaluate/Compare/Execute/IsSatisfied runtime method exists on this runtime type |
| 133351 | RPG.GameCore.ByCompareDynamicValue.OJNNBEJLDIJ | 0x1CE2F160 | 92 | 26 | 1 | 3 | SKIP_SERIALIZATION | wrapper/impl serializer pair (historical 4.4.54 evidence) |
| 133352 | RPG.GameCore.ByCompareDynamicValue.MGMEGEDLMAK | 0x1CE2F200 | 755 | 163 | 34 | 33 | SKIP_SERIALIZATION | wrapper/impl serializer pair (historical 4.4.54 evidence) |
| 133353 | RPG.GameCore.ByCompareDynamicValue.LJACLBNEEEB | 0x1CE2F500 | 92 | 26 | 1 | 3 | SKIP_SERIALIZATION | wrapper/impl serializer pair (historical 4.4.54 evidence) |
| 133354 | RPG.GameCore.ByCompareDynamicValue.EOJLPDGNHEK | 0x1CE2F560 | 509 | 121 | 27 | 7 | SKIP_SERIALIZATION | wrapper/impl serializer pair (historical 4.4.54 evidence) |
| 133355 | RPG.GameCore.ByCompareValue..ctor | 0x1CE7C770 | 9 | 3 | 0 | 0 | SKIP_SERIALIZATION | runtime class contains only ctor/wrapper/impl serialization methods; comparison semantics live in the FixPoint compare core recovered by this batch |
| 125477 | RPG.GameCore.ByDynamicValueDefined..ctor | 0x1CE899F0 | 5 | 2 | 0 | 0 | SKIP_SERIALIZATION | same serializer/wrapper family; no non-serialization runtime predicate method on the type |
| 132841 | RPG.GameCore.PredicateConfig..ctor | 0x1D2CA150 | 510 | 124 | 20 | 9 | SKIP_SERIALIZATION | config runtime type with only ctor/wrapper/impl serializer methods |
| 106308 | RPG.GameCore.CondCompareConfig..ctor | 0x1CF67770 | 8 | 2 | 0 | 0 | SKIP_SERIALIZATION | config runtime type with only ctor/wrapper/impl serializer methods |
| 505866 | RPG.GameCore.TaskContext.Evaluate | 0xE6F0A60 | 347 | 108 | 14 | 11 | SKIP_CONTEXT_HEAVY | bool predicate dispatcher: reads TaskContext evaluator dictionary, hashes a string key, calls dictionary/index helpers and a tail dispatcher; call graph exceeds the batch budget |
| 505884 | RPG.GameCore.TaskContext.EvaluateOrDefault | 0xE6F24D0 | 93 | 33 | 3 | 2 | SKIP_WRAPPER | null -> false, otherwise tailcall TaskContext.Evaluate(bool); no independent semantic beyond the skipped heavy dispatcher |
| 135383 | RPG.GameCore.ValueEvaluatorConfig.FEIIDFFOICL | 0x1D606570 | 197 | 63 | 7 | 0 | SKIP_WRAPPER | compares a wrapped object field [rcx+0x20] to a FixPoint raw; current Kernel has no wrapper-object representation and the compare core is already recovered as FixPointEqual |
| 135384 | RPG.GameCore.ValueEvaluatorConfig.DLDBLNNPHKE | 0x1D606640 | 197 | 63 | 7 | 0 | SKIP_WRAPPER | same wrapped-field compare pattern as 135383; no additional semantic operation |
| 68257 | RPG.GameCore.FixPoint.op_Implicit | 0x1D668000 | 28 | 8 | 0 | 0 | SKIP_WRAPPER | same standard/extended encoding core as accepted 68256; native ABI shows an unsigned 32-bit entry (cmovb threshold) and is deferred to respect the batch value budget |
| 68147 | RPG.GameCore.FixPoint.ToBoolean | 0x1D6628B0 | 71 | 16 | 1 | 4 | SKIP_COMPLEX | one-time IL2CPP class-init wrapper + interface conversion path; not a leaf predicate |
| 68258 | RPG.GameCore.FixPoint.Approximately | 0x1D668020 | 326 | 93 | 11 | 1 | SKIP_COMPLEX | epsilon/global-constant-dependent approximate comparison; larger body and more branches than the exact six-operator core |
| 68259 | RPG.GameCore.FixPoint.IsAlmostZero | 0x1D668170 | 322 | 90 | 11 | 0 | SKIP_COMPLEX | epsilon-dependent helper; outside this batch's exact-comparison core |
| 68185 | RPG.GameCore.FixPoint.BothStandardMode | 0x1D663220 | 9 | 4 | 0 | 0 | SKIP_COMPLEX | mode helper, not a predicate/compare primitive; recovered compare code already handles mixed modes directly |
| 88610 | RPG.GameCore.DialogueConditionRow.CompareItemState | 0x1CF94880 | 26 | 12 | 2 | 0 | SKIP_NON_BATTLE | dialogue content condition comparison, not battle gameplay semantic |
| 546444 | RPG.Client.ConditionCheckerUtil.DoCheckConditions | 0xCC3A300 | 159 | 51 | 8 | 6 | SKIP_CONTEXT_HEAVY | client condition list dispatcher; call graph and client state dependencies exceed the batch budget |
| 102771 | RPG.GameCore.CheckPredicateAxis..ctor | 0x1CF125B0 | 1 | 1 | 0 | 0 | SKIP_SERIALIZATION | serializer-shaped runtime type; no leaf predicate body |

## 3. FixPoint raw encoding and comparison semantics (recovered in this batch)

- `type_index 9881`, single instance field `m_rawValue` (field_index 40768).
- bit0 is the mode flag: `0 = STANDARD`, `1 = EXTENDED`.
- canonical STANDARD raw = `signed64 << 0x21`.
- canonical EXTENDED raw = `(signed64 << 0x1A) | 1`.
- mixed-mode comparison normalizes with a 7-bit arithmetic shift and keeps a
  low-7-bit fraction tie-break exactly as the native bodies do.
- **Signedness:** every same-mode comparison and every mixed-mode normalized
  comparison is a signed 64-bit comparison.  `get_IsNegative` reads bit 63;
  `get_IsPositive` tests `signed(raw & ~1) > 0`.
- **Special mode / sentinel:** `NONE_OBSERVED`.  The accepted bodies contain no
  NaN / infinity / saturation / sentinel branch; every raw qword participates
  in the same total order.
- **Proven comparison coverage:** all six operators over the full qword raw
  domain, including non-canonical mixed-mode and low-7-bit-fraction inputs.
- **Sandbox-constructible domain:** canonical raw values produced by
  `FixPointFromInt32(int32)` only.  Comparison primitives accept full qword
  raw inputs for differential verification, but the IR constructor set stays
  minimal and does not grow into a full FixPoint framework.

## 4. Accepted primitives

### FixPointEqual (`op_Equality`, method_index 68214)

- Primitive: `battle.ir.compare.fixpoint_equal`; result `boolean`
- RVA `0x1D661340`; body 144 bytes /
  48 instructions / 3
  conditional branches / 0 calls
- Body sha256 `3963434ce2135d416a79792abd0aeef934d304aa2354c75cff534d366a9a6cdc`
- ABI: `x64: lhs=rcx (raw qword), rhs=rdx (raw qword), bool return=al`
- Operation: `return FixPointCompareRaw(lhs, rhs) == 0`
- Field reads:
- none
- Branch conditions:
- lhs mode flag bit0 == 0 and rhs mode flag bit0 == 0 -> compare raw qwords directly
- lhs mode flag bit0 == 0 and rhs mode flag bit0 == 1 -> compare sar(lhs,7) with rhs & ~1; tie broken by lhs low 7 bits
- lhs mode flag bit0 == 1 and rhs mode flag bit0 == 0 -> compare lhs & ~1 with sar(rhs,7); tie broken by rhs low 7 bits
- both mode flag bit0 == 1 -> compare (lhs & ~1) with (rhs & ~1)
- Required callees:

- none

- Pseudocode:

```
    int FixPointCompareRaw(lhs, rhs):               # consolidated native dataflow, not a callee
        le = lhs & 1; re = rhs & 1                  # mode flags: 0=STANDARD, 1=EXTENDED
        if le == 1 and re == 0:
            c = sign64((lhs & ~1) - sar64(rhs, 7))
            if c == 0: c = -1 if (rhs & 0x7F) != 0 else 0
            return c
        if le == 0 and re == 1:
            c = sign64(sar64(lhs, 7) - (rhs & ~1))
            if c == 0: c = 1 if (lhs & 0x7F) != 0 else 0
            return c
        if le == 0 and re == 0: return sign64(lhs - rhs)
        return sign64((lhs & ~1) - (rhs & ~1))
    bool FixPointEqual(lhs, rhs):
        return FixPointCompareRaw(lhs, rhs) == 0   # native: sete
```

- Native evidence:

```
    1D661340  f6 c1 01                  test     cl, 1
    1D661343  75 36                     jne      0x19d66137b
    1D661345  f6 c2 01                  test     dl, 1
    1D661348  74 6d                     je       0x19d6613b7
    1D66134A  48 83 e2 fe               and      rdx, 0xfffffffffffffffe
    1D66134E  48 89 c8                  mov      rax, rcx
    1D661351  48 c1 f8 07               sar      rax, 7
    1D661355  45 31 c0                  xor      r8d, r8d
    1D661358  48 39 d0                  cmp      rax, rdx
    1D66135B  41 0f 9f c0               setg     r8b
    1D66135F  ba ff ff ff ff            mov      edx, 0xffffffff
    1D661364  41 0f 4d d0               cmovge   edx, r8d
    1D661368  31 c0                     xor      eax, eax
    1D66136A  f6 c1 7f                  test     cl, 0x7f
    1D66136D  0f 95 c0                  setne    al
    1D661370  85 d2                     test     edx, edx
    1D661372  0f 45 c2                  cmovne   eax, edx
    1D661375  85 c0                     test     eax, eax
    1D661377  0f 94 c0                  sete     al
    1D66137A  c3                        ret      
    1D66137B  48 83 e1 fe               and      rcx, 0xfffffffffffffffe
    1D66137F  f6 c2 01                  test     dl, 1
    1D661382  75 2f                     jne      0x19d6613b3
    1D661384  48 89 d0                  mov      rax, rdx
    1D661387  48 c1 f8 07               sar      rax, 7
    1D66138B  45 31 c0                  xor      r8d, r8d
    1D66138E  48 39 c8                  cmp      rax, rcx
    1D661391  41 0f 9f c0               setg     r8b
    1D661395  b9 ff ff ff ff            mov      ecx, 0xffffffff
    1D66139A  41 0f 4d c8               cmovge   ecx, r8d
    1D66139E  31 c0                     xor      eax, eax
    1D6613A0  f6 c2 7f                  test     dl, 0x7f
    1D6613A3  0f 95 c0                  setne    al
    1D6613A6  85 c9                     test     ecx, ecx
    1D6613A8  0f 45 c1                  cmovne   eax, ecx
    1D6613AB  f7 d8                     neg      eax
    1D6613AD  85 c0                     test     eax, eax
    1D6613AF  0f 94 c0                  sete     al
    1D6613B2  c3                        ret      
    1D6613B3  48 83 e2 fe               and      rdx, 0xfffffffffffffffe
    1D6613B7  45 31 c0                  xor      r8d, r8d
    1D6613BA  48 39 d1                  cmp      rcx, rdx
    1D6613BD  41 0f 9f c0               setg     r8b
    1D6613C1  b8 ff ff ff ff            mov      eax, 0xffffffff
    1D6613C6  41 0f 4d c0               cmovge   eax, r8d
    1D6613CA  85 c0                     test     eax, eax
    1D6613CC  0f 94 c0                  sete     al
    1D6613CF  c3                        ret      
```

### FixPointNotEqual (`op_Inequality`, method_index 68215)

- Primitive: `battle.ir.compare.fixpoint_not_equal`; result `boolean`
- RVA `0x1D664520`; body 144 bytes /
  48 instructions / 3
  conditional branches / 0 calls
- Body sha256 `1eaefceff08ec26448664713c68e48fb0995b0ca4f0624c453e7b587afff3274`
- ABI: `x64: lhs=rcx (raw qword), rhs=rdx (raw qword), bool return=al`
- Operation: `return FixPointCompareRaw(lhs, rhs) != 0`
- Field reads:
- none
- Branch conditions:
- same mode -> raw qword signed comparison; mixed mode -> 7-bit-shifted normalization
- mixed-mode equality tie is broken by the standard-mode low 7 fraction bits
- Required callees:

- none

- Pseudocode:

```
    int FixPointCompareRaw(lhs, rhs):               # consolidated native dataflow, not a callee
        le = lhs & 1; re = rhs & 1                  # mode flags: 0=STANDARD, 1=EXTENDED
        if le == 1 and re == 0:
            c = sign64((lhs & ~1) - sar64(rhs, 7))
            if c == 0: c = -1 if (rhs & 0x7F) != 0 else 0
            return c
        if le == 0 and re == 1:
            c = sign64(sar64(lhs, 7) - (rhs & ~1))
            if c == 0: c = 1 if (lhs & 0x7F) != 0 else 0
            return c
        if le == 0 and re == 0: return sign64(lhs - rhs)
        return sign64((lhs & ~1) - (rhs & ~1))
    bool FixPointNotEqual(lhs, rhs):
        return FixPointCompareRaw(lhs, rhs) != 0   # native: setne
```

- Native evidence:

```
    1D664520  f6 c1 01                  test     cl, 1
    1D664523  75 36                     jne      0x19d66455b
    1D664525  f6 c2 01                  test     dl, 1
    1D664528  74 6d                     je       0x19d664597
    1D66452A  48 83 e2 fe               and      rdx, 0xfffffffffffffffe
    1D66452E  48 89 c8                  mov      rax, rcx
    1D664531  48 c1 f8 07               sar      rax, 7
    1D664535  45 31 c0                  xor      r8d, r8d
    1D664538  48 39 d0                  cmp      rax, rdx
    1D66453B  41 0f 9f c0               setg     r8b
    1D66453F  ba ff ff ff ff            mov      edx, 0xffffffff
    1D664544  41 0f 4d d0               cmovge   edx, r8d
    1D664548  31 c0                     xor      eax, eax
    1D66454A  f6 c1 7f                  test     cl, 0x7f
    1D66454D  0f 95 c0                  setne    al
    1D664550  85 d2                     test     edx, edx
    1D664552  0f 45 c2                  cmovne   eax, edx
    1D664555  85 c0                     test     eax, eax
    1D664557  0f 95 c0                  setne    al
    1D66455A  c3                        ret      
    1D66455B  48 83 e1 fe               and      rcx, 0xfffffffffffffffe
    1D66455F  f6 c2 01                  test     dl, 1
    1D664562  75 2f                     jne      0x19d664593
    1D664564  48 89 d0                  mov      rax, rdx
    1D664567  48 c1 f8 07               sar      rax, 7
    1D66456B  45 31 c0                  xor      r8d, r8d
    1D66456E  48 39 c8                  cmp      rax, rcx
    1D664571  41 0f 9f c0               setg     r8b
    1D664575  b9 ff ff ff ff            mov      ecx, 0xffffffff
    1D66457A  41 0f 4d c8               cmovge   ecx, r8d
    1D66457E  31 c0                     xor      eax, eax
    1D664580  f6 c2 7f                  test     dl, 0x7f
    1D664583  0f 95 c0                  setne    al
    1D664586  85 c9                     test     ecx, ecx
    1D664588  0f 45 c1                  cmovne   eax, ecx
    1D66458B  f7 d8                     neg      eax
    1D66458D  85 c0                     test     eax, eax
    1D66458F  0f 95 c0                  setne    al
    1D664592  c3                        ret      
    1D664593  48 83 e2 fe               and      rdx, 0xfffffffffffffffe
    1D664597  45 31 c0                  xor      r8d, r8d
    1D66459A  48 39 d1                  cmp      rcx, rdx
    1D66459D  41 0f 9f c0               setg     r8b
    1D6645A1  b8 ff ff ff ff            mov      eax, 0xffffffff
    1D6645A6  41 0f 4d c0               cmovge   eax, r8d
    1D6645AA  85 c0                     test     eax, eax
    1D6645AC  0f 95 c0                  setne    al
    1D6645AF  c3                        ret      
```

### FixPointGreaterThan (`op_GreaterThan`, method_index 68216)

- Primitive: `battle.ir.compare.fixpoint_greater`; result `boolean`
- RVA `0x1D6645B0`; body 144 bytes /
  48 instructions / 3
  conditional branches / 0 calls
- Body sha256 `93587ee19a0b623341ca4c341c52676f312c7b3225e84f6463473bf2880c58c0`
- ABI: `x64: lhs=rcx (raw qword), rhs=rdx (raw qword), bool return=al`
- Operation: `return FixPointCompareRaw(lhs, rhs) > 0`
- Field reads:
- none
- Branch conditions:
- same mode -> raw qword signed comparison; mixed mode -> 7-bit-shifted normalization
- mixed-mode equality tie is broken by the standard-mode low 7 fraction bits
- Required callees:

- none

- Pseudocode:

```
    int FixPointCompareRaw(lhs, rhs):               # consolidated native dataflow, not a callee
        le = lhs & 1; re = rhs & 1                  # mode flags: 0=STANDARD, 1=EXTENDED
        if le == 1 and re == 0:
            c = sign64((lhs & ~1) - sar64(rhs, 7))
            if c == 0: c = -1 if (rhs & 0x7F) != 0 else 0
            return c
        if le == 0 and re == 1:
            c = sign64(sar64(lhs, 7) - (rhs & ~1))
            if c == 0: c = 1 if (lhs & 0x7F) != 0 else 0
            return c
        if le == 0 and re == 0: return sign64(lhs - rhs)
        return sign64((lhs & ~1) - (rhs & ~1))
    bool FixPointGreaterThan(lhs, rhs):
        return FixPointCompareRaw(lhs, rhs) > 0    # native: setg
```

- Native evidence:

```
    1D6645B0  f6 c1 01                  test     cl, 1
    1D6645B3  75 36                     jne      0x19d6645eb
    1D6645B5  f6 c2 01                  test     dl, 1
    1D6645B8  74 6d                     je       0x19d664627
    1D6645BA  48 83 e2 fe               and      rdx, 0xfffffffffffffffe
    1D6645BE  48 89 c8                  mov      rax, rcx
    1D6645C1  48 c1 f8 07               sar      rax, 7
    1D6645C5  45 31 c0                  xor      r8d, r8d
    1D6645C8  48 39 d0                  cmp      rax, rdx
    1D6645CB  41 0f 9f c0               setg     r8b
    1D6645CF  ba ff ff ff ff            mov      edx, 0xffffffff
    1D6645D4  41 0f 4d d0               cmovge   edx, r8d
    1D6645D8  31 c0                     xor      eax, eax
    1D6645DA  f6 c1 7f                  test     cl, 0x7f
    1D6645DD  0f 95 c0                  setne    al
    1D6645E0  85 d2                     test     edx, edx
    1D6645E2  0f 45 c2                  cmovne   eax, edx
    1D6645E5  85 c0                     test     eax, eax
    1D6645E7  0f 9f c0                  setg     al
    1D6645EA  c3                        ret      
    1D6645EB  48 83 e1 fe               and      rcx, 0xfffffffffffffffe
    1D6645EF  f6 c2 01                  test     dl, 1
    1D6645F2  75 2f                     jne      0x19d664623
    1D6645F4  48 89 d0                  mov      rax, rdx
    1D6645F7  48 c1 f8 07               sar      rax, 7
    1D6645FB  45 31 c0                  xor      r8d, r8d
    1D6645FE  48 39 c8                  cmp      rax, rcx
    1D664601  41 0f 9f c0               setg     r8b
    1D664605  b9 ff ff ff ff            mov      ecx, 0xffffffff
    1D66460A  41 0f 4d c8               cmovge   ecx, r8d
    1D66460E  31 c0                     xor      eax, eax
    1D664610  f6 c2 7f                  test     dl, 0x7f
    1D664613  0f 95 c0                  setne    al
    1D664616  85 c9                     test     ecx, ecx
    1D664618  0f 45 c1                  cmovne   eax, ecx
    1D66461B  f7 d8                     neg      eax
    1D66461D  85 c0                     test     eax, eax
    1D66461F  0f 9f c0                  setg     al
    1D664622  c3                        ret      
    1D664623  48 83 e2 fe               and      rdx, 0xfffffffffffffffe
    1D664627  45 31 c0                  xor      r8d, r8d
    1D66462A  48 39 d1                  cmp      rcx, rdx
    1D66462D  41 0f 9f c0               setg     r8b
    1D664631  b8 ff ff ff ff            mov      eax, 0xffffffff
    1D664636  41 0f 4d c0               cmovge   eax, r8d
    1D66463A  85 c0                     test     eax, eax
    1D66463C  0f 9f c0                  setg     al
    1D66463F  c3                        ret      
```

### FixPointLessThan (`op_LessThan`, method_index 68217)

- Primitive: `battle.ir.compare.fixpoint_less`; result `boolean`
- RVA `0x1D6646D0`; body 138 bytes /
  45 instructions / 3
  conditional branches / 0 calls
- Body sha256 `818b30631659aaca453f57ec25fd9bfa8c7355b3241186bb5787f929f033aed8`
- ABI: `x64: lhs=rcx (raw qword), rhs=rdx (raw qword), bool return=al`
- Operation: `return FixPointCompareRaw(lhs, rhs) < 0`
- Field reads:
- none
- Branch conditions:
- same mode -> raw qword signed comparison; mixed mode -> 7-bit-shifted normalization
- mixed-mode equality tie is broken by the standard-mode low 7 fraction bits
- Required callees:

- none

- Pseudocode:

```
    int FixPointCompareRaw(lhs, rhs):               # consolidated native dataflow, not a callee
        le = lhs & 1; re = rhs & 1                  # mode flags: 0=STANDARD, 1=EXTENDED
        if le == 1 and re == 0:
            c = sign64((lhs & ~1) - sar64(rhs, 7))
            if c == 0: c = -1 if (rhs & 0x7F) != 0 else 0
            return c
        if le == 0 and re == 1:
            c = sign64(sar64(lhs, 7) - (rhs & ~1))
            if c == 0: c = 1 if (lhs & 0x7F) != 0 else 0
            return c
        if le == 0 and re == 0: return sign64(lhs - rhs)
        return sign64((lhs & ~1) - (rhs & ~1))
    bool FixPointLessThan(lhs, rhs):
        return FixPointCompareRaw(lhs, rhs) < 0     # native: setl
```

- Native evidence:

```
    1D6646D0  f6 c1 01                  test     cl, 1
    1D6646D3  75 34                     jne      0x19d664709
    1D6646D5  f6 c2 01                  test     dl, 1
    1D6646D8  74 69                     je       0x19d664743
    1D6646DA  48 83 e2 fe               and      rdx, 0xfffffffffffffffe
    1D6646DE  48 89 c8                  mov      rax, rcx
    1D6646E1  48 c1 f8 07               sar      rax, 7
    1D6646E5  45 31 c0                  xor      r8d, r8d
    1D6646E8  48 39 d0                  cmp      rax, rdx
    1D6646EB  41 0f 9f c0               setg     r8b
    1D6646EF  ba ff ff ff ff            mov      edx, 0xffffffff
    1D6646F4  41 0f 4d d0               cmovge   edx, r8d
    1D6646F8  31 c0                     xor      eax, eax
    1D6646FA  f6 c1 7f                  test     cl, 0x7f
    1D6646FD  0f 95 c0                  setne    al
    1D664700  85 d2                     test     edx, edx
    1D664702  0f 45 c2                  cmovne   eax, edx
    1D664705  c1 e8 1f                  shr      eax, 0x1f
    1D664708  c3                        ret      
    1D664709  48 83 e1 fe               and      rcx, 0xfffffffffffffffe
    1D66470D  f6 c2 01                  test     dl, 1
    1D664710  75 2d                     jne      0x19d66473f
    1D664712  48 89 d0                  mov      rax, rdx
    1D664715  48 c1 f8 07               sar      rax, 7
    1D664719  45 31 c0                  xor      r8d, r8d
    1D66471C  48 39 c8                  cmp      rax, rcx
    1D66471F  41 0f 9f c0               setg     r8b
    1D664723  b9 ff ff ff ff            mov      ecx, 0xffffffff
    1D664728  41 0f 4d c8               cmovge   ecx, r8d
    1D66472C  31 c0                     xor      eax, eax
    1D66472E  f6 c2 7f                  test     dl, 0x7f
    1D664731  0f 95 c0                  setne    al
    1D664734  85 c9                     test     ecx, ecx
    1D664736  0f 45 c1                  cmovne   eax, ecx
    1D664739  f7 d8                     neg      eax
    1D66473B  c1 e8 1f                  shr      eax, 0x1f
    1D66473E  c3                        ret      
    1D66473F  48 83 e2 fe               and      rdx, 0xfffffffffffffffe
    1D664743  45 31 c0                  xor      r8d, r8d
    1D664746  48 39 d1                  cmp      rcx, rdx
    1D664749  41 0f 9f c0               setg     r8b
    1D66474D  b8 ff ff ff ff            mov      eax, 0xffffffff
    1D664752  41 0f 4d c0               cmovge   eax, r8d
    1D664756  c1 e8 1f                  shr      eax, 0x1f
    1D664759  c3                        ret      
```

### FixPointGreaterEqual (`op_GreaterThanOrEqual`, method_index 68218)

- Primitive: `battle.ir.compare.fixpoint_greater_equal`; result `boolean`
- RVA `0x1D660C50`; body 144 bytes /
  48 instructions / 3
  conditional branches / 0 calls
- Body sha256 `927ce232af90a197938433fff3c904fa43ac27ff7bc6874f20d7e6e27b4c9573`
- ABI: `x64: lhs=rcx (raw qword), rhs=rdx (raw qword), bool return=al`
- Operation: `return FixPointCompareRaw(lhs, rhs) >= 0`
- Field reads:
- none
- Branch conditions:
- same mode -> raw qword signed comparison; mixed mode -> 7-bit-shifted normalization
- mixed-mode equality tie is broken by the standard-mode low 7 fraction bits
- Required callees:

- none

- Pseudocode:

```
    int FixPointCompareRaw(lhs, rhs):               # consolidated native dataflow, not a callee
        le = lhs & 1; re = rhs & 1                  # mode flags: 0=STANDARD, 1=EXTENDED
        if le == 1 and re == 0:
            c = sign64((lhs & ~1) - sar64(rhs, 7))
            if c == 0: c = -1 if (rhs & 0x7F) != 0 else 0
            return c
        if le == 0 and re == 1:
            c = sign64(sar64(lhs, 7) - (rhs & ~1))
            if c == 0: c = 1 if (lhs & 0x7F) != 0 else 0
            return c
        if le == 0 and re == 0: return sign64(lhs - rhs)
        return sign64((lhs & ~1) - (rhs & ~1))
    bool FixPointGreaterEqual(lhs, rhs):
        return FixPointCompareRaw(lhs, rhs) >= 0   # native: setns
```

- Native evidence:

```
    1D660C50  f6 c1 01                  test     cl, 1
    1D660C53  75 36                     jne      0x19d660c8b
    1D660C55  f6 c2 01                  test     dl, 1
    1D660C58  74 6d                     je       0x19d660cc7
    1D660C5A  48 83 e2 fe               and      rdx, 0xfffffffffffffffe
    1D660C5E  48 89 c8                  mov      rax, rcx
    1D660C61  48 c1 f8 07               sar      rax, 7
    1D660C65  45 31 c0                  xor      r8d, r8d
    1D660C68  48 39 d0                  cmp      rax, rdx
    1D660C6B  41 0f 9f c0               setg     r8b
    1D660C6F  ba ff ff ff ff            mov      edx, 0xffffffff
    1D660C74  41 0f 4d d0               cmovge   edx, r8d
    1D660C78  31 c0                     xor      eax, eax
    1D660C7A  f6 c1 7f                  test     cl, 0x7f
    1D660C7D  0f 95 c0                  setne    al
    1D660C80  85 d2                     test     edx, edx
    1D660C82  0f 45 c2                  cmovne   eax, edx
    1D660C85  85 c0                     test     eax, eax
    1D660C87  0f 99 c0                  setns    al
    1D660C8A  c3                        ret      
    1D660C8B  48 83 e1 fe               and      rcx, 0xfffffffffffffffe
    1D660C8F  f6 c2 01                  test     dl, 1
    1D660C92  75 2f                     jne      0x19d660cc3
    1D660C94  48 89 d0                  mov      rax, rdx
    1D660C97  48 c1 f8 07               sar      rax, 7
    1D660C9B  45 31 c0                  xor      r8d, r8d
    1D660C9E  48 39 c8                  cmp      rax, rcx
    1D660CA1  41 0f 9f c0               setg     r8b
    1D660CA5  b9 ff ff ff ff            mov      ecx, 0xffffffff
    1D660CAA  41 0f 4d c8               cmovge   ecx, r8d
    1D660CAE  31 c0                     xor      eax, eax
    1D660CB0  f6 c2 7f                  test     dl, 0x7f
    1D660CB3  0f 95 c0                  setne    al
    1D660CB6  85 c9                     test     ecx, ecx
    1D660CB8  0f 45 c1                  cmovne   eax, ecx
    1D660CBB  f7 d8                     neg      eax
    1D660CBD  85 c0                     test     eax, eax
    1D660CBF  0f 99 c0                  setns    al
    1D660CC2  c3                        ret      
    1D660CC3  48 83 e2 fe               and      rdx, 0xfffffffffffffffe
    1D660CC7  45 31 c0                  xor      r8d, r8d
    1D660CCA  48 39 d1                  cmp      rcx, rdx
    1D660CCD  41 0f 9f c0               setg     r8b
    1D660CD1  b8 ff ff ff ff            mov      eax, 0xffffffff
    1D660CD6  41 0f 4d c0               cmovge   eax, r8d
    1D660CDA  85 c0                     test     eax, eax
    1D660CDC  0f 99 c0                  setns    al
    1D660CDF  c3                        ret      
```

### FixPointLessEqual (`op_LessThanOrEqual`, method_index 68219)

- Primitive: `battle.ir.compare.fixpoint_less_equal`; result `boolean`
- RVA `0x1D664760`; body 144 bytes /
  48 instructions / 3
  conditional branches / 0 calls
- Body sha256 `09db8124c55603f512dc2b0d1ff7bf239a7e4573f6c7312afd92561c45904334`
- ABI: `x64: lhs=rcx (raw qword), rhs=rdx (raw qword), bool return=al`
- Operation: `return FixPointCompareRaw(lhs, rhs) <= 0`
- Field reads:
- none
- Branch conditions:
- same mode -> raw qword signed comparison; mixed mode -> 7-bit-shifted normalization
- mixed-mode equality tie is broken by the standard-mode low 7 fraction bits
- Required callees:

- none

- Pseudocode:

```
    int FixPointCompareRaw(lhs, rhs):               # consolidated native dataflow, not a callee
        le = lhs & 1; re = rhs & 1                  # mode flags: 0=STANDARD, 1=EXTENDED
        if le == 1 and re == 0:
            c = sign64((lhs & ~1) - sar64(rhs, 7))
            if c == 0: c = -1 if (rhs & 0x7F) != 0 else 0
            return c
        if le == 0 and re == 1:
            c = sign64(sar64(lhs, 7) - (rhs & ~1))
            if c == 0: c = 1 if (lhs & 0x7F) != 0 else 0
            return c
        if le == 0 and re == 0: return sign64(lhs - rhs)
        return sign64((lhs & ~1) - (rhs & ~1))
    bool FixPointLessEqual(lhs, rhs):
        return FixPointCompareRaw(lhs, rhs) <= 0    # native: setle
```

- Native evidence:

```
    1D664760  f6 c1 01                  test     cl, 1
    1D664763  75 36                     jne      0x19d66479b
    1D664765  f6 c2 01                  test     dl, 1
    1D664768  74 6d                     je       0x19d6647d7
    1D66476A  48 83 e2 fe               and      rdx, 0xfffffffffffffffe
    1D66476E  48 89 c8                  mov      rax, rcx
    1D664771  48 c1 f8 07               sar      rax, 7
    1D664775  45 31 c0                  xor      r8d, r8d
    1D664778  48 39 d0                  cmp      rax, rdx
    1D66477B  41 0f 9f c0               setg     r8b
    1D66477F  ba ff ff ff ff            mov      edx, 0xffffffff
    1D664784  41 0f 4d d0               cmovge   edx, r8d
    1D664788  31 c0                     xor      eax, eax
    1D66478A  f6 c1 7f                  test     cl, 0x7f
    1D66478D  0f 95 c0                  setne    al
    1D664790  85 d2                     test     edx, edx
    1D664792  0f 45 c2                  cmovne   eax, edx
    1D664795  85 c0                     test     eax, eax
    1D664797  0f 9e c0                  setle    al
    1D66479A  c3                        ret      
    1D66479B  48 83 e1 fe               and      rcx, 0xfffffffffffffffe
    1D66479F  f6 c2 01                  test     dl, 1
    1D6647A2  75 2f                     jne      0x19d6647d3
    1D6647A4  48 89 d0                  mov      rax, rdx
    1D6647A7  48 c1 f8 07               sar      rax, 7
    1D6647AB  45 31 c0                  xor      r8d, r8d
    1D6647AE  48 39 c8                  cmp      rax, rcx
    1D6647B1  41 0f 9f c0               setg     r8b
    1D6647B5  b9 ff ff ff ff            mov      ecx, 0xffffffff
    1D6647BA  41 0f 4d c8               cmovge   ecx, r8d
    1D6647BE  31 c0                     xor      eax, eax
    1D6647C0  f6 c2 7f                  test     dl, 0x7f
    1D6647C3  0f 95 c0                  setne    al
    1D6647C6  85 c9                     test     ecx, ecx
    1D6647C8  0f 45 c1                  cmovne   eax, ecx
    1D6647CB  f7 d8                     neg      eax
    1D6647CD  85 c0                     test     eax, eax
    1D6647CF  0f 9e c0                  setle    al
    1D6647D2  c3                        ret      
    1D6647D3  48 83 e2 fe               and      rdx, 0xfffffffffffffffe
    1D6647D7  45 31 c0                  xor      r8d, r8d
    1D6647DA  48 39 d1                  cmp      rcx, rdx
    1D6647DD  41 0f 9f c0               setg     r8b
    1D6647E1  b8 ff ff ff ff            mov      eax, 0xffffffff
    1D6647E6  41 0f 4d c0               cmovge   eax, r8d
    1D6647EA  85 c0                     test     eax, eax
    1D6647EC  0f 9e c0                  setle    al
    1D6647EF  c3                        ret      
```

### FixPointFromInt32 (`op_Implicit`, method_index 68256)

- Primitive: `battle.ir.value.fixpoint_from_int32`; result `fixpoint_raw`
- RVA `0x1D664F30`; body 40 bytes /
  11 instructions / 0
  conditional branches / 0 calls
- Body sha256 `d8a50ec778ccf54f73d573b7b90ebd3d45efa42ecad0c0f528d0d53f6031c4fb`
- ABI: `x64: value=ecx (int32), raw qword return=rax`
- Operation: `n = sign_extend_32(value); if abs(n) >= 0x40000000: return ((n << 0x1A) | 1) & MASK64; return (n << 0x21) & MASK64`
- Field reads:
- none
- Branch conditions:
- abs(sign_extend_32(value)) < 0x40000000 -> STANDARD raw = n << 0x21
- abs(sign_extend_32(value)) >= 0x40000000 -> EXTENDED raw = (n << 0x1A) | 1
- Required callees:

- none

- Pseudocode:

```
    fixpoint_raw FixPointFromInt32(int32 value):
        n = sign_extend_32(value)
        if abs(n) >= 0x40000000:
            return ((n << 26) | 1) & 0xFFFFFFFFFFFFFFFF   # EXTENDED
        return (n << 33) & 0xFFFFFFFFFFFFFFFF            # STANDARD
```

- Native evidence:

```
    1D664F30  48 63 c1                  movsxd   rax, ecx
    1D664F33  48 89 c1                  mov      rcx, rax
    1D664F36  48 f7 d9                  neg      rcx
    1D664F39  48 0f 48 c8               cmovs    rcx, rax
    1D664F3D  48 89 c2                  mov      rdx, rax
    1D664F40  48 c1 e2 1a               shl      rdx, 0x1a
    1D664F44  48 83 ca 01               or       rdx, 1
    1D664F48  48 c1 e0 21               shl      rax, 0x21
    1D664F4C  48 81 f9 00 00 00 40      cmp      rcx, 0x40000000
    1D664F53  48 0f 43 c2               cmovae   rax, rdx
    1D664F57  c3                        ret      
```

### FixPointIsZero (`get_IsZero`, method_index 68173)

- Primitive: `battle.ir.predicate.fixpoint_is_zero`; result `boolean`
- RVA `0x1D663050`; body 8 bytes /
  3 instructions / 0
  conditional branches / 0 calls
- Body sha256 `8906a40a247b85d04a354b1223a3d02b6db1826e5e042512f03fa476df425425`
- ABI: `x64: this=rcx (boxed FixPoint), raw qword read from [this+0x00], bool return=al`
- Operation: `return raw < 2 (unsigned qword compare)`
- Field reads:
- FixPoint.m_rawValue qword (field_index 40768) at boxed offset +0x00
- Branch conditions:
- raw qword < 2 -> true; otherwise false
- Required callees:

- none

- Pseudocode:

```
    bool FixPointIsZero(fixpoint_raw raw):
        return (raw & 0xFFFFFFFFFFFFFFFF) < 2   # native: cmp [this], 2; setb al
```

- Native evidence:

```
    1D663050  48 83 39 02               cmp      qword ptr [rcx], 2
    1D663054  0f 92 c0                  setb     al
    1D663057  c3                        ret      
```

### FixPointIsNegative (`get_IsNegative`, method_index 68174)

- Primitive: `battle.ir.predicate.fixpoint_is_negative`; result `boolean`
- RVA `0x1D663060`; body 8 bytes /
  3 instructions / 0
  conditional branches / 0 calls
- Body sha256 `1ca64b1d9b713881cd1a1487ea8d98e6d6767fccb9f82540f8dadcd9787153a1`
- ABI: `x64: this=rcx (boxed FixPoint), raw qword read from [this+0x00], bool return=al`
- Operation: `return (raw >> 63) == 1 (logical shift of qword)`
- Field reads:
- FixPoint.m_rawValue qword (field_index 40768) at boxed offset +0x00
- Branch conditions:
- raw bit 63 == 0 -> false
- raw bit 63 == 1 -> true
- Required callees:

- none

- Pseudocode:

```
    bool FixPointIsNegative(fixpoint_raw raw):
        return ((raw & 0xFFFFFFFFFFFFFFFF) >> 63) == 1   # native: shr rax, 0x3F
```

- Native evidence:

```
    1D663060  48 8b 01                  mov      rax, qword ptr [rcx]
    1D663063  48 c1 e8 3f               shr      rax, 0x3f
    1D663067  c3                        ret      
```

### FixPointIsPositive (`get_IsPositive`, method_index 68175)

- Primitive: `battle.ir.predicate.fixpoint_is_positive`; result `boolean`
- RVA `0x1D663070`; body 11 bytes /
  3 instructions / 0
  conditional branches / 0 calls
- Body sha256 `79bf1170fb0648c9a9e5df923e69ba962d81044ea4e9872a0490e071601094c1`
- ABI: `x64: this=rcx (boxed FixPoint), raw qword read from [this+0x00], bool return=al`
- Operation: `return signed64(raw & ~1) > 0`
- Field reads:
- FixPoint.m_rawValue qword (field_index 40768) at boxed offset +0x00
- Branch conditions:
- signed(raw & ~1) > 0 -> true
- signed(raw & ~1) <= 0 -> false (covers 0, 1, and negative encodings)
- Required callees:

- none

- Pseudocode:

```
    bool FixPointIsPositive(fixpoint_raw raw):
        masked = (raw & 0xFFFFFFFFFFFFFFFF) & ~1
        return signed64(masked) > 0            # native: test [this], -2; setg al
```

- Native evidence:

```
    1D663070  48 f7 01 fe ff ff ff      test     qword ptr [rcx], -2
    1D663077  0f 9f c0                  setg     al
    1D66307A  c3                        ret      
```


## 5. Skipped candidates

- 133350 RPG.GameCore.ByCompareDynamicValue..ctor (SKIP_SERIALIZATION): all five declared methods are ctor/serializer wrapper shapes; no Check/Evaluate/Compare/Execute/IsSatisfied runtime method exists on this runtime type
- 133351 RPG.GameCore.ByCompareDynamicValue.OJNNBEJLDIJ (SKIP_SERIALIZATION): wrapper/impl serializer pair (historical 4.4.54 evidence)
- 133352 RPG.GameCore.ByCompareDynamicValue.MGMEGEDLMAK (SKIP_SERIALIZATION): wrapper/impl serializer pair (historical 4.4.54 evidence)
- 133353 RPG.GameCore.ByCompareDynamicValue.LJACLBNEEEB (SKIP_SERIALIZATION): wrapper/impl serializer pair (historical 4.4.54 evidence)
- 133354 RPG.GameCore.ByCompareDynamicValue.EOJLPDGNHEK (SKIP_SERIALIZATION): wrapper/impl serializer pair (historical 4.4.54 evidence)
- 133355 RPG.GameCore.ByCompareValue..ctor (SKIP_SERIALIZATION): runtime class contains only ctor/wrapper/impl serialization methods; comparison semantics live in the FixPoint compare core recovered by this batch
- 125477 RPG.GameCore.ByDynamicValueDefined..ctor (SKIP_SERIALIZATION): same serializer/wrapper family; no non-serialization runtime predicate method on the type
- 132841 RPG.GameCore.PredicateConfig..ctor (SKIP_SERIALIZATION): config runtime type with only ctor/wrapper/impl serializer methods
- 106308 RPG.GameCore.CondCompareConfig..ctor (SKIP_SERIALIZATION): config runtime type with only ctor/wrapper/impl serializer methods
- 505866 RPG.GameCore.TaskContext.Evaluate (SKIP_CONTEXT_HEAVY): bool predicate dispatcher: reads TaskContext evaluator dictionary, hashes a string key, calls dictionary/index helpers and a tail dispatcher; call graph exceeds the batch budget
- 505884 RPG.GameCore.TaskContext.EvaluateOrDefault (SKIP_WRAPPER): null -> false, otherwise tailcall TaskContext.Evaluate(bool); no independent semantic beyond the skipped heavy dispatcher
- 135383 RPG.GameCore.ValueEvaluatorConfig.FEIIDFFOICL (SKIP_WRAPPER): compares a wrapped object field [rcx+0x20] to a FixPoint raw; current Kernel has no wrapper-object representation and the compare core is already recovered as FixPointEqual
- 135384 RPG.GameCore.ValueEvaluatorConfig.DLDBLNNPHKE (SKIP_WRAPPER): same wrapped-field compare pattern as 135383; no additional semantic operation
- 68257 RPG.GameCore.FixPoint.op_Implicit (SKIP_WRAPPER): same standard/extended encoding core as accepted 68256; native ABI shows an unsigned 32-bit entry (cmovb threshold) and is deferred to respect the batch value budget
- 68147 RPG.GameCore.FixPoint.ToBoolean (SKIP_COMPLEX): one-time IL2CPP class-init wrapper + interface conversion path; not a leaf predicate
- 68258 RPG.GameCore.FixPoint.Approximately (SKIP_COMPLEX): epsilon/global-constant-dependent approximate comparison; larger body and more branches than the exact six-operator core
- 68259 RPG.GameCore.FixPoint.IsAlmostZero (SKIP_COMPLEX): epsilon-dependent helper; outside this batch's exact-comparison core
- 68185 RPG.GameCore.FixPoint.BothStandardMode (SKIP_COMPLEX): mode helper, not a predicate/compare primitive; recovered compare code already handles mixed modes directly
- 88610 RPG.GameCore.DialogueConditionRow.CompareItemState (SKIP_NON_BATTLE): dialogue content condition comparison, not battle gameplay semantic
- 546444 RPG.Client.ConditionCheckerUtil.DoCheckConditions (SKIP_CONTEXT_HEAVY): client condition list dispatcher; call graph and client state dependencies exceed the batch budget
- 102771 RPG.GameCore.CheckPredicateAxis..ctor (SKIP_SERIALIZATION): serializer-shaped runtime type; no leaf predicate body

## 6. Semantic dependencies

- DynamicValueToInt32 (battle.ir.value.dynamic_value_to_int): SATISFIED
- DynamicValueEquals (battle.ir.value.dynamic_value_equals): SATISFIED
- TaskContext.Evaluate(bool) predicate dispatcher: SEMANTIC_DEPENDENCY_REQUIRED — PHASE B does not implement this dispatcher; see skipped_candidates

## 7. Known unknowns

- Numeric FixPoint reconstruction outside the recovered raw-encoding order/conversion predicates is not part of this batch
- type_reference identities (71/424/20642) are anchored by consumers; no formal type-reference resolver exists in the normalized pipeline yet
- IL2CPP boxed-object ABI for get_IsZero/get_IsNegative/get_IsPositive is provenance only; canonical IR models the raw qword
- No E5 client-side runtime observation for any Batch 03 primitive

Machine-readable companion:
`data/semantics/4.4.54/fixpoint_comparison_batch_03.json`.
