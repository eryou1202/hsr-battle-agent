# HSR Battle Agent — Authoritative Project Index

> **Session entry point.** This is the compact, evidence-first map of the
> checked local repository as of the current `main` (2026-08-24), including
> the version-locked Nanoka 4.4.54 content-database work.
> Read this file, then the linked artifact for the subsystem being changed.
> Source code, tests, committed artifacts, and Git history take precedence
> over historical handoffs.  Do not treat uncommitted worktree files as
> published evidence.

## 1. Project Goal

The end product is a **deterministic, high-speed, cloneable HSR battle
simulation sandbox** for automated planning, Beam Search, MCTS, policy/value
training, and eventually real-time battle advice.  Reverse engineering is
supporting infrastructure, not the product.

The current strategy is deliberately corpus-first:

`full content census → generic content compiler → corpus semantic coverage → coverage-driven primitive recovery → standard battle E2E → planner / training APIs`

Do not make character-by-character semantic reverse the primary development
method again.

## 2. Current Architecture

```text
Nanoka 4.4.54 snapshot
  └─ `game_data/nanoka_content.py` adapter
       └─ Canonical JSONL + SQLite query database

Pinned external reference snapshots
  └─ `game_data/external_reconstruction.py` independent adapter
       └─ external Canonical additions + SQLite augmentation

Canonical content + static external additions
  └─ static Loadout materializer / amount-only reference evaluator
       └─ future Scenario / Loadout compiler
            └─ Battle IR / battle runtime

Local HSR client / DesignData archive
  └─ tools/unpack_pipeline + tools/reverse/scripts
       ├─ data/parsed/4.4.54       (pipeline reports, structural records)
       ├─ data/normalized/4.4.54   (type/method/field/parameter registries)
       └─ data/raw/4.4.54          (bounded reverse evidence)
            └─ selected ability containers / TaskConfig registry
                 └─ data/semantics/4.4.54 catalog
                      └─ src/hsr_battle_agent/battle_ir
                           └─ src/hsr_battle_agent/battle_runtime
                                └─ src/hsr_battle_agent/battle_sandbox
                                     └─ tests + data/sandbox reports
                                          └─ dynamic_core semantic-packet contracts
                                          └─ future planning/ and models/
```

Existing planner/model/frontend directories are placeholders; they are not a
working planning product.

## 3. Repository Directory Index

| Area | Primary location | Checked state |
| --- | --- | --- |
| Versioned unpack pipeline | `tools/unpack_pipeline/`, `scripts/unpack_version.ps1`, `docs/unpack/` | PASS; static pipeline v1 |
| DesignData/reverse helpers | `tools/reverse/scripts/`, `data/raw/4.4.54/` | PARTIAL; evidence and bounded parsers |
| Parsed/normalized registries | `data/parsed/4.4.54/`, `data/normalized/4.4.54/` | PASS for metadata registries |
| Content path indexes | `data/extracted/4.4.53/direct_json/` | PARTIAL; paths, not a content database |
| External raw content snapshot | `data/external/nanoka/4.4.54/` | Local ignored cache; version-locked oracle evidence |
| Canonical static content | `data/content/4.4.54/nanoka/` | Local ignored, deterministic JSONL build |
| Pinned external references | `.external_refs/`, `scripts/fetch_external_references.py` | PASS; minimal commit-addressed cache, ignored by Git |
| External reconstruction | `game_data/external_reconstruction.py`, `data/semantics/4.4.54/external_reconstruction/` | PASS for bounded static gaps and amount-only reference rules; no local runtime proof |
| Dynamic-core reconstruction contracts | `data/semantics/4.4.54/dynamic_core/`, `docs/agent/dynamic_core_reconstruction.md` | PARTIAL; auditable candidate/stop boundaries, not a runtime |
| Content SQLite/query facade | `data/db/`, `game_data/nanoka_content.py` | PASS for static query/build surface; external augmentation is separately provenanced, not a runtime compiler |
| Battle IR | `src/hsr_battle_agent/battle_ir/` | PARTIAL-to-PASS by primitive |
| Battle runtime | `src/hsr_battle_agent/battle_runtime/` | PARTIAL; proof-scoped only |
| Battle state/kernel | `src/hsr_battle_agent/battle_sandbox/` | PASS for deterministic kernel/state boundaries |
| Real content loader | `src/hsr_battle_agent/game_data/real_skill.py` | PARTIAL; one validated Natasha slice |
| Tests | `tests/` | PARTIAL; see §9 |
| Sandbox reports | `data/sandbox/` | PASS as recorded evidence |
| Human handoffs | `docs/agent/handoffs/` | Historical supporting evidence |
| Planner/model/UI placeholders | `src/hsr_battle_agent/planning/`, `models/`, `apps/` | NOT_IMPLEMENTED |

