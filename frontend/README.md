# HSR Battle Agent — Frontend Foundation

Desktop-first planning workspace for the HSR 4.4.54 deterministic
evidence-gated battle sandbox / planner.

## Scope

This frontend is **presentation and orchestration only**. It does not own battle
semantics and must never re-implement them client-side.

Explicitly NOT done here:

- no damage / toughness / survival formula;
- no speed or action-value calculation;
- no turn-order or scheduler computation;
- no target-legality inference;
- no modifier stacking model;
- no promotion of `REFERENCE_MODEL` results to executable;
- no invention of Stage progression or native RNG behaviour.

Every number on screen is a field supplied by an adapter document. When the
adapter does not supply a figure, the UI renders an explicit "not supplied"
state rather than a computed default.

## Stack

React 18 + TypeScript + Vite. No UI framework — hand-written CSS in
`src/styles/global.css`. Tests use Vitest.

## Layout

```
┌──────────────────────────────────────────────────────────────┐
│ top status bar                                               │
├──────────────┬──────────────────────────┬────────────────────┤
│ battle setup │ battle board             │ preflight /        │
│ + roster     │ + timeline               │ evidence inspector │
│              │ + action controls        │                    │
├──────────────┴──────────────────────────┴────────────────────┤
│ console: trace · strict pipeline · transaction · diff ·       │
│          quarantine · JSON import · raw                       │
└──────────────────────────────────────────────────────────────┘
```

## Strict execution pipeline

Console tab **Strict pipeline** renders the end-to-end G01 chain:

```
Request → DependencyObligation → DependencyClosure → PreflightResult
        → GateCertificate → TransactionPlan
        → StagedDelta / TransactionRng / StagedTrace
        → AtomicCommit → StrictStepResult
```

Each stage shows one of `NOT_AVAILABLE · READY · BLOCKED · REJECTED ·
UNSUPPORTED · COMMITTED`. A stage is `NOT_AVAILABLE` whenever its document was
not supplied — **the frontend never infers a stage from the one before it**
(`src/utils/strictStages.ts`).

Stages holding pre-commit material (`StagedDelta`, `TransactionRng`,
`StagedTrace`) carry a `PRE-COMMIT · NOT LIVE` tag; committed output carries a
`PUBLISHED` tag.

## Mirrored backend schemas

Schema strings match the backend exactly (`src/models/`):

| Document | Schema |
|---|---|
| DependencyObligation | `dependency_obligation/1` |
| DependencyClosure | `dependency_closure/1` |
| ClosureBlocker | `dependency_closure_blocker/1` |
| PreflightResult | `preflight_result/1` |
| StructuredRejection | `structured_rejection/1` |
| GateCertificate | `terra_gate_certificate/1` |
| TransactionPlan / Operation | `terra_transaction_plan/1`, `terra_transaction_operation/1` |
| StagedDelta | `terra_staged_delta/1` |
| TransactionRng | `terra_transaction_rng/1` |
| StagedTrace | `terra_staged_trace/1` |
| AtomicCommitResult | `terra_atomic_commit_result/1` |
| StrictStepResult | `terra_strict_step_result/1` |
| ContractSlot (FC-02) | `terra_modifier_contract_slot/1` |
| StateRevision / sequence | `state_revision/1`, `revision_and_transaction_sequence/1` |

### Certificate labelling

The certificate panel is labelled **LOCAL STRICT CERTIFICATE**. It is local
integrity infrastructure and is never labelled an official client or native game
certificate.

### Pre-commit vs published

`TransactionPlan`, `StagedDelta`, `TransactionRng` and `StagedTrace` are private
until an atomic commit consumes them. The transaction view groups them under a
`pre-commit material (staged · not live)` heading; published output appears
separately under the commit result.

### Atomic rejection view

For REJECTED / UNSUPPORTED steps the view shows reason, blockers, before/after
revision, RNG draw delta, allocator delta and queue/event deltas — each from a
supplied document, each rendered as `not supplied` when absent.

**LIVE STATE UNCHANGED** is displayed only when supplied before/after identity
documents actually match (`liveStateUnchangedVerified`). The word `REJECTED` is
not treated as evidence.

