# Full Reconstruction Handoff — 2026-08-25

## Current state

- Root: `D:\HSR_Battle_Agent\hsr-battle-agent`.
- Preserve all existing dirty reverse files; this program did not edit them.
- Highest goal: `FULL_4_4_54_SANDBOX_RECONSTRUCTION_FREEZE`.
- DSH production build remains frozen.

## Completed

- `RECON-STATE-REPAIR-001` repaired SSOT status, Effect IR vocabulary,
  detailed free-loadout input, opaque-disabled restrictions and dependency
  order.
- External discovery inspected all four pinned repositories. The
  TurnBasedGameData tree is truncated: positive paths are usable; absences are
  not proof.
- Ten reviewed TurnBasedGameData behavior files are cached and hash-recorded
  in `.external_refs/TurnBasedGameData/manifest.json`.
- `external_behavior.py` normalizes the reviewed files without runtime network
  access. Its generated corpus has 541 Behavior Records, 252 entrypoints
  (including 148 Modifier callbacks), and 829 recursively lifted semantic
  nodes (784 operations and 45 Predicate AST nodes); corpus hash:
  `c1fa2d9151de778dbe2494fa61b6f713f0b8df4084684618053e0c1a8399fc29`.
- `coverage_baseline_001.json`: MODELLED 27, REQUIRES_PACKET 490,
  PRESENTATION 148, OPAQUE 164; compiled/golden-tested behavior counts remain
  zero. The old 279/122 figures were root-entrypoint-only and must not be used
  as a semantic denominator.

## Source state

Behavior source: TurnBasedGameData commit
`b11066beacc4de454b625fafc7ea3dd540c5bbf3`, relation
`CLOSE_4.4.0_TO_4.4.54`. Nanoka 4.4.54 remains the exact static oracle.
External raw files are build-time-only and must not be read by runtime.

## Exact resume point

`NEXT TICKET = KERNEL-EVENT-001`.

Input: `effect_ir_contract_v1.json`, `external_behavior_corpus_v1.json`, and
`dynamic_mvp_v1`. Use the 829 recursively normalized nodes (not the retired
entrypoint-only denominator), particularly the 490 `REQUIRES_PACKET` nodes,
to produce and test an R3 deterministic event/effect queue packet with
registration, listener ordering, nested invoke, commit visibility,
cancellation and ordered trace contracts. Record ambiguity; do not turn the
164 OPAQUE nodes into no-ops and do not start local reverse.

Acceptance: a selected no-opaque behavior subset schedules to an ordered trace
with explicit state writes/dependencies. Then implement `SCENARIO-FREE-001`
and continue to `COMPILER-VERTICAL-001`.

## Mandatory reads

`program_v1.json`, `external_source_expansion_profile_v1.json`,
`effect_ir_contract_v1.json`, `free_scenario_assembly_contract_v1.json`,
`external_behavior_corpus_v1.json`, `coverage_baseline_001.json`, and
`coverage_ledger_v1.json`.
