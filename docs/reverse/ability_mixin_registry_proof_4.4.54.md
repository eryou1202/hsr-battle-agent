# Ability Mixin Runtime Type Bridge Proof 4.4.54

> Session after `DESIGN_RUNTIME_BRIDGE = PARTIAL_MAPPING_RECOVERED` (1f9e1cc).
> Goal: recover the AbilityList polymorphic element Runtime Type / parser
> descriptor dispatch, and close
> serialized element -> subtype discriminator -> concrete Runtime Class.
>
> final_status = **DESIGN_RUNTIME_BRIDGE = ABILITY_MIXIN_REGISTRY_PROOF**

## 0. Conclusion

The polymorphic Ability element dispatch is a **generated runtime parser
registry**, not a per-domain static switch:

```text
serialized element
  -> ULEB128 discriminator
  -> MKIOEPLIEIH.OJNNBEJLDIJ (0x1CB743F0)
  -> [[[0x95B1518] + 0x6990] + 0x20 + discriminator*8]   ; registry entry
  -> [entry + 8]                                          ; generated helper
  -> helper allocates concrete object from its type_global
  -> helper calls concrete Runtime Class parser MethodDefinition
```

This chain is now machine-proven for **634 runtime-initialized registry slots**
(636 array entries, 2 null slots), with **614 concrete parser
MethodDefinitions** recovered. The same mechanism is used by **111 confirmed
callers**, including `SkillConfig.VisibleCondition`,
`SkillConfig.InsertCondition`, and `UsableConditionConfig.UsableCondition`.

The previous target field `SkillAbilityConfig.AbilityList` was corrected: it is
`List<string>`, not the polymorphic mixin list (see section 2).

## 1. Registry identity

| item | 4.4.54 value |
|---|---|
| builder | `MKIOEPLIEIH.cctor`, method index `132205`, RVA `0x1CB745A0` |
| entry count | `0x27C` = 636 |
| registry array static slot | `[[0x95B1518] + 0x6990]` |
| dispatcher | `MKIOEPLIEIH.OJNNBEJLDIJ`, method index `132840`, RVA `0x1CB743F0` |
| discriminator reader | ULEB128 (`MOMNMLHNPLH.BIKABOFADBP @ 0x1CB8A410`) |
| dispatch shape | `entry = [array + 0x20 + code*8]; call [entry + 8]` |
| helper slot relation | discriminator `d>=1` -> helper method index `132205 + d` (code table verified for all 634 non-null slots) |

The `.cctor` is a generated unrolled initializer: it allocates a 636-entry
array, explicitly stores 0 into slots 0 and 538, and copies the remaining
qwords from 634 static `.data` descriptor globals. Every descriptor global RVA
was recovered automatically from the unrolled `mov reg,[rip+disp];
mov [rax+slot],reg` pairs.

## 2. Correction: SkillAbilityConfig.AbilityList is List<string>

Code-level, not name-level, evidence:

1. `SkillAbilityConfig.OJNNBEJLDIJ` (method index 103105, RVA `0x1D4AAC90`)
   reads one field-presence bitfield. Bit 0 parses `Skill` through
   `0x1CBA4E70`; bit 1 loads descriptor pair `0x96B7C00 / 0x96B7C08` and
   tail-jumps to the generic object-list reader `0x16C86A10`.
2. The generic reader stores the list at object offset `+0x18`; this is the
   field `AbilityList` (metadata FieldDefinition index 75482, type_reference
   433276).
3. Runtime read of `[0x96B7C00 + 8]` = `0x1CBA4E70`
   (`NJLMNDLDGNF.HLECIAGGJGH`, method index 74347). That function reads a
   ULEB length and calls `System.Text.Encoding.get_UTF8`
   (`0x1BB86510`) to materialize a length-prefixed UTF-8 string.
4. The same descriptor pair and parser serve `SkillConfig.ChildSkillList` and
   every field carrying type_reference 433276.

Therefore:

```text
SkillAbilityConfig.AbilityList -> List<string>
SkillAbilityConfig.Skill      -> string
historical label "AbilityList = polymorphic mixin list": DISPROVEN by code
```

This is recorded as a correction; no old semantic name was reused.

## 3. Where the real Ability polymorphic elements are

`SkillConfig.FromBinary` (method index 108915, RVA `0x1D4AAEE0`) reads two
ULEB field-presence bitfields and branches over 64 + 13 = 77 fields in
metadata FieldDefinition order. The automated field map
(`extract_skillconfig_field_map.py`) recovered all 77 branch -> field-name
pairs. The relevant ability-element fields:

| ordinal | bitfield bit | field | parser dataflow |
|---|---|---|---|
| 57 | rbx bit 57 | `UsableConditions` | list reader `0x16C86A10`, descriptor pair `0x96BF2A0/0x96BF2A8`, element parser `RPG.GameCore.UsableConditionConfig.OJNNBEJLDIJ` (`0x1D597320`) -> registry dispatcher |
| 58 | rbx bit 58 | `VisibleCondition` | direct call to registry dispatcher `0x1CB743F0` |
| 65 | r14 bit 1 | `InsertCondition` | direct call to registry dispatcher `0x1CB743F0` |

The list reader path satisfies the original "generic list/object reader ->
descriptor -> element parser" question for the real polymorphic list:
element descriptor `0x96BF2A0` has `[+8] = UsableConditionConfig.OJNNBEJLDIJ`
(so the element Runtime Class and parser are now known), and that parser
dispatches its polymorphic `UsableCondition` field through the registry.

