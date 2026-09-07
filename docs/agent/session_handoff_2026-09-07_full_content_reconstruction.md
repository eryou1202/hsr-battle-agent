# Full-content Reconstruction Handoff — 2026-09-07

## Project goal

Build a **full-content, deterministic HSR 4.4.54 battle sandbox**: freely
composable Avatar/trace/eidolon/LightCone/relic loadouts, Monster/Boss/waves,
Buffs, mode rules, RNG, compiled behavior, and a deterministic battle kernel.
This is neither the historical standard MVP nor a 249-record representative
sandbox. `FULL_4_4_54_SANDBOX_RECONSTRUCTION_FREEZE = NO`; DSH production
implementation remains frozen.

## Repository state

- Repository root: `D:\HSR_Battle_Agent\hsr-battle-agent`
- Read the current `HEAD`: it is the checkpoint that contains this handoff.
- Preserve historical dirty/untracked reverse and unpack evidence. Never use
  `git add .`, `git clean`, `git reset --hard`, `git restore .`, or `git stash`
  to obtain a clean tree.
- The historical 249-record corpus is regression/reference-only. It is not the
  behavior denominator for the full reconstruction program.

## Static data authority

- Exact static authority: `data/db/hsr_content_4.4.54.sqlite`, built from the
  immutable local Nanoka 4.4.54 snapshot.
- Do not rebuild the static database just to resume behavior work.
- The behavior corpus is an independently provenanced, pinned external
  reconstruction input. A source filename, source name, or close-version
  record is not proof of a native 4.4.54 static-ID join.

## Pinned external sources

All source manifests and cached raw payload hashes are under `.external_refs/`.
Use the cache before fetching; never use repository `HEAD`.

| Source | Pinned commit | Local manifest | Role |
| --- | --- | --- | --- |
| DimbreathBot/TurnBasedGameData | `b11066beacc4de454b625fafc7ea3dd540c5bbf3` | `.external_refs/TurnBasedGameData/manifest.json` | close-version behavior/config source |
| Mar-7th/StarRailRes | `02bdd75e1e3cf4272cea94165275c98a17ff1719` | `.external_refs/StarRailRes/manifest.json` | structured derived static/mapping evidence |
| nathacks/HSR-Mapping-DATA | `245f286185f5274609be264b6ef6dbc15e8a27ad` | `.external_refs/HSR-Mapping-DATA/manifest.json` | auditable mapping reference |
| fribbels/hsr-optimizer | `47ae66d8abac80b1f485a06fc11fe5e54c349c60` | `.external_refs/hsr-optimizer/manifest.json` | mature amount/formula reference only |

## Full-content pipeline

```text
pinned family discovery
  -> explicit fixed-commit fetch/cache + raw hash manifest
  -> full_content_behavior_ingestion_manifest_001.json
  -> shared recursive normalizer
  -> full_content_behavior_corpus_001.json
  -> strict Modifier definition catalog
  -> BehaviorCompiler / full compiler report
  -> static-to-behavior mapping
  -> coverage census + failure clusters + handler/context audit
```

Primary entry points:

- `src/hsr_battle_agent/game_data/full_content_behavior_ingestion.py`
- `scripts/build_full_content_behavior_ingestion_manifest.py`
- `scripts/fetch_full_content_behavior_families.py`
- `scripts/build_full_content_behavior_corpus.py`
- `scripts/build_full_modifier_definition_catalog.py`
- `scripts/build_behavior_ir.py`
- `scripts/build_content_behavior_mapping.py`
- `scripts/build_full_content_compiler_census.py`
- `scripts/audit_executable_handler_eligibility.py`

The large corpus and compiler-report JSON products are rebuildable and ignored;
the manifest, mapping, compact catalog, census, coverage census and audit are
the committed evidence products.

## Verified full-content baseline

All values below are read from the committed generated artifacts, not copied
from an earlier chat report.

- Manifest: `a11c42bb63a6c0db2ab23c00339c19981963735d143cc94557740197d137ca11`
- Corpus: `c89e6f41e133d4b0444fce0388de0b88a66aa6520ae03ce145f212f66b83658d`
- Source inputs selected for normalization: 711
- Canonical records: 14,042
- Behavior-bearing records: 10,685
- Static-definition-only records: 3,357
- Structural records: 2,579
- Executable-reference whole records: 1,528
- Executable entrypoints: 4,738
- Executable operation bindings: 59,595
- Source-backed whole records: 4
- Source-backed executed components: 27
- Golden-tested records: 0
- Compiler report:
  `26643b96b7daf90773f0e68a132f7e762b73822479c3792ac7dc3ed04f1f5ddb`
- Executor handler/context audit: `PASS_ALL_EXECUTABLE_KINDS_HAVE_HANDLER_AND_CONTEXT_CONTRACT`

`EXECUTABLE_REFERENCE` means all selected compiler, executor and declared
context dependencies close under strict reference rules. It does **not** mean
the record has been source-backed executed or independently Golden tested.

### Source families in the pinned corpus

