# Simple Skill Candidate Index 21

`STATUS = CONTENT_TOPOLOGY_SELECTION`

This is a selection index for the first complete Sandbox E2E vertical slice. It
does **not** resolve gameplay semantics.

Artifact: `data/raw/4.4.54/simple_skill_candidate_index_21.json`

---

## Candidate count scanned

- `10` config/executor + representative avatar ability paths.

## Ranked candidates (top 5)

| Rank | Skill | Path class | PGOO blocker reached |
| --- | --- | --- | --- |
| 1 | HealHP (Natasha/Lynx/Bailu representative paths) | C.USES_DIRECT_HP_OR_ALREADY_RECOVERED_PATH | No |
| 2 | LoseHP | C.USES_DIRECT_HP_OR_ALREADY_RECOVERED_PATH | No |
| 3 | LoseHPByRatio | C.USES_DIRECT_HP_OR_ALREADY_RECOVERED_PATH | No |
| 4 | SetHP | C.USES_DIRECT_HP_OR_ALREADY_RECOVERED_PATH | No |
| 5 | Asta Basic ATK / simple damage skill | A.USES_BLOCKED_PGOO_DAMAGEBYATTACKPROPERTY | Yes |

## PGOO usage for each

- HealHP/LoseHP/LoseHPByRatio/SetHP: **PGOO not present**
- Asta/Herta/DanHeng/March 7th/Trailblazer Basic ATK candidates: **PGOO present**, runtime dispatch reached
- ProcessStoredDamage: **PGOO present**, runtime dispatch reached

## Best bypass candidate

- **HealHP config-level candidate**
- Representative avatar ability paths: `Avatar_Natasha_00_Ability.json`,
  `Avatar_Lynx_00_Ability.json`, `Avatar_Bailu_00_Ability.json`
- Chain: `AAOLFLMHBEK -> M507658 -> M506500 DirectChangeHP -> M506499 DirectDamageHP`
- Does **not** reach `PGOOHIHKHNJ +0x120`.

## Remaining unknowns

- Exact character ability file that instantiates HealHP (ability JSON contents are not parsed in the current repo extraction)
- HealHP config field mapping for that specific character
- Whether the chosen heal skill has any extra conditional/target complexity

## PGOO blocker assessment

- **`BYPASSABLE_FOR_NON_DAMAGE_OR_DIRECT_HP_SLICE`**
- Typical Basic ATK / direct damage skills are expected to route through `DamageByAttackProperty` and therefore hit the PGOOHIHKHNJ runtime dispatch.
- A heal/direct-HP skill provides a real E2E path that avoids the blocker using already recovered primitives.

## Recommended next task

Select a real healer ability path (Natasha/Lynx/Bailu), parse its ability JSON content to confirm `HealHP` instantiation, then build the first E2E Sandbox slice around `HealHP -> DirectChangeHP -> DirectDamageHP`.