## 4. Version and Data Sources

- Pipeline game version: `4.4.54`; build token is recorded in
  `data/parsed/4.4.54/pipeline_report.json`.
- Client location used by the recovered DesignData evidence:
  `D:\StarRail_4.4.53\StarRail_Data\Persistent\DesignData\Windows`.
- Main archive: `8625dd99e13b0dfe6b45f47f9bfe3e36.bytes`, 125,829,538 bytes,
  SHA-256 `098EC31C5C03A0F6FBF030D6B2579A5E60C03639CE7060F68FA52371A03DC64B`.
- Path/index archive: `edd7d527b0962f4ec2e49789746fb0d2.bytes`, 184,370 bytes,
  SHA-256 `078AC12FAB39F08401B777D9F7C35BA0B1248CB28F7AF19AFFA1EA900FA731E4`.
- Do **not** add either large client archive to Git.  Provenance is retained
  in `data/raw/4.4.54/designdata_recovery_audit_23.json` and the audit files.

The static unpack run is `V1_STATIC_COMPLETE`: 20 DesignData files were
discovered; 80,880 types, 732,328 methods, 555,259 fields, and 655,072
parameters are normalized.  Optional generated-polymorphic runtime enrichment
was not run.

The version-locked external static oracle is Nanoka `4.4.54`; Nanoka `4.4.55`
is a version-delta/schema-discovery input only.  See
`docs/agent/content_database.md` for raw/canonical/SQLite separation and
provenance rules.

An additional external reconstruction layer is pinned to four public
references: TurnBasedGameData and StarRailRes are CLOSE, HSR-Mapping-DATA is
SCHEMA_ONLY, and hsr-optimizer is ALGORITHM_ONLY. It cannot fill 4.4.54 with
4.4.55, overwrite a Nanoka record, or serve as local semantic proof. See
`docs/agent/external_reconstruction.md`.

## 5. Content Extraction State

Use these levels literally: **L0 NOT_FOUND**, **L1 RAW_PRESENT**, **L2
INDEXED**, **L3 STRUCTURALLY_DECODED**, **L4 SANDBOX_SEMANTICS_AVAILABLE**.

| Content family | Current level | Evidence and boundary |
| --- | --- | --- |
| Avatar ability file paths | L2 | 1,510 TurnBasedAbility paths, including 124 core `Avatar_*_Ability` paths; path ≠ parsed ability contents |
| Selected Avatar containers | L3 | Generic outer container recovery for Black Swan (15 named records) and Natasha (8); see `ability_file_container_*_30.json` |
| Avatar full configuration family | L2/L3 partial | No avatar has identity/stat template, all traces, and Rank01–Rank06 jointly recovered; see `avatar_content_completeness_audit.json` |
| Concrete task content | L3, one slice | Natasha `Skill02_Phase02` includes a structural `PredicateTaskList`, DispelStatus, and HealHP 1481 records |
| Natasha heal formula runtime | L4 boundary only | FormulaType 4 computes and emits typed request boundaries; it does not consume HealData or mutate HP |
| Monster entity records | L1 | 10,168 unique `Monster_*` raw token candidates in the main archive; no entity table was parsed |
| Monster ability config paths | L2 | 377 core `/Monster/..._Ability` paths (679 broad monster/enemy paths); no entity-to-ability join |
| Monster AI paths | L2 | Two explicitly indexed Monster ComplexSkillAI config paths; no parsed selection policy |
| Stage/encounter entities | L1 | 137 raw `Stage*` token candidates; encounter records and waves are not parsed |
| Stage/mode ability paths | L2 | 323 Stage/Maze/Challenge/GridFight-like paths, which are ability files, not stage encounter configs |
| Stage buff/modifier family | L2 external-static partial | 160 exact-version Nanoka bindings are preserved; 17/18 raw config details are separately attached from a CLOSE source, while `3110018` remains unknown |
| Versioned external static content | Reconstruction-ready external | Canonical/SQLite content may be C0 external-only but is ID-preserving, provenance-bearing static input; it is not local runtime proof |

