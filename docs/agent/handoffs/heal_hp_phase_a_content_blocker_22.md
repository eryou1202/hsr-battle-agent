# HealHP Phase A Content Blocker 22

`STATUS = BLOCKED`

`BLOCKER = REAL_ABILITY_CONTENT_REQUIRED`

Artifact: `data/raw/4.4.54/heal_hp_phase_a_content_blocker_22.json`

## What is confirmed

- The extracted TurnBasedAbilityConfig path index contains
  `Config/ConfigAbility/Avatar/Avatar_Natasha_00_Ability.json`.
- The 4.4.54 action bridge maps `RPG.GameCore.HealHP` to generated executor
  `AAOLFLMHBEK` and M507657 `OnTaskBegin`.
- The generic native topology is
  `AAOLFLMHBEK -> M507658 -> M506500 DirectChangeHP -> M506499 DirectDamageHP`.
- This route does not require or enter the PGOOHIHKHNJ damage dispatch.

These facts prove a candidate path and a generic runtime binding. They do not
prove that a particular Natasha ability record instantiates HealHP or provide
that action's fields.

## Why Phase A cannot close

`data/extracted/4.4.53/direct_json/TurnBasedAbilityConfig.json` is an array of
config paths, not the JSON contents of those configs. No
`Avatar_Natasha_00_Ability.json` file is present in the workspace.

The DesignData archive paths recorded in
`data/raw/4.4.53/manifest/effective_design_chunks.csv` no longer exist at the
recorded local client location, and no full archive copy exists in the
workspace. Consequently, the required real ability ID, target selector, and
populated HealHP amount fields cannot be recovered from current inputs.

The reference `heal_hp.ksy` is useful discovery material but explicitly
targets an older client version. Its names cannot replace the missing 4.4.54
record or native dataflow evidence.

## Exact next frontier

Restore a hash-matching copy of the recorded 4.4.54 DesignData archive, or
provide the extracted `Avatar_Natasha_00_Ability.json`. Then:

1. Extract only Natasha's ability records.
2. Identify one concrete ability ID containing a HealHP action.
3. Recover its exact target config and populated amount fields.
4. Follow only those fields through M507657/M507658 into the already-proven
   HP transition.

`battle_ir/heal.py`, `battle_runtime/heal.py`, and the E2E test remain
uncreated because any real fixture would otherwise fabricate content.
