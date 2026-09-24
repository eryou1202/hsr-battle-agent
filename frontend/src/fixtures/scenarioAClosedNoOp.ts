/**
 * FIXTURE A — closed native no-op strict step.
 *
 * Mirrors the real G01-012 shape: a CLOSED conservative closure, a sealed local
 * strict certificate, a TransactionPlan with ZERO operations, empty staged
 * delta / RNG ledger / staged trace, and a `StrictStepResult` with outcome
 * COMMITTED for `terra.strict.no_op/1`.
 *
 * MOCK DATA. No gameplay semantics are encoded here.
 */
import type {
  ActionPreview,
  AvailableAction,
  ClosureBlocker,
  DependencyObligation,
  ExecutionResult,
  GateCertificate,
  PreflightResult,
  ScenarioDescriptor,
  SessionInfo,
  StrictStepResult,
  StagedRecord,
  TraceEvent,
  TransactionPlan,
  TransactionRngDocument,
} from '../models';
import { STRICT_NO_OP_ACTION } from '../models/strict';
import { FIXTURE_SETUP } from './roster';
import { buildSnapshot, policyIdentity } from './buildSnapshot';
import type { MockScenarioBundle } from './types';
import { access, childRef, contractRef, fixtureHex, present, revision, timelineEntry } from './shared';

const SNAPSHOT_ID = 'mock-a-strict-noop';
const BEFORE = revision(12, SNAPSHOT_ID);
const AFTER = revision(13, SNAPSHOT_ID);
const BEFORE_HASH = `terra-semantic-sha256:${fixtureHex(`${SNAPSHOT_ID}#12#NATIVE_EVIDENCED`)}`;
const AFTER_HASH = `terra-semantic-sha256:${fixtureHex(`${SNAPSHOT_ID}#13#NATIVE_EVIDENCED`)}`;
const EMPTY_PLAN_IDENTITY = `terra-plan-sha256:${fixtureHex(`${SNAPSHOT_ID}:empty-operations`)}`;

const readContract = contractRef(
  'unit_hp_read',
  'terra.battle.state',
  '1.0.0',
  'NATIVE_EVIDENCED',
  ['fixture://unit_hp_current', 'fixture://unit_hp_max'],
);

const actionContract = contractRef(
  'strict_no_op',
  'terra.battle.action',
  '1.0.0',
  'NATIVE_EVIDENCED',
  ['fixture://strict_executor/STRICT_NO_OP_ACTION'],
);

const turnContract = contractRef(
  'turn_order_snapshot',
  'terra.battle.turn',
  '1.0.0',
  'NATIVE_EVIDENCED',
  ['fixture://turn_order_av'],
);

function obligations(): readonly DependencyObligation[] {
  return [
    {
      schema: 'dependency_obligation/1',
      owner: 'STATE_READ',
      contractRef: readContract,
      evidenceMode: 'NATIVE_EVIDENCED',
      resolution: 'RESOLVED',
      reads: [
        access('store:unit_hp_current:*', present({ extent: 'full' })),
        // Deliberately repeated: order and duplicates are data, not noise.
        access('store:unit_hp_current:*', present({ extent: 'full' })),
      ],
      writes: [],
      children: [],
      unknownHandles: [],
    },
    {
      schema: 'dependency_obligation/1',
      owner: 'ACTION_EXEC',
      contractRef: actionContract,
      evidenceMode: 'NATIVE_EVIDENCED',
      resolution: 'RESOLVED',
      reads: [access('store:status_modifier_binding:*', present({ extent: 'declared' }))],
      writes: [],
      children: [childRef('STATE_READ', readContract), childRef('STATE_READ', readContract)],
      unknownHandles: [],
    },
    {
      schema: 'dependency_obligation/1',
      owner: 'TURN_SCHEDULE',
      contractRef: turnContract,
      evidenceMode: 'NATIVE_EVIDENCED',
      resolution: 'RESOLVED',
      reads: [access('store:turn_order_av:*', present({ extent: 'declared' }))],
      writes: [],
      children: [],
      unknownHandles: [],
    },
  ];
}

const BLOCKERS: readonly ClosureBlocker[] = [];

const PREFLIGHT: PreflightResult = {
  schema: 'preflight_result/1',
  outcome: 'CLOSED',
  closure: {
    schema: 'dependency_closure/1',
    status: 'CLOSED',
    obligations: obligations(),
    blockers: BLOCKERS,
    allowedReads: [
      access('store:unit_hp_current:*', present({ extent: 'full' })),
      access('store:unit_hp_current:*', present({ extent: 'full' })),
      access('store:status_modifier_binding:*', present({ extent: 'declared' })),
      access('store:turn_order_av:*', present({ extent: 'declared' })),
    ],
    allowedWrites: [],
  },
  rejections: [],
};