The complete audit artifacts are:

- `data/raw/4.4.54/avatar_content_completeness_audit.json`
- `data/content/4.4.54/audit/black_swan_content_family_manifest.json`
- `data/raw/4.4.54/monster_stage_content_audit.json`

### Version-locked external static database

The Nanoka 4.4.54 local snapshot is now a reconstruction-ready static layer:
97 Avatars, 664 Skills, 5,018 Traces, 582 Eidolons, 169 LightCones, 60
RelicSets, 628 Monsters, 12,873 MonsterSkills, 1,543 Encounter contexts, and
1,459 Maze/Story/Boss Challenge Stage records. Stage→Wave→Monster is
preserved (1,459 waves, 6,717 placements). The 160 discovered Stage→Buff
bindings stay exact-version Nanoka records; 17 of their 18 raw Buff details
are now separately available as CLOSE-version external records, with
`3110018` explicitly unresolved.
Read `docs/agent/content_database.md`; do not mistake static C0/C1 content
for local runtime semantics.

## 6. Runtime Capability Matrix

`PASS` means a checked, proof-scoped implementation exists; it does not mean
the corresponding game-wide mechanic is complete.

| Capability | Status | Main implementation/evidence | Limitation |
| --- | --- | --- | --- |
| Unpack pipeline and normalized registries | PASS | `tools/unpack_pipeline/`, `data/parsed/4.4.54/` | Content records are not generically compiled |
| Ability content graph | PARTIAL | `recover_ability_file_container_30.py` | Selected prefixes; no corpus graph |
| TaskConfig registry | PASS | `taskconfig_registry_30.json` | Registry does not parse every payload |
| DynamicValue | PASS | `battle_ir/values.py`, `battle_runtime/values.py` | Only recovered batch scope |
| FixPoint and comparison | PASS | `battle_runtime/predicates.py` | Special encodings remain bounded where documented |
| Predicate | PARTIAL | `battle_runtime/predicates.py` | Natasha `BySkillPointActivated` context semantics external |
| Target | PARTIAL | `battle_runtime/targets.py` | Target discriminator 12 is not joined to runtime selector |
| Action | PARTIAL | `battle_runtime/actions.py` | No generic decoded action compiler |
| Modifier and lifecycle | PARTIAL | `battle_runtime/modifiers.py` | Recovered lifecycle/property routes only |
| Property | PASS (scoped) | `battle_runtime/property.py` | Materialization kinds 3–7 formulas unresolved |
| HP | PARTIAL | `battle_runtime/hp.py` | DirectDamageHP mode 0 only; not a general damage system |
| Heal | PARTIAL | `battle_runtime/healing.py` | Request boundary only; positive HealData consumer unknown |
| Damage | PARTIAL | `damage_value_to_hp_bridge_13.json`, external reference evaluator | Explicit external amount → local TargetDamageHP/DirectDamageHP mode-0 is reconstruction-ready; native general DamageRequest/formula remains unknown |
| Turn / AV | PARTIAL | `battle_runtime/turns.py` | Ordinary eligible actions only; recharge is explicit input |
| Event dispatch | BLOCKED | boundary objects/traces only | Listener registration/order/consumers unknown |
| Energy / Skill Point | BLOCKED | no state/runtime primitive | Skill-point predicate is externally resolved in the one E2E |
| Shield, Toughness/Break, Death | BLOCKED | no accepted runtime implementation | Config/type names are not runtime proof |
| Summon, follow-up, extra action | BLOCKED | no accepted runtime implementation | no generic content compiler or event sequencing |
| Content compiler | BLOCKED | no module | Next architectural milestone |
| Static content query database | PASS | `game_data/nanoka_content.py`, `scripts/*content*` | Static only; no BattleInitialState/runtime effect compiler |
| External static reconstruction | PASS (bounded) | `game_data/external_reconstruction.py` | 165 relic affixes, 742 templates, 17 external Stage Buff details; exact local validation deferred |
| Reference evaluator | EXPERIMENTAL | `ReferenceEvaluator` | Amount-only external algorithms; not a Battle Runtime or semantic proof |
| BattleState | PASS | `battle_sandbox/state.py` (schema v4) | Deliberately does not model full combat state |
| Clone / hash / snapshot | PASS | `battle_sandbox/{state,hash,snapshot}.py` | Logical state only |
| Planner API | BLOCKED | `Sandbox.legal_actions/step/is_terminal` | Explicitly raises NOT_IMPLEMENTED |
| Real-content E2E | PARTIAL | Natasha test/report 30 | Turn → formula → ordered event boundary, no HP mutation |
| Dynamic Core Closure v1 | PARTIAL | `dynamic_core/packets_v1.json` | Damage amount→HP is reconstruction-ready; Heal consumer, resources, recharge, death/terminal and target legality remain MVP blockers |

