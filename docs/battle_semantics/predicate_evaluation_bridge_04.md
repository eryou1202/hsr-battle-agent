# Battle Semantic Predicate / Evaluator Bridge Batch 04

> Final status: **`BATTLE_SEMANTIC = PREDICATE_EVALUATION_BRIDGE_04_PROOF`**
> Game version: `4.4.54`
> Evidence level: `E4_STATIC_MACHINE_CODE` (all accepted primitives)
> Artifact schema: `battle_semantics_batch/1`

## 1. Scope

This batch closes the predicate/evaluator execution bridge on a bounded
set of real `RPG.GameCore.ValueEvaluatorConfig` native leaves.  It does
**not** recover the full `TaskContext` predicate dispatcher, target
selection, modifiers or damage.

Recovered composition shape:

```text
evaluator-spec runtime object (type_reference 23221)
  -> object field [obj+0x20] = FixPoint raw qword        (CONFIRMED)
  -> int32 RHS -> FixPointFromInt32                       (Batch 03 reuse)
  -> FixPointEqual / FixPointNotEqual                     (Batch 03 reuse)
  -> bool
```

## 2. Candidate discovery (callers, not names)

Raw single-pass rel32 scan counts for the already-proven cores:

| Target core | RVAs | rel32 direct-call sites |
|---|---|---:|
| FixPoint == / != / > / < / >= / <= | 0x1D661340 / 0x1D664520 / 0x1D6645B0 / 0x1D6646D0 / 0x1D660C50 / 0x1D664760 | 102 / 29 / 18 / 13 / 16 / 4 |
| DynamicValue to Int32 / UInt32 / Int64 / Float32 / Float64 / Bool / TypeTag / IsNull | Batch 02 RVAs | 2 / 21 / 0 / 1 / 0 / 0 / 0 / 0 |

The most relevant callers of comparison operators are heavy gameplay
components (TurnBasedAbilityComponent.ModifyProperty, SkillCharacterComponent,
AbilityStatic.TargetDamageHP) or heavy Evaluate bodies; they were
SKIP_CONTEXT_HEAVY after one bounded look.  DynamicValue conversions have
no direct RPG.GameCore caller in this static scan, so the conversion->comparison
bridge is proven inside ValueEvaluatorConfig instead of a conversion caller.

### First-round report (before PHASE A acceptance)

1. Commits confirmed: `e1b2668`, `11a6019`, `c66451f`, `a2ea2d1`.
2. Tracked state was clean at session start; only Batch 04 files are added
   by this session, and pre-existing untracked files are left untouched.
3. FixPoint comparator direct rel32 caller counts: 102 / 29 / 18 / 13 / 16 / 4
   for == / != / > / < / >= / <= (raw one-pass scan).
4. DynamicValue conversion direct rel32 caller counts: 2 / 21 / 0 / 1 / 0 / 0 / 0 / 0
   for ToInt32 / ToUInt32 / ToInt64 / ToFloat32 / ToFloat64 / ToBool / TypeTag / IsNull.
5. Intersection with `ValueEvaluatorConfig` / `TaskContext`: ValueEvaluatorConfig
   leaves inline the Batch 03 compare core rather than calling its RVAs;
   `TaskContext.Evaluate(bool)` remains a dictionary dispatcher with no
   recoverable leaf at depth 1.  No `RPG.GameCore` direct caller of the
   DynamicValue conversions was found in this scan.
6. Plausible candidates: the 19 rows in the candidate table below.
7. Shortlist: 5 accepted methods (`135379`, `135380`, `135381`, `135383`, `135384`).
8. Shortlist details: see the accepted-primitive sections; every entry has
   type / method / method_index / RVA / size / branch / callee / caller path.
9. Most likely to close the real predicate chain: `135381`
   (`FEIIDFFOICL(type_ref_23221, int32)`), because one bounded native body
   proves object-field read -> FixPointFromInt32 -> FixPointEqual -> bool.
10. Explicitly skipped as heavy: `TaskContext.Evaluate(bool)`
    (`SKIP_CONTEXT_HEAVY`), `INEOLMDOFMB.Evaluate`, `LKJEOBHCOID.Evaluate`,
    `KPCACPAEMGK.ILOHHJDPDBE`, `DHGEHJGMCLB.ILOHHJDPDBE`, and
    `RPG.Client.SpaceZooUtils.IsMatch` (`SKIP_NON_BATTLE`).

