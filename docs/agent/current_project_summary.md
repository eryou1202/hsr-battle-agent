# Current Project Summary

This summary reflects the current local `main`, not an older handoff snapshot.

## Full reconstruction program — current phase

The highest target is `FULL_4_4_54_SANDBOX_RECONSTRUCTION_FREEZE`; DSH
production implementation remains frozen until that gate. The canonical
external behavior corpus v2 contains 553 records: 508 entrypoints (404
Modifier callbacks), 2 TaskListTemplate definitions, 287 DynamicValue
definitions, and 2295 recursive semantic nodes (1780 operations, 515
Predicate AST). 249 records are behavior-bearing and 304 are
static-definition-only references, which no longer deflate the behavior
denominator. Current lifted node statuses: 1826 `REQUIRES_PACKET`, 430
`PRESENTATION`, 32 `MODELLED`, 7 `OPAQUE`. The strict compiler structurally
compiles 201 of 249 behavior-bearing records; zero are executable or
golden-tested. Reference semantics now exist and are tested for: KERNEL-EVENT
ordering, Modifier lifecycle, DynamicValue store + all 1347 corpus PostfixExpr
programs, TargetAlias resolution, Scheduler markers/templates/loops/delay,
normal/Break/SuperBreak/DoT damage formulas, shield/lock-HP/death survival
transitions, Predicate AST evaluation with provider hooks, weighted RNG
selection, stable modifier property-contribution slots, one
cross-family interaction fixture (explicitly
`REFERENCE_INTERACTION_NOT_SOURCE_GOLDEN`), and one source-backed HOT
reference trace for the real canonical `MAvatar_Natasha_00_HOT_HPByMaxHP`
record (`SOURCE_BACKED_REFERENCE_NOT_GOLDEN`). Corpus hash:
`4fac2724182b31cb903fb96e56aa9b1c583b588fbf075615b93277b57c570ff5`.
Authoritative state lives in `coverage_ledger_v1.json`.

It now also has a separate static-content route: Nanoka 4.4.54 is captured as
an immutable local raw snapshot, normalized into Canonical JSON/JSONL, and
rebuilt into a local SQLite query database.  That makes static Character,
LightCone, RelicSet, Monster, and supported Stage data usable as future
reconstruction input without claiming the game client's runtime semantics.
Nanoka 4.4.55 is not allowed to fill 4.4.54 records.

The completed 4.4.54 database contains 97 characters, 664 skills, 5,018
trace records, 582 Eidolons, 169 LightCones, 60 RelicSets, 628 Monsters,
12,873 MonsterSkills, 1,543 Encounter contexts, and 1,459
Maze/Story/Boss Challenge Stage records.  It can export a static Stage Package
that keeps its real Stage ID, wave, enemy slots, levels, rule metadata,
encounter context, and Buff references. The 160 bindings remain exact-version
Nanoka facts; a separate external reconstruction layer has attached raw
close-version MazeBuff detail to 17 of the 18 referenced Buff IDs. The missing
ID `3110018` remains explicit **UNKNOWN** rather than approximated.

## What the external reconstruction layer adds

Four pinned public references now add a strictly separated static layer. It
contains 165 relic main/sub-affix records with level/roll data, 742 relic
templates with slot and affix-group constraints, 1,394 EliteGroup records,
741 HardLevelGroup records, 17 close-version Stage Buff raw configs, and two
raw candidates for the unresolved Monster `4034020` variant family.

It can materialize a static Loadout from real IDs: Avatar level/promotion,
compatible LightCone, selected trace stat additions, Eidolon rank metadata,
and template-validated six-slot relic input. It intentionally reports
LightCone, RelicSet, and Eidolon effects as unapplied contextual effects until
their dynamic semantics are proven. A narrow external formula helper evaluates
damage, Break, Super Break, heal, and shield **amounts only**; it has no event
ordering, targeting, or HP-writing authority.

All imported facts retain source pin, raw hash, and a separate external
evidence level. They do not overwrite Nanoka 4.4.54 records or prove local
client runtime behavior. See `docs/agent/external_reconstruction.md`.

## What has been successfully unpacked

The repeatable static 4.4.54 pipeline is working.  It has catalogued local
DesignData files and produced normalized registries for 80,880 types, 732,328
methods, 555,259 fields, and 655,072 parameters.  The main recovered
DesignData archive is present locally and its SHA-256 matches the recorded
`098EC31C…A03DC64B` value.

That success should not be overstated: it means the client metadata and many
configuration **paths** are available.  It does not yet mean the repository
has a full database of decoded character, monster, or stage configuration
records.

## What can be read for characters

The repository can enumerate 1,510 TurnBasedAbility configuration paths,
including 124 core Avatar ability paths.  For two selected prefixes it can
also parse the outer ability-file container and enumerate real named records.

Black Swan has the widest checked family: Skill01/02/03 phases, a passive,
two maze/technique records, two SkillTree records, and Rank01, Rank02, and
Rank06.  That is useful structured evidence, but it is not a complete
character export: no numeric Avatar ID or base stat template is connected,
SkillTree coverage is incomplete, and Rank03–Rank05 are not found in the
recovered family.

Natasha has fewer named records, but one real Skill02 Phase02 subtree is
decoded further: it contains a predicate, DispelStatus, HealHP (global
TaskConfig discriminator 1481), target reference, FormulaType 4, and two
serialized DynamicFloat formulas.  The formulas’ operands still require
external resolution.

