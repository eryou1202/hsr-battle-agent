# Terra implementation master handoff — 2026-09-20

Status: **M0 ASTRA FREEZE COMPLETE**. The next milestone is **M0.5 REPOSITORY STABILIZED**. No production implementation or test edit was performed in this planning session.

The machine-readable source of truth is [`terra_implementation_master_v1.json`](../../data/semantics/4.4.54/full_reconstruction/terra_implementation_master_v1.json). If this handoff and the master disagree, the master wins; if the master and the Astra freeze disagree, the freeze wins.

## Where are we now?

Repository HEAD is `ce62dc0028d15cbdc7a332c3db860ed7fffb9c58`. At plan creation, `src/` and `tests/` were pristine. The semantic freeze, reverse master, nine frozen domain contracts, exact followups, and audit are mostly untracked. Two unrelated tracked files were already modified and must remain untouched and unstaged:

- `data/raw/4.4.54/damage_request_dispatch_resolution_18.json`
- `docs/agent/handoffs/damage_request_dispatch_resolution_18.md`

The current kernel has an ungated, non-transactional primitive executor over six JSON stores. `legal_actions()`, `step()`, and `is_terminal()` are stubs. Clone/snapshot/hash are partial. There is no typed identity system, opaque unresolved store, state revision, deterministic allocator, dependency closure, or atomic transaction.

## Why can't we just implement step() yet?

A safe `step()` requires all four foundation tickets in their frozen dependency order:

```
F01 ──┬──> F02 ──┐
      └──> R01 ──┴──> G01 ──> strict step
```

F01 supplies lossless presence, numbers, evidence and rejection types. F02 supplies the owned state aggregate, typed identities, revision, allocator, snapshot/hash and state-owned RNG. R01 supplies lossless cross-domain descriptors and resolution states. G01 can then close the entire reachable dependency graph, stage state/RNG/queues privately, and publish atomically. Calling today's `PrimitiveExecutor` from `step()` would pass live mutable state into primitives and permit partial writes before a later blocker is found.

## Architecture decisions

**Migration:** freeze the legacy runtime behind adapters and build a new Terra state/executor path. Do not put a live compatibility façade over the old stores. Migrate one primitive at a time only after its reads, writes, obligations and evidence mode are certified. Legacy fixtures remain available under explicit reference labels.

**RNG:** production RNG state belongs to the new BattleState. A transaction receives a private clone only after preflight. Draws and the draw ledger become visible only at atomic commit. Rejection leaves live RNG bit-identical. `SANDBOX_RNG_ALGORITHM=PYTHON_RANDOM_MT19937` remains a local deterministic algorithm, not a native client equivalence claim.

**Reference quarantine:** wrapper types, separate registries, a single adapter boundary, evidence-mode labels, and import/reachability tests prevent reference objects from satisfying native contracts. The strict executor may not directly import target/modifier/scenario/reference-execution modules.

## Live production conflicts

- **FC-02:** `battle_runtime/modifiers.py` groups Refresh with Replace and writes count. Native-evidenced execution must deny this primitive. Old behavior may exist only under an explicit `REFERENCE_MODEL` adapter. A future corrected implementation follows the frozen Modifier contract and still rejects unsupported Refresh subcases.
- **FC-19:** `BattleState.from_dict` loses absent versus empty, and the current hash helper silently converts tuples. F01 establishes the new lossless boundary; F02 replaces the new-path serializer/hash. The legacy path remains quarantined.
- **G01 mutation conflict:** `PrimitiveExecutor` hands live context to implementations, and `turns.advance_to_next_actor` mutates state incrementally. Neither may enter strict execution without isolated staging.
- Reference-only quarantines remain in force for target adjacency and entity-ID ties, reference modifier lifecycle, scenario wave sorting/flattening, static `golden_eligible`, and the `EXACT_CONFIG_ID` / `EXECUTABLE_REFERENCE` labels.

All FC-01..FC-19 dispositions are recorded in the master.

## P0 — repository stabilization

1. **P0-A1 READY:** build a hash-verified, explicit authority commit manifest. It does not stage or commit.
2. **P0-A2:** stage only manifest paths with explicit pathspecs and create the preservation commit after review. Never use `git add .`, `-A`, directory staging, or globs.
3. **P0-B:** repair root unittest discovery.
4. **P0-C:** replace stale catalog numeric constants with counts derived from the catalog under test; do not silently change semantic expectations.
5. **P0-D:** freeze the fast test matrix and the environmental/optional-dependency policy.
6. **P0-E:** add reference quarantine guard rails.
7. **P0-F:** ratify the three ADRs and validate the DAG.

M0.5 closes only when authority is durable, the fast regression baseline is trustworthy, guard rails pass, and architecture decisions are frozen.

## What runs where?

The plan has 75 tasks: 8 `CHEAP_MODEL_OK`, 21 `CHEAP_MODEL_STRICT`, 36 `SOL_IMPLEMENT`, and 10 conditional `ASTRA_EVIDENCE_ONLY` reopen tasks. Cheap models receive bounded files, explicit tests and no semantic inference. Sol owns state architecture, descriptor-family design, closure, transactions, RNG and primitive migration. Astra is used only if new version/hash-qualified evidence reopens a frozen blocker.

The next READY task is **P0-A1 — Build exact authority preservation manifest**, assigned to **CHEAP_MODEL_STRICT** with Sol review.

## Milestone timing

- The first strict executable primitives appear at **M2**, after M1's F01/F02/R01/G01 foundation.
- The first runnable battle is the explicitly scoped ordinary reference kernel at **M3**.
- A custom, single-wave, StageID-optional battle appears at **M4**.
- Planner search may start at **M5**, once supported-scope legal actions, atomic step, deterministic clone/hash/RNG, explicit unsupported results, scenario rule identity and meaningful multi-turn depth all exist.
- Data generation and Policy/Value work start at **M8**, with provenance-labelled trajectories and validation modes.
- Native Golden remains **0** until M7 receives an independent qualifying oracle.

Beam Search and MCTS do not wait for full native reconstruction, but their outputs must be labelled `REFERENCE_MODEL` or `SANDBOX_EXTENSION` until native validation exists. A real-time advisor also needs a separately authorized live-input contract.

## Test policy

The deterministic fast regression lane is the battle IR, sandbox and runtime unittest suites. P0 repairs root discovery and the three stale catalog tests first. Slow SQLite reconstruction, unpacker and cross-version suites are not required on every task. Windows tempfile teardown errors are recorded as environmental only with exact reproduction and re-entry criteria. Missing `numpy`/`jsonschema` is `BLOCKED_OPTIONAL`, never green. Golden stays zero.

## What must never be touched?

Cheap-model task work must not modify the Astra freeze, reverse master, nine frozen domain contracts, exact Terra followups, catalog or its hash-pinned artifacts, or either Astra handoff. Every task may modify only its explicit allowlist. Production/reference code must not be used to override the freeze. No task may infer Stage semantics, AI selection, TriggerAbility behavior, native lifecycle blockers, native RNG, or official terminal/wave rules.

## Operating rule

Every session follows [`terra_progress_protocol.md`](terra_progress_protocol.md): read master and exact task, inspect git status, verify dependencies and authority, edit only allowed files, run narrow tests, and persist an honest checkpoint. A task is never `DONE` until all listed acceptance tests pass. Cheap models may update task-local notes/results/checkpoints but may not rewrite the DAG or architecture.

