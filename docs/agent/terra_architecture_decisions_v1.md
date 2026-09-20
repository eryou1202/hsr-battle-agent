# Terra architecture decisions v1

Status: **RATIFIED**

Ratified: 2026-09-20

Control revision: `terra_implementation_master/v1` plan version `1.0.7`

Change request: `CR-P0-F-LOCAL-20260920-001`

These decisions close P0-F. They are architecture constraints, not new HSR
semantic claims. The authority order remains Astra freeze > frozen Domain 1–9
contracts > exact Terra followups > local audit > historical packets/reports >
existing implementation.

## MIGRATION_STRATEGY_DECISION

**Chosen architecture:** `B_FREEZE_LEGACY_BEHIND_ADAPTER_AND_CREATE_NEW_TERRA_PATH`.
The legacy runtime remains quarantined behind explicit adapters. The new Terra
state and strict-executor path is separate; there is no live bidirectional
compatibility façade. A legacy primitive migrates one primitive at a time only
after its reads, writes, dependency obligations, and evidence mode are
certified. Until then, legacy fixtures remain explicitly reference-labelled.

**Rejected alternatives:**

- A live compatibility façade: it would leak absence collapse, generic IDs,
  and live mutation into the new state and prevent a clean atomicity proof.
- A big-bang rewrite: its blast radius is too large to validate incrementally.
- Reusing the reference executor as production: reuse cannot promote reference
  semantics into native evidence.

**Compatibility cost:** Two state/executor surfaces coexist temporarily.
Adapters must project and diff only certified subsets, and some serialization
coverage is duplicated during migration.

**Affected modules:** `battle_sandbox/state_v2.py`,
`battle_sandbox/legacy_state_adapter.py`, `battle_sandbox/strict_executor.py`,
`battle_sandbox/legacy_primitive_adapter.py`, and `battle_sandbox/sandbox.py`.

**Deprecation path:** Keep `state.py` and `PrimitiveExecutor` unchanged and
reference-labelled; introduce `TerraBattleState` and `StrictExecutor`; migrate
each qualified primitive; remove legacy native reachability; retire the
adapter only after all retained primitives migrate or are classified
reference-only.

**Rollback plan:** Remove the profile-gated strict router/export without
downgrading snapshots or changing legacy fixtures. Never translate v2 state
back to v1 while claiming semantic equality.

**Change control:** Any change requires a unique change-request ID, reason and
evidence, affected task IDs/files, semantic and migration impact, rollback,
Sol authorization, a new master revision, and a change-history entry. Astra is
involved only if new version/hash-qualified evidence reopens a frozen blocker.

## RNG_OWNERSHIP_DECISION

**Chosen architecture:**
`RNG_STATE_OWNED_BY_TERRA_BATTLE_STATE_TRANSACTION_GETS_PRIVATE_CLONE`.
RNG belongs to Terra `BattleState`. Preflight performs zero draws. Only after a
gate certificate exists may a transaction receive a private RNG state. Draws,
the updated state, and the draw ledger become visible together at atomic
commit; rejection or abort consumes zero live RNG. Clone, snapshot, canonical
serialization, and semantic hash include algorithm, state, stream, and draw
position.

`SANDBOX_RNG_ALGORITHM=PYTHON_RANDOM_MT19937` is a deterministic local
algorithm label. It remains distinct from, and makes no equivalence claim
about, the unknown client-native RNG.

**Rejected alternatives:**

- Executor-owned or process-global RNG: ownership would be absent from state
  identity and deterministic replay.
- Drawing during preflight: rejected actions would consume RNG.
- Publishing each draw immediately: later failure could expose a partial
  transaction.
- Treating MT19937 as the client algorithm: no qualifying native evidence
  supports that claim.

**Compatibility cost:** Legacy adapters need a private RNG clone and may
publish only a certified staged RNG delta. Snapshots and hashes become larger,
and old snapshots require explicit migration rather than silent defaults.

**Affected modules:** `battle_sandbox/state_v2.py`,
`battle_sandbox/snapshot_v2.py`, `battle_sandbox/hash_v2.py`,
`battle_sandbox/transaction_rng.py`, `battle_sandbox/atomic_commit.py`, and
`battle_sandbox/legacy_primitive_adapter.py`.