## 4. Runtime validation (read-only, code-guided)

Local ppSR / Cultivation client was already running and initialized.
`tools/runtime_snapshot/mkioeplieih_registry_snapshot.py` used only:

- `OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ)`
- PSAPI `EnumProcessModulesEx`
- `ReadProcessMemory` on the static-derived chain:
  `GameAssembly.base + 0x95B1518 -> +0x6990 -> array +0x20 + i*8 ->
   entry + 8`

Results:

| item | value |
|---|---|
| registry array pointer | runtime heap array, length 636 |
| null slots | 2 (discriminators 0 and 538) |
| executable parser entries | 634 |
| parser code table exact matches | 634/634 |
| concrete parser MethodDefinitions recovered | 614 |
| pure allocation stubs (no internal parser call) | 20 |

No full address-space scan, no random heap scan, no writes, no remote code.

## 5. Black Swan 2 / 8 / 14 / 16

After the mechanism was recovered, the historical 15 Black Swan records were
re-checked. Their historical `first_mixin_type` codes are all inside the
registry range, and the four observed values resolve to four distinct Runtime
Classes:

| historical code | frequency | Runtime Class | parser index | parser RVA |
|---|---|---|---|---|
| 2 | 7 | `RPG.GameCore.AdvByCheckGameMode` | 118892 | `0x1CD2B170` |
| 8 | 3 | `RPG.GameCore.AdvByCompareDynamicValue` | 117174 | `0x1CD2DFF0` |
| 14 | 1 | `RPG.GameCore.AdvByFastDeliverHasMultiRoute` | 123198 | `0x1CD30B60` |
| 16 | 4 | `RPG.GameCore.AdvByInCustomZone` | 116292 | `0x1CD31740` |

Honest boundary: this is **registry-range validation**. The byte-level identity
of the historical Black Swan record prefix (which outer parser consumes that
ULEB as the registry discriminator) is still not closed, and the historical
field name `first_mixin_type` remains provisional. No mapping was adjusted to
make the old numbers fit.

## 6. Cross-version 4.4.0

No 4.4.0 client was running, so the 4.4.0 bridge was built fully statically:

- same registry type `MKIOEPLIEIH`, same dispatch schema;
- 4.4.0: cctor method 129674 `0x1BE83B20`, dispatcher 130306 `0x1BE83970`,
  global `0x964F4E0`, slot offset `+0x22C0`, entry count 633;
- 632 common discriminators are aligned by Runtime Class sequence with
  `SequenceMatcher` ratio 0.9945;
- 630 aligned pairs all have identical concrete parser method names; all
  checked RVAs differ as expected;
- 4.4.54 inserts 4 registry entries and drops one trailing unresolved slot
  relative to 4.4.0.

Status: `BRIDGE_CROSS_VERSION_OK_WITH_INSERTIONS`. Discriminator numbers are
version-specific; the descriptor/factory schema and Runtime Class identities
are stable.

## 7. Machine outputs

```text
data/raw/4.4.54/bridge/ability_mixin_type_bridge_4.4.54.json
data/raw/4.4.54/bridge/ability_mixin_registry_proof_4.4.54.json
data/raw/4.4.54/bridge/mkioeplieih_registry_snapshot_4.4.54.json
data/raw/4.4.54/bridge/skillconfig_field_map_4.4.54.json
data/raw/4.4.54/bridge/ability_mixin_registry_black_swan_validation_4.4.54.json
data/raw/4.4.0/bridge/ability_mixin_type_bridge_4.4.0.json
data/raw/4.4.54/bridge/ability_mixin_registry_cross_version_4.4.0_vs_4.4.54.json
```

Supporting disassembly under `data/raw/4.4.54/bridge/` and
`data/raw/4.4.0/bridge/` (registry cctor, dispatcher, helper samples).

## 8. Tools added / extended

- `tools/runtime_snapshot/ability_descriptor_snapshot.py` - one
  parser/type descriptor global pair snapshot.
- `tools/runtime_snapshot/mkioeplieih_registry_snapshot.py` - full 636-entry
  registry runtime snapshot, code-guided reads only.
- `tools/reverse/scripts/build_ability_mixin_registry_bridge.py` - runtime
  registry -> method code registry -> metadata bridge builder.
- `tools/reverse/scripts/build_ability_mixin_registry_bridge_static.py` -
  static-only cross-version bridge builder.
- `tools/reverse/scripts/compare_ability_mixin_registries.py` - cross-version
  schema + sequence alignment validator.
- `tools/reverse/scripts/extract_skillconfig_field_map.py` - 77 branch ->
  FieldDefinition name map.
- `tools/reverse/scripts/build_black_swan_registry_validation.py` - historical
  code range validation.

## 9. Not claimed / next session boundary

- Battle DSL / Execute / Apply / damage / modifier settlement semantics.
- Semantic TypeDefinition name of the shared polymorphic base field
  (metadata type_reference 480840).
- Byte-level serializer identity of the historical Black Swan record prefix.
- Generic IL2CPP runtime type system recovery.
- `.upx0` dispatcher internals.

Stop condition reached: **DESIGN_RUNTIME_BRIDGE = ABILITY_MIXIN_REGISTRY_PROOF**.
