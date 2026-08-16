# HSR Unpack/Reverse Pipeline v1

> **Pipeline status for this repository snapshot:**
> `UNPACK_PIPELINE = V1_STATIC_COMPLETE`
>
> The full static pipeline runs PASS on the current 4.4.54 client assets.
> Runtime enrichment (`generated_polymorphic_registry`) is optional and
> currently `NOT_RUN`; `static_pipeline = PASS + runtime_enrichment = NOT_RUN`
> is an explicitly supported legal state.

This is the **engineering-facing, versioned, repeatable** wrapper around the
CONFIRMED reverse results. It does not perform new discovery. Unknown items
are preserved or reported as anomalies, never silently dropped or renamed.

- Client = **Reference / Oracle**. The local client is only read as the source
  of truth. It is not a training sandbox and is never modified.
- Historical reverse evidence lives in `docs/reverse/*_4.4.54.md` and
  `data/raw/<version>/`; this pipeline writes to a separate layer.
- Capability matrix: [`capability_matrix.md`](capability_matrix.md).

---

## 1. Input

A local HSR client install root, for example `D:\StarRail_4.4.53`. The
directory name is **never trusted**; the pipeline reads the real version from
`StarRail_Data\StreamingAssets\BinaryVersion.bytes`.

Expected files:

```text
<GameRoot>\GameAssembly.dll
<GameRoot>\StarRail_Data\il2cpp_data\Metadata\global-metadata.dat
<GameRoot>\StarRail_Data\StreamingAssets\BinaryVersion.bytes
<GameRoot>\StarRail_Data\Persistent\DesignData\Windows\*.bytes
```

## 2. Run (one command)

From the repository root:

```powershell
.\scripts\unpack_version.ps1 -GameRoot "D:\StarRail_4.4.53"
```

Optional arguments:

```powershell
.\scripts\unpack_version.ps1 -GameRoot "D:\StarRail_4.4.53" `
    -RuntimeSnapshot data\raw\4.4.54\bridge\mkioeplieih_registry_snapshot_4.4.54.json

.\scripts\unpack_version.ps1 -GameRoot "D:\StarRail_4.4.53" `
    -PythonExe "C:\path\to\verified\python.exe"

.\scripts\unpack_version.ps1 -GameRoot "D:\StarRail_4.4.53" `
    -ReferenceNormalized data\normalized\4.4.0
