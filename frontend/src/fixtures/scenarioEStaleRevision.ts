/**
 * FIXTURE E — stale-revision rejection.
 *
 * Demonstrates: a certificate and plan sealed against revision r7 while the live
 * state has advanced to r9. The commit is refused. The UI must make it obvious
 * that LIVE STATE WAS UNCHANGED and that no automatic retry is performed.
 *
 * MOCK DATA.
 */
import type {
  ActionPreview,
  AvailableAction,
  DependencyObligation,
  ExecutionResult,
  GateCertificate,
  PreflightResult,
  ScenarioDescriptor,
  SessionInfo,
  StagedRngDraw,
  StagedWrite,
  StrictStepResult,
  StructuredRejection,
  TraceEvent,
  TransactionPlan,
  TransactionRngDocument,
} from '../models';
import { FIXTURE_SETUP } from './roster';
import { buildSnapshot, policyIdentity } from './buildSnapshot';
import type { MockScenarioBundle } from './types';
import { access, contractRef, fixtureHex, present, revision, timelineEntry } from './shared';

const SNAPSHOT_ID = 'mock-e-stale-revision';
const STALE_REVISION = revision(7, SNAPSHOT_ID);
const LIVE_REVISION = revision(9, SNAPSHOT_ID);

const ACTION_CONTRACT = contractRef(
  'basic_action_write',
  'terra.battle.action',
  '1.0.0',
  'NATIVE_EVIDENCED',
  ['fixture://action_descriptor/basic_action_write'],
);

const OBLIGATIONS: readonly DependencyObligation[] = [
  {
    schema: 'dependency_obligation/1',
    owner: 'ACTION_EXEC',
    contractRef: ACTION_CONTRACT,
    evidenceMode: 'NATIVE_EVIDENCED',
    resolution: 'RESOLVED',
    reads: [access('store:unit_hp_current:*', present({ extent: 'full' }))],
    writes: [access('store:unit_hp_current:enemy-eg1', present({ mode: 'replace' }))],
    children: [],
    unknownHandles: [],
  },
];

const PREFLIGHT: PreflightResult = {
  schema: 'preflight_result/1',
  outcome: 'CLOSED',
  closure: {
    schema: 'dependency_closure/1',
    status: 'CLOSED',
    obligations: OBLIGATIONS,
    blockers: [],
    allowedReads: [access('store:unit_hp_current:*', present({ extent: 'full' }))],
    allowedWrites: [access('store:unit_hp_current:enemy-eg1', present({ mode: 'replace' }))],
  },
  rejections: [],
};

const STALE_HASH = `terra-semantic-sha256:${fixtureHex(`${SNAPSHOT_ID}#7#NATIVE_EVIDENCED`)}`;
const LIVE_HASH = `terra-semantic-sha256:${fixtureHex(`${SNAPSHOT_ID}#9#NATIVE_EVIDENCED`)}`;

const CERTIFICATE: GateCertificate = {
  schema: 'terra_gate_certificate/1',
  planIdentity: `terra-plan-sha256:${fixtureHex(`${SNAPSHOT_ID}:stale-plan`)}`,
  evidenceMode: 'NATIVE_EVIDENCED',
  policyIdentity: policyIdentity('NATIVE_EVIDENCED'),
  inputIdentity: fixtureHex(`${SNAPSHOT_ID}:input:r7`),
  inputRevision: 'r7',
  stateRevision: STALE_REVISION,
  contractRef: ACTION_CONTRACT,
  contractRevision: '1.0.0',
  closureIdentity: fixtureHex(`${SNAPSHOT_ID}:closure:r7`),
  allowedReads: PREFLIGHT.closure.allowedReads,
  allowedWrites: PREFLIGHT.closure.allowedWrites,
  identity: fixtureHex(`${SNAPSHOT_ID}:certificate:r7`),
};

const PLAN: TransactionPlan = {
  schema: 'terra_transaction_plan/1',
  operations: [
    {
      schema: 'terra_transaction_operation/1',
      operationId: 'op-apply-hp-write',
      payload: { kind: 'STORE_APPEND', target: 'store:unit_hp_current:enemy-eg1' },
    },
  ],
  certificateIdentity: CERTIFICATE.identity,
  sourceRevision: STALE_REVISION,
  sourceStateHash: STALE_HASH,
  allowedReads: PREFLIGHT.closure.allowedReads,
  allowedWrites: PREFLIGHT.closure.allowedWrites,
};

