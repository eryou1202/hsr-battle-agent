# MHY Metadata Registry — 4.4.54 Session 2

> Session 2 after `MHY_METADATA = PARTIAL_SCHEMA_RECOVERED`.
> Goal: turn the partial directory into a consumer-driven table registry and
> prepare the String / TypeDefinition recovery.
>
> final_status = **MHY_METADATA = CROSS_TABLE_SCHEMA_RECOVERED**

## 0. Summary

- Confirmed previous commit `9cb58d9`.
- Audited usage-tag semantics: parser no longer claims standard IL2CPP enum
  names as CONFIRMED. Tag structure is CONFIRMED; only `0xC0000000` has a
  confirmed special code branch.
- Expanded the directory from 22 candidates to **47 template-field rules**,
  every one of them code-derived (`movsxd [tpl+field]` + `add/xor const` +
  payload/startup base or count transform).
- Reused the same rules against the real 4.4.0 CN GameAssembly/metadata:
  **47/47 transforms identical**, and every payload-rule file offset falls
  inside both metadata files. The table offsets differ between versions, the
  schema transform does not.
- Recovered several consumer-driven cross-table chains (see below).
- Found plaintext, length-prefixed string-literal data at
  `0x166E87E` (`... "ddd, dd MMM yyyy ..." ...`), but the index/offset rule
  for that literal heap is **not yet recovered**. This is recorded as a
  literal-data fact, not as `STRING_TABLE_RECOVERED`.

Machine outputs:

- `data/raw/4.4.54/il2cpp/mhy_table_registry_4.4.54.json`
- `data/raw/4.4.0/il2cpp/mhy_table_registry_4.4.0.json`
- `data/raw/4.4.54/il2cpp/mhy_directory_decode_v2_4.4.54.json`
- `data/raw/4.4.54/il2cpp/mhy_usage_tag_audit_4.4.54.json`

## 1. Usage-tag semantic audit

Code evidence (RVA `0x5720`, second accessor `0x1EB31`, many generated
accessors):

```text
mov ecx, [usage_table + index*4]
mov ebx, ecx
and ebx, 0x1FFFFFFF          ; low 29 bits = index
and ecx, 0xE0000000          ; high 3 bits = tag
cmp ecx, 0xC0000000          ; only this tag has a special branch
```

Conclusion:

| raw tag | structure | semantic name |
|---|---|---|
| `0x00000000` | CONFIRMED | UNCONFIRMED |
| `0x20000000` | CONFIRMED | UNCONFIRMED (standard candidate TypeInfo) |
| `0x40000000` | CONFIRMED | UNCONFIRMED (standard candidate Il2CppType) |
| `0x60000000` | CONFIRMED | UNCONFIRMED (standard candidate MethodDef) |
| `0x80000000` | CONFIRMED | UNCONFIRMED (standard candidate FieldInfo) |
| `0xA0000000` | CONFIRMED | UNCONFIRMED (standard candidate StringLiteral) |
| `0xC0000000` | CONFIRMED | SPECIAL_BRANCH_CONFIRMED; standard enum name UNPROVEN |
| `0xE0000000` | CONFIRMED | UNCONFIRMED |

Historical raw tag data was not modified. `parse_mhy_metadata_primitives.py`
now stores structure names and semantic candidates separately and emits a
`tag_semantic_audit` block.

## 2. Consumer-driven registry highlights

`recover_mhy_table_registry.py` records, per template field:

`template_field`, `transform_type`, `transform_constant`, `decoded_u32`,
`base_kind`, `file_offset`, `consumer_rvas`, `entry_size`,
`entry_field_accesses`, `candidate_semantic`, `semantic_evidence`,
`structure_status`, `semantic_status`.

Notable rows:

