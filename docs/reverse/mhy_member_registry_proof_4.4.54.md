# MHY Metadata Member Registry Proof — 4.4.54 Session 4

> Session after `MHY_METADATA = TYPE_REGISTRY_PROOF`.
> Goal: recover MethodDefinition and FieldDefinition on top of the CONFIRMED
> TypeDefinition table, and build Type -> Method -> Field registry proofs.
>
> final_status = **MHY_METADATA = MEMBER_REGISTRY_PROOF**

## 0. Conclusion

The MHY metadata format has direct MethodDefinition and FieldDefinition
tables. Both are now CONFIRMED, cross-version validated, and connected to the
existing TypeDefinition registry:

| table | template field | entry size | 4.4.54 count | 4.4.0 count | semantic status |
|---|---|---|---|---|---|
| TypeDefinition | `0x84` | 70 | 80880 | 76921 | CONFIRMED (previous session) |
| MethodDefinition | `0x14C` | 26 | 732328 | 703008 | **CONFIRMED** |
| ParameterDefinition | `0x30` | 8 | 655072 | 625798 | SUPPORTED (table identity CONFIRMED) |
| FieldDefinition | `0x20` | 8 | 555259 | 526693 | **CONFIRMED** |

Every one of those counts is machine-derived from code-proven range relations,
not guessed from file size.

## 1. MethodDefinition: 0x14C, entry size 26

### 1.1 Table identity

- Directory rule: `payload + signed32(template[0x14C] + 0xF3A04294)`.
- Consumer addressing: `idx -> idx*26` (`lea idx*5; lea ...*5; add idx`).
- Upper bound: next code-known table `0x160`.
  - 4.4.54: `(0x4C4308C - 0x3A1A77C) / 26 = 732328`.
  - 4.4.0: `(0x484B560 - 0x36DCE20) / 26 = 703008`.
- The TypeDefinition `+0x08 ^ 0x1A7AF5FE` / `+0x34 + 0x5F93` ranges cover
  `0..N-1` exactly once in both versions. Table capacity equals the partition
  total in both versions.

### 1.2 Per-record transform

Every field is keyed by a 64-bit rolling hash of the method index:

```text
h = (((idx*0x31E1) ^ 0x33914937) * 0x2C03F17D) >> 0x17
h = (h * 0x540CC9F4) >> 0x15
hash32c = (h + 0x71BC7861) & 0xFFFFFFFF
```

This transform appears in every 0x14C consumer
(`0x3C66FCC`, `0x3C7136D`, `0x3C71C8F`, `0x3C72048`, `0x3C72324`,
`0x3C7D470`).

### 1.3 Recovered field map

| off | width | decode | semantic |
|---|---|---|---|
| `+0x00` | u32 | `name_key = hash32c ^ raw ^ 0x0E714BC1` -> `0x3C58D70` | **name key (CONFIRMED)** |
| `+0x04` | u32 | `param_start = hash32c ^ raw ^ 0x009889B8` | **parameter start (CONFIRMED, -1 sentinel)** |
| `+0x08` | u32 | `return_ref = hash32c ^ ((raw + 0x9AC1F4E3) & M32)` | return type reference (SUPPORTED, -1 sentinel) |
| `+0x0C` | u32 | `raw ^ hash32c ^ 0x09F73733` | flags candidate (UNKNOWN) |
| `+0x0E` | u16 | `raw ^ low16(hash32c)` | flags; bit 0x10 gates name lookup (SUPPORTED) |
| `+0x10` | u32 | `declaring_type = hash32c ^ raw ^ 0x2A5FABE8` | **declaring TypeDefinition index (CONFIRMED)** |
| `+0x14` | u16 | `sext16((raw + 0xFFFF86FD) ^ low16(hash32c))` | signed slot/index candidate (UNKNOWN) |
| `+0x16` | u16 | `(raw + 0xFFFFE395) ^ low16(hash32c)` | UNKNOWN |
| `+0x18` | u8 | `raw ^ low8(hash + 0x71BC7861) ^ 0xA8` | **parameter count (CONFIRMED)** |
| `+0x19` | u8 | `raw ^ low8(hash + 0x71BC7861)` | flags candidate (UNKNOWN) |