## 3. Candidate table

| method_index | candidate | native_rva | size(B) | insn | branch | callee | classification |
|---:|---|---|---:|---:|---:|---:|---|
| 135379 | RPG.GameCore.ValueEvaluatorConfig.BBNJCKPKPDN(int32) | 0x1D5AA260 | 73 | 21 | 1 | 1 | ACCEPT_BRIDGE |
| 135380 | RPG.GameCore.ValueEvaluatorConfig.BBNJCKPKPDN(FixPoint) | 0x1D5AA2B0 | 35 | 11 | 1 | 1 | ACCEPT_BRIDGE |
| 135381 | RPG.GameCore.ValueEvaluatorConfig.FEIIDFFOICL(type_ref_23221, int32) | 0x1D5AA2E0 | 232 | 71 | 7 | 0 | ACCEPT_PREDICATE |
| 135383 | RPG.GameCore.ValueEvaluatorConfig.FEIIDFFOICL(type_ref_23221, FixPoint) | 0x1D606570 | 197 | 63 | 7 | 0 | ACCEPT_PREDICATE |
| 135384 | RPG.GameCore.ValueEvaluatorConfig.DLDBLNNPHKE(type_ref_23221, FixPoint) | 0x1D606640 | 197 | 63 | 7 | 0 | ACCEPT_PREDICATE |
| 135382 | RPG.GameCore.ValueEvaluatorConfig.DLDBLNNPHKE(type_ref_23221, int32) | 0x1D606560 | 16 | 5 | 0 | 1 | SKIP_WRAPPER |
| 505866 | RPG.GameCore.TaskContext.Evaluate(bool) | 0xE6F0A60 | 347 | 108 | 14 | 11 | SKIP_CONTEXT_HEAVY |
| 505884 | RPG.GameCore.TaskContext.EvaluateOrDefault(bool) | 0xE6F24D0 | 93 | 33 | 3 | 2 | SKIP_WRAPPER |
| 507741 | INEOLMDOFMB.Evaluate | 0x16117690 | ~2180 observed window | ~400 observed window | ~90 observed window | ~25 observed window | SKIP_CONTEXT_HEAVY |
| 531579 | LKJEOBHCOID.Evaluate | 0xB8AE270 | ~2200 observed window | ~300 observed window | ~60 observed window | ~20 observed window | SKIP_CONTEXT_HEAVY |
| 500558 | KPCACPAEMGK.ILOHHJDPDBE | 0xB6D6E00 | ~2000 observed window | ~300 observed window | ~40 observed window | ~15 observed window | SKIP_CONTEXT_HEAVY |
| 500572 | DHGEHJGMCLB.ILOHHJDPDBE | 0xE88F360 | ~3600 observed window | ~500 observed window | ~70 observed window | ~20 observed window | SKIP_CONTEXT_HEAVY |
| 617796 | RPG.Client.SpaceZooUtils.IsMatch | 0xE0884E0 | ~800 observed window | ~150 observed window | ~20 observed window | ~8 observed window | SKIP_NON_BATTLE |
| 133350 | RPG.GameCore.ByCompareDynamicValue..ctor | 0x1CE2F1C0 | 57 | 15 | 1 | 2 | SKIP_SERIALIZATION |
| 133355 | RPG.GameCore.ByCompareValue..ctor | 0x1CE7C770 | 9 | 3 | 0 | 0 | SKIP_SERIALIZATION |
| 125477 | RPG.GameCore.ByDynamicValueDefined..ctor | 0x1CE899F0 | 5 | 2 | 0 | 0 | SKIP_SERIALIZATION |
| 132841 | RPG.GameCore.PredicateConfig..ctor | 0x1D2CA150 | 510 | 124 | 20 | 9 | SKIP_SERIALIZATION |
| 106308 | RPG.GameCore.CondCompareConfig..ctor | 0x1CF67770 | 8 | 2 | 0 | 0 | SKIP_SERIALIZATION |
| 102771 | RPG.GameCore.CheckPredicateAxis..ctor | 0x1CF125B0 | 1 | 1 | 0 | 0 | SKIP_SERIALIZATION |

Shortlist (5 accepted): `135379`, `135380`, `135381`, `135383`, `135384`.
`135381` is the most important chain-closing leaf: one bounded native body
proves `object field -> value conversion -> comparison -> bool`.