| field | transform | file offset | entry | structure / semantic | evidence |
|---|---|---|---|---|---|
| `0x160` | `+0xC769CD52` | `0x4C4308C` | 4 | CONFIRMED / SUPPORTED | tag mask + `0xC` branch |
| `0x38` | `+0xF778F1AB` | `0x1D4207C` | 12 | CONFIRMED / SUPPORTED | `0xC` branch triple reader |
| `0x84` | `^0x68531D3F` | `0x17DBCDC` | **70** | CONFIRMED / CANDIDATE | `imul idx,0x46`; `+0xC` magic `0x1C2AD2AB`; decoded `+0x24/+0x28/+0x3A/+0x3C/+0x43` |
| `0x70` | `^0x57A78949` | `0x16687B8` | 4 | CONFIRMED / SUPPORTED | value indexes `0x84` records |
| `0x12C` | `^0x26F0FC20` | `0x3712A1C` | 4 | CONFIRMED / SUPPORTED | `0x84` `+0x3A` indexes this type-index table |
| `0x1FC` | `^0x6238CDB0` | `0x8C8BC0` | 12 | CONFIRMED / SUPPORTED | `+0x0` -> 16-byte type entry, `+0x4` -> `0x3C` data offset, `+0x8` match key |
| `0x3C` | `+0x978BE7A5` | `0x166CE90` | 4 stream | SUPPORTED / SUPPORTED | consumer `0x3C1151B` interprets `0x1FC` offset into this stream |
| `0x14C` | `+0xF3A04294` | `0x3A1A77C` | 26 | CONFIRMED / SUPPORTED | usage resolver `0x3C66F80` |
| `0x18` | `+0xE6CD8E6C` | `0x3725A4C` | 8 | CONFIRMED / SUPPORTED | packed `count<<24|start` ranges; binary search |
| `0x1EC` | `+0xA75A2A51` | `0x5D8CA44` | 4 | CONFIRMED / SUPPORTED | `0x18` range scan target; `-1` sentinel |

Count/size fields recovered separately: `0xBC`, `0x74`, `0x134`, `0x178`,
`0x1A8`, `0x1F8` are loader-consumed count/size transforms, not table
pointers.

Startup-metadata fields use the second loaded buffer (`0x9D387B8`), not the
global-metadata payload: `0x150` (40-byte), `0x158`, `0x164` (8-byte),
`0x170`. They are labeled `base_kind=startup` and are not emitted as
global-metadata file offsets.

## 3. Cross-table links (consumer evidence)

```text
usage 0x160 (tag 0xC) ──> 0x38 triples
0x70 u32 ──> 0x84 70-byte record
0x84 +0x3A ──> 0x12C type index ──> 0x3C66940 type resolver
0x34 u16 ──> 0x1C4 12-byte record
0x1C4 +0xA ──> 0x2C 8-byte record ──> 0x3C03BA0
0x18 packed ranges ──> 0x1EC u32 targets ──> allocA pointer cache
0x180 u32 ──> 0x9C 12-byte records
0x1FC 12-byte key map ──> 0x3C type-data byte offsets
```

The `0x84` 70-byte record is the strongest definition-record candidate found
this session: four independent consumers validate the magic at `+0xC`, and
`0x3C67270`/`0x3C674F0` consume its decoded fields to build metadata objects.
Its exact semantic (TypeDefinition vs MethodDefinition) is **CANDIDATE**,
not CONFIRMED.

## 4. String facts

- Plaintext literal data starts at `0x166E87A` with a `0xFFFFFFFF` sentinel
  followed by `int32 length + UTF-8 bytes` records; first entries are
  `"ddd, dd MMM yyyy HH':'mm':'ss 'GMT'"` (len 35),
  `"yyyy'-'MM'-'dd'T'HH':'mm':'ss"` (len 29), etc.
- Search for `Assembly-CSharp` / `UnityEngine` / `mscorlib` in plaintext
  metadata returned no hits; identifier strings are not in this plaintext
  literal heap (or are transformed).
- Therefore **string literals and metadata identifiers are distinct** and
  still require separate recovery. No index rule is claimed.

## 5. Cross-version validation

| check | 4.4.54 | 4.4.0 |
|---|---|---|
| template RVA | `0x47BA958` | `0x563FA90` |
| metadata size | 100,182,380 | 94,803,092 |
| payload rules decoded in-file | 47/47 | 47/47 |
| identical transform (field, op, const) | 47/47 | 47/47 |
| identical file offsets | only the two payload-start aliases and shared aliases | expected |

This upgrades the schema-shape reuse to strong E2: same code-level decode
rules, different per-build template values, both decode to valid in-file
table offsets.

## 6. Not claimed / next session

Not recovered yet:

- identifier string table index/length rule;
- TypeDefinition identity (the `0x84` 70-byte chain is the first target);
- MethodDefinition / FieldDefinition identities;
- payload transform algorithm.

Recommended next move: trace `0x3C67270`/`0x3C674F0` callers backwards to the
object whose fields select `0x84` records, and use the decoded `+0x24/+0x28`
indices against the literal heap / identifier heap to prove or reject
TypeDefinition.
