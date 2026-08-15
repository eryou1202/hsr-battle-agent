# MHY 0x84 TypeDefinition Proof — 4.4.54 Session 3

> Session after `MHY_METADATA = CROSS_TABLE_SCHEMA_RECOVERED`.
> Goal: prove or disprove that template field 0x84 is the TypeDefinition /
> definition-record table, for the chain `0x70 -> 0x84 -> 0x12C`.
>
> final_status = **MHY_METADATA = TYPE_REGISTRY_PROOF**

## 0. Conclusion

`0x84` is the **TypeDefinition table** of the MHY global-metadata format.

This is the first real Type Registry Proof for this format. It is supported by
four independent evidence classes:

| evidence | class | result |
|---|---|---|
| 70-byte records, `imul idx,0x46`, magic gate | E4 + E2 | CONFIRMED |
| code-proven identifier resolver; names decode to real mscorlib/Unity/game types | E4 + E3 | CONFIRMED |
| `+0x08/+0x34` method range covers 0..N exactly once | E4 + E2 | SUPPORTED |
| `+0x3A/+0x43` type-descriptor ranges cover the 0x12C table exactly once | E4 + E2 | SUPPORTED |

`0x84` semantic status is upgraded from CANDIDATE to **CONFIRMED as
TypeDefinition**. Field-level semantic names remain SUPPORTED/UNKNOWN exactly
as recorded in the access map.

## 1. Record identity

| item | 4.4.54 | 4.4.0 |
|---|---|---|
| template field | `0x84` | `0x84` |
| transform | `xor 0x68531D3F` | identical |
| file offset | `0x17DBCDC` | `0x1697B20` |
| entry size | 70 (`0x46`) | identical |
| record count | 80880 | 76921 |
| identifier resolver | CONFIRMED | CONFIRMED, same constants |

Counts are bounded by the next known table offset (field `0x38`). 4.4.0 has
two padding bytes after the last record; fixed offsets are not compared.

## 2. Access map (manual discovery -> automated extraction)

Machine outputs:

- `data/raw/4.4.54/il2cpp/mhy_0x84_record_access_map_4.4.54.json`
- `data/raw/4.4.0/il2cpp/mhy_0x84_record_access_map_4.4.0.json`

`analyze_mhy_definition_candidate.py` finds 43 static `0x84` decode sites in
GameAssembly; 9 of them form record pointers with `imul 0x46`. The automated
extractor cross-checks `+0x0C` and `+0x3C`; the rest of the map is curated
from exact disassembly lines and is identical across versions.

Recovered field map (field names deliberately `field_0xXX`):

| off | width | access | decode | downstream | semantic status |
|---|---|---|---|---|---|
| `+0x08` | u32 | read | `^ 0x1A7AF5FE` (s32, -1 sentinel) | qword runtime pointer list start | method range start (SUPPORTED) |
| `+0x0C` | u32 | cmp | none | acceptance gate `== 0x1C2AD2AB` | UNKNOWN (not universal) |
| `+0x24` | u32 | read | `+ 0xF1D32D89` | 0x3C58D70 resolver | namespace key (SUPPORTED) |
| `+0x28` | u32 | read | `+ 0xE9FD68F8` (-1 sentinel) | 0x3C58D70 resolver | name key (CONFIRMED) |
| `+0x34` | u16 | read | `+ 0x5F93` (u16 wrap) | loop count over `+0x08` list | method range count (SUPPORTED) |
| `+0x3A` | s16 | read | `^ 0xB2C0` sign-extended | start index into `0x12C` | type descriptor range start (SUPPORTED) |
| `+0x3C` | u16 | read | `+ 0x5404` (-1 sentinel) | index into `0xF0` 16-byte records | type relation index (SUPPORTED) |
| `+0x43` | u8 | read | `(v+4)&0xFF`; `0xFC` -> 0 | loop count over `0x12C` | type descriptor range count (SUPPORTED) |
| `+0x44` | u8 | read | `^ 0xC7` | pointer comparison count | UNKNOWN |

## 3. Identifier resolver (the key result)

`0x3C58D70` is the code-proven identifier resolver. A 32-bit key packs:

- negative key: `offset = key & 0x7FFFFF`, `length = (key >> 23) & 0xFF`;
- non-negative key: `offset = key & 0x1FFFFFF`, `length = (key >> 25) & 0x3F`;
- `key == -1` returns the empty string.

Ciphertext sits at `field_0x1B4_base + offset` and is decoded with a rolling
64-bit XOR:

```text
seed = 0x75B679DAF67C3F24 + 0x907C49622D94D21A * offset
for each qword: plain = cipher ^ seed; seed += 0x3E693CD23A41FDEF
```