| Family | Status | Cached/selected | Notes |
| --- | --- | ---: | --- |
| Avatar Ability | DONE for selected pinned family | 266/266 | behavior source, exact static Skill/Trace/Eidolon joins still incomplete |
| Avatar Config | DISCOVERED | 143/143 | owner/index evidence; not normalized as behavior payload |
| Global Modifier | DONE for selected family | 15/15 | behavior plus definition catalog input |
| LightCone Ability | PARTIAL | 15/15 | 187 captured behavior records; 165 exact structured config-ID joins, not full behavior coverage |
| RelicSet Ability | PARTIAL | 1/1 | 44 captured records; no exact static RelicSet join yet |
| Monster Ability | PARTIAL | 373/373 | 3,983 captured records; no direct MonsterSkill join or full AI/phase semantics |
| Monster AI | DISCOVERED | 2/2 | index evidence; not a complete AI corpus |
| Stage Buff Ability | PARTIAL | 3/3 | 134 captured records; static StageBuff join remains incomplete |
| Stage AdventureModifier | PARTIAL | 2/2 | behavior source, not a universal Stage/Mode mapping |
| Level Ability | PARTIAL | 13/13 | newly ingested source-family content; no inferred static Stage/Mode identity |
| AdventureModifier | PARTIAL | 28/28 | newly ingested source-family content; no inferred static Stage/Mode identity |
| Boss/Environment/Mode behavior | NOT COMPLETE | source candidates only where represented above | requires targeted discovery, mapping, and semantics |

### Static-to-behavior mapping boundary

The exact Nanoka 4.4.54 static denominator remains separate from the captured
behavior denominator. The current mapping artifact records 165 LightCone
exact-config links; Avatar records are representation-transform candidates,
not direct native-ID relations. Direct behavior mapping remains absent for
Skill, Trace, Eidolon, MonsterSkill and RelicSet. Do not convert static totals
into behavior or executable coverage percentages.

## Major completed foundations

- Recursive behavior IR lifting, nested callback/template/predicate/DynamicValue
  preservation, and strict opaque rejection.
- Event-ordering reference contract; Modifier lifecycle foundation and property
  contribution slots.
- DynamicValue/PostfixExpr, Target, Predicate, deterministic RNG, shared SP,
  selected damage/heal/survival, DoT tick, weakness, and toughness/Break
  reference branches.
- Scheduler primitives and bounded composition: task markers, templates/loops,
  action delay, inserted-action visibility, but **not** full AV/arbitration.
- Generic compiler → ExecutionContext → SemanticExecutor bridge, with a
  compiler/executor/context eligibility audit.
- Strict Modifier catalog: structured identity, exact-payload-only dedupe,
  all provenance retained, true conflicts preserved.
- Family-level bulk ingestion and full-content census.

## Current top blockers

The full compiler census measures blocked whole records and blocked operations.
It does not yet publish a separate per-cluster entrypoint denominator, so do
not fabricate one; use the report's sampled operation IDs to calculate it when
an implementation ticket requires that finer measurement.

| Priority | Cluster | Blocked records | Blocked operations | Affected scope | Evidence state / next action |
| --- | --- | ---: | ---: | --- | --- |
| 1 | `TriggerAbility` → `INVOKE_BEHAVIOR` | 1,459 | 2,863 | Monster, with equivalent Avatar cluster also present | Structural target names exist; call boundary and scheduler impact are unresolved. Build a corpus-wide resolved/ambiguous target registry; lower only deterministic calls. |
| 2 | `AddModifier` definition unresolved | 1,458 | 4,644 | Monster | Catalog visibility is complete; most remaining cases lack explicit supported stacking or have conflicts. Do not guess policies. |
| 3 | `SetTeamFormation` → `FORMATION_CHANGE` | 796 | 1,072 | Monster/Boss | No selected formation/body-part/summon state transition model. Requires Boss/formation packet. |
| 4 | mixed `DamageByAttackProperty` request | 685 | 1,692 | Monster, plus Avatar variants | Existing normal HP and separate toughness paths cannot silently consume mixed fields. Split exact request families. |
| 5 | `Retarget` unsupported target form | 627 | 1,858 | Monster, plus Avatar/Modifier variants | Target model is only partial; inspect alias/selector groups and preserve unclosed target semantics. |

Other material clusters include IncludeTaskListTemplate cross-record expansion,
unsupported ActionDelay targets, `DispelStatus`, and unsupported Modifier
Add arguments. These are strict failures, not no-ops.

## Exact next task — do not preempt it

`CROSS-BEHAVIOR-INVOKE-001`

Why: `TriggerAbility` blocks 1,459 Monster records / 2,863 operations and is
the highest-leverage architecture dependency after the catalog repair. It may
also establish a reusable cross-record call graph for Avatar, equipment and
Buff behavior. It must begin by publishing a resolved/ambiguous/missing target
registry from the current corpus. Only a target with a unique same-corpus
behavior record and an explicit deterministic invocation boundary may be
lowered. Any call that changes scheduling/arbitration, has a missing/ambiguous
target, or carries unknown state/effect semantics remains uncompiled.

First resume commands:

```powershell
git status --short
git log --oneline -10
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
& 'C:\Users\而忧\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.game_data.test_behavior_compiler tests.game_data.test_reference_execution
```

Then read the manifest, corpus/report/census/catalog, this handoff, and the
existing `INVOKE_BEHAVIOR` binding in `behavior_compiler.py`. Do not rerun
initial discovery, re-fetch cached source families, rebuild the static content
database, re-open blind unpack/native reverse, or return to per-record
Natasha/Black-Swan semantic work.

## Verification at this landing

- Targeted normalizer/catalog/compiler/reference-execution tests: PASS (86).
- Python compile check for edited game-data modules and full-content scripts:
  PASS.
- Full corpus, compiler report, mapping, catalog, coverage and handler audit
  regenerated from the same corpus/report provenance.
- Golden tests: none; no Golden claim is made.