const CERTIFICATE: GateCertificate = {
  schema: 'terra_gate_certificate/1',
  planIdentity: EMPTY_PLAN_IDENTITY,
  evidenceMode: 'NATIVE_EVIDENCED',
  policyIdentity: policyIdentity('NATIVE_EVIDENCED'),
  inputIdentity: fixtureHex(`${SNAPSHOT_ID}:input:r12`),
  inputRevision: 'r12',
  stateRevision: BEFORE,
  contractRef: actionContract,
  contractRevision: '1.0.0',
  closureIdentity: fixtureHex(`${SNAPSHOT_ID}:closure:r12`),
  allowedReads: PREFLIGHT.closure.allowedReads,
  allowedWrites: [],
  identity: fixtureHex(`${SNAPSHOT_ID}:certificate:r12`),
};

export const SCENARIO_A_PLAN: TransactionPlan = {
  schema: 'terra_transaction_plan/1',
  operations: [],
  certificateIdentity: CERTIFICATE.identity,
  sourceRevision: BEFORE,
  sourceStateHash: BEFORE_HASH,
  allowedReads: PREFLIGHT.closure.allowedReads,
  allowedWrites: [],
};

/** Empty private RNG ledger — a no-op plan draws nothing. */
export const SCENARIO_A_RNG: TransactionRngDocument = {
  schema: 'terra_transaction_rng/1',
  planIdentity: EMPTY_PLAN_IDENTITY,
  certificateIdentity: CERTIFICATE.identity,
  sourceRevision: BEFORE,
  sourceStateHash: BEFORE_HASH,
  rng: {
    schema: 'sandbox_rng_state/1',
    algorithm: 'PYTHON_RANDOM_MT19937',
    state: { version: '1', internal_state: '(mock)', gauss_next: null },
  },
  ledger: [],
  consumed: false,
};

const RECORDS: readonly StagedRecord[] = [
  { channel: 'TRACE', kind: 'STRICT_NO_OP_STAGED', payload: { operations: 0 } },
  { channel: 'EVENT', kind: 'STRICT_STEP_COMMITTED', payload: { before_revision: 12, after_revision: 13 } },
];

export const SCENARIO_A_STRICT_STEP: StrictStepResult = {
  schema: 'terra_strict_step_result/1',
  outcome: 'COMMITTED',
  resultingRevision: AFTER,
  transactionIdentity: fixtureHex(`${SNAPSHOT_ID}:transaction:r13`),
  rejections: [],
};

const SNAPSHOT = buildSnapshot({
  snapshotId: SNAPSHOT_ID,
  revisionCounter: 12,
  rngDrawPosition: 41,
  currentActorId: 'ally-vg',
  selectedTargetId: 'enemy-eg1',
  timeline: [
    timelineEntry(1, 'ORDINARY', 'VG-01 ordinary turn', 'ally-vg', 'NATIVE_EVIDENCED', {
      av: 0,
      detail: 'Supplied order position 1.',
    }),
    timelineEntry(2, 'ORDINARY', 'EG-01 ordinary turn', 'enemy-eg1', 'NATIVE_EVIDENCED', { av: 34 }),
    timelineEntry(3, 'ORDINARY', 'BW-02 ordinary turn', 'ally-bw', 'NATIVE_EVIDENCED', { av: 62 }),
  ],
  replaySequence: 0,
  committedEffectSequence: 0,
});

const ACTIONS: readonly AvailableAction[] = [
  {
    id: 'act-strict-noop',
    label: `Strict no-op step (${STRICT_NO_OP_ACTION})`,
    actorId: 'ally-vg',
    actorName: 'Vanguard Unit',
    targetRule: { supplied: true, summary: 'Single declared target', allowedTargetIds: ['enemy-eg1', 'enemy-eg2'] },
    evidenceMode: 'NATIVE_EVIDENCED',
    support: 'AVAILABLE',
    preflightState: 'CLOSED',
    descriptorOnly: false,
    notes: [
      'Adapter reports AVAILABLE for this fixture; not inferred from the descriptor.',
      'Only the strict no-op action is supported by the strict executor.',
    ],
  },
];