**Deprecation path:** Introduce state-owned RNG and transaction staging; route
strict primitives only through it; isolate legacy RNG access behind the
adapter; remove any legacy native reachability after qualified migration.

**Rollback plan:** Disable the strict router while preserving v2 snapshots and
their RNG identity. Never discard RNG state, reset draw position, or reinterpret
a sandbox stream as client-native during rollback.

**Change control:** The same formal change-control record required by the
migration ADR applies. A native-RNG equivalence claim additionally requires a
frozen evidence reopen with version/hash-qualified observations.

## REFERENCE_QUARANTINE_DECISION

**Chosen architecture:**
`TYPE_AND_REGISTRY_SEPARATION_PLUS_SINGLE_ADAPTER_BOUNDARY`. Native and
reference objects are different types. `NativeContractRegistry` and
`ReferenceRegistry` are unrelated registry types. Quarantined material crosses
only through `battle_sandbox.reference_boundary`, and every output preserves
its evidence class. Reference reuse never changes evidence class.

`StrictExecutor` must not directly import the quarantined target, modifier,
scenario, reference-execution, or cross-family reference modules. Static
import/reachability tests enforce this boundary. The boundary labels and
checks material; it does not introduce runtime battle behaviour.

**Reference registry invariant:** The current `ReferenceRegistry` is
homogeneous and accepts `REFERENCE_MODEL` profiles only. It may therefore
report `REFERENCE_MODEL` as its scalar evidence mode without mislabelling its
contents. `SANDBOX_EXTENSION` and `UNSUPPORTED` remain distinct evidence
classes; they are valid on profiles, envelopes, and results, but must use
separate explicitly typed registries if registry storage is introduced. They
must never be collapsed merely because all three modes are non-native.

**Canonical EvidenceMode migration rule:**
`battle_sandbox.evidence_boundary.EvidenceMode` is provisional P0 guard-rail
infrastructure. F01-001 must create the sole canonical class in
`battle_ir/evidence.py`. In the same F01-001 change, the sandbox module must
delete its local enum definition and import/re-export that exact class (or
otherwise consume the identical class object). All `is EvidenceMode.*`
comparisons in `battle_sandbox.evidence_boundary`,
`battle_sandbox.reference_boundary`, and their tests must then resolve to the
canonical class. Two equal-valued but identity-unequal enum classes are
forbidden. F01-001 is not implemented by this ADR.

**Rejected alternatives:**

- One registry for every non-native mode: a scalar registry label would
  collapse distinct evidence classes or mislabel heterogeneous contents.
- String-only labelling: equal strings cannot enforce type or enum identity.
- Multiple long-lived `EvidenceMode` enums: identity comparisons would fail
  even when serialized spellings match.
- Direct strict imports or multiple crossing points: quarantine reachability
  would become difficult to audit.
- Promoting a reference result after reuse: evidence class is provenance, not
  a quality score that execution can upgrade.

**Compatibility cost:** Reference material requires wrappers and a declared
crossing point. Registries cannot be shared. F01-001 must perform the enum
canonicalization as an atomic compatibility edit across the sandbox imports
and identity tests.

**Affected modules:** `battle_ir/evidence.py` (future F01-001),
`battle_sandbox/evidence_boundary.py`, `battle_sandbox/reference_boundary.py`,
`battle_sandbox/strict_executor.py` (future), and
`tests/battle_sandbox/test_reference_quarantine.py`.

**Deprecation path:** Keep the P0 sandbox enum only until F01-001 lands; then
replace it with an import/re-export of the canonical battle-IR type in the same
change. Preserve the four spellings and serialized values. Later consumers
must import the canonical type directly or through the identity-preserving
re-export.

**Rollback plan:** Before F01-001, roll back only the P0 guard-rail modules and
tests together. After F01-001, roll back the canonicalization and all consumers
as one unit; never leave two enum definitions active. Quarantined modules stay
reference-labelled throughout.

**Change control:** The same formal change-control record required by the
migration ADR applies. Any reference-to-native promotion or frozen evidence
mode change is outside local software authority and requires the applicable
evidence reopen.
