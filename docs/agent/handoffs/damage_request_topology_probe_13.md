# Damage Request Topology Probe 13

Status: `TOPOLOGY_PROBE_ONLY` — not a semantic handoff.

This probe mechanically reduces the native damage candidate space for V4P. It
does **not** recover gameplay formulas, DamageRequest semantics, or implement
a damage runtime.

## Inputs

- `data/raw/4.4.54/action_config_runtime_bridge_06.json`
- `data/raw/4.4.54/generated_task_damage_topology_10.json`
- `data/raw/4.4.54/damage_direct_hp_xrefs_10.json`
- Normalized `methods.json` / `types.json` for 4.4.54

## Counts

- Generated executors scanned: **3024**
- Damage-hinted generated executors: **146**
- Initial candidate count after mechanical filter: **101**
- Shared-helper clusters: **11**

## Top ranked candidates

| Rank | Classification | Method | RVA | Reuse |
| --- | --- | --- | --- | --- |
| 1 | DAMAGE_VALUE_RESOLVE_CANDIDATE | `NNGMOCFGPBN` (PGOOHIHKHNJ) | `0xC3123B0` | 2 damage executors |
| 2 | HP_DELTA_BRIDGE_CANDIDATE | `TargetDamageHP` (AbilityStatic) | `0xE46D760` | 3 damage executors |
| 3 | HP_DELTA_BRIDGE_CANDIDATE | `DirectChangeHP` (TurnBasedAbilityComponent) | `0xE733830` | 2 damage executors |
| 4 | HIT_CONTEXT_CANDIDATE | `HPKFAFOPGPG` (PGOOHIHKHNJ) | `0xC30FC40` | 1 damage executor |
| 5 | HP_DELTA_BRIDGE_CANDIDATE | `DirectDamageHP` (already recovered anchor) | `0xE732180` | terminal |
| 6 | DAMAGE_REQUEST_CANDIDATE | `DCADIANHPFD` (JKNLHJLPIOO) | `0x162C0160` | 7 damage executors |
| 7 | DAMAGE_REQUEST_CANDIDATE | `GetAttackDamageType` (AbilityStatic) | `0xE44A310` | 6 damage executors |
| 8 | DAMAGE_REQUEST_CANDIDATE | `ProcessAttackResultDirectKill` (AdventureStatic) | `0xE4CC670` | 6 damage executors |

## Reference anchors

- `BeginDamageChunk` — `0xE7227E0` — `DAMAGE_CHUNK_SCOPE_ONLY`
- `EndDamageChunk` — `0xE722880` — `DAMAGE_CHUNK_SCOPE_ONLY`
- `0x15C6D120` (VA `0x195C6D120`) — `GENERATED_DISPATCH`

## Shared helper clusters

Strong clusters include:

- `TryGetLockHP` hub (`0xE7333E0`) — connects HP bridge candidates
- `DirectDamageHP` hub (`0xE732180`) — connects `TargetDamageHP` and `DirectChangeHP`
- `GetStanceDamageType` / `CanStanceDamage` / `GetStanceDamage` — stance-adjacent shared helpers
- `get_AttackType` — attack-type read helper cluster
- `RefreshPalyerLockable` — lockable refresh cluster (lower rank)

## Shortest observed path to known HP transition

```text
NNGMOCFGPBN 0xC3123B0
  -> TargetDamageHP 0xE46D760
  -> DirectDamageHP 0xE732180
```

Also observed:

```text
HPKFAFOPGPG 0xC30FC40
  -> ... -> TargetDamageHP 0xE46D760
  -> DirectDamageHP 0xE732180
```

## Recommended V4P entry

- **Primary:** `NNGMOCFGPBN` — method 507308, RVA `0xC3123B0`, type `PGOOHIHKHNJ`
  - Shared by `RPG.GameCore.DamageByAttackProperty` and `RPG.GameCore.ProcessStoredDamage`
  - Calls damage resolve/finish helpers and `TargetDamageHP`
- **Alternates:**
  - `TargetDamageHP` — method 504579, RVA `0xE46D760`
  - `DirectChangeHP` — method 506500, RVA `0xE733830`
  - `HPKFAFOPGPG` — method 507297, RVA `0xC30FC40`
  - `DirectDamageHP` — method 506499, RVA `0xE732180` (terminal anchor only)

## Explicitly excluded

- `SetHP` is an HP-state mutation path, not a normal combat DamageRequest boundary.
- `0x195C6D120` / `0x15C6D120` is generated tag-dispatch evidence, not a settled DamageRequest.
- M506499 modes 4/5/6, damage formula, ATK/DEF/RES/Crit, Break/Toughness, events, and Turn/AV are out of scope.