## 4. Runtime type / method identity

| Item | Value |
|---|---|
| Runtime type | `RPG.GameCore.ValueEvaluatorConfig` (type_index `23733`) |
| Operand type | runtime `type_reference 23221`, name UNKNOWN, class-pointer global RVA `0x95E2B08` |
| Static ABI evidence | method flags 0x0E == `16293`, identical to `FixPoint.op_Equality` / `op_Implicit` static operators |

Field map proven by native bodies:

| Offset | Width | Role | Evidence |
|---|---:|---|---|
| +0x20 | 8 | FixPoint raw qword operand | CONFIRMED |
| runtime class identity | - | type_reference 23221 / class global 0x95E2B08 | SUPPORTED |
| other object fields | - | not read by accepted bodies | UNKNOWN |

## 5. Accepted primitives

### EvaluatorSpecFromInt32 (`BBNJCKPKPDN`, method_index 135379)

- Primitive: `battle.ir.predicate.evaluator_spec_from_int32`; result `evaluator_spec`
- RVA `0x1D5AA260`; body 73 bytes / 21 instructions / 1 conditional branches / 1 calls
- Body sha256 `02384075d8a455905021f3640e3e1b59790052b0df8169f861f696de06a2356a`
- Field reads:
  - runtime operand class [obj+0x20] <- written
- Field writes:
  - runtime operand class +0x20 qword = fixpoint raw
- Branch conditions:
  - il2cpp object allocation returned null -> return null (allocation failure path)
  - abs(sign_extend_32(value)) >= 0x40000000 -> EXTENDED FixPoint raw
- Default / error path:
  - object allocation null -> return null; sandbox representation never allocates
- Required callees:
  - 0x3C736B0 il2cpp_object_new (runtime allocation infrastructure, UNKNOWN_HELPER_NOT_NEEDED)
- Pseudocode:
```
EvaluatorSpec EvaluatorSpecFromInt32(int32 value):
    obj = il2cpp_object_new(class_global_0x95E2B08)
    if obj == null: return null
    raw = FixPointFromInt32(value)      # reuses battle.ir.value.fixpoint_from_int32
    obj[+0x20] = raw                    # CONFIRMED single qword write
    return obj
```
- Native evidence (first instructions + body hash anchor):
```
1D5AA260  56                        push     rsi
1D5AA261  48 83 ec 20               sub      rsp, 0x20
1D5AA265  89 ce                     mov      esi, ecx
1D5AA267  48 8b 0d 9a 88 03 ec      mov      rcx, qword ptr [rip - 0x13fc7766] ; [rip]->0x1895E2B08 (rva 0x95E2B08)
1D5AA26E  e8 3d 94 6c e6            call     0x183c736b0
1D5AA273  48 85 c0                  test     rax, rax
1D5AA276  74 31                     je       0x19d5aa2a9
1D5AA278  48 63 ce                  movsxd   rcx, esi
1D5AA27B  48 89 ca                  mov      rdx, rcx
1D5AA27E  48 f7 da                  neg      rdx
1D5AA281  48 0f 48 d1               cmovs    rdx, rcx
1D5AA285  48 89 ce                  mov      rsi, rcx
1D5AA288  48 c1 e6 1a               shl      rsi, 0x1a
1D5AA28C  48 83 ce 01               or       rsi, 1
1D5AA290  48 c1 e1 21               shl      rcx, 0x21
1D5AA294  48 81 fa 00 00 00 40      cmp      rdx, 0x40000000
1D5AA29B  48 0f 43 ce               cmovae   rcx, rsi
1D5AA29F  48 89 48 20               mov      qword ptr [rax + 0x20], rcx
1D5AA2A3  48 83 c4 20               add      rsp, 0x20
1D5AA2A7  5e                        pop      rsi
1D5AA2A8  c3                        ret      
```

### EvaluatorSpecFromFixPointRaw (`BBNJCKPKPDN`, method_index 135380)

- Primitive: `battle.ir.predicate.evaluator_spec_from_fixpoint_raw`; result `evaluator_spec`
- RVA `0x1D5AA2B0`; body 35 bytes / 11 instructions / 1 conditional branches / 1 calls
- Body sha256 `4990ec9752807b54d0baff97e99d1476710ac8b686ae50385ebb3d7fd72de0ea`
- Field reads:
  - none