/** Private RNG ledger bound to the stale plan; never consumed. */
const SCENARIO_E_RNG: TransactionRngDocument = {
  schema: 'terra_transaction_rng/1',
  planIdentity: CERTIFICATE.planIdentity,
  certificateIdentity: CERTIFICATE.identity,
  sourceRevision: STALE_REVISION,
  sourceStateHash: STALE_HASH,
  rng: {
    schema: 'sandbox_rng_state/1',
    algorithm: 'PYTHON_RANDOM_MT19937',
    state: { version: '1', internal_state: '(mock)', gauss_next: null },
  },
  ledger: [],
  consumed: false,
};

const REJECTION: StructuredRejection = {
  schema: 'structured_rejection/1',
  reasonCode: 'SOURCE_REVISION_STALE',
  obligationOwner: 'ACTION_EXEC',
  evidenceRequest: 'A plan and certificate sealed against the current live revision; automatic retry is forbidden',
  contractRefs: [ACTION_CONTRACT],
  unknownHandles: [],
  diagnostics: {
    planned_revision: { counter: STALE_REVISION.counter, snapshot_id: STALE_REVISION.snapshotId },
    live_revision: { counter: LIVE_REVISION.counter, snapshot_id: LIVE_REVISION.snapshotId },
    automatic_retry: false,
    note: 'Live state was not modified by the refused commit.',
  },
};

const SNAPSHOT = buildSnapshot({
  snapshotId: SNAPSHOT_ID,
  revisionCounter: 9,
  rngDrawPosition: 52,
  currentActorId: 'ally-vg',
  selectedTargetId: 'enemy-eg1',
  timeline: [
    timelineEntry(1, 'ORDINARY', 'VG-01 ordinary turn', 'ally-vg', 'NATIVE_EVIDENCED', { av: 0 }),
    timelineEntry(2, 'INSERTED', 'Inserted task (advanced the revision)', 'ally-bw', 'NATIVE_EVIDENCED', {
      av: 8,
      detail: 'Rendered as INSERTED — a distinct row kind, not merged with ORDINARY.',
    }),
    timelineEntry(3, 'ORDINARY', 'EG-01 ordinary turn', 'enemy-eg1', 'NATIVE_EVIDENCED', { av: 30 }),
  ],
});

const ACTIONS: readonly AvailableAction[] = [
  {
    id: 'act-stale-strike',
    label: 'Basic action (stale certificate)',
    actorId: 'ally-vg',
    actorName: 'Vanguard Unit',
    targetRule: { supplied: true, summary: 'Single declared target', allowedTargetIds: ['enemy-eg1'] },
    evidenceMode: 'NATIVE_EVIDENCED',
    support: 'BLOCKED',
    preflightState: 'STALE',
    descriptorOnly: false,
    notes: [
      'The certificate was sealed against r7; live state is at r9.',
      'The UI marks the certificate STALE instead of reusing it.',
    ],
  },
];

const STAGED_WRITES: readonly StagedWrite[] = [
  { kind: 'STORE_APPEND', target: 'store:unit_hp_current:enemy-eg1', payload: { placeholder: true } },
];

const RNG_DRAWS: readonly StagedRngDraw[] = [
  { sequence: 1, operationId: 'op-apply-hp-write', draw: { kind: 'uniform', value_supplied: false } },
];

const PREVIEWS: Readonly<Record<string, ActionPreview>> = {
  'act-stale-strike': {
    actionId: 'act-stale-strike',
    label: 'Basic action (stale certificate)',
    evidenceMode: 'NATIVE_EVIDENCED',
    support: 'BLOCKED',
    preflight: PREFLIGHT,
    certificate: {
      status: 'STALE',
      certificate: CERTIFICATE,
      refusalReason:
        'Certificate is sealed against r7 but the live revision is r9. The certificate cannot be reused.',
      sealedAgainstRevision: STALE_REVISION,
    },
    rejection: null,
    plan: PLAN,
    delta: {
      schema: 'terra_staged_delta/1',
      planIdentity: PLAN.certificateIdentity,
      certificateIdentity: CERTIFICATE.identity,
      sourceRevision: STALE_REVISION,
      sourceStateHash: STALE_HASH,
      allowedWrites: PREFLIGHT.closure.allowedWrites,
      writes: STAGED_WRITES,
      storeNames: ['unit_hp_current'],
    },
    trace: null,
    rngDraws: RNG_DRAWS,
    diff: null,
    execution: null,
    strictStep: null,
    transactionRng: SCENARIO_E_RNG,
    notes: [
      'Staged material exists but is bound to a stale revision.',
      'Committing it would be refused; nothing here retries automatically.',
    ],
  },
};

/**
 * The strict step result the executor would return for a stale source revision:
 * REJECTED with `STRICT_TRANSACTION_REJECTED`, and NO resulting revision.
 */