## 7. Real Content and E2E State

The strongest current E2E is
`tests/battle_sandbox/test_real_skill_turn_e2e_30.py` and
`data/sandbox/core_real_skill_runtime_30_report.json`:

1. ordinary Turn/AV selects Natasha;
2. the committed Natasha `Skill02_Phase02` artifact is validated;
3. externally provenance-bearing bindings resolve its still-unknown predicate,
   target, and DynamicFloat operands;
4. FormulaType 4 returns the amount and emits ordered DispelStatus then Heal
   request boundaries; and
5. CurrentHP remains unchanged because the positive HealData consumer is not
   recovered.

This is real-content boundary execution, **not** a complete playable skill or
a full battle.

## 8. Known External Blockers and UNKNOWN Semantics

- The approved read-only runtime readers cannot locate the required live
  `PGOOHIHKHNJ` executor instance / dispatch target.  No injection, write,
  hook, or protection bypass is allowed.
- General DamageRequest resolution and formula are therefore unknown.
- Positive heal event consumption, event listener ordering, and action
  completion/recharge discovery are unknown.
- Full DesignData ability-action container decoding and corpus-level
  Avatar/Monster/Stage record parsing are absent.
- No monster entity-to-ability/property/weakness relationship and no
  Stage→wave→monster or Stage→Buff relationship is structurally decoded.
- External content does not resolve dynamic event ordering or permit a
  simulator to execute an imported effect without a local Semantic Packet.
- Dynamic Core Closure v1 does **not** close the positive HealData consumer,
  SP/Energy write phases, generic action-delay recharge, TargetConfig 12,
  death, or terminal transitions.  Its packet bundle is deliberately
  `DYNAMIC_CORE_RECONSTRUCTION_PARTIAL`; see the dynamic-core guide before
  scheduling a new reverse task.

## 9. Tests and Verification Commands

Use the verified Python resolver described in
`docs/agent/dsh_windows_environment.md`; do not use bare `python` or `py`.

```powershell
& "C:\Users\而忧\AppData\Local\Programs\Python\Python311\python.exe" -m unittest discover -s tests -p "test_*.py" -v
```

Audit result on 2026-08-24: **489 tests run; 486 passed; 3 failed**.  All
three failures are stale cardinality assertions in
`tests/battle_ir/test_semantic_batch_catalog.py`: the catalog now contains
13 artifacts / 92 primitives after `turn_av_semantics_29.json`, while that
test still expects 12 / 91 (and 80 rather than 81 when Batch 02 is disabled).
This is a test-maintenance issue, not evidence that the additional runtime
artifact failed to load.  Do not silently call the test suite fully green
until those expectations are updated and tests rerun.

Focused evidence also lives in `data/sandbox/*.json`, especially the real
skill report, HP transition report, and the artifact-validation tests under
`tests/reverse/`.

For the static database, run the offline fixture tests under
`tests/game_data/`; network is never required by those tests.  Fetch/build
instructions are in `docs/agent/content_database.md`.

## 10. Important Commits

- `ca98440` — versioned reverse pipeline v1 baseline.
- `a2ea2d1` / `c66451f` — DynamicValue proof/runtime.
- `11a6019` / `e1b2668` — FixPoint comparison proof/runtime.
- `8d4319e` through `04dc482` — predicate, target, action, modifier, and
  lifecycle proof/runtime chain.