const PREVIEWS: Readonly<Record<string, ActionPreview>> = {
  'act-strict-noop': {
    actionId: 'act-strict-noop',
    label: `Strict no-op step (${STRICT_NO_OP_ACTION})`,
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
    plan: SCENARIO_A_PLAN,
    delta: {
      schema: 'terra_staged_delta/1',
      planIdentity: EMPTY_PLAN_IDENTITY,
      certificateIdentity: CERTIFICATE.identity,
      sourceRevision: BEFORE,
      sourceStateHash: BEFORE_HASH,
      allowedWrites: [],
      writes: [],
      storeNames: [],
    },
    trace: {
      schema: 'terra_staged_trace/1',
      planIdentity: EMPTY_PLAN_IDENTITY,
      certificateIdentity: CERTIFICATE.identity,
      sourceStateHash: BEFORE_HASH,
      allowedWrites: [],
      records: RECORDS,
      discarded: false,
    },
    rngDraws: [],
    diff: null,
    execution: null,
    strictStep: null,
    transactionRng: SCENARIO_A_RNG,
    notes: [
      'Zero operations: a no-op plan. Certification is not a promise of effect.',
      'Staged material is PRE-COMMIT; nothing is published until the atomic commit.',
    ],
  },
};

const EXECUTIONS: Readonly<Record<string, ExecutionResult>> = {
  'act-strict-noop': {
    outcome: 'COMMITTED',
    actionId: 'act-strict-noop',
    plan: SCENARIO_A_PLAN,
    delta: PREVIEWS['act-strict-noop']?.delta ?? null,
    trace: PREVIEWS['act-strict-noop']?.trace ?? null,
    rngDraws: [],
    commit: {
      schema: 'terra_atomic_commit_result/1',
      planIdentity: EMPTY_PLAN_IDENTITY,
      certificateIdentity: CERTIFICATE.identity,
      beforeRevision: BEFORE,
      afterRevision: AFTER,
      beforeStateHash: BEFORE_HASH,
      afterStateHash: AFTER_HASH,
      records: RECORDS,
      liveStateChanged: true,
    },
    rejection: null,
    strictStep: SCENARIO_A_STRICT_STEP,
    transactionRng: SCENARIO_A_RNG,
    liveStateUnchanged: false,
    // Both identity documents are supplied and they differ, so the advance is
    // verified from documents rather than inferred from the outcome name.
    revisionWindow: { before: BEFORE, after: AFTER, beforeHash: BEFORE_HASH, afterHash: AFTER_HASH },
    message:
      'Strict no-op step COMMITTED. The atomic commit published once and the revision advanced r12 → r13.',
  },
};

const EVENTS: readonly TraceEvent[] = [
  {
    id: 'ev-a-1',
    sequence: 1,
    timestamp: null,
    category: 'STATE',
    summary: `Snapshot ${SNAPSHOT_ID} loaded at revision r12.`,
    evidenceMode: 'NATIVE_EVIDENCED',
    raw: { snapshot_id: SNAPSHOT_ID, revision: 12, provenance: 'MOCK_DATA' },
  },
  {
    id: 'ev-a-2',
    sequence: 2,
    timestamp: null,
    category: 'PREFLIGHT',
    summary: 'Dependency closure CLOSED with 3 obligations and 0 blockers.',
    evidenceMode: 'NATIVE_EVIDENCED',
    raw: { outcome: 'CLOSED', obligations: 3, blockers: 0 },
  },
  {
    id: 'ev-a-3',
    sequence: 3,
    timestamp: null,
    category: 'COMMIT',
    summary: 'StrictStepResult COMMITTED · r12 → r13 · zero-operation no-op plan.',
    evidenceMode: 'NATIVE_EVIDENCED',
    raw: { outcome: 'COMMITTED', before: 12, after: 13, operations: 0 },
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
  scenarioId: 'A',
  scenarioLabel: 'A · closed native no-op strict step',
  scenarioSummary:
    'Closed closure + sealed local certificate + zero-operation plan + StrictStepResult COMMITTED.',
  stateRevisionCounter: 12,
  semanticHash: BEFORE_HASH,
  rngDrawPosition: 41,
  transactionState: 'PLANNED',
  notes: [
    'DEMO / MOCK DATA — served by MockBattleBackendAdapter.',
    'The certificate is LOCAL STRICT infrastructure, not an official client certificate.',
  ],
};

const DESCRIPTOR: ScenarioDescriptor = {
  id: 'A',
  label: 'A · closed native no-op strict step',
  summary: 'Closed closure, sealed certificate, StrictStepResult COMMITTED.',
  backendMode: 'NATIVE_EVIDENCED',
  category: 'CLOSED_NOOP',
};

export const SCENARIO_A: MockScenarioBundle = {
  descriptor: DESCRIPTOR,
  session: SESSION,
  setup: FIXTURE_SETUP,
  snapshot: SNAPSHOT,
  actions: ACTIONS,
  previews: PREVIEWS,
  executions: EXECUTIONS,
  events: EVENTS,
};