### FC-02 quarantine

Quarantine is modelled as **data**, one contract slot per operation and evidence
mode. Badges derive from `status` + `evidence_mode`:

- `BLOCKED_NATIVE` + `NATIVE_EVIDENCED` → BLOCKED / QUARANTINED
- `REFERENCE_ONLY` + `REFERENCE_MODEL` → REFERENCE ONLY
- `SEPARATELY_CERTIFIED` → separately certified

No modifier rule is hardcoded; a different operation with a different status
renders differently without a code change.

## JSON import (dev tool)

Console tab **JSON import** accepts pasted or file-loaded backend JSON when no
live HTTP backend exists. Validation is conservative
(`src/utils/jsonImport.ts`):

- unknown schema → **UNSUPPORTED SCHEMA**, never a guess;
- unknown fields are preserved and listed, never discarded;
- missing fields are reported, never defaulted.

## Adapter boundary

`src/adapters/BattleBackendAdapter.ts` defines the frontend-facing contract:

```
getSessionInfo()         getBattleSnapshot()      getBattleSetup()
getAvailableActions()    previewAction()          executeAction()
getTraceEvents()         getQuarantineEntries()   reset()
cloneInfo()
```

Two implementations:

| Adapter | Status | Purpose |
|---|---|---|
| `MockBattleBackendAdapter` | working | deterministic fixtures under `src/fixtures` |
| `LiveBattleBackendAdapter` | **NOT_CONNECTED** | skeleton; throws a typed `BackendNotConnectedError` |

The live adapter invents **no** HTTP contract, endpoint or payload envelope,
because the real backend API does not exist yet.

## Mock data policy

Mock data is labelled loudly and everywhere: a hatched `MOCK DATA` badge in the
status bar and on every panel that shows fixture content, plus a banner on the
setup column. The mode badge shows the fixture's evidence mode, but a
`MOCK_DATA` provenance chip always accompanies it — a native-looking mode must
never by itself imply live native execution.

## Fixtures

| Id | Scenario | Demonstrates |
|---|---|---|
| A | closed native no-op strict step | CLOSED closure + sealed local certificate + zero-operation plan + `StrictStepResult` COMMITTED (r12 → r13) |
| B | unknown preflight blocker | `BLOCKED_UNKNOWN` closure + structured rejection + UnknownHandle; no certificate |
| C | unsupported operation | settled negative; inspectable, execution denied |
| D | reference-only operation | closure CLOSES but certification is REFUSED; REFERENCE_ONLY |
| E | stale revision rejection | plan sealed at r7 vs live r9; `STRICT_TRANSACTION_REJECTED`; verified LIVE STATE UNCHANGED |
| F | successful atomic no-op commit | pre-commit material vs published output; before r3 / after r4 |
| G | FC-02 quarantine | corrected Refresh `BLOCKED_NATIVE`, legacy label `REFERENCE_MODEL` only, separate Replace slot blocked |

Fixtures contain no real Honkai: Star Rail combat semantics. Names, affinities
and roles are original generic placeholders; no official artwork is used.

## Deliberate UI states

backend disconnected · no scenario loaded · no legal actions · UNKNOWN
dependency · UNSUPPORTED operation · REFERENCE_ONLY result · stale certificate ·
transaction rejection · empty trace.

None of these collapse into a generic "something went wrong" message.

## Commands

```bash
npm install
npm run dev        # vite dev server
npm run build      # tsc -b && vite build
npm run typecheck  # tsc -b
npm test           # vitest run
npm run lint       # eslint
```

## Source map

```
src/
  app/          App shell + workspace state provider
  panels/       status bar, setup, board, timeline, actions, inspector, console, drawer
  components/   badges, meters, JSON viewer, unit/action cards, empty states
  models/       TypeScript mirrors of backend serialized shapes (read-only)
  adapters/     BattleBackendAdapter + mock + live skeleton
  fixtures/     deterministic demo scenarios A–G
  utils/        formatters, strict stage derivation, JSON import recognizer
  styles/       global CSS / design tokens
```
