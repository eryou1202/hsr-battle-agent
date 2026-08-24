# Natasha HealHP Content 24

`STATUS = NATASHA_HEALHP_CONTENT_24_PARTIAL`

This is a targeted binary ability-format parse. It does **not** reverse
gameplay semantics or implement Sandbox runtime.

Artifact: `data/raw/4.4.54/natasha_healhp_content_24.json`

---

## Chosen Natasha ability

- **`Avatar_Natasha_00_Skill02_Phase02`**
- Record range: `0xBC995F` – `0xBC9BC8`
- Length: `617` bytes
- Wrapper type: `0`
- Bitfield: `51` (`0x33`)
- Archive SHA256: `098EC31C5C03A0F6FBF030D6B2579A5E60C03639CE7060F68FA52371A03DC64B`

## HealHP node identity

- Status: `SUPPORTED`
- The record contains:
  - `Heal` prefab reference (`Eff_Avatar_Natasha_00_Skill02_Heal.prefab`)
  - `SkillTargetEntityList`
  - `TargetEntity`
  - `HPByMaxHP`
  - `MaxHP`
- The exact polymorphic config tag for `RPG.GameCore.HealHP` is `UNKNOWN`.

## Target config

- Status: `SUPPORTED`
- Observed tokens: `SkillTargetEntityList`, `TargetEntity`, `AbilityTargetEntity`
- Exact target selector object is `UNKNOWN`; a polymorphic tag decode is required.

## Populated amount fields

| Field candidate | Status | Offset | Classification |
| --- | --- | --- | --- |
| `HPByMaxHP` | DISCOVERY_EVIDENCE_ONLY | `0xBC9AF5` | UNKNOWN |
| `MaxHP` | DISCOVERY_EVIDENCE_ONLY | `0xBC9AF9` | PROPERTY_REFERENCE_CANDIDATE |
| `M_SkillTree_HealRatioUp` | DISCOVERY_EVIDENCE_ONLY | near `0xBCA87D` | UNKNOWN |

## Decoded values/types

- Not yet proven.
- The archive stores these in the encoded ability format; no decoded FixPoint/DynamicValue values are emitted yet.

## Unresolved nested parser primitives

- `UNKNOWN_POLYMORPHIC_TAG_FOR_HEALHP`
- `UNKNOWN_DYNAMICVALUE_ENCODING_FOR_HEAL_AMOUNT`
- `UNKNOWN_TARGET_SELECTOR_TAG`

## Content status

- `NATASHA_HEALHP_CONTENT_24_PARTIAL`
- The correct Natasha heal-bearing ability record has been located and bounded.
- The exact HealHP config node and amount fields are not yet decoded.

## Exact next frontier

Decode the polymorphic config tag inside `Avatar_Natasha_00_Skill02_Phase02`
that maps to `RPG.GameCore.HealHP`, then parse its target selector and amount
fields.
