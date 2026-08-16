# MHY Method Code Registry Proof — 4.4.54

> Session after `MHY_METADATA = MEMBER_REGISTRY_PROOF`.
> Goal: recover `MethodDefinition index -> GameAssembly native implementation RVA`
> from the real MHY runtime consumer, without assuming a standard IL2CPP
> CodeRegistration layout.
>
> final_status = **METHOD_CODE = RVA_REGISTRY_PROOF**

## 0. Conclusion

The runtime registry struct already observed by the metadata builder carries a
direct one-slot-per-method native code table. The consumer code proves the
mapping rule:

```text
code_table = runtime_registry[+0x40]                     (4.4.54)
code_table = runtime_registry[+0x88]                     (4.4.0)
native_rva = qword(code_table + method_index * 8)
qword == 0 => no direct native body (see classification)
```

No per-index transform, no token lookup, no standard CodeRegistration layout
assumption. The index is the same MethodDefinition index recovered from
TypeDefinition `+0x08 ^ 0x1A7AF5FE` / `+0x34 + 0x5F93`.

## 1. Consumer evidence (E4 code-level)

Both versions contain the identical consumer shape while iterating a
TypeDefinition's method range:

```text
movsxd rax, [typerec + 0x08]
xor   rax, 0x1A7AF5FE          ; method range start
...
mov   rax, [rip + registry_ptr_global]
mov   rax, [rax + FIELD]       ; FIELD = 0x40 (4.4.54), 0x88 (4.4.0)
mov   r12, [rax + r14*8]       ; r14 = method_index
test  r12, r12                 ; 0 is a valid no-body sentinel
```

| version | consumer RVA | registry ptr global RVA | registry struct RVA | code-table field |
|---|---|---|---|---|
| 4.4.54 | `0x3C80C1A` | `0x9D38788` | `0x432ED30` | `+0x40` |
| 4.4.0 | `0x656D8A` | `0x8F09D58` | `0x5652650` | `+0x88` |

The 4.4.54 registry struct is the one already used by the runtime method
builder at `0x3C5DFD0`; `[registry+0x40]` was previously unlabeled.

## 2. Code table identity

| item | 4.4.54 | 4.4.0 |
|---|---|---|
| code table RVA | `0x483BBA0` | `0x3E9D000` |
| entry size | 8 | 8 |
| slots | 732328 | 703008 |
| MethodDefinition count | 732328 | 703008 |
| null slots | 32130 | 26166 |
| non-null slots | 700198 | 676842 |
| unique native RVAs | 700198 | 676842 |
| out-of-range / non-executable | 0 | 0 |
| target section | `il2cpp` (all) | `il2cpp` (all) |

The locator used structural anchors (first four slots are zero) plus semantic
machine-code anchors at stable mscorlib indices:

| method_index | method | machine shape |
|---|---|---|
| 4 | `Locale.GetText(string)` | `mov rax, rcx; ret` |
| 16 | `Mono.RuntimeClassHandle.get_Value` | `mov rax, [rcx]; ret` |
| 18 | `Mono.RuntimeClassHandle.GetHashCode` | `mov eax, [rcx]; ret` |
| 22 | `Mono.RuntimeGenericParamInfoHandle..ctor` | `mov [rcx], rdx; ret` |

The same anchors match both versions.

## 3. Classification

All 0x14C slot values in this proof are decoded exactly as the builder does:
`low16(hash32c)` (`hash32c = low32(rolling_hash + 0x71BC7861)`). The earlier
member access-map text specified the same form; its secondary helper used
`low16(hash64)` for the slot/flags columns, so this proof records the corrected
slot values without re-opening the archived MethodDefinition proof.

| class | 4.4.54 | 4.4.0 | meaning |
|---|---|---|---|
| DIRECT_NATIVE | 700198 | 676842 | slot < 0, code_table entry != 0 |
| VIRTUAL_VTABLE | 3800 | 2831 | slot >= 0, direct entry = 0; native entry resolved via type vtable (`[type + 0xD0]`) |
| NO_BODY | 28330 | 23335 | slot < 0, direct entry = 0; generic/abstract/interface/internal |
| THUNK | sample-dependent | sample-dependent | first instruction is `jmp`; stable entry RVA recorded, dispatcher not analyzed |

Null-slot samples decode to the expected classes: generic
`<>f__AnonymousType0`1`, `IContentHandler`, `IAttrList`,
`Microsoft.Win32.IRegistryApi`, `System.ReadOnlySpan`1`, `System.Span`1`,
`System.ValueTuple*`, etc.

## 4. Semantic sanity

Beyond the four locator anchors, the first common mscorlib methods match
their expected shapes, for example:

- `Mono.RuntimeClassHandle.get_Value` -> `mov rax,[rcx]; ret`
- `Mono.RuntimeClassHandle.GetHashCode` -> `mov eax,[rcx]; ret`
- `Mono.RuntimeGenericParamInfoHandle..ctor` -> `mov [rcx],rdx; ret`
- `DynamicValue` constructor overloads are small field-store ctors
- `BattleEventRow.get_Prefab` / `get_LevelAreaPrefab` /
  `get_BEActionBarPrefab` resolve to distinct executable bodies that read the
  object header/state before returning the cached prefab pointer

These are recorded as mapping evidence only; no implementation was
decompiled for Battle DSL semantics.

## 5. Cross-version validation

`compare_method_code_registries.py` validates version-independent shape:

- MethodDefinition schema `0x14C / 26 bytes`: PASS
- consumer shape `method_index -> registry.field -> qword[idx*8]`: PASS
- method-index decode markers (`0x1A7AF5FE`, `0x5F93`): PASS
- one table slot per MethodDefinition: PASS
- all non-null pointers executable / unique / in `il2cpp`: PASS
- common sample type+method identity: PASS (38/38)
- common direct-native samples valid in both versions: PASS (20/20)
- native RVA differs between versions: PASS (20/20, expected)

Field offset `+0x40` vs `+0x88` is recorded as a version-specific registry
layout detail, not as a mechanism mismatch.

## 6. Machine outputs

```text
data/raw/4.4.54/il2cpp/method_code_registry_proof_4.4.54.json
data/raw/4.4.0/il2cpp/method_code_registry_proof_4.4.0.json
data/raw/4.4.54/il2cpp/method_code_cross_version_validation.json
```

The proofs contain ~80 sample rows (names, mapping_kind, native RVA, section,
first bytes, first instructions) plus full table statistics; they are not a
700k-method dump.

## 7. Tools added

- `tools/reverse/scripts/build_method_code_registry.py`
  - auto-locates the consumer and the code table;
  - decodes metadata names and builds the proof JSON;
  - `--code-table-rva` override available for future versions.
- `tools/reverse/scripts/compare_method_code_registries.py`
  - cross-version shape / semantic validation.

## 8. Not claimed / next session boundary

- vtable slot -> final implementation RVA resolution (virtual methods);
- dispatcher / `.upx0` internals (THUNK entries are stable entry RVAs only);
- semantic decompilation of mapped functions;
- Battle DSL / ability logic / Black Swan analysis.

Stop condition reached: **METHOD_CODE = RVA_REGISTRY_PROOF**.