Validation: all `80880 * 2` decoded keys in 4.4.54 produce printable/empty
UTF-8, 0 failures. First 12 records decode to the standard mscorlib order:
`<Module>`, `<>f__AnonymousType0`1`, `Locale`, `SR`, `Mono.Runtime`,
`Mono.RuntimeClassHandle`, ... Cross-version 4.4.0 produces identical names
for common indices with the same resolver constants.

This also answers the identifier question from earlier sessions: identifiers
are **not plaintext**, they are offset+length packed keys into a
code-decrypted heap at field `0x1B4`. No brute-force was used; the transform
is code-proven.

## 4. The 0x70 -> 0x84 -> 0x12C chain

### 4.1 `0x70` = INDEX_MAP (SUPPORTED)

- entry size 4, consumer `mov ecx,[base+idx*4]`.
- Leading domain-valid run: 3106 entries in 4.4.54 / 3088 in 4.4.0.
- Values: `0x72..0x17A7` (4.4.54), all inside the 0x84 record count.
- No `-1` in the leading run; 3076 distinct of 3106 (30 values repeat twice).
- Not an identity map and not a permutation of the full table.
- The consumer compares the mapped value to `-1`, then uses `imul 0x46`.

Classification: **INDEX_MAP**, not DIRECT_INDEX / TOKEN_MAP / OFFSET_MAP.
The map is used by the image/assembly initializer (`0x3C82BAC`) to translate a
logical index space into 0x84 record indices.

### 4.2 `0x84` = TypeDefinition (CONFIRMED)

See sections 1-3. Additional consumer evidence:

- `0x3C67270` builds runtime metadata objects from the record: decodes
  `+0x28/+0x24` names, iterates `+0x3A..+0x43` entries and resolves each one
  through `0x3C66940`.
- `0x3C82BAC` and `0x3C674F0` validate `+0x0C` and call the same builder.
- `0x3C80BA6/0x3C80C09` walks the `+0x08/+0x34` range and collects qword
  runtime pointers into a per-type list.
- `0x3C5B5F1 / 0x3C63107` use `+0x3C` to address 16-byte records in the
  `0xF0` table while comparing runtime type objects.

### 4.3 `0x12C` = type descriptor index table (SUPPORTED)

- entry size 4, capacity 19468 (bounded by field `0x18`).
- Values `0x0D..0x13BE3`, all distinct, no `-1` sentinel.
- `0x84` records reference the table through `+0x3A` (start) and `+0x43`
  (count): the ranges cover **every entry exactly once**, no gaps and no
  overlaps (10568 referencing records).
- Consumer `0x3C672F1` passes each entry to `0x3C66940`, a `.upx0` thunk,
  so the final semantic name of an entry is intentionally left UNKNOWN.

## 5. Magic 0x1C2AD2AB questions

1. Are all entries equal? **No.** 61412 / 80880 (75.9%) equal the value;
   10569 distinct values observed.
2. Does 4.4.0 show it? Yes: same dominant value and same consumer compare.
3. Do consumers compare it explicitly? Yes (`0x3C82A81`, `0x3C82BD8`,
   `0x3C67526`).
4. Is it a hash/tag/validation value? Only the **gate role** is proven:
   mismatch skips the record in those loops. No semantic name is claimed.
5. Other constants exist in neighboring fields (e.g. `+0x1C` is mostly
   `0x39D706EE`), but only `0x1C2AD2AB` has consumer validation evidence.

So `0x1C2AD2AB` is a consumer-validated gate value, not a universal record
magic. The previous "stable magic" wording is corrected in the access map.

## 6. Cross-version validation

`compare_mhy_definition_access_maps.py` compares version-independent shape:

- schema / entry size / index stride: PASS
- field access map (offset, width, decode, consumer RVAs): PASS
- identifier resolver constants: PASS
- method range coverage / 0x12C coverage / 0xF0 bounds: PASS
- consumer scan site count: PASS
- identifier samples for common indices: PASS
- type registry proof status: PASS

Fixed file offsets are intentionally not compared.

Output: `data/raw/4.4.54/il2cpp/mhy_0x84_cross_version_validation.json`.

## 7. Minimal Type Registry Proof

Outputs:

- `data/raw/4.4.54/il2cpp/type_registry_proof_4.4.54.json`
- `data/raw/4.4.0/il2cpp/type_registry_proof_4.4.0.json`

Each proof contains 32 records with stable record index, resolved name and
namespace, method range, type-descriptor range, and 0xF0 relation index.
Semantic sanity search hits (not xref work): `DynamicValue`
(`RPG.GameCore.DynamicValue`), `BattleEvent*` (`RPG.GameCore`), `Ability*`,
`Modifier*`, `Predicate*`, `Target*`, `Mixin*`.

Stop condition reached: **MHY_METADATA = TYPE_REGISTRY_PROOF**.

## 8. Tools added / extended

- `tools/reverse/scripts/analyze_mhy_definition_candidate.py`
  (narrow; access map + chain analysis + identifier resolver + proof)
- `tools/reverse/scripts/compare_mhy_definition_access_maps.py`
  (cross-version validator)

## 9. Not claimed / next session boundary

- 0x12C entry semantic name (consumer is a `.upx0` thunk).
- Full MethodDefinition / FieldDefinition table recovery.
- Parent/base relation and image/assembly relation semantic decoding
  (code evidence exists but is not part of this minimal proof).
- Payload transform for regions outside the identifier heap.
- Any of the other 44 registry tables.

Do not continue into MethodDefinition recovery or Battle DSL in this session.