- Field writes:
  - runtime operand class +0x20 qword = fixpoint raw
- Branch conditions:
  - il2cpp object allocation returned null -> return null (allocation failure path)
- Default / error path:
  - object allocation null -> return null; sandbox representation never allocates
- Required callees:
  - 0x3C736B0 il2cpp_object_new (runtime allocation infrastructure, UNKNOWN_HELPER_NOT_NEEDED)
- Pseudocode:
```
EvaluatorSpec EvaluatorSpecFromFixPointRaw(fixpoint_raw value):
    obj = il2cpp_object_new(class_global_0x95E2B08)
    if obj == null: return null
    obj[+0x20] = value                 # CONFIRMED single qword write
    return obj
```
- Native evidence (first instructions + body hash anchor):
```
1D5AA2B0  56                        push     rsi
1D5AA2B1  48 83 ec 20               sub      rsp, 0x20
1D5AA2B5  48 89 ce                  mov      rsi, rcx
1D5AA2B8  48 8b 0d 49 88 03 ec      mov      rcx, qword ptr [rip - 0x13fc77b7] ; [rip]->0x1895E2B08 (rva 0x95E2B08)
1D5AA2BF  e8 ec 93 6c e6            call     0x183c736b0
1D5AA2C4  48 85 c0                  test     rax, rax
1D5AA2C7  74 0a                     je       0x19d5aa2d3
1D5AA2C9  48 89 70 20               mov      qword ptr [rax + 0x20], rsi
1D5AA2CD  48 83 c4 20               add      rsp, 0x20
1D5AA2D1  5e                        pop      rsi
1D5AA2D2  c3                        ret      
```

### EvaluatorSpecFixPointEqualInt32 (`FEIIDFFOICL`, method_index 135381)

- Primitive: `battle.ir.predicate.evaluator_spec_fixpoint_equal_int32`; result `boolean`
- RVA `0x1D5AA2E0`; body 232 bytes / 71 instructions / 7 conditional branches / 0 calls
- Body sha256 `4fa3153382473968958206931a1644cbd14d49603c321d04e4a3b5d23d2b2e47`
- Field reads:
  - runtime operand class +0x20 qword = FixPoint raw (CONFIRMED)
- Field writes:
- Branch conditions:
  - obj == null -> return false (CONFIRMED default path)
  - obj class is not class_global_0x95E2B08 nor subclass -> return false (CONFIRMED default path)
  - FixPoint compare: same-mode standard -> raw signed comparison
  - FixPoint compare: lhs EXTENDED, rhs canonical STANDARD/EXTENDED from int32 -> Batch 03 mixed-mode normalization
  - FixPoint compare: lhs STANDARD, rhs canonical from int32 -> Batch 03 mixed-mode normalization
- Default / error path:
  - null / wrong runtime type -> false