const STRICT_STEP: StrictStepResult = {
  schema: 'terra_strict_step_result/1',
  outcome: 'REJECTED',
  resultingRevision: null,
  transactionIdentity: null,
  rejections: [
    {
      schema: 'structured_rejection/1',
      reasonCode: 'STRICT_TRANSACTION_REJECTED',
      obligationOwner: 'STRICT_STEP',
      evidenceRequest: 'unchanged certified source state',
      contractRefs: [ACTION_CONTRACT],
      unknownHandles: [],
      diagnostics: {
        detail: 'source revision is stale; automatic retry is forbidden',
        planned_revision: { counter: STALE_REVISION.counter, snapshot_id: STALE_REVISION.snapshotId },
        live_revision: { counter: LIVE_REVISION.counter, snapshot_id: LIVE_REVISION.snapshotId },
      },
    },
  ],
};

const EXECUTIONS: Readonly<Record<string, ExecutionResult>> = {
  'act-stale-strike': {
    outcome: 'REJECTED',
    actionId: 'act-stale-strike',
    plan: PLAN,
    delta: PREVIEWS['act-stale-strike']?.delta ?? null,
    trace: null,
    rngDraws: RNG_DRAWS,
    commit: null,
    rejection: REJECTION,
    strictStep: STRICT_STEP,
    transactionRng: SCENARIO_E_RNG,
    liveStateUnchanged: true,
    // BOTH identity documents are supplied and they MATCH (r9 == r9), so the
    // "LIVE STATE UNCHANGED" claim is verified rather than inferred from the
    // word REJECTED.
    revisionWindow: {
      before: LIVE_REVISION,
      after: LIVE_REVISION,
      beforeHash: LIVE_HASH,
      afterHash: LIVE_HASH,
    },
    message:
      'Commit refused: source revision r7 is stale against live revision r9. Live state was NOT changed; automatic retry is forbidden.',
  },
};

const EVENTS: readonly TraceEvent[] = [
  {
    id: 'ev-e-1',
    sequence: 1,
    timestamp: null,
    category: 'STATE',
    summary: `Snapshot ${SNAPSHOT_ID} loaded at revision r9.`,
    evidenceMode: 'NATIVE_EVIDENCED',
    raw: { snapshot_id: SNAPSHOT_ID, revision: 9, provenance: 'MOCK_DATA' },
  },
  {
    id: 'ev-e-2',
    sequence: 2,
    timestamp: null,
    category: 'PREFLIGHT',
    summary: 'Closure CLOSED against the planned revision r7.',
    evidenceMode: 'NATIVE_EVIDENCED',
    raw: { outcome: 'CLOSED', source_revision: 7 },
  },
  {
    id: 'ev-e-3',
    sequence: 3,
    timestamp: null,
    category: 'COMMIT',
    summary: 'Commit refused: SOURCE_REVISION_STALE (planned r7 vs live r9).',
    evidenceMode: 'NATIVE_EVIDENCED',
    raw: { reason_code: REJECTION.reasonCode, planned: 7, live: 9, live_state_changed: false },
  },
];

const SESSION: SessionInfo = {
  adapterId: 'mock-battle-backend',
  adapterLabel: 'MockBattleBackendAdapter',
  adapterKind: 'MOCK',
  contentVersion: '4.4.54',
  backendMode: 'NATIVE_EVIDENCED',
  connection: 'CONNECTED',
  connectionDetail: 'In-process mock adapter. No live backend is attached.',
  dataProvenance: 'MOCK_DATA',
  scenarioId: 'E',
  scenarioLabel: 'E · stale-revision rejection',
  scenarioSummary:
    'Plan and certificate sealed at r7 while live state is at r9; the commit is refused and live state is untouched.',
  stateRevisionCounter: 9,
  semanticHash: SNAPSHOT.semanticHash,
  rngDrawPosition: 52,
  transactionState: 'REJECTED',
  notes: [
    'DEMO / MOCK DATA — served by MockBattleBackendAdapter.',
    'A stale certificate is shown as STALE and is never silently refreshed.',
  ],
};

const DESCRIPTOR: ScenarioDescriptor = {
  id: 'E',
  label: 'E · stale-revision rejection',
  summary: 'Stale certificate: commit refused, live state unchanged.',
  backendMode: 'NATIVE_EVIDENCED',
  category: 'STALE_REVISION',
};

export const SCENARIO_E: MockScenarioBundle = {
  descriptor: DESCRIPTOR,
  session: SESSION,
  setup: FIXTURE_SETUP,
  snapshot: SNAPSHOT,
  actions: ACTIONS,
  previews: PREVIEWS,
  executions: EXECUTIONS,
  events: EVENTS,
};