```

The wrapper resolves Python only through
`scripts/python/resolve_python.ps1` (`-PythonExe` → `HSR_PYTHON_EXE` →
verified local Python 3.11 fallback → explicit FAIL). Bare `python`,
`py.exe`, `where.exe` and `vswhere.exe` are not used.

Run tests:

```powershell
.\scripts\python\resolve_python.ps1 -Resolve
$Py = <reported exe path>
& $Py -m unittest discover -s tests\unpacker -p "test_*.py" -v
```

## 3. Output layout

```text
data/
  raw/                       # immutable historical evidence (pipeline does not write here)
    <version>/
  parsed/                    # pipeline stage artifacts
    <version>/
      manifest.json
      asset_inventory.json
      stage_status.json
      mhy_table_registry.json
      type_registry_evidence.json
      member_registry_evidence.json
      method_code_registry.json
      method_code_table.bin
      design_runtime_registry.json
      design/design_structural.json
      design/ability_directory.csv
      design/black_swan_records/*.bin
      anomalies.json
      pipeline_report.json
  normalized/                # stable normalized registries
    <version>/
      types.json
      methods.json
      fields.json
      parameters.json
      normalization_summary.json
      design_runtime_registry.json
      pipeline_report.json
      anomalies.json
  diff/
    <old>_vs_<new>/
      version_diff.json
      version_diff.md
```

`methods.json` / `fields.json` are intentionally full registries (hundreds of
MB for 4.4.54). `method_code_table.bin` is the raw qword table used for RVA
lookups.

## 4. Stage design

| # | Stage | Runtime | Input | Output | Status semantics |
|---|---|---|---|---|---|
| 1 | VERSION_DISCOVERY | static | `BinaryVersion.bytes` | `manifest.json` | PASS = real version token found |
| 2 | ASSET_DISCOVERY | static | client root | `asset_inventory.json` | PASS = required binaries present |
| 3 | DESIGNDATA_STRUCTURAL_PARSE | static | DesignData chunks | ability directory + neutral record prefixes | PASS/WARN; unknown ULEBs kept as `field_x`/`structural_code` |
| 4 | MHY_METADATA_PARSE | static | GameAssembly + metadata | `mhy_table_registry.json` | PASS = 47+ code-derived rules decode in-file |
| 5 | TYPE_REGISTRY | static | 0x84 table + identifier heap | `type_registry_evidence.json` | PASS = partitions/identifier checks hold |
| 6 | MEMBER_REGISTRY | static | 0x14C/0x30/0x20 tables | `member_registry_evidence.json` | PASS = partitions exact + declaring type match |
| 7 | METHOD_CODE_REGISTRY | static | code table + method table | `method_code_registry.json` + `.bin` | PASS = consumer + anchors + executable pointers |
| 8 | DESIGN_RUNTIME_BRIDGE | static + runtime-optional | factory code / optional snapshot | `design_runtime_registry.json` | static factory PASS; generated registry NOT_RUN unless snapshot |
| 9 | NORMALIZATION | static | stage 5-8 outputs | `types/methods/fields/parameters.json` | PASS = normalized files written |
| 10 | VERSION_DIFF | static | two normalized dirs or archived raw reference | `version_diff.json` + `.md` | PASS = diff feature executed |

A stage failure is recorded in `stage_status.json` and `anomalies.json`; outputs
written by earlier stages are preserved.

## 5. Static vs runtime

All ten stages can run fully offline. The only runtime-dependent component is
Stage 8's `generated_polymorphic_registry`:

- Optional snapshot input produced by
  `tools/runtime_snapshot/mkioeplieih_registry_snapshot.py`.
- Allowed boundary: `OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ)`,
  PSAPI `EnumProcessModulesEx`, `ReadProcessMemory` on the code-derived chain
  only.
- Forbidden: write, inject, remote thread, hook, patch, driver, blind process
  memory scan. The archived loader route is not reopened.

Without a snapshot the pipeline reports
`runtime_enrichment = NOT_RUN` and still finishes successfully.

## 6. Evidence and correction discipline

- `structure_status` and `semantic_status` are stored separately.
- UNKNOWN values are preserved with neutral names (`field_0xNN`,
  `structural_code`, `raw_value`).
- **Correction carried by every bridge output:** `SkillAbilityConfig.AbilityList`
  is `List<string>`, **not** a polymorphic Ability Mixin list. The historical
  `ABILITY_MIXIN_REGISTRY_PROOF` label is interpreted as the **generated /
  polymorphic DesignData runtime registry** (`MKIOEPLIEIH` discriminator →
  parser → Runtime Class), not a Black Swan ability-mixin semantic proof.
- Black Swan 2/8/14/16 are recorded only as
  `STRUCTURAL_VALUE_CONFIRMED` / `SERIALIZER_SEMANTIC_UNRESOLVED`.
  Registry-range membership ≠ serializer identity.
- Historical experiment JSON under `data/raw` is not modified.

## 7. Anomaly policy

`anomalies.json` entries have `stage`, `expected_invariant`,
`observed_result`, `severity`, and `suggested_follow_up`. Trigger examples:

- MHY table transform changed or decoded offset outside metadata;
- identifier decode failures;
- method partition no longer exact;
- native pointer outside executable sections;
- bridge factory/registry shape changed.

The update goal is: **a new client version inherits automatically; only
anomalies need human reverse work.**

## 8. Updating a new game version

```powershell
.\scripts\unpack_version.ps1 -GameRoot "D:\path\to\new_client"
```

Then read, in order:

1. `data\parsed\<version>\pipeline_report.json`
2. `data\parsed\<version>\anomalies.json`
3. `data\diff\<old>_vs_<new>\version_diff.md`

Manual reverse work is required **only when** an anomaly reports a changed
invariant (transform, locator, partition, code table, bridge shape). Do not
start new semantic reverse because some directory rules remain UNKNOWN.

## 9. Current known invariants (4.4.54 / 4.4.0)

| Item | 4.4.54 | 4.4.0 |
|---|---|---|
| Type count | 80880 | 76921 |
| Method count | 732328 | 703008 |
| Field count | 555259 | 526693 |
| Method code non-null | 700198 | 676842 |

Tests in `tests/unpacker/test_pipeline_units.py` pin these invariants and
cover version-source discipline, parser units, and semantic diff alignment.

## 10. Scope boundaries

This pipeline intentionally does **not** do:

- new metadata table semantic reverse;
- Black Swan skill semantics / Ability Mixin Execute;
- Battle DSL / Sandbox / damage formula / modifier runtime / turn system;
- generic runtime full reverse;
- `.upx0` deep-dive.

If an unknown field is encountered: record anomaly / `semantic_status=UNKNOWN`,
stop, and do not open a new reverse task inside the pipeline.
