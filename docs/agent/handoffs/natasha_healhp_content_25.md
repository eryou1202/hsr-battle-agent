# Natasha HealHP Content 25

`STATUS = NATASHA_HEALHP_CONTENT_25_PARTIAL`

This is a targeted format-mapping probe. It does **not** recover gameplay
semantics or implement Sandbox runtime.

Artifact: `data/raw/4.4.54/natasha_healhp_content_25.json`

---

## HealHP serialized discriminator

- Reference parser says `53 -> heal_hp`.
- The 617-byte `Avatar_Natasha_00_Skill02_Phase02` record contains **no**
  standalone `0x35` byte that parses as a `disp__config_ability_action`
  type code `53`.
- Therefore the 4.4.54 serialized discriminator for HealHP is `UNKNOWN`.

## Discriminator → runtime type proof

- `INSUFFICIENT`
- The reference `53 -> heal_hp` mapping is from an older/other parser family
  and is not present in this record.
- The 4.4.54 polymorphic action registry entry for HealHP is not yet
  recovered.

## Concrete target config

- `SUPPORTED_BUT_NOT_DECODED`
- Tokens present: `SkillTargetEntityList`, `TargetEntity`, `AbilityTargetEntity`
- Exact serialized target tag is `UNKNOWN`.

## HealHP populated fields

- `UNKNOWN`
- No heal_hp-shaped node could be structurally decoded from the record using
  the reference format.

## Amount-field encoded types

- `UNKNOWN`
- No amount DynamicValue/FixPoint payload was structurally linked to a HealHP
  node.

## Decoded DynamicValue/FixPoint values

- None.

## HPByMaxHP / MaxHP linkage

- `UNRELATED_NEARBY_RECORD_DATA_OR_UNKNOWN`
- They appear inside the modifier name `MAvatar_Natasha_00_HOT_HPByMaxHP` and
  are not proven to be linked to a decoded HealHP action node.

## Remaining parser UNKNOWN

- `POLYMORPHIC_REGISTRY_ENTRY_HEALHP_MISSING`
- `TARGET_CONFIG_SERIALIZER_TAG_UNKNOWN`
- `HEALHP_FIELD_BITMAP_UNKNOWN`

## Content status

- `NATASHA_HEALHP_CONTENT_25_PARTIAL`

## Exact next frontier

Recover the 4.4.54 polymorphic action registry mapping for
`RPG.GameCore.HealHP` (which serialized type code maps to HealHP in this
binary), then re-parse the `Skill02_Phase02` record.
