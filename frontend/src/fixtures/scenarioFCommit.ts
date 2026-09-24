/**
 * FIXTURE F — successful atomic no-op commit.
 *
 * Mirrors the AtomicCommit boundary: a plan with ZERO operations, an empty
 * staged delta, an empty private RNG ledger, and one published commit whose
 * before/after identity documents are both supplied so the UI can verify the
 * revision advance (r3 → r4) rather than assume it.
 *
 * MOCK DATA. No gameplay semantics are encoded here.
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
  StagedRecord,
  StateDiff,
  TraceEvent,
  TransactionPlan,
  TransactionRngDocument,
} from '../models';
import { FIXTURE_SETUP } from './roster';
import { buildSnapshot, policyIdentity } from './buildSnapshot';
import type { MockScenarioBundle } from './types';
import { access, childRef, contractRef, fixtureHex, present, revision, timelineEntry } from './shared';

const SNAPSHOT_ID = 'mock-f-atomic-noop-commit';
const BEFORE = revision(3, SNAPSHOT_ID);
const AFTER = revision(4, SNAPSHOT_ID);
const BEFORE_HASH = `terra-semantic-sha256:${fixtureHex(`${SNAPSHOT_ID}#3#NATIVE_EVIDENCED`)}`;
const AFTER_HASH = `terra-semantic-sha256:${fixtureHex(`${SNAPSHOT_ID}#4#NATIVE_EVIDENCED`)}`;
const PLAN_IDENTITY = `terra-plan-sha256:${fixtureHex(`${SNAPSHOT_ID}:empty-operations`)}`;

const ACTION_CONTRACT = contractRef(
  'strict_no_op',
  'terra.battle.action',
  '1.0.0',
  'NATIVE_EVIDENCED',
  ['fixture://strict_executor/STRICT_NO_OP_ACTION'],
);

const HP_CONTRACT = contractRef(
  'unit_hp_read',
  'terra.battle.state',
  '1.0.0',
  'NATIVE_EVIDENCED',
  ['fixture://unit_hp_current'],
);

const OBLIGATIONS: readonly DependencyObligation[] = [
  {
    schema: 'dependency_obligation/1',
    owner: 'STATE_READ',
    contractRef: HP_CONTRACT,
    evidenceMode: 'NATIVE_EVIDENCED',
    resolution: 'RESOLVED',
    reads: [access('store:unit_hp_current:*', present({ extent: 'full' }))],
    writes: [],
    children: [],
    unknownHandles: [],
  },
  {
    schema: 'dependency_obligation/1',
    owner: 'ACTION_EXEC',
    contractRef: ACTION_CONTRACT,
    evidenceMode: 'NATIVE_EVIDENCED',
    resolution: 'RESOLVED',
    reads: [access('store:unit_hp_current:*', present({ extent: 'full' }))],
    writes: [],
    children: [childRef('STATE_READ', HP_CONTRACT)],
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
    allowedWrites: [],
  },
  rejections: [],
};

const CERTIFICATE: GateCertificate = {
  schema: 'terra_gate_certificate/1',
  planIdentity: PLAN_IDENTITY,
  evidenceMode: 'NATIVE_EVIDENCED',
  policyIdentity: policyIdentity('NATIVE_EVIDENCED'),
  inputIdentity: fixtureHex(`${SNAPSHOT_ID}:input:r3`),
  inputRevision: 'r3',
  stateRevision: BEFORE,
  contractRef: ACTION_CONTRACT,
  contractRevision: '1.0.0',
  closureIdentity: fixtureHex(`${SNAPSHOT_ID}:closure:r3`),
  allowedReads: PREFLIGHT.closure.allowedReads,
  allowedWrites: [],
  identity: fixtureHex(`${SNAPSHOT_ID}:certificate:r3`),
};

const PLAN: TransactionPlan = {
  schema: 'terra_transaction_plan/1',
  operations: [],
  certificateIdentity: CERTIFICATE.identity,
  sourceRevision: BEFORE,
  sourceStateHash: BEFORE_HASH,
  allowedReads: PREFLIGHT.closure.allowedReads,
  allowedWrites: [],
};

const RNG: TransactionRngDocument = {
  schema: 'terra_transaction_rng/1',
  planIdentity: PLAN_IDENTITY,
  certificateIdentity: CERTIFICATE.identity,
  sourceRevision: BEFORE,
  sourceStateHash: BEFORE_HASH,
  rng: {
    schema: 'sandbox_rng_state/1',
    algorithm: 'PYTHON_RANDOM_MT19937',
    state: { version: '1', internal_state: '(mock)', gauss_next: null },
  },
  ledger: [],
  consumed: true,
};

const RECORDS: readonly StagedRecord[] = [
  { channel: 'TRACE', kind: 'NO_OP_COMMIT_STAGED', payload: { operations: 0 } },
  { channel: 'EVENT', kind: 'ATOMIC_COMMIT_PUBLISHED', payload: { before_revision: 3, after_revision: 4 } },
];

const DIFF: StateDiff = {
  beforeRevision: BEFORE,
  afterRevision: AFTER,
  entries: [
    { field: 'revision.counter', before: 3, after: 4 },
    { field: 'revision_and_transaction_sequence.committed_effect_sequence', before: 0, after: 1 },
    { field: 'semantic_hash', before: BEFORE_HASH, after: AFTER_HASH },
  ],
};

const SNAPSHOT = buildSnapshot({
  snapshotId: SNAPSHOT_ID,
  revisionCounter: 4,
  rngDrawPosition: 88,
  currentActorId: 'ally-bw',
  selectedTargetId: 'enemy-eg2',
  timeline: [
    timelineEntry(1, 'ORDINARY', 'VG-01 ordinary turn (committed)', 'ally-vg', 'NATIVE_EVIDENCED', { av: 0 }),
    timelineEntry(2, 'IMMEDIATE', 'Immediate follow-up request', 'ally-vg', 'NATIVE_EVIDENCED', {
      av: 5,
      detail: 'Rendered as IMMEDIATE, never merged into ORDINARY.',
    }),
    timelineEntry(3, 'ORDINARY', 'BW-02 ordinary turn', 'ally-bw', 'NATIVE_EVIDENCED', { av: 40 }),
    timelineEntry(4, 'ULTIMATE_REQUEST', 'Ultimate request pending', 'ally-bw', 'NATIVE_EVIDENCED', {
      av: 40,
      detail: 'Rendered as ULTIMATE_REQUEST.',
    }),
  ],
  committedEffectSequence: 1,
  replaySequence: 1,
});

const ACTIONS: readonly AvailableAction[] = [
  {
    id: 'act-commit-noop',
    label: 'Atomic no-op commit',
    actorId: 'ally-vg',
    actorName: 'Vanguard Unit',
    targetRule: { supplied: true, summary: 'Single declared target', allowedTargetIds: ['enemy-eg1'] },
    evidenceMode: 'NATIVE_EVIDENCED',
    support: 'AVAILABLE',
    preflightState: 'CLOSED',
    descriptorOnly: false,
    notes: ['Adapter reports AVAILABLE with a CLOSED preflight and a sealed local certificate.'],
  },
];

const PREVIEWS: Readonly<Record<string, ActionPreview>> = {
  'act-commit-noop': {
    actionId: 'act-commit-noop',
    label: 'Atomic no-op commit',
    evidenceMode: 'NATIVE_EVIDENCED',
    support: 'AVAILABLE',
    preflight: PREFLIGHT,
    certificate: {
      status: 'ISSUED',
      certificate: CERTIFICATE,
      refusalReason: null,
      sealedAgainstRevision: BEFORE,
    },
    rejection: null,
    plan: PLAN,
    delta: {
      schema: 'terra_staged_delta/1',
      planIdentity: PLAN_IDENTITY,
      certificateIdentity: CERTIFICATE.identity,
      sourceRevision: BEFORE,
      sourceStateHash: BEFORE_HASH,
      allowedWrites: [],
      writes: [],
      storeNames: [],
    },
    trace: {
      schema: 'terra_staged_trace/1',
      planIdentity: PLAN_IDENTITY,
      certificateIdentity: CERTIFICATE.identity,
      sourceStateHash: BEFORE_HASH,
      allowedWrites: [],
      records: RECORDS,
      discarded: false,
    },
    rngDraws: [],
    diff: DIFF,
    execution: null,
    strictStep: null,
    transactionRng: RNG,
    notes: [
      'Everything above is PRE-COMMIT: staged, private, not yet live.',
      'After commit the revision moves r3 → r4 and the staged material becomes published output.',
    ],
  },
};

const EXECUTIONS: Readonly<Record<string, ExecutionResult>> = {
  'act-commit-noop': {
    outcome: 'COMMITTED',
    actionId: 'act-commit-noop',
    plan: PLAN,
    delta: PREVIEWS['act-commit-noop']?.delta ?? null,
    trace: PREVIEWS['act-commit-noop']?.trace ?? null,
    rngDraws: [],
    commit: {
      schema: 'terra_atomic_commit_result/1',
      planIdentity: PLAN_IDENTITY,
      certificateIdentity: CERTIFICATE.identity,
      beforeRevision: BEFORE,
      afterRevision: AFTER,
      beforeStateHash: BEFORE_HASH,
      afterStateHash: AFTER_HASH,
      records: RECORDS,
      liveStateChanged: true,
    },
    rejection: null,
    strictStep: null,
    transactionRng: RNG,
    liveStateUnchanged: false,
    // Both identity documents are supplied and they differ, so the advance is
    // verified from documents rather than inferred from the outcome name.
    revisionWindow: { before: BEFORE, after: AFTER, beforeHash: BEFORE_HASH, afterHash: AFTER_HASH },
    message: 'Atomic no-op commit published. Revision advanced r3 → r4 with zero staged writes.',
  },
};

const EVENTS: readonly TraceEvent[] = [
  {
    id: 'ev-f-1',
    sequence: 1,
    timestamp: null,
    category: 'STATE',
    summary: `Snapshot ${SNAPSHOT_ID} loaded at revision r3.`,
    evidenceMode: 'NATIVE_EVIDENCED',
    raw: { snapshot_id: SNAPSHOT_ID, revision: 3, provenance: 'MOCK_DATA' },
  },
  {
    id: 'ev-f-2',
    sequence: 2,
    timestamp: null,
    category: 'PREFLIGHT',
    summary: 'Closure CLOSED with 2 obligations and 0 blockers.',
    evidenceMode: 'NATIVE_EVIDENCED',
    raw: { outcome: 'CLOSED', obligations: 2 },
  },
  {
    id: 'ev-f-3',
    sequence: 3,
    timestamp: null,
    category: 'RNG',
    summary: 'Private transaction RNG ledger: 0 draws (no-op).',
    evidenceMode: 'NATIVE_EVIDENCED',
    raw: { algorithm: 'PYTHON_RANDOM_MT19937', draws: 0 },
  },
  {
    id: 'ev-f-4',
    sequence: 4,
    timestamp: null,
    category: 'COMMIT',
    summary: 'Atomic no-op commit published: r3 → r4.',
    evidenceMode: 'NATIVE_EVIDENCED',
    raw: { before: 3, after: 4, live_state_changed: true },
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
  scenarioId: 'F',
  scenarioLabel: 'F · successful atomic no-op commit',
  scenarioSummary:
    'Zero-operation plan published by one atomic commit; before r3 / after r4 identity documents supplied.',
  stateRevisionCounter: 3,
  semanticHash: BEFORE_HASH,
  rngDrawPosition: 86,
  transactionState: 'PLANNED',
  notes: [
    'DEMO / MOCK DATA — served by MockBattleBackendAdapter.',
    'Staged material is PRE-COMMIT; published output appears only after the commit.',
  ],
};

const DESCRIPTOR: ScenarioDescriptor = {
  id: 'F',
  label: 'F · successful atomic no-op commit',
  summary: 'Atomic no-op commit published with before/after identity r3 → r4.',
  backendMode: 'NATIVE_EVIDENCED',
  category: 'COMMIT',
};

export const SCENARIO_F: MockScenarioBundle = {
  descriptor: DESCRIPTOR,
  session: SESSION,
  setup: FIXTURE_SETUP,
  snapshot: SNAPSHOT,
  actions: ACTIONS,
  previews: PREVIEWS,
  executions: EXECUTIONS,
  events: EVENTS,
};