### 1.4 Closing evidence

- All `732328` decoded `+0x10` values equal the TypeDefinition record that
  owns the corresponding method range. 0 mismatches.
- First methods decode to the expected mscorlib order: `.ctor`, `Equals`,
  `GetHashCode`, `ToString`, `Locale.GetText`, `SR.Format`,
  `mono_runtime_install_handlers`, ...
- 4.4.0 uses the identical layout / transforms / consumer constants and the
  same names for common indices.

## 2. ParameterDefinition: 0x30, entry size 8 (natural bonus)

The MethodDefinition consumer at `0x3C72314` reads `+0x04` as parameter start
and `+0x18` as parameter count, then addresses 8-byte records at:

```text
payload + signed32(template[0x30] + 0xDCF5FDBE)
```

- Method parameter ranges cover the table exactly once:
  - 4.4.54: 655072 parameters.
  - 4.4.0: 625798 parameters.
- Record decode for parameter ordinal `q = method.paramStart + i`:

```text
roll = ((((q*0x72E1D74B12B + 0x1911D05AFF5) >> 0xB) * 0x58B870A2
         + 0x83CF7B44)) & 0xFFFFFFFF
name_key  = (raw[+4] ^ 0x7103092E - roll) & 0xFFFFFFFF   -> 0x3C58D70
type_ref  = (raw[+0] ^ 0x67E90DC5 - roll) & 0xFFFFFFFF   -> 16-byte type entries
```

All observed parameter `name_key`s are `0xFFFFFFFF` in both versions; MHY
stripped parameter names. The type reference path is stable and is recorded as
`relation candidate` for later type-system work.

## 3. FieldDefinition: 0x20, entry size 8

### 3.1 TypeDefinition field range (consumer recovered)

Two previously unknown TypeDefinition fields are now CONFIRMED:

| off | width | decode | semantic |
|---|---|---|---|
| `+0x20` | u32 | `field_start = (raw + 0x8B7AC79C) & 0xFFFFFFFF` | **field range start (CONFIRMED, -1 sentinel)** |
| `+0x32` | u16 | `field_count = (raw + 0x444D) & 0xFFFF` | **field range count (CONFIRMED)** |

Consumer: `0x3C5C19A` (count -> allocation), `0x3C5C4D8` (start -> loop over
0x20 table). The ranges cover the field table exactly once, in TypeDefinition
record order:

- 4.4.54: 555259 fields.
- 4.4.0: 526693 fields.

### 3.2 FieldDefinition record

- Directory rule: `payload + signed32(template[0x20] + 0xB2FCE189)`.
- Entry size 8: consumer `0x3C5C5CA` reads `[base + idx*8 + 4]` and
  `0x3C5C5FC` reads `[base + idx*8]`.
- Per-record rolling key derives from the declaring type's raw `+0x20` value
  and the field ordinal:

```text
roll = 0xAD416BB9 - (raw_type_field_start * 0x2C5DCB00)   (mod 2^32)
roll += field_ordinal * 0xD3A23500                      (mod 2^32)

name_key  = (raw[+0] + roll + 0x2AAFC785) & 0xFFFFFFFF  -> 0x3C58D70
type_ref  = (raw[+4] + roll) & 0xFFFFFFFF               -> 16-byte type entries
```

- `type_ref == 0xFFFFFFFF` is the sentinel; non-sentinel values index the same
  16-byte type-entry array used by MethodDefinition return references.
- Sanity names decode to real fields: `<message>i__Field`, `default_vtable`,
  `error_code`, `name`, `culture`, `xmlSpace`, `handler`, and game fields such
  as `AbilityList`, `BattleEventName`, `ParamList`, `mapValue`,
  `s_escapeStringBuilder`.

## 4. Registry corrections

The 0x20 FieldDefinition region is large (8 * field count). It supersedes a
few earlier HYPOTHESIS / UNKNOWN directory starts that fell inside the region
(e.g. 4.4.54 candidates `0x1DC`, `0x78`, `0x158`). Those entries remain in the
historical session-2 files but are not treated as independent table starts in
the refreshed registry.