- `3d57c76` / `4c62261` — generic property mutation runtime.
- `12d1584` / `bd65c5f` — DirectDamageHP transition runtime.
- `ab4e15c` — direct HP content census (historical/local selector scope).
- `2c44428` / `dc35457` — scoped Turn/AV semantics/runtime.
- `4d27854` / `f819cc3` — real Natasha HealHP extraction to event boundary.
- `dd1a62c` — bounded core E2E status.
- `7c5793c` — normalized reverse disassembly output baseline.
- `31d4ed6` — authoritative repository/content audit index.
- `994bc14` — version-locked Nanoka raw snapshot, Canonical/SQLite database,
  query/export tools, tests, documentation, and 4.4.54→4.4.55 delta report.
- `69c1cff` — pinned external reconstruction adapter, static Loadout
  materializer, amount-only reference evaluator, offline tests, and compact
  source/mapping/rule/gap artifacts.

## 11. Important Artifacts and Handoffs

- Session/environment rules: `docs/agent/dsh_windows_environment.md`.
- Current semantic entry point: `docs/agent/battle_reverse_current_state.md`.
- Unpack capability matrix: `docs/unpack/capability_matrix.md`.
- Content recovery: `data/raw/4.4.54/designdata_recovery_audit_23.json`.
- Full TaskConfig registry: `data/raw/4.4.54/taskconfig_registry_30.json`.
- Natasha content: `data/raw/4.4.54/natasha_skill02_healhp_content_30.json`.
- Current real E2E: `data/semantics/4.4.54/real_skill_heal_boundary_30.json`
  and `data/sandbox/core_real_skill_runtime_30_report.json`.
- Runtime semantic catalog: `data/semantics/4.4.54/catalog.json`.
- Static content database guide: `docs/agent/content_database.md`.
- External reconstruction entry point: `docs/agent/external_reconstruction.md`.
- External-source license/use audit: `docs/agent/external_reference_licenses.md`.
- External rule boundary: `docs/agent/reconstruction_rule_pack.md`.
- Dynamic-core closure / freeze decision:
  `docs/agent/dynamic_core_reconstruction.md`.
- Dynamic machine packets and partial E2E:
  `data/semantics/4.4.54/dynamic_core/`.
- Machine mapping/rule/gap artifacts:
  `data/semantics/4.4.54/external_reconstruction/`.
- Ticket impact after oracle adoption: `docs/agent/semantic_ticket_oracle_v2.md`.

Historical handoffs are evidence, not a substitute for this index.  Read a
handoff only when the linked artifact or source points to it.

## 12. Superseded / Do-Not-Reopen Findings

- **SUPERSEDED AS GLOBAL ID:** `HealHP selector = 7` in the older Direct HP
  census is a family-local factory/selector observation.  It is **not** the
  global TaskConfig discriminator.  The global ULEB TaskConfig registry has
  HealHP discriminator **1481**; see `taskconfig_registry_30.json` and the
  concrete Natasha record.  Keep old selector evidence as `LOCAL_ONLY`.
- **SUPERSEDED:** `natasha_skill02_action_graph_27.json` records the earlier
  missing Skill02→HealHP link.  `natasha_skill02_healhp_content_30.json`
  later proves the bounded subtree and FormulaType 4 config.
- **DO NOT USE AS CURRENT STATUS:** the repository `README.md` claims zero
  business code/raw data/stable interfaces, and `PROJECT_STRUCTURE.md` lists
  the initial skeleton.  Both are historical bootstrap documents; this index
  and `battle_reverse_current_state.md` are current.
- **STALE TEST EXPECTATION:** catalog-size assertions in
  `test_semantic_batch_catalog.py` predate Turn/AV catalog registration; see
  §9.  The code is not changed by this audit.
- The PGOO live-instance blocker remains active.  Do not re-open forbidden
  injection/remote-thread/manual-map routes.

## 13. Current Recommended Development Strategy

Start the next implementation session with the strategy stated in §1:

`full content census → generic content compiler → corpus semantic coverage → coverage-driven primitive recovery → standard battle E2E → planner / training APIs`

The immediate research gap is a small set of Dynamic Core packets, not another
character inventory: positive HealData consumption, SP/Energy boundaries,
ordinary action-delay recharge, target legality, and death/terminal.  Each
must start with the distinguishing observation in
`dynamic_core/packets_v1.json`; do not reopen PGOO or run blind sweeps.  A
generic Scenario/Loadout compiler remains the first DSH implementation step
after the freeze gate, not before it.
