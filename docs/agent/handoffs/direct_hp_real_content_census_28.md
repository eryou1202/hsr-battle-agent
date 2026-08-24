# Direct HP Real Content Census 28

`STATUS = DIRECT_HP_AVATAR_SLICE_NOT_FOUND`

This is a structural content census. It does **not** recover gameplay
semantics or implement Sandbox runtime.

Artifact: `data/raw/4.4.54/direct_hp_real_content_census_28.json`

---

## Direct-HP type registry

| Config | Type index | Selector | Factory thunk |
| --- | --- | --- | --- |
| SetHP | 22351 | 5 | `0x1CE5D000` |
| HealHP | 22352 | 7 | `0x1CC131D0` |
| LoseHPByRatio | 22420 | 8 | `0x1CC16410` |
| LoseHP | 22421 | 7 | `0x1CC16360` |

Selectors are ULEB/VLQ unsigned varints.

## Structurally valid direct-HP nodes

- **None mapped in this bounded census.**

## Mapped real-avatar nodes

- **None.**

## Ranked candidates

- None.

## Primary candidate

- None selected.

## Natasha Skill02 status

- `NOT_PROVEN / DEFERRED`
- Natasha Skill02 does not currently have a proven HealHP node; do not force it.

## Remaining parser unknowns

- `OUTER_ABILITY_ACTION_CONTAINER_ENCODING_UNKNOWN`
- `REAL_AVATAR_TO_DIRECT_HP_NODE_MAPPING_NOT_FOUND`
- `TARGET_CONFIG_SERIALIZER_TAG_UNKNOWN`

## Recommended next step

Map the outer ability/action container encoding used by real avatar ability
records, then locate structurally valid direct-HP nodes and map them to avatar
abilities.
