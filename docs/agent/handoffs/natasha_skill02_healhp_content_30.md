# Natasha Skill02 HealHP Content 30

`STATUS = REAL_SKILL_HEALHP_NODE_AND_FORMULA4_CONFIG_CONFIRMED`

This handoff supersedes the file-local selector conclusion in Handoffs 25–28.
Those probes treated a small factory table as the global `TaskConfig`
registry. The generated global registry has 3,915 slots and reads a ULEB
discriminator. Its confirmed mappings are:

| Discriminator | Runtime type | Parser RVA |
| ---: | --- | --- |
| 1199 | `RPG.GameCore.DispelStatus` | `0x1CFAB680` |
| 1481 | `RPG.GameCore.HealHP` | `0x1D0EBEB0` |
| 1960 | `RPG.GameCore.PredicateTaskList` | `0x1D2CA1A0` |
| 3726 | `RPG.GameCore.WaitAnimState` | `0x1D60D750` |

The old claim “global serialized HealHP selector = 7” is therefore retracted.
Selector 7 belonged to the previously observed file-local factory family; it
is not the generated global `TaskConfig` discriminator.

Primary artifact:
`data/raw/4.4.54/natasha_skill02_healhp_content_30.json`.

## Container and parent linkage

The extractor validates archive SHA-256
`098ec31c5c03a0f6fbf030d6b2579a5e60c03639ce7060f68fa52371a03dc64b`
and the generic Natasha ability container before decoding the subtree.

- Ability: `Avatar_Natasha_00_Skill02_Phase02`
- Ability anchor: `0xBC9960`
- Next ability anchor / exclusive bound: `0xBC9BC9`
- `AbilityConfig` bitmap: `0x33` = `Name`, `TargetInfo`, `OnStart`,
  `DynamicValues`
- `OnStart` count: 22 at `0xBC9985`
- First `OnStart` task: discriminator 3726 / `WaitAnimState`
- Unique recovered parent: `PredicateTaskList` at `0xBC9A1C`
- Parent bitmap: `0x06` = `Predicate`, `SuccessTaskList`
- Predicate: discriminator 496 / `BySkillPointActivated`, bitmap `0x08`,
  serialized trigger key 12
- Success task count: 2

The success children are structurally contiguous:

1. `DispelStatus`, `0xBC9A24..0xBC9A4B`
2. `HealHP`, `0xBC9A4B..0xBC9A7E`

The ULEB discriminator beginning exactly at `0xBC9A7E` is 1960, the next
outer `PredicateTaskList`. This proves the exclusive end of the HealHP node.

## Concrete HealHP config

`HealHP` discriminator 1481 has bitmap `0xB2` (178). The populated fields in
native parser order are:

| Field | Serialized value |
| --- | --- |
| `TargetType` | discriminator 12, bitmap 1, name `AbilityTargetEntity` |
| `FormulaType` | 4 |
| `HealPercentage` | formula opcodes `01 00 11`, int32 operand `-1544075911` |
| `ModifyValue` | formula opcodes `01 00 11`, int32 operand `-203632277` |

The two negative int32 values are serialized DynamicFloat operands, not
literal signed heal amounts. Their bytecode/hash binding is not recovered.
They must be evaluated by a provenance-bearing external resolver until that
semantic is closed.

Absent/default config fields are `HealerTargetType`, `AliveOnly`,
`SPHitRatio`, `IsHealRallyHP`, `ScreenSpaceFloatMsg`, `DisplayData`, and
`PerformanceDelay`.

## Native FormulaType 4 arithmetic

The executor path is:

```text
AAOLFLMHBEK.OnTaskBegin M507657 0xB3F43C0
  -> TaskContext.Evaluate M505862 0xE6EFAE0
  -> AbilityStatic.SetupHealData M504574 0xE468390
  -> AbilityStatic.HealFormula M504575 0xE468720
  -> EventManager.FireEvent M519357 0xE5EA080
```

For FormulaType 4, `HealFormula` selects:

```text
base = target.MaxHP(property 1) - target.CurrentHP(property 10)
configured = base * HealPercentage + ModifyValue
ordinary_factor = 1 + healer.HealRatio(property 124)
                    + target.HealTakenRatio(property 127)
special_factor = (1 + healer.ExtraHealAddedRatio(property 179))
                   * healer.ExtraHealBase(property 208) / 100
                 + healer.ExtraHealConvert(property 220) / 100
amount = max(configured * ordinary_factor * special_factor, 0)
```

`SetupHealData` initializes the special base scale to fixed-point 100 and
leaves the other special terms at zero in the ordinary component path, making
`special_factor = 1`. The fixed-point constants are confirmed machine-code
literals: `1 = 0x200000000`, `100 = 0xC800000000`.

Natasha's absent `IsHealRallyHP` field selects the non-rally formula path.

## Coding boundary

The content graph and FormulaType 4 arithmetic are coding-ready. A complete
real skill that mutates HP is not yet coding-ready. Four dependencies remain
explicit:

1. `BySkillPointActivated` runtime-context evaluation.
2. DynamicFloat bytecode/hashed-operand evaluation.
3. Runtime join for TargetConfig discriminator 12 (the serialized name is
   known, but its selector implementation is not joined here).
4. The positive HealData event consumer that performs the eventual CurrentHP
   mutation.

Do not substitute the recovered negative-delta `DirectDamageHP` path for the
positive heal consumer. The current sandbox intentionally rejects that
equivalence.

## Reproduction

Run `tools/reverse/scripts/extract_natasha_skill02_healhp_30.py` with the
DesignData archive, `ability_file_container_natasha_30.json`,
`taskconfig_registry_slice_30.json`, and
`predicateconfig_registry_slice_30.json`. The compact slices retain the
global registry provenance/statistics and the exact mappings used here; the
full generated registries can be reproduced with the two registry builders.
The extractor rejects SHA, registry identity, field bitmap, child-boundary,
and next-selector mismatches.