- Required callees:
- Pseudocode:
```
bool EvaluatorSpecFixPointEqualInt32(EvaluatorSpec obj, int32 rhs):
    if obj == null: return false
    if not is_instance_of(obj, class_global_0x95E2B08): return false
    lhs = obj[+0x20]
    rhs_raw = FixPointFromInt32(rhs)
    return FixPointEqual(lhs, rhs_raw)
# lhs -> battle.ir.value.fixpoint_from_int32 -> battle.ir.compare.fixpoint_equal -> bool
```
- Native evidence (first instructions + body hash anchor):
```
1D5AA2E0  48 85 c9                  test     rcx, rcx
1D5AA2E3  74 2b                     je       0x19d5aa310
1D5AA2E5  4c 8b 05 1c 88 03 ec      mov      r8, qword ptr [rip - 0x13fc77e4] ; [rip]->0x1895E2B08 (rva 0x95E2B08)
1D5AA2EC  48 8b 01                  mov      rax, qword ptr [rcx]
1D5AA2EF  4c 39 c0                  cmp      rax, r8
1D5AA2F2  74 1f                     je       0x19d5aa313
1D5AA2F4  45 0f b6 88 c4 00 00 00   movzx    r9d, byte ptr [r8 + 0xc4]
1D5AA2FC  44 38 88 c4 00 00 00      cmp      byte ptr [rax + 0xc4], r9b
1D5AA303  72 0b                     jb       0x19d5aa310
1D5AA305  48 8b 40 70               mov      rax, qword ptr [rax + 0x70]
1D5AA309  4e 39 44 c8 f8            cmp      qword ptr [rax + r9*8 - 8], r8
1D5AA30E  74 03                     je       0x19d5aa313
1D5AA310  31 c0                     xor      eax, eax
1D5AA312  c3                        ret      
1D5AA313  4c 8b 41 20               mov      r8, qword ptr [rcx + 0x20]
1D5AA317  48 63 ca                  movsxd   rcx, edx
1D5AA31A  48 89 ca                  mov      rdx, rcx
1D5AA31D  48 f7 da                  neg      rdx
1D5AA320  48 0f 48 d1               cmovs    rdx, rcx
1D5AA324  48 89 c8                  mov      rax, rcx
1D5AA327  48 c1 e0 1a               shl      rax, 0x1a
1D5AA32B  48 83 c8 01               or       rax, 1
1D5AA32F  48 c1 e1 21               shl      rcx, 0x21
1D5AA333  48 81 fa 00 00 00 40      cmp      rdx, 0x40000000
1D5AA33A  48 0f 43 c8               cmovae   rcx, rax
1D5AA33E  41 f6 c0 01               test     r8b, 1
1D5AA342  75 37                     jne      0x19d5aa37b
1D5AA344  f6 c1 01                  test     cl, 1
1D5AA347  74 69                     je       0x19d5aa3b2
1D5AA349  48 81 e1 00 00 00 fc      and      rcx, 0xfffffffffc000000
1D5AA350  4c 89 c0                  mov      rax, r8
1D5AA353  48 c1 f8 07               sar      rax, 7
1D5AA357  31 d2                     xor      edx, edx
1D5AA359  48 39 c8                  cmp      rax, rcx
1D5AA35C  0f 9f c2                  setg     dl
1D5AA35F  b8 ff ff ff ff            mov      eax, 0xffffffff
1D5AA364  0f 4d c2                  cmovge   eax, edx
1D5AA367  31 c9                     xor      ecx, ecx
1D5AA369  41 f6 c0 7f               test     r8b, 0x7f
1D5AA36D  0f 95 c1                  setne    cl
1D5AA370  85 c0                     test     eax, eax
1D5AA372  0f 45 c8                  cmovne   ecx, eax
1D5AA375  85 c9                     test     ecx, ecx
1D5AA377  0f 94 c0                  sete     al
1D5AA37A  c3                        ret      
1D5AA37B  49 83 e0 fe               and      r8, 0xfffffffffffffffe
1D5AA37F  f6 c1 01                  test     cl, 1
1D5AA382  75 27                     jne      0x19d5aa3ab
1D5AA384  48 89 c8                  mov      rax, rcx
1D5AA387  48 c1 f8 07               sar      rax, 7
1D5AA38B  31 d2                     xor      edx, edx
1D5AA38D  4c 39 c0                  cmp      rax, r8
1D5AA390  0f 9f c2                  setg     dl
1D5AA393  b8 ff ff ff ff            mov      eax, 0xffffffff
1D5AA398  0f 4d c2                  cmovge   eax, edx
1D5AA39B  83 e1 01                  and      ecx, 1
1D5AA39E  85 c0                     test     eax, eax
1D5AA3A0  0f 45 c8                  cmovne   ecx, eax
1D5AA3A3  f7 d9                     neg      ecx
1D5AA3A5  85 c9                     test     ecx, ecx
1D5AA3A7  0f 94 c0                  sete     al
1D5AA3AA  c3                        ret      
1D5AA3AB  48 81 e1 00 00 00 fc      and      rcx, 0xfffffffffc000000
1D5AA3B2  31 c0                     xor      eax, eax
1D5AA3B4  49 39 c8                  cmp      r8, rcx
1D5AA3B7  0f 9f c0                  setg     al
1D5AA3BA  b9 ff ff ff ff            mov      ecx, 0xffffffff
1D5AA3BF  0f 4d c8                  cmovge   ecx, eax
1D5AA3C2  85 c9                     test     ecx, ecx
1D5AA3C4  0f 94 c0                  sete     al
1D5AA3C7  c3                        ret      
```

### EvaluatorSpecFixPointEqualRaw (`FEIIDFFOICL`, method_index 135383)

