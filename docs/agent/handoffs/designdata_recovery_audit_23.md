# DesignData Recovery Audit 23

`STATUS = LOCAL_ARCHIVE_FOUND_AND_NATASHA_HEALHP_EVIDENCE_PRESENT`

This is a local file / provenance recovery audit. It does **not** implement
Sandbox code.

Artifact: `data/raw/4.4.54/designdata_recovery_audit_23.json`

---

## Expected archive inventory recovered?

- Yes, partially.
- Historical StreamingAssets inventory is recorded in `hsr_design_data_hashes.csv` / `hsr_design_data_inventory.csv`.
- Historical Persistent examples are recorded in `avatar_token_locations.csv` and related manifests.

## Full local archive found?

- Yes.
- `D:\StarRail_4.4.53\StarRail_Data\Persistent\DesignData\Windows\8625dd99e13b0dfe6b45f47f9bfe3e36.bytes`
  - Size: `125,829,538`
  - SHA256: `098EC31C5C03A0F6FBF030D6B2579A5E60C03639CE7060F68FA52371A03DC64B`
- `D:\StarRail_4.4.53\StarRail_Data\Persistent\DesignData\Windows\edd7d527b0962f4ec2e49789746fb0d2.bytes`
  - Size: `184,370`
  - SHA256: `078AC12FAB39F08401B777D9F7C35BA0B1248CB28F7AF19AFFA1EA900FA731E4`

## Natasha content found?

- Yes, in encoded ability-record form.
- `edd7...` contains the path string:
  `Config/ConfigAbility/Avatar/Avatar_Natasha_00_Ability.json`
- `8625...` contains real Natasha ability tokens:
  - `Avatar_Natasha_00_HOT_HPByMaxHP`
  - `Skill02`
  - `SkillTargetEntityList`
  - `AllTeammate`
  - `Avatar_Natasha_00_Skill03_EnterReady`
  - `M_SkillTree_HealRatioUp`
  - `BattleEvent_GridFight_Natasha_00_Skill03`
  - `AllTeamMember`
  - `_Heal_Percentage`
  - `Eff_Avatar_Natasha_00_Skill02_Heal.prefab`
  - `Eff_Common_Heal.prefab`

## Exact source file / hash

- Primary content archive:
  `D:\StarRail_4.4.53\StarRail_Data\Persistent\DesignData\Windows\8625dd99e13b0dfe6b45f47f9bfe3e36.bytes`
  - SHA256: `098EC31C5C03A0F6FBF030D6B2579A5E60C03639CE7060F68FA52371A03DC64B`
- Key offsets:
  - `12361281` — `Avatar_Natasha_00_HOT_HPByMaxHP` / `Skill02` / `AllTeammate`
  - `15614487` — `BattleEvent_GridFight_Natasha_00_Skill03` / `AllTeamMember` / `_Heal_Percentage`

## Concrete HealHP config recoverable?

- **Partially recoverable.**
- The archive contains concrete Natasha/HealHP-bearing ability records, but they are in the game’s encoded ability format, not raw JSON.
- A binary ability-format parser is required to emit the exact `Avatar_Natasha_00_Ability.json` HealHP action.

## Recovery status

- `CONTENT_RECOVERED`
- `CONCRETE_JSON_CONFIG_EXTRACTION = PENDING_BINARY_ABILITY_PARSE`

## Minimum external file required if blocked

- No external archive is required if the local `8625...` archive is accepted.
- Required next step: parse the encoded ability records around offsets `12361281` and `15614487` to produce the concrete HealHP action.

## Recommended next step

Build/apply a bounded parser for the encoded DesignData ability records in `8625...` and extract one Natasha HealHP action with:
- ability ID
- target config
- heal amount / amount-expression fields
- executor binding (`HealHP -> AAOLFLMHBEK`)
