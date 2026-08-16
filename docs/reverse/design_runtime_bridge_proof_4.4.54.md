# DesignData ↔ Runtime Type Bridge Proof — 4.4.54

> Session after `METHOD_CODE = RVA_REGISTRY_PROOF` (41ad29d).
> Goal: recover the real mapping mechanism from DesignData serialized type
> identity to MHY metadata Runtime Class.
>
> final_status = **DESIGN_RUNTIME_BRIDGE = PARTIAL_MAPPING_RECOVERED**

## 0. Conclusion

The generated binary deserializer uses a **static switch factory**:

```text
serialized type tag (ULEB128)
  -> factory method (declaring TypeDefinition recovered)
  -> `cmp tag, N; ja default; movsxd [table + tag*4]; add table; jmp`
  -> concrete case block creates the runtime object
  -> tail `jmp` to the concrete class parser MethodDefinition
```

This chain is now machine-proven for two polymorphic domains and is
cross-version stable:

| serialized_domain | factory | case_count | status |
|---|---|---|---|
| `ability_config` | `RPG.GameCore.AbilityConfig.FromBinary` | 4 (0..3) | **CONFIRMED** |
| `modifier_config` | `RPG.GameCore.ModifierConfig.OJNNBEJLDIJ` | 4 (0..3) | **CONFIRMED** |
| Black Swan ability `mixin` codes 2/8/14/16 | not recovered | — | **UNRESOLVED** (see §5) |

Every factory, case block and parser was resolved through the already-proven
registries (`0x84` TypeDefinition → `0x14C` MethodDefinition → method code
table), not by manual address search.

## 1. Bridge mechanism (E4 machine-code evidence)

`AbilityConfig.FromBinary` (4.4.54 method index `103101`, RVA `0x1CCDCAF0`)
shows the exact shape:

```text
call  MOMNMLHNPLH.BIKABOFADBP   ; ULEB128 reader @ 0x1CB8A410
cmp   eax, 3
ja    default
lea   rcx, [rip + table]        ; table RVA 0x1CCDCCF8
movsxd rax, dword ptr [rcx + rax*4]
add   rax, rcx
jmp   rax
```

Each case block calls the shared object allocator (`0x183C736B0`), stores the
new object, and tail-jumps to the concrete parser:

| type_code | Runtime Class | parser MethodDefinition | parser index | parser RVA |
|---|---|---|---|---|
| 0 | `RPG.GameCore.AbilityConfig` | `FromBinaryImpl` | 103102 | `0x1CCDCD20` |
| 1 | `RPG.GameCore.AdventureAbilityConfig` | `MGMEGEDLMAK` | 107046 | `0x1CD50E60` |
| 2 | `RPG.GameCore.RtAbilityConfig` | `MGMEGEDLMAK` | 107513 | `0x1D4084D0` |
| 3 | `RPG.GameCore.TurnBasedAbilityConfig` | `MGMEGEDLMAK` | 108926 | `0x1D580150` |

`ModifierConfig.OJNNBEJLDIJ` (method index `103116`, RVA `0x1D21C470`,
table RVA `0x1D21C7AC`) has the identical mechanism:

| type_code | Runtime Class | parser MethodDefinition | parser index | parser RVA |
|---|---|---|---|---|
| 0 | `RPG.GameCore.ModifierConfig` | `MGMEGEDLMAK` | 103117 | `0x1D21C7D0` |
| 1 | `RPG.GameCore.AdventureModifierConfig` | `FromBinaryImpl` | 107223 | `0x1CD63BA0` |
| 2 | `RPG.GameCore.RtModifierConfig` | `MGMEGEDLMAK` | 107548 | `0x1D4219B0` |
| 3 | `RPG.GameCore.TurnBasedModifierConfig` | `FromBinaryImpl` | 108955 | `0x1D5810E0` |

`MGMEGEDLMAK` / `OJNNBEJLDIJ` are obfuscated metadata names; the machine-code
factory dataflow is what makes the mapping, not the names.

## 2. Cross-version validation (4.4.0 vs 4.4.54)

`compare_bridge_registries.py` compares version-independent identity only:

| check | ability_config | modifier_config |
|---|---|---|
| same case set | PASS | PASS |
| same factory type name | PASS | PASS |
| same Runtime Class per type_code | PASS (4/4) | PASS (4/4) |
| same parser method name per type_code | PASS (4/4) | PASS (4/4) |
| native RVA differs | PASS (4/4) | PASS (4/4) |

4.4.0 factories:

- `AbilityConfig.FromBinary`: method `101053`, RVA `0x1B9F9910`,
  table `0x1B9F9B18`.
- `ModifierConfig.OJNNBEJLDIJ`: method `101068`, RVA `0x1AF70C30`,
  table `0x1AF70F6C`.

RVA is version-specific; serialized type → Runtime Class identity is stable.

## 3. Machine outputs

