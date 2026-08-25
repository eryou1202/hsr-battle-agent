# Full Simulation Reconstruction Plan — HSR 4.4.54

## Decision and scope

The target is no longer merely the frozen **standard battle MVP**.  The
target handoff lets DSH construct a deterministic, cloneable, high-fidelity
simulation of the declared HSR 4.4.54 combat corpus: characters and their
equipment, enemies, real encounter topology, stage effects, global combat
rules, and the supported game modes.  It is not a claim to reproduce Unity,
animations, UI, network services, or every opaque internal implementation
detail.

The deliverable is a **reconstruction package**, not a collection of scraped
JSON: versioned canonical content, a behavior/effect IR, semantic packets,
compiler mappings, and deterministic golden state traces.  The implementation
must not query Nanoka, GitHub, a DesignData archive, or an external source at
runtime.

The previous `dynamic_mvp_v1` closure remains a valuable P0 base.  It covers
ordinary Basic/Skill/Ultimate resource gates, normal AV, ordinary target
legality, death, and standard terminal behavior.  It does **not** constitute a
whole-game handoff; it cannot on its own compile arbitrary skills, equipment,
monsters, buffs, modes, follow-ups, summons, or break interactions.

The machine-readable authority for this plan is
`data/semantics/4.4.54/full_reconstruction/program_v1.json`.  Its companion
coverage ledger is the required resume point for future API sessions.

## Evidence strategy

Use source classes for their proper job rather than trying to make any one
source prove everything.

| Source | Role | Allowed use | Not allowed to prove |
| --- | --- | --- | --- |
| Local Nanoka 4.4.54 DB | Exact-version static oracle | IDs, content relationships, stats, stage topology and retained raw fields | Client execution order by itself |
| TurnBasedGameData (pinned 4.4.0) | Close client-dump reference | Discover config schema, behavior-bearing fields, IDs, task/formula/condition candidates | A conflicting 4.4.54 value or native scheduling order |
| StarRailRes (pinned 4.4) | Independent close data/schema reference | Cross-check records and readable effect hints | Runtime implementation order |
| HSR-Mapping-DATA (pinned 4.0) | Mapping hypothesis source | Translate source fields into canonical model candidates | Version-specific facts or semantics |
| hsr-optimizer (pinned 4.4v5) | Mature algorithm reference | Formula, rounding and test-vector hypotheses | Event order or arbitrary skill behavior |
| Existing local artifacts | Bounded local evidence | Strengthen a packet where already present | A reason to restart local reverse in this program |

The program deliberately defers new local unpack/native work.  A reconstructed
rule can be accepted when its source inputs, selected deterministic model,
state writes, ordering, unsupported cases, and golden scenario are explicit.
Where a later local validation is valuable, it is recorded as optional rather
than silently claimed already proved.

## Architecture to hand to DSH

```text
Pinned external snapshots + Nanoka 4.4.54 raw/canonical DB
                    ↓ adapters with provenance/conflict preservation
         Canonical static entities + Canonical behavior records
                    ↓ generic Content / Effect compiler
  Battle IR (effects, conditions, targets, formulas, subscriptions, phases)
                    ↓
Deterministic Battle Kernel (state, event queue, legality, scheduler, RNG)
                    ↓
Scenario compiler (loadout + stage + waves + buffs + mode policy)
                    ↓
Sandbox step / legal-actions / clone / hash / replay / terminal
                    ↓
Golden scenario corpus → planner and training APIs
```

The separation is mandatory: a character or Stage ID is static content;
what it *does* is a behavior record; how it executes is the generic kernel.
No source-specific runtime branches and no direct external JSON reads are
permitted below the adapter layer.

## Workstreams and their boundaries

### 0. Reproducible corpus control

**Start:** the existing Nanoka database and pinned reference manifest.

**Finish:** every raw source, canonical entity, semantic packet and golden
trace has version, ID, hash, source relation, and rebuild command.  A close
source is never silently normalized into exact 4.4.54 content.

### 1. Bounded external behavior-corpus capture

**Start:** inspect the pinned Git trees for the candidate schema families in
`external_source_expansion_profile_v1.json`.

**Finish:** retrieve only an explicit reviewed list of behavior-bearing files
(Avatar skills/traces/ranks, equipment effects, monster skills/AI/phase,
stage Buff/rules, global task/target/condition/formula schemas).  Store raw
payloads with commit path and hash.  Candidate file names are not evidence
until discovery confirms them.

This is deliberately aggressive about useful data, but bounded: it is not a
mirror of four repositories and it never ranges arbitrary IDs.

### 2. Canonical behavior/effect IR

**Start:** one captured effect-bearing family plus the Dynamic MVP packets.

**Finish:** an ID-preserving format can express an ability phase, trigger,
condition, target intent, formula, modifier, event subscription, action or
timeline operation, references, and unparsed/opaque fields.  It must express
unknowns without discarding them, and it must be source-schema independent.

The critical artifact is a compiler contract.  “We have a skill description”
does not count as modeled; a record counts only when it becomes an effect
graph or is explicitly unsupported.