- Primitive: `battle.ir.predicate.evaluator_spec_fixpoint_equal_raw`; result `boolean`
- RVA `0x1D606570`; body 197 bytes / 63 instructions / 7 conditional branches / 0 calls
- Body sha256 `a27da10a435eba599e12ece1b85b9de8ff84a1fc01358a3d4e06b1d6f4b2744d`
- Field reads:
  - runtime operand class +0x20 qword = FixPoint raw (CONFIRMED)
- Field writes:
- Branch conditions:
  - obj == null -> return false (CONFIRMED default path)
  - obj class is not class_global_0x95E2B08 nor subclass -> return false (CONFIRMED default path)
  - then exactly the six-way Batch 03 FixPointEqual branch structure
- Default / error path:
  - null / wrong runtime type -> false
- Required callees:
- Pseudocode:
```
bool EvaluatorSpecFixPointEqualRaw(EvaluatorSpec obj, fixpoint_raw rhs):
    if obj == null: return false
    if not is_instance_of(obj, class_global_0x95E2B08): return false
    lhs = obj[+0x20]
    return FixPointEqual(lhs, rhs)
# reuses battle.ir.compare.fixpoint_equal
```
- Native evidence (first instructions + body hash anchor):
```
1D606570  48 85 c9                  test     rcx, rcx
1D606573  74 2b                     je       0x19d6065a0
1D606575  4c 8b 05 8c c5 fd eb      mov      r8, qword ptr [rip - 0x14023a74] ; [rip]->0x1895E2B08 (rva 0x95E2B08)
1D60657C  48 8b 01                  mov      rax, qword ptr [rcx]
1D60657F  4c 39 c0                  cmp      rax, r8
1D606582  74 1f                     je       0x19d6065a3
1D606584  45 0f b6 88 c4 00 00 00   movzx    r9d, byte ptr [r8 + 0xc4]
1D60658C  44 38 88 c4 00 00 00      cmp      byte ptr [rax + 0xc4], r9b
1D606593  72 0b                     jb       0x19d6065a0
1D606595  48 8b 40 70               mov      rax, qword ptr [rax + 0x70]
1D606599  4e 39 44 c8 f8            cmp      qword ptr [rax + r9*8 - 8], r8
1D60659E  74 03                     je       0x19d6065a3
1D6065A0  31 c0                     xor      eax, eax
1D6065A2  c3                        ret      
1D6065A3  48 8b 41 20               mov      rax, qword ptr [rcx + 0x20]
1D6065A7  a8 01                     test     al, 1
1D6065A9  75 35                     jne      0x19d6065e0
1D6065AB  f6 c2 01                  test     dl, 1
1D6065AE  74 6c                     je       0x19d60661c
1D6065B0  48 83 e2 fe               and      rdx, 0xfffffffffffffffe
1D6065B4  48 89 c1                  mov      rcx, rax
1D6065B7  48 c1 f9 07               sar      rcx, 7
1D6065BB  45 31 c0                  xor      r8d, r8d
1D6065BE  48 39 d1                  cmp      rcx, rdx
1D6065C1  41 0f 9f c0               setg     r8b
1D6065C5  ba ff ff ff ff            mov      edx, 0xffffffff
1D6065CA  41 0f 4d d0               cmovge   edx, r8d
1D6065CE  31 c9                     xor      ecx, ecx
1D6065D0  a8 7f                     test     al, 0x7f
1D6065D2  0f 95 c1                  setne    cl
1D6065D5  85 d2                     test     edx, edx
1D6065D7  0f 45 ca                  cmovne   ecx, edx
1D6065DA  85 c9                     test     ecx, ecx
1D6065DC  0f 94 c0                  sete     al
1D6065DF  c3                        ret      
1D6065E0  48 83 e0 fe               and      rax, 0xfffffffffffffffe
1D6065E4  f6 c2 01                  test     dl, 1
1D6065E7  75 2f                     jne      0x19d606618
1D6065E9  48 89 d1                  mov      rcx, rdx
1D6065EC  48 c1 f9 07               sar      rcx, 7
1D6065F0  45 31 c0                  xor      r8d, r8d
1D6065F3  48 39 c1                  cmp      rcx, rax
1D6065F6  41 0f 9f c0               setg     r8b
1D6065FA  b8 ff ff ff ff            mov      eax, 0xffffffff
1D6065FF  41 0f 4d c0               cmovge   eax, r8d
1D606603  31 c9                     xor      ecx, ecx
1D606605  f6 c2 7f                  test     dl, 0x7f
1D606608  0f 95 c1                  setne    cl
1D60660B  85 c0                     test     eax, eax
1D60660D  0f 45 c8                  cmovne   ecx, eax
1D606610  f7 d9                     neg      ecx
1D606612  85 c9                     test     ecx, ecx
1D606614  0f 94 c0                  sete     al
1D606617  c3                        ret      
1D606618  48 83 e2 fe               and      rdx, 0xfffffffffffffffe
1D60661C  45 31 c0                  xor      r8d, r8d
1D60661F  48 39 d0                  cmp      rax, rdx
1D606622  41 0f 9f c0               setg     r8b
1D606626  b9 ff ff ff ff            mov      ecx, 0xffffffff
1D60662B  41 0f 4d c8               cmovge   ecx, r8d
1D60662F  85 c9                     test     ecx, ecx
1D606631  0f 94 c0                  sete     al
1D606634  c3                        ret      
```