## 5. Battle sanity sample (metadata names only, no xref / no DSL)

`build_mhy_member_registry.py` picks the types already found by the Type
Registry proof and prints member names. Highlights from 4.4.54:

- `RPG.GameCore.DynamicValue`: 6 fields (`s_escapeStringBuilder`, `EMPTY`,
  `mapValue`, `stringValue`, `arrayValue`, `unionValue`), constructor overloads.
- `RPG.GameCore.DynamicValueType`: enum fields `INT/FLOAT/BOOL/ARRAY/MAP/
  STRING/NULL/value__`.
- `RPG.GameCore.DynamicValueReadType`: `None/SkillParam/.../StageBattleEvent`.
- `RPG.GameCore.BattleEventButtonType`: `None/Attack/Buff/Debuff/Heliobus`.
- `RPG.GameCore.BattleEventEntitySubType`: `Unknown/TurnCountDownEvent/
  ChallengerEvent/.../TurnCountDownWarningEvent`.
- `RPG.GameCore.BattleEventRow`: methods `FromTableOffset`, `Reset`,
  `FromBinaryWithoutNew`, `FromBinary`, `get_Prefab`, ...; fields
  `AbilityList`, `DescrptionText`, `BattleEventName`, `ParamList`,
  `HeadIcon`, ...

4.4.0 shows the same class of results with its own type indices.

## 6. Cross-version validation

`compare_mhy_member_access_maps.py` compares version-independent shape only:

- MethodDefinition table rule / entry size / field access paths: PASS.
- ParameterDefinition table rule / range relation: PASS.
- FieldDefinition table rule / TypeDefinition field range rule: PASS.
- Structural validations (partitions exact once, declaring type 0 mismatch):
  PASS.
- Identifier samples for common record indices: PASS.
- Semantic sample type member names (multiset comparison): PASS.

Output: `data/raw/4.4.54/il2cpp/mhy_member_cross_version_validation.json`.

## 7. Machine outputs

```text
data/raw/4.4.54/il2cpp/mhy_method_definition_access_map_4.4.54.json
data/raw/4.4.54/il2cpp/method_registry_proof_4.4.54.json
data/raw/4.4.54/il2cpp/mhy_field_definition_access_map_4.4.54.json
data/raw/4.4.54/il2cpp/field_registry_proof_4.4.54.json
data/raw/4.4.54/il2cpp/metadata_member_registry_proof_4.4.54.json
data/raw/4.4.54/il2cpp/mhy_member_cross_version_validation.json
data/raw/4.4.0/il2cpp/mhy_method_definition_access_map_4.4.0.json
data/raw/4.4.0/il2cpp/method_registry_proof_4.4.0.json
data/raw/4.4.0/il2cpp/mhy_field_definition_access_map_4.4.0.json
data/raw/4.4.0/il2cpp/field_registry_proof_4.4.0.json
data/raw/4.4.0/il2cpp/metadata_member_registry_proof_4.4.0.json
```

Proof samples are deliberately limited; the machine files contain stats and
samples, not a 700k-method human dump.

## 8. Tools added / extended

- `tools/reverse/scripts/analyze_mhy_method_candidate.py` — narrow Method
  access-map / partition / declaring-type validator.
- `tools/reverse/scripts/analyze_mhy_field_candidate.py` — narrow Field
  access-map / range validator.
- `tools/reverse/scripts/build_mhy_member_registry.py` — limited Type ->
  Method -> Field proof builder.
- `tools/reverse/scripts/compare_mhy_member_access_maps.py` — cross-version
  member validator.
- `tools/reverse/scripts/recover_mhy_table_registry.py` — refreshed 0x14C /
  0x30 / 0x20 semantics and cross-links.

## 9. Not claimed / next session boundary

- MethodDefinition -> code registration -> GameAssembly RVA mapping.
- Return type / field type semantic names (the stable references are recorded,
  the type system is not decoded).
- Parameter names (MHY stores sentinel-only in the observed builds).
- Image / Assembly semantic decoding.
- Battle DSL, ability logic, Black Swan analysis.

Stop condition reached: **MHY_METADATA = MEMBER_REGISTRY_PROOF**.
