# Dynamic Core Reconstruction v1

## Decision

**Status: `DYNAMIC_CORE_RECONSTRUCTION_PARTIAL`.**  The static database remains
the version-locked 4.4.54 input.  This pass added no static-content expansion,
did not reopen PGOO, and did not turn a temporary harness into a Battle
Runtime.  It instead records the smallest honest dynamic contract that a
future implementation must obey.

Start here with the machine artifacts in
`data/semantics/4.4.54/dynamic_core/`:

- `packets_v1.json` — eleven mechanism packets, each with candidates,
  evidence, state reads/writes, a distinguishing observation, and an explicit
  DSH boundary.
- `standard_dynamic_fixture_v1.json` — real 4.4.54 static scenario and atomic
  probes.
- `semantic_e2e_v1.json` — an auditable state-diff replay, deliberately
  stopping at unrecovered transitions.
- `closure_v1.json` — machine-readable freeze decision and remaining gaps.

These files are **not** registered in the Battle IR semantic catalog.  They
are reconstruction contracts, some of which are hypotheses or blocked
boundaries rather than ready runtime primitives.

## Evidence and use law

Use the two confidence axes independently:

| Evidence | Meaning |
| --- | --- |
| R0 | hypothesis; useful only when named as such |
| R1 | client-dump-derived/static fact |
| R2 | mature implementation reference; amount-only where stated |
| R4 | local structural/machine-code support |
| R5 | local runtime verification |

`RECONSTRUCTION_READY` does not mean `R5`.  In particular, ordinary damage
is ready only as **external amount evaluation plus a separately local HP
bridge**.  It must keep both provenances in any trace.  Conversely, a static
cost/gain number cannot prove resource write timing.

The only permitted next local reverse is a narrow answer to one packet's
`distinguishing_observations`.  No open-ended PGOO, static sweep, metadata
census, or repeated evidence collection is authorized by this document.

## Current core matrix

| Core | Status | What is actually usable | Why not further claimed |
| --- | --- | --- | --- |
| SP | PARTIAL | exact 4.4.54 Basic `bp_add=1`, Skill `bp_need=1` facts | holder, max, clamp, and write phase unknown |
| Energy / Ult | PARTIAL | exact max Energy and 20/30/5 `sp_base` facts for Natasha/Black Swan | gain/cost interpretation, gate, cap, and write phase unknown |
| Heal | PARTIAL | real Natasha FormulaType 4 -> ordered Dispel/Heal request | positive HealData consumer and CurrentHP clamp/write unknown |
| Target / action legality | PARTIAL | local context selector leaves; static skill metadata | TargetConfig 12 join and ordinary faction/alive/count rules unknown |
| Ordinary action / Turn / AV | PARTIAL | local sort, select, property-38 advance, cleanup completion boundary | generic property-38 recharge writer/formula unknown |
| Damage | RECONSTRUCTION_READY | external deterministic amount -> local `TargetDamageHP` / `DirectDamageHP` mode-0 bridge | not a local general damage evaluator or death proof |
| Death | BLOCKED | zero-HP boundary exists | alive/dead record and cleanup domains unknown |
| Wave / terminal | BLOCKED | static Stage->Wave->Monster order | wave/victory/defeat writes unknown |
| Break | PARTIAL | external Break/Super Break amounts | toughness/broken state/lifecycle/order unknown |
| Minimal events | PARTIAL | named request/property/completion boundaries | generic listener registration/order unknown |
| Monster AI | PARTIAL | `8011010` has one static selectable skill | singleton is not a general policy or target selector |

## The bounded fixture

`STANDARD_DYNAMIC_FIXTURE_V1` is intentionally small:

- exact content version: `4.4.54`;
- real Stage `30113121`, Challenge, one wave, level 95, one Monster
  `4014030`, and **no** Stage→Buff binding;
- Avatar `1105` Natasha for the real heal boundary, plus `1307` Black Swan as
  a second version-locked player-content fixture;
- atomic ordinary-monster probe `8011010`, whose static candidate set contains
  only `801101001`.

The Stage's monster is not used to claim boss AI, phase, or a full combat E2E.
The simple `8011010` probe does not claim a generic AI rule.  They isolate
static scenario validity from the still-missing dynamic semantics.

The current semantic replay is valid only through these facts:

```text
Stage package resolves
  -> ordinary Turn/AV selects active actor (R4)
  -> real Natasha FormulaType 4 emits ordered request boundaries (R4)
  -> CurrentHP intentionally remains unchanged (positive consumer unknown)
  -> separately, external damage amount can use the local HP bridge
  -> completion can settle only with an explicit recharge value
  -> no death/wave/victory transition is asserted
```

This is a useful integration contract, but not a playable standard battle.

## Required narrow closure questions

The following are the **MVP-blocking** questions.  Each names the observation
that can change its packet; do not reverse more than that.

1. **Heal:** which consumer receives positive `HealData`, writes clamped
   CurrentHP, and in what order relative to listeners?
2. **SP/Energy:** where are shared SP and per-actor Energy stored, and at what
   named action phase do ordinary Skill and Ultimate gate/write them?
3. **Action recharge:** what generic post-action writer computes property 38
   for a next ordinary turn?
4. **Target legality:** how does TargetConfig discriminator 12 resolve, and
   which ordinary faction/alive/count checks are applied?
5. **Death/terminal:** after CurrentHP reaches zero, which writes remove the
   entity and transition one-wave victory/defeat?

The following are **post-MVP**, not blockers for selecting the next narrow
task: generic Monster AI, Break state lifecycle, Ultimate interruption,
follow-up, extra action, summon, boss phase, shield lifecycle, and mode
rules.

## Freeze decision

`FREEZE_MVP_CANDIDATE = NO`.

The eventual DSH handoff must be frozen only when the five MVP questions above
are promoted to reconstruction-ready packets.  At that point the handoff set
is:

```text
Nanoka 4.4.54 Content DB
+ External Reconstruction Rule Pack
+ Dynamic Core Packets with evidence levels
+ Standard fixture and expected trace
+ Explicit UNKNOWN / unsupported list
```

Until then, DSH can safely consume the static database and the ready Damage
bridge as isolated components, but cannot honestly implement a legal,
terminating standard battle simulator.

## Verification

The artifact-only validator has no network or SQLite dependency:

```powershell
$env:PYTHONUTF8 = "1"
& "C:\Users\而忧\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" scripts/validate_dynamic_core_semantic_e2e.py
& "C:\Users\而忧\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests/battle_ir -p "test_dynamic_core_packets.py" -v
```

Do not use a green packet-validator result as evidence that the dynamic gaps
are solved: it validates the integrity and honesty of the reconstruction
contract, including its `PARTIAL` result.