### EvaluatorSpecFixPointNotEqualRaw (`DLDBLNNPHKE`, method_index 135384)

- Primitive: `battle.ir.predicate.evaluator_spec_fixpoint_not_equal_raw`; result `boolean`
- RVA `0x1D606640`; body 197 bytes / 63 instructions / 7 conditional branches / 0 calls
- Body sha256 `d53ea065424b1b8db001f7527068206b2c58ae3809cbef0dec660c9b4b68e0c8`
- Field reads:
  - runtime operand class +0x20 qword = FixPoint raw (CONFIRMED)
- Field writes:
- Branch conditions:
  - obj == null -> return true (CONFIRMED default path)
  - obj class is not class_global_0x95E2B08 nor subclass -> return true (CONFIRMED default path)
  - then exactly the six-way Batch 03 FixPointNotEqual branch structure
- Default / error path:
  - null / wrong runtime type -> true (operator semantics, not an error)
- Required callees:
- Pseudocode:
```
bool EvaluatorSpecFixPointNotEqualRaw(EvaluatorSpec obj, fixpoint_raw rhs):
    if obj == null: return true
    if not is_instance_of(obj, class_global_0x95E2B08): return true
    lhs = obj[+0x20]
    return FixPointNotEqual(lhs, rhs)
# reuses battle.ir.compare.fixpoint_not_equal
```
- Native evidence (first instructions + body hash anchor):
```
1D606640  b0 01                     mov      al, 1
1D606642  48 85 c9                  test     rcx, rcx
1D606645  74 2b                     je       0x19d606672
1D606647  4c 8b 05 ba c4 fd eb      mov      r8, qword ptr [rip - 0x14023b46] ; [rip]->0x1895E2B08 (rva 0x95E2B08)
1D60664E  4c 8b 09                  mov      r9, qword ptr [rcx]
1D606651  4d 39 c1                  cmp      r9, r8
1D606654  74 1d                     je       0x19d606673
1D606656  45 0f b6 90 c4 00 00 00   movzx    r10d, byte ptr [r8 + 0xc4]
1D60665E  45 38 91 c4 00 00 00      cmp      byte ptr [r9 + 0xc4], r10b
1D606665  72 0b                     jb       0x19d606672
1D606667  4d 8b 49 70               mov      r9, qword ptr [r9 + 0x70]
1D60666B  4f 39 44 d1 f8            cmp      qword ptr [r9 + r10*8 - 8], r8
1D606670  74 01                     je       0x19d606673
1D606672  c3                        ret      
1D606673  48 8b 41 20               mov      rax, qword ptr [rcx + 0x20]
1D606677  a8 01                     test     al, 1
1D606679  75 35                     jne      0x19d6066b0
1D60667B  f6 c2 01                  test     dl, 1
1D60667E  74 6c                     je       0x19d6066ec
1D606680  48 83 e2 fe               and      rdx, 0xfffffffffffffffe
1D606684  48 89 c1                  mov      rcx, rax
1D606687  48 c1 f9 07               sar      rcx, 7
1D60668B  45 31 c0                  xor      r8d, r8d
1D60668E  48 39 d1                  cmp      rcx, rdx
1D606691  41 0f 9f c0               setg     r8b
1D606695  ba ff ff ff ff            mov      edx, 0xffffffff
1D60669A  41 0f 4d d0               cmovge   edx, r8d
1D60669E  31 c9                     xor      ecx, ecx
1D6066A0  a8 7f                     test     al, 0x7f
1D6066A2  0f 95 c1                  setne    cl
1D6066A5  85 d2                     test     edx, edx
1D6066A7  0f 45 ca                  cmovne   ecx, edx
1D6066AA  85 c9                     test     ecx, ecx
1D6066AC  0f 95 c0                  setne    al
1D6066AF  c3                        ret      
1D6066B0  48 83 e0 fe               and      rax, 0xfffffffffffffffe
1D6066B4  f6 c2 01                  test     dl, 1
1D6066B7  75 2f                     jne      0x19d6066e8
1D6066B9  48 89 d1                  mov      rcx, rdx
1D6066BC  48 c1 f9 07               sar      rcx, 7
1D6066C0  45 31 c0                  xor      r8d, r8d
1D6066C3  48 39 c1                  cmp      rcx, rax
1D6066C6  41 0f 9f c0               setg     r8b
1D6066CA  b8 ff ff ff ff            mov      eax, 0xffffffff
1D6066CF  41 0f 4d c0               cmovge   eax, r8d
1D6066D3  31 c9                     xor      ecx, ecx
1D6066D5  f6 c2 7f                  test     dl, 0x7f
1D6066D8  0f 95 c1                  setne    cl
1D6066DB  85 c0                     test     eax, eax
1D6066DD  0f 45 c8                  cmovne   ecx, eax
1D6066E0  f7 d9                     neg      ecx
1D6066E2  85 c9                     test     ecx, ecx
1D6066E4  0f 95 c0                  setne    al
1D6066E7  c3                        ret      
1D6066E8  48 83 e2 fe               and      rdx, 0xfffffffffffffffe
1D6066EC  45 31 c0                  xor      r8d, r8d
1D6066EF  48 39 d0                  cmp      rax, rdx
1D6066F2  41 0f 9f c0               setg     r8b
1D6066F6  b9 ff ff ff ff            mov      ecx, 0xffffffff
1D6066FB  41 0f 4d c8               cmovge   ecx, r8d
1D6066FF  85 c9                     test     ecx, ecx
1D606701  0f 95 c0                  setne    al
1D606704  c3                        ret      
```

