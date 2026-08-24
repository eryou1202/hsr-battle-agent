# Current Project Summary

This summary reflects a local repository audit at `main` / `7c5793c`, not an
older handoff snapshot.

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

Therefore the answer to “can one character already be exported with all
skills, traces, and six Eidolons?” is **no**.  A generic content compiler and
full record coverage are still missing.

## Monsters, stages, and stage buffs

Monster data is genuinely present, but only at mixed raw/path-index levels.
The main DesignData archive has 10,168 unique `Monster_*` token candidates,
and the path index lists 377 core monster ability paths (679 broad
monster/enemy paths).  Two Monster ComplexSkillAI paths are also indexed.
There is no parsed monster entity table, no reliable ID-to-name/attributes
table, no weakness/toughness table, and no proven entity-to-ability join.

Stages also genuinely leave evidence: 137 raw `Stage*` token candidates and
323 stage/mode-related ability paths.  But the stage encounter records,
waves, monster levels, victory/failure rules, and spawn groups are not
decoded.  A StageAbility file is not proof of a complete stage configuration.

Stage-buff-related config paths are present (`AdventureModifier_MazeChallenge`,
`AdventureModifier_MazeEnvi`, and level/global modifier files), so stage-buff
material is present and indexable as file paths.  No real Stage → Buff record
relationship has been recovered.  The “Aha” request has a low-cost
**FOUND_CANDIDATE** only: Elation/rogue buff and `StageAbility_Elation` paths
exist; they are not yet identified as a specific Aha mechanic.

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

## What remains partial or blocked

Ordinary damage is blocked by the unresolved runtime-dispatch observation
needed for the general DamageRequest path, and the general damage formula is
not recovered.  Event listeners/consumers, energy, skill points, shields,
toughness/break, death, summons, follow-ups, extra actions, Monster AI, and
Stage runtime are not implemented.

So a complete battle cannot run yet.  The current real skill does not complete
all of its effects, and there is no generic content compiler, encounter
loader, legal-action generator, terminal-condition model, or stage loader.

Beam Search, MCTS, and policy/value training should **not** begin yet.  First
build the corpus-oriented content compiler; then measure content/primitive
coverage, recover missing primitives in coverage order, close a standard
battle E2E, and finally expose legal actions, transitions, terminal rules,
and training/planner APIs.

## Verification note

The audit ran the local full unit suite: 489 tests ran, 486 passed, and 3
failed only because catalog-size assertions still expect the pre-Turn/AV count
(12 artifacts/91 primitives instead of 13/92).  This is recorded for the
next maintenance task; the audit did not change runtime behavior.

For the detailed source map, limits, and next development sequence, start at
`docs/agent/project_index.md`.
