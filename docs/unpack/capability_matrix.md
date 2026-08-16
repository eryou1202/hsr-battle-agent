# Unpack/Reverse Capability Matrix — Pipeline v1

This matrix records what is **proven** and exactly which script implements it
in the formal pipeline. Evidence levels follow the project convention
(E2 repeated structure, E3 metadata semantic, E4 machine-code evidence,
E5 runtime observation).

Legend: `core script` = pipeline implementation; `historical evidence tool` =
original reverse-session script that produced/validates the proof.

| ID | Capability | Input | Output | Core script | Historical evidence tool | Evidence level | Static / Runtime |
|---|---|---|---|---|---|---|---|
| A | Version identification | `BinaryVersion.bytes` | `game_version`, `binary_version`, `build_string`, source hash | `tools/unpack_pipeline/version_discovery.py` | `tools/runtime_probe/probe/health_check.cpp` (same source rule) | E5 client self-report | Static |
| B | DesignData discovery | `Persistent/DesignData/Windows/*.bytes` | hashed inventory (`sha256`, md5-name check, channel) | `tools/unpack_pipeline/asset_discovery.py` | `tools/unpack/probe_design_index.py`, historical `design_data_hashes.csv` | E2 structural | Static |
| C | Ability directory adaptive discovery | DesignData chunk | payload base, directory rows, record offsets | `tools/unpack_pipeline/design_structural.py` | `tools/unpack/probe_ability_directory_adaptive.py` | E2 structural | Static |
| D | MHY header/directory decode | GameAssembly MHY template block + `global-metadata.dat` | 47+ template-field rules, decoded file offsets, in-file validation | `tools/unpack_pipeline/run_pipeline.py` stage 4 → `recover_mhy_table_registry.build_registry` | `tools/reverse/scripts/decode_mhy_directory.py`, `decode_mhy_header_template.py` | E4 code-derived transforms + E2 cross-version | Static |
| E | identifier resolver | identifier key + 0x1B4 ciphertext heap | UTF-8 namespace/name | `tools/unpack_pipeline/mhy_core.py::resolve_identifier` | `tools/reverse/scripts/analyze_mhy_definition_candidate.py` | E4 code-proven rolling-XOR | Static |
| F | TypeDefinition | 0x84 table (70-byte records) | `types.json` (index, namespace, name, method/field/descriptor ranges) | `tools/unpack_pipeline/mhy_core.py` + `normalize.py` | `analyze_mhy_definition_candidate.py` | E4 + E2 + E3 | Static |
| G | MethodDefinition | 0x14C table (26-byte records) | `methods.json` (name, declaring type, parameter relation, return ref) | `tools/unpack_pipeline/mhy_core.py` + `normalize.py` | `analyze_mhy_method_candidate.py` | E4 + E2 + E3 | Static |
| H | FieldDefinition | 0x20 table (8-byte records) | `fields.json` (declaring type, name, type reference) | `tools/unpack_pipeline/mhy_core.py` + `normalize.py` | `analyze_mhy_field_candidate.py` | E4 + E2 + E3 | Static |
| I | ParameterDefinition relation | 0x30 table via MethodDefinition ranges | `parameters.json` + per-method start/count | `tools/unpack_pipeline/mhy_core.py` + `normalize.py` | `analyze_mhy_method_candidate.py` | E4 + E2 partition | Static |
| J | metadata member registry | decoded directory + consumer rules | `mhy_table_registry.json` with structure/semantic status | `tools/unpack_pipeline/run_pipeline.py` stage 4 | `recover_mhy_table_registry.py` | E4 consumers + E2 cross-version | Static |
| K | method native RVA registry | MethodDefinition index + static code table | `method_code_registry.json`, `method_code_table.bin`, per-method RVA in `methods.json` | `tools/unpack_pipeline/method_code.py` | `build_method_code_registry.py` | E4 consumer + E3 anchors | Static |
| L | static DesignData factory bridge | `AbilityConfig.FromBinary`, `ModifierConfig.OJNNBEJLDIJ` | discriminator → Runtime Class → parser method → RVA | `tools/unpack_pipeline/bridge.py` | `extract_factory_switch.py`, `compare_bridge_registries.py` | E4 machine code + E3 registry | Static |
| M | runtime/generated polymorphic registry bridge | read-only snapshot of MKIOEPLIEIH registry | discriminator → Runtime Class → parser method | `tools/unpack_pipeline/bridge.py` (snapshot path) | `mkioeplieih_registry_snapshot.py`, `build_ability_mixin_registry_bridge.py` | E4 static chain + E5 read | Runtime-optional |
| N | cross-version comparison | two normalized dirs (or archived raw reference) | `version_diff.json` / `version_diff.md` | `tools/unpack_pipeline/diff.py` | `compare_mhy_definition_access_maps.py`, `compare_mhy_member_access_maps.py`, `compare_method_code_registries.py`, `compare_bridge_registries.py`, `compare_ability_mixin_registries.py` | E2/E3 semantic alignment | Static |

## Semantic corrections carried forward

1. `SkillAbilityConfig.AbilityList` = `List<string>` (DISPROVEN as polymorphic
   mixin list). See `docs/reverse/ability_mixin_registry_proof_4.4.54.md` §2.
2. Historical `ABILITY_MIXIN_REGISTRY_PROOF` reads as **generated /
   polymorphic DesignData runtime registry**; the Black Swan observations
   2/8/14/16 stay `STRUCTURAL_VALUE_CONFIRMED` +
   `SERIALIZER_SEMANTIC_UNRESOLVED`.
3. Version diff aligns by `namespace + type`, `declaring type + method
   identity`, and `runtime class identity`; numeric registry indices are never
   compared directly.