## 6. Composition chains (machine-readable in the artifact)

### evaluator_spec_int32_equal_chain

Runtime evidence: `ValueEvaluatorConfig.FEIIDFFOICL(type_ref_23221, int32)`

```text
  runtime object construction (native allocation + [obj+0x20] store)
    battle.ir.predicate.evaluator_spec_from_int32
  predicate leaf: [obj+0x20] read -> inline FixPointFromInt32 -> inline FixPointEqual -> bool
    battle.ir.predicate.evaluator_spec_fixpoint_equal_int32
```

### evaluator_spec_raw_equal_chain

Runtime evidence: `ValueEvaluatorConfig.FEIIDFFOICL(type_ref_23221, FixPoint)`

```text
  runtime object construction with a raw FixPoint qword
    battle.ir.predicate.evaluator_spec_from_fixpoint_raw
  predicate leaf: [obj+0x20] read -> FixPointEqual -> bool
    battle.ir.predicate.evaluator_spec_fixpoint_equal_raw
```

### evaluator_spec_raw_not_equal_chain

Runtime evidence: `ValueEvaluatorConfig.DLDBLNNPHKE(type_ref_23221, FixPoint)`

```text
  runtime object construction with a raw FixPoint qword
    battle.ir.predicate.evaluator_spec_from_fixpoint_raw
  predicate leaf: [obj+0x20] read -> FixPointNotEqual -> bool
    battle.ir.predicate.evaluator_spec_fixpoint_not_equal_raw
```

## 7. Dependencies / unknowns

- `battle.ir.value.fixpoint_from_int32`: SATISFIED (Batch 03)
- `battle.ir.compare.fixpoint_equal` / `fixpoint_not_equal`: SATISFIED (Batch 03)
- `TaskContext.Evaluate(bool)` dispatcher: SEMANTIC_DEPENDENCY_REQUIRED
- operand runtime type name (`type_reference 23221`) remains UNKNOWN_NAME
- no E5 runtime observation

Machine-readable companion:
`data/semantics/4.4.54/predicate_evaluation_bridge_04.json`.

