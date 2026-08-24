# Authoritative External Reconstruction Layer v1

## Purpose and non-goals

This layer turns a small, pinned set of public references into independently
normalized, provenance-bearing **static** content additions for the local HSR
4.4.54 content database.  It is intentionally outside `battle_runtime`.

```text
Pinned public snapshot → independent adapter → external Canonical records
                                                ↓
Nanoka 4.4.54 Canonical/SQLite ───────────────→ augmented query database
                                                ↓
                               static Loadout materializer / reference evaluator
```

It does not read DesignData, IL2CPP metadata, native code, reverse artifacts,
or a `BattleState`.  It neither proves nor implements event order, state
mutation timing, target legality, monster AI, or an official runtime.

The authoritative target content version is **4.4.54**.  The builder rejects a
different version; in particular, 4.4.55 cannot enter the 4.4.54 database.

## Fixed source law

| Source | Selected commit | Version relation | Role | What is used |
| --- | --- | --- | --- | --- |
| [TurnBasedGameData](https://github.com/DimbreathBot/TurnBasedGameData) | `b11066beacc4de454b625fafc7ea3dd540c5bbf3` | CLOSE (declared 4.4.0 build) | client-dump reference | RelicConfig, main/sub affixes, MazeBuff, EliteGroup, HardLevelGroup, narrow monster candidates |
| [StarRailRes](https://github.com/Mar-7th/StarRailRes) | `02bdd75e1e3cf4272cea94165275c98a17ff1719` | CLOSE (4.4) | independently structured cross-check | relic-affix representation and documented content schema |
| [HSR-Mapping-DATA](https://github.com/nathacks/HSR-Mapping-DATA) | `245f286185f5274609be264b6ef6dbc15e8a27ad` | SCHEMA_ONLY | auditable mapping reference | field transformation intent for Avatar, LightCone, and Relic tables |
| [hsr-optimizer](https://github.com/fribbels/hsr-optimizer) | `47ae66d8abac80b1f485a06fc11fe5e54c349c60` | ALGORITHM_ONLY (4.4v5) | numeric algorithm reference | narrow, independently implemented amount-only evaluator |

`EXACT` means Nanoka 4.4.54.  `CLOSE`, `SCHEMA_ONLY`, and
`ALGORITHM_ONLY` are retained as such; none may overwrite exact-version
Nanoka values.  An external record uses evidence levels `R1`
(client-dump-derived), `R2` (mature implementation), or `R3`
(cross-source reconstructed).  These are deliberately separate from local
semantic confidence `C0`–`C4`.

The pinned raw snapshot is a minimal cache at `.external_refs/` and is ignored
by Git.  It contains selected files, per-file raw SHA-256, source URL where
available, and the selected commit—not a third-party checkout or mirror.

## Current external reconstruction result

The build emits Canonical additions under
`data/content/4.4.54/external_reconstruction/` (ignored) and augments
`data/db/hsr_content_4.4.54.sqlite` with these tables:

| Family | Records | Evidence / result |
| --- | ---: | --- |
| Relic main/sub affixes | 165 | 117 main + 48 sub; group/affix composite game IDs, level curves and roll tiers preserved; `R3`, CLOSE |
| Relic templates | 742 | template ID, set ID, slot, rarity, maximum level, main/sub-affix groups; `R1`, CLOSE |
| Stage Buff raw configuration | 17 | Nanoka exact Stage→Buff binding remains separate; raw MazeBuff detail is attached as `EXTERNAL_CLOSE` only |
| EliteGroup / HardLevelGroup | 2,135 | 1,394 + 741 raw records; no Stage/Mode join is claimed |
| Monster candidate for `4034020` | 2 | raw candidate records preserved; not a full variant relation |

The 18 exact-version Nanoka Stage Buff references are never overwritten.  Of
them, 17 get a separately-provenanced close-version MazeBuff detail; ID
`3110018` remains explicit `UNKNOWN`.  `get_stage_package()` therefore adds
`detail_source: EXTERNAL_CLOSE` only when that separate detail exists.

The cross-source check finds all 117 TurnBasedGameData main-affix group/affix
keys in StarRailRes, but only 80 exact numeric/property matches; 37 are a
`SOURCE_CONFLICT` at the selected CLOSE-version pins.  This conflict is an
artifact, not silently normalized away.

## Mapping index and rule pack

The machine-readable mapping index is
`data/semantics/4.4.54/external_reconstruction/authoritative_mapping_index.json`.
It maps canonical Avatar, Skill, Trace, Eidolon, LightCone, RelicTemplate,
RelicAffix, Monster, MonsterSkill, Stage, and StageBuff fields to the actual
source table/path and mapping symbol.  It is a source-navigation and adapter
audit tool, not a claim that every table was imported.

`reconstruction_rule_pack.json` and `fribbels_rule_inventory.json` record the
only numeric formulas implemented here: normal damage, Break, Super Break,
Heal, and Shield.  Each result carries `amount_only` scope.  The normal-damage
reference is deliberately restricted to the source's level-80 attacker
assumption; passing another attacker level is rejected rather than generalized.

`ReferenceEvaluator.materialize_loadout()` supports ID-preserving Avatar,
Eidolon rank, compatible LightCone, selected Trace status additions, and
template-validated relic pieces.  It verifies relic slot, level, and affix
group, then returns base/final static properties plus the unapplied contextual
LightCone, RelicSet, and Eidolon effects.  Those mechanisms are not guessed
into the properties.

## Deterministic operation

```powershell
$env:PYTHONPATH = "src"
python scripts/fetch_external_references.py
python scripts/build_content_db.py 4.4.54
python scripts/build_external_reconstruction.py 4.4.54
```

Fetching and building are separate.  Once the raw pinned snapshot is present,
the build makes no network request.  Rebuilding the Nanoka database followed
by the external augmentation is deterministic at the logical SQLite level.

The build writes these committed, compact evidence artifacts:

- `external_reference_manifest.json`
- `authoritative_mapping_index.json`
- `cross_source_checks.json`
- `fribbels_rule_inventory.json`
- `reconstruction_rule_pack.json`
- `static_reconstruction_gaps.json`
- `dynamic_reconstruction_matrix.json`
- `local_validation_queue.json`

## Remaining boundaries

Static work left by this layer is narrow: exact 4.4.54 validation of relic
numeric values, the missing Stage Buff `3110018`, an evidence-backed
Stage/Mode join for EliteGroup and HardLevelGroup, and the unresolved complete
variant list for Monster `4034020`.

Dynamic work is intentionally not closed here: Damage request ordering, HP
write/HealData consumption, SP and Energy mutation order, AV recharge, event
listener order, shield lifecycle, Break state changes, Death/Victory, wave
transitions, action legality, follow-up, extra action, summon, boss phase, and
monster-AI scheduling.  See `dynamic_reconstruction_matrix.json` before
proposing a runtime task.
