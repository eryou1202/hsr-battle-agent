# Versioned Local Content Database

## Purpose and boundary

This subsystem turns public, versioned static content into a local, auditable
input for the future scenario/loadout compiler.  It is deliberately separate
from both raw local DesignData and the battle runtime:

```text
Nanoka raw snapshot → adapter → Canonical JSON/JSONL → SQLite query layer
Pinned external references → independent adapter ───────┘
Local DesignData evidence ────────────────────────────→ validation metadata
                                                      ↓
                                          future Scenario / Loadout compiler
                                                      ↓
                                                battle runtime
```

The runtime must not read a Nanoka URL, Nanoka raw JSON, archive offset, or
DesignData serializer directly.  This database carries **static facts** only;
it does not prove dynamic formula order, event order, target legality, or any
other battle semantic.

## Version and source policy

- `CONTENT_VERSION = 4.4.54` is the database key in this repository.
- Primary oracle: `https://static.nanoka.cc/hsr/4.4.54/`.
- Nanoka's newer `4.4.55` data is a version-delta/schema-discovery input only.
  It must never silently fill a `4.4.54` record.
- Source facts retain `source = nanoka`, source version, category, URL,
  locale, HTTP ETag/Last-Modified where received, fetch time, and raw SHA-256.
  An interrupted pre-index fetch is recorded as `RECOVERED_UNINDEXED`, with
  unavailable HTTP metadata explicitly null rather than invented.

Confidence and usability are independent:

| Confidence | Meaning |
| --- | --- |
| C0 | external-only Nanoka fact |
| C1 | multi-source match |
| C2 | local entity/ID match |
| C3 | local structural parser match |
| C4 | local runtime verified (dynamic semantics only) |

`RECONSTRUCTION_READY` means a static record has enough preserved data for a
future compiler even when its confidence is C0.  It does not make a runtime
effect executable.

The external reconstruction layer has a separate evidence scale (`R1` client
dump-derived, `R2` mature implementation reference, `R3` cross-source
reconstructed). It never upgrades a local semantic confidence level and does
not overwrite an exact Nanoka record with a close-version source. Its source
law, pins, and limitations are in `docs/agent/external_reconstruction.md`.

## On-disk layers

| Layer | Location | Git policy |
| --- | --- | --- |
| Immutable raw snapshot | `data/external/nanoka/4.4.54/` | ignored except README |
| Canonical content | `data/content/4.4.54/nanoka/` | ignored except README |
| SQLite query database | `data/db/hsr_content_4.4.54.sqlite` | ignored |
| Pinned external snapshot | `.external_refs/` | ignored; minimal commit-addressed cache |
| External Canonical additions | `data/content/4.4.54/external_reconstruction/` | ignored |
| External mapping/rule/gap artifacts | `data/semantics/4.4.54/external_reconstruction/` | committed |
| Small offline fixture | `tests/game_data/fixtures/` | committed |

Raw data is never edited by the adapter.  Deleting Canonical and SQLite
outputs and rebuilding from the same raw snapshot must yield the same logical
SQLite hash.

## Fetch and build

Run these from the repository root with a Python 3.11+ environment and
`src` on `PYTHONPATH`:

```powershell
$env:PYTHONPATH = "src"
python scripts/fetch_nanoka_snapshot.py 4.4.54 --workers 3
python scripts/build_content_db.py 4.4.54
python scripts/fetch_external_references.py
python scripts/build_external_reconstruction.py 4.4.54
python scripts/export_stage_package.py 4.4.54 <stage-id>
```

The fetcher is collection-key driven, concurrency-limited to 1–4 workers,
resumable, and respects cached raw hashes.  It fetches only 4.4.54 collections
and their listed details, plus Stage-referenced `_BindingMazeBuff` details;
it does not numeric-scan IDs.  HTTP failures are persisted in
`provenance/errors.json` rather than hidden.

## Canonical model and SQLite

Canonical records have:

- `game_version`, `entity_type`, `entity_id`, and preserved
  `original_game_id` (or an explicit non-native ID status);
- `confidence` and `reconstruction_status`;
- source payload fields without gameplay-inference rewriting;
- an array of raw source references and a canonical SHA-256.

The query database has typed entity tables for Avatar/Skill/Trace/Eidolon,
LightCone/promotion/superimposition, RelicSet/item, Monster/variant/skill,
mode metadata, Stage/Wave/WaveMonster/StageBuff, as well as typed relation,
snapshot, validation, and gap tables.  Its logical primary key is
`(game_version, entity_id)`.