The older local-only answer was “no”; the new version-locked content database
can export whatever the Nanoka 4.4.54 Avatar detail exposes, including skills,
traces, and six Eidolons when present.  It preserves provenance and unknown
fields rather than guessing.  A generic runtime Content/Scenario compiler is
still missing.

## Monsters, stages, and stage buffs

Monster data is genuinely present, but only at mixed raw/path-index levels.
The main DesignData archive has 10,168 unique `Monster_*` token candidates,
and the path index lists 377 core monster ability paths (679 broad
monster/enemy paths).  Two Monster ComplexSkillAI paths are also indexed.
The local archive itself still lacks that generic parser. Separately, the
Nanoka 4.4.54 content database imports version-locked Monster
identity/stat/variant and skill-list facts; the new external layer preserves
only two raw candidates for the remaining `4034020` variant gap. Neither layer
establishes Monster AI or ability execution order.

Stages also genuinely leave evidence: 137 raw `Stage*` token candidates and
323 stage/mode-related ability paths.  But the stage encounter records,
waves, monster levels, victory/failure rules, and spawn groups are not
decoded.  A StageAbility file is not proof of a complete stage configuration.

Stage-buff-related config paths are present (`AdventureModifier_MazeChallenge`,
`AdventureModifier_MazeEnvi`, and level/global modifier files), so stage-buff
material is present and indexable as file paths.  No local DesignData Stage →
Buff record relationship has been recovered. The external database preserves
Stage-referenced Buff bindings, supplies separate raw detail for 17 IDs, and
represents `3110018` as unresolved in its exported Stage Package; it does not
approximate or flatten waves. The “Aha”
request remains a low-cost **FOUND_CANDIDATE** only: Elation/rogue buff and
`StageAbility_Elation` paths exist, but are not proven as a specific Aha
mechanic.

## What the sandbox can execute

The sandbox has deterministic state cloning, snapshots, hashes, a seeded RNG,
and an artifact-driven primitive registry.  It can execute the proof-scoped
DynamicValue, FixPoint, comparison, predicate, target, action, modifier,
property, DirectDamageHP mode-0, and ordinary Turn/AV slices described in the
semantic artifacts.

The best real-content run selects Natasha through the ordinary Turn/AV
timeline, loads the validated real Skill02 data, calculates the supported
FormulaType 4 heal amount, and emits ordered DispelStatus and Heal request
boundaries.  It deliberately does not change CurrentHP: the positive heal
event consumer is unknown.

## Dynamic MVP closure result

Dynamic MVP Blocker Closure v1 freezes the smallest standard battle model for
implementation. A real 4.4.54 no-Buff Stage fixture is recorded (Stage
`30113121`, one configured active-wave Monster `4014030`), alongside Natasha,
Black Swan, an ordinary one-skill Monster probe, and a semantic E2E trace.
The result is **DYNAMIC_MVP_BLOCKERS_CLOSED** and
**FREEZE_MVP_CANDIDATE = YES**. This is a DSH implementation handoff, not a
claim that the existing proof-scoped runtime has already become a full battle
engine.

The strongest new composable path is ordinary Damage: a separately
provenanced external amount evaluator can feed the locally supported
`TargetDamageHP`/`DirectDamageHP` transition.  That is reconstruction-ready
for the stated scope and does not reopen PGOO.  It is still not a local damage
formula proof.

The real Natasha heal consumer is still not named, but its normal living-target
state transition is frozen at a settled action boundary: add positive HealData
to CurrentHP and clamp at MaxHP. The local resource component identifies the
holders and before/after `UseSkill` hooks for team skill points and actor
energy. Local scheduler/death/target structures identify the ordinary AV
reset, alive filtering, entity-death, wave, and result boundaries. Their
standard-MVP transitions are therefore explicit packets rather than silent
guesses.

DSH may now build a **strict standard**, legal, terminating simulator from the
frozen packets. It must keep special resources, insert Ultimates, follow-ups,
extra actions, Break, revive, advanced target rules, generic Monster AI,
special boss death, and score/mode rules outside the supported model.

## What remains partial or blocked

The native general DamageRequest path and formula remain blocked by the
unresolved runtime-dispatch observation.  That does not block the narrower
reconstruction boundary: an explicit external amount can feed the locally
supported TargetDamageHP/DirectDamageHP mode-0 path with both provenances
preserved. Event listeners/consumers, energy, skill points, shields,
toughness/break, death, summons, follow-ups, extra actions, Monster AI, and
Stage runtime are not implemented.

The existing proof runtime still cannot run a complete battle: DSH has not yet
implemented the generic content compiler, encounter loader, legal-action
generator, terminal model, or production BattleSession. The required semantic
contracts are now frozen, however.

Beam Search, MCTS, and policy/value training should still wait. First DSH must
build the Scenario/Loadout compiler and deterministic BattleSession, validate
the supplied standard E2E state diff, then expose `legal_actions`, transition,
terminal, cloning, and hash APIs. Only after that production implementation is
stable should planner/training work begin.

## Verification note

The audit ran the local full unit suite: 489 tests ran, 486 passed, and 3
failed only because catalog-size assertions still expect the pre-Turn/AV count
(12 artifacts/91 primitives instead of 13/92).  This is recorded for the
next maintenance task; the audit did not change runtime behavior.

For the detailed source map, limits, and next development sequence, start at
`docs/agent/project_index.md`.