### 3. Global battle kernel

**Start:** retain the ordinary Dynamic MVP packets as existing behavior.

**Finish:** generic contracts and interaction tests cover:

- state ownership, clone/hash/snapshot, deterministic RNG and transactions;
- nested event/effect ordering, listener priority, cancellation and commit
  boundaries;
- action legality and scheduling: normal, interrupts, extra action,
  follow-up and summons;
- SP, energy and special resources; gates, costs, gains and clamps;
- damage, healing, shield, stat changes, DoT, toughness, break and
  super-break;
- modifier stacking, duration, expiry, dispel and triggers;
- target classes including alive/dead, factions, AOE, random, taunt, parts and
  special objects;
- death, revive, prevent-death, wave progression and terminal outcomes;
- AV, speed mutation, advance/delay, recharge and all declared timeline
  objects.

An internal timing ambiguity is admissible only when the selected canonical
boundary is explicit and cannot change any published state, legal action,
next actor, listener outcome or terminal result.  Otherwise it remains open
in the coverage denominator.

### 4. Content compiler coverage

**Start:** stable IR and source-family registry.

**Finish:** separate compiler passes consume Canonical Avatar, LightCone,
RelicSet/affix, Monster, Stage Buff and Stage/Mode records.  Each pass reports
an actual effect-bearing denominator:

`captured → canonicalized → modeled → compiled → golden-tested → unsupported`

Static entity counts (e.g. 97 avatars or 628 monsters) are never used as a
surrogate for behavior coverage.  Keep every game/source ID and every phase;
do not merge variants for convenience.

### 5. Free scenario, encounter, enemy and mode reconstruction

**Start:** stage package topology plus generic death/scheduling behavior.

**Finish:** a free Scenario Package can select player loadouts, enemy
instances, ordered waves and Buff bindings without any Stage ID. A real Stage
Package may optionally seed that request, but **exhaustive one-to-one
reconstruction of all Stage records is not a completion gate**. Normal wave
spawn/clear behavior, AI policy model, boss phase/body-part model, Stage Buff
activation, and explicit rules for every declared mode remain separate rule
families; they cannot be collapsed into a generic “win when enemies die”
rule.

### 6. Differential verification and planner gate

**Start:** one cross-family vertical scenario compiles.

**Finish:** a deterministic trace suite verifies behavior interactions,
scenario initialization, legal action enumeration, replay, clone/hash and
terminal results.  Only then is `Sandbox.step`, `legal_actions`, planner,
Beam Search, MCTS or training a valid DSH implementation target.

## Immediate execution sequence

1. `EXT-DISC-001` — inspect only the four pinned source trees and write the
   reviewed exact retrieval manifest for behavior-bearing families.
2. `EXT-PROFILE-001` — capture that bounded raw corpus with provenance/hash;
   leave existing snapshots untouched.
3. `IR-CORE-001` — define and test the canonical behavior/effect IR against
   current MVP packets and one external record.
4. `KERNEL-EVENT-001` — make event/effect/commit ordering a first-class,
   deterministic DSH contract.
5. `SCENARIO-FREE-001` — establish free player/enemy/wave/Buff assembly;
   Stage Packages become optional templates.
6. `COMPILER-VERTICAL-001` — compile that freely assembled scenario with two
   avatars, an equipment effect, a monster ability and a Buff into one
   replayable trace.
7. `COVERAGE-BASELINE-001` — calculate denominators and generate the first
   real semantic coverage report.

The next session must not jump from static imports directly to a production
runtime.  The vertical slice is the test that the source adapter, IR, kernel,
compiler and scenario layer actually meet.

## DSH handoff gates

There are three useful handoff levels:

| Gate | What DSH may build | What must be present |
| --- | --- | --- |
| P0 — standard MVP | A bounded standard battle simulator | Existing `dynamic_mvp_v1`, Nanoka static DB, amount rules and standard trace fixtures |
| P1 — compiler vertical slice | The real compiler/kernel architecture | IR, event contract, source profile, one multi-family compiled/golden scenario |
| P2 — full published corpus | The requested comprehensive simulator | Every declared behavior denominator is compiled/tested or explicitly outside the published scope; all modes and special mechanisms have packets |

**Current repository position: P0 only.**  It is ready to help DSH implement
a standard-MVP baseline, but it is **not** ready for DSH to “complete HSR” in
one pass.  P1 gives DSH the right architecture; P2 is the full-recreation
handoff requested here.

## Resumability and token discipline

This file and the two JSON files in
`data/semantics/4.4.54/full_reconstruction/` are the recovery checkpoint.
Each coherent future ticket must update the coverage ledger with source refs,
accepted/rejected models, exact next question, output files and no-network
test/rebuild command before moving on.  If an API budget cannot close one
ticket, it must persist that partial state and stop at the ticket boundary;
no reasoning may exist only in chat history.

Do not restart broad local unpack or native reverse under this program.  New
local validation can be scheduled later against a precise discrepancy, but
the active route is external-corpus-driven reconstruction with transparent
assumptions and deterministic tests.