The public query facade is `ContentDatabase` in
`src/hsr_battle_agent/game_data/nanoka_content.py`:
`get_avatar`, `get_skill`, `get_lightcone`, `get_relic_set`, `get_monster`,
`get_encounter`, `get_stage`, and `get_stage_package`. When the external
augmentation is built it additionally offers `get_relic_affix`,
`get_relic_template`, `get_stage_buff`, and `get_external_stage_buff`.

`get_stage_package(stage_id)` preserves wave ordering, group/slot identity,
monster IDs, levels, Stage Buff links, rule metadata, source references, and
explicit unresolved references.  When a Stage appears in multiple Maze,
Story, or Boss contexts, the package returns each distinct `Encounter` context
instead of merging them.  It returns static scenario data, not an initial
battle state. The exact Nanoka Stage→Buff relation remains the package
authority; a separate close-version MazeBuff record is surfaced only as
`detail_source: EXTERNAL_CLOSE` and never replaces that binding.

## Validation and gaps

Local DesignData is a validation/proof source, not a fallback value source.
The Canonical build records `EXACT`, `ROUNDING_EQUIVALENT`,
`TRANSFORM_EQUIVALENT`, `VERSION_DELTA`, `LOCAL_MISSING`, `EXTERNAL_MISSING`,
`CONFLICT`, or `UNKNOWN`; conflicting local/external facts are retained,
never overwritten.

The build emits separate machine-readable files:

- `validation/local_validation.json`
- `validation/reconstruction_coverage.json`
- `validation/nanoka_static_gaps.json`
- `validation/dynamic_semantic_gaps.json`

The first is the low-cost Local 4.4.54 sanity layer.  The latter two must not
be conflated: missing relic-affix or Stage fields are static-recovery work;
Damage, HealData consumption, SP/Energy ordering, Turn recharge, Event order,
Death/Victory, Break, follow-up, and action legality are dynamic-semantic work.

## Verification

The committed offline fixture covers two Avatars including Natasha and all
six Eidolons, two LightCones, two RelicSets, three Monsters, and a Stage with
wave/group/monster/Buff relationships.  It verifies normalization, SQLite
rebuild determinism, ID preservation, version isolation, relations, and stage
package export without making a network request.

## Current verified 4.4.54 build

The local snapshot build completed with 1,055 indexed raw payloads (about
22.9 MB) and 20 explicit unavailable endpoints.  The latter consist of the
two requested global auxiliary endpoints and 18 Stage-referenced
`_BindingMazeBuff` detail endpoints; they are not silently treated as content.

| Family | Reconstruction-ready / total |
| --- | --- |
| Avatar | 97 / 97 |
| Skill | 664 / 664 |
| Trace | 5,018 / 5,018 |
| Eidolon | 582 / 582 |
| LightCone | 169 / 169 |
| RelicSet | 60 / 60 |
| Monster | 627 / 628 |
| MonsterSkill | 12,873 / 12,873 |
| Encounter | 1,543 / 1,543 |
| Stage / Wave / WaveMonster | 1,459 / 1,459, 1,459 / 1,459, 6,717 / 6,717 |
| StageBuff | exact binding 18 / 18; 17 close-version raw detail records; 1 explicit unknown (`3110018`) |
| Stage→Buff relation | 160 bindings preserved; raw Buff configuration is not runtime semantics |

The generated SQLite is about 76.0 MB and its two successive rebuilds from
the same raw snapshot had logical SHA-256
`ea45fd588551ccc0543131e16e1379461995c89875d35d491a42fc56a56109eb`.
The health report has no duplicate IDs, dangling Monster references, missing
Avatar owners, orphan skills, Stage/Wave inconsistency, or version
contamination.  Raw Maze input has 84 exact duplicate Stage→Wave rows and
428 exact duplicate Wave→Monster rows; they are surfaced in health output and
materialized only once in SQLite. The original Nanoka-only static gaps are now
narrowed by the external layer: the Relic affix/roll schema is reconstructed
as 165 ID-preserving records; the `EliteGroup` / `HardLevelGroup` raw tables
are present but lack a claimed exact Stage/Mode join; Monster `4034020` still
lacks a complete variant list; and Stage Buff `3110018` still has no external
raw detail. Story detail is captured as Encounter→Stage context rather than
being treated as a missing link.

The collection-only 4.4.54 → 4.4.55 delta has no added or removed IDs and no
collection schema key changes; only two Monster collection entries differ.
It is recorded in `data/content/diffs/4.4.54_to_4.4.55.json` and is not used
by the 4.4.54 database.