```text
data/raw/4.4.54/bridge/ability_config_type_bridge_4.4.54.json
data/raw/4.4.54/bridge/modifier_config_type_bridge_4.4.54.json
data/raw/4.4.54/bridge/design_runtime_bridge_proof_4.4.54.json
data/raw/4.4.54/bridge/design_runtime_bridge_cross_version_4.4.0_vs_4.4.54.json
data/raw/4.4.0/bridge/ability_config_type_bridge_4.4.0.json
data/raw/4.4.0/bridge/modifier_config_type_bridge_4.4.0.json
```

Supporting artifacts (disassembly, dispatch scan, xrefs, metadata candidate
queries) are under the same `bridge/` directories.

## 4. Audit: old slot/flags hash rule

The old `low16(hash64)` helper is **not present in any active parser/builder
used by this session**. Current code (`analyze_mhy_method_candidate.py`,
`build_method_code_registry.py`) uses `low16(hash32c)` for `+0x14` slot and
`+0x0E` flags exactly like the real builder. No code correction was needed.
The correction note already exists in
`docs/reverse/method_code_registry_proof_4.4.54.md` §3; historical JSON/doc
text was not modified.

## 5. Ability Mixin codes 2/8/14/16 — honest status

The Black Swan records still show first-mixin codes `2 ×7, 16 ×4, 8 ×3, 14 ×1`
across 4.4.53/4.4.54. This session did **not** map them to Runtime Classes.
Structural findings:

- The first two ULEB128 values of each record are **field-presence
  bitfields**, not proven type tags. `SkillConfig.FromBinary`
  (`0x1D4AAEE0`) reads exactly two ULEBs and then tests 64+13 bits (77
  optional fields), which matches the two-bitfield record shape.
- `CommonSkill.OJNNBEJLDIJ` (`0x1CF60710`) is a static direct caller of both
  `SkillConfig.FromBinary` and `SkillAbilityConfig.OJNNBEJLDIJ`; it is the
  strongest wrapper-candidate dataflow.
- No static jump-table switch in the 4.4.54 `il2cpp` section covers a core
  ability domain with case codes 2/8/14/16.
- The generic list/object readers (`0x16C86A10`, `0x16C8E0D0`) dispatch
  element parsers through **runtime type descriptors** whose static slots are
  BSS-initialized. Recovering the mixin element class from those descriptors
  requires the runtime registry initializer path, which was not opened in this
  session.

Therefore:

```text
ability_mixin serialized codes 2/8/14/16 -> Runtime Class: UNRESOLVED
serialized_domain identity for Black Swan records: two-bitfield object,
    strongest parser candidate SkillConfig / CommonSkill / SkillAbilityConfig
    (E4 dataflow, but not yet record-byte-level closed)
```

No semantic guess (e.g. “type 16 = damage mixin”) is recorded as CONFIRMED.

## 6. Success level

```text
BRIDGE_LEVEL_1  deserializer/factory located                 = PASS
BRIDGE_LEVEL_2  serialized discriminator recovered           = PASS
BRIDGE_LEVEL_3  discriminator -> Runtime Type mapping        = PASS
BRIDGE_LEVEL_4  multiple codes validated                     = PASS
                (ability_config 0..3, modifier_config 0..3)
BRIDGE_LEVEL_5  cross-version / automated registry validated = PASS
                (4.4.0 vs 4.4.54 for both confirmed domains)
```

Ability-mixin-specific LEVEL 4 remains not reached, hence the session status
is `PARTIAL_MAPPING_RECOVERED`, not `ABILITY_MIXIN_REGISTRY_PROOF`.

## 7. Tools added / extended

- `extract_factory_switch.py` — automatic static-switch factory bridge
  extractor (the core bridge tool).
- `compare_bridge_registries.py` — cross-version bridge identity validator.
- `scan_dispatch_tables.py` — GameAssembly jump-table dispatcher locator.
- `resolve_method_rvas.py` — native RVA → MethodDefinition reverse lookup.
- `find_method_xrefs.py` — qword / rel32 / RIP-mov / lea xref scanner.
- `query_bridge_candidates.py`, `query_types_by_method.py`,
  `query_fields_by_name.py`, `dump_mhy_types.py`, `inspect_mhy_type.py`,
  `annotate_pe_qwords.py`, `scan_parser_fingerprints.py`,
  `filter_dispatch_scan.py`, `summarize_dispatch_scan.py`,
  `list_dispatch_cases.py` — metadata / code candidate tooling.

## 8. Not claimed / next session boundary

- Ability Mixin 2/8/14/16 → Runtime Class mapping.
- Runtime type descriptor registry initializer internals.
- Battle Execute / damage / modifier settlement semantics.
- Battle DSL / Sandbox / Black Swan semantic recovery.
- `.upx0` deep-dive and any runtime injection.

Stop condition reached: **DESIGN_RUNTIME_BRIDGE = PARTIAL_MAPPING_RECOVERED**.
