/**
 * FIXTURE D — REFERENCE_MODEL result.
 *
 * Demonstrates the case the UI must NOT paper over: the closure can be locally
 * CLOSED while every obligation carries REFERENCE_MODEL evidence. The backend
 * therefore refuses to seal a certificate, and the frontend shows a
 * REFERENCE_ONLY result instead of an executable one.
 *
 * MOCK DATA. The reference figures below are placeholders, not a model of any
 * real combat mechanic.
 */
import type {
  ActionPreview,
  AvailableAction,
  DependencyObligation,
  ExecutionResult,
  PreflightResult,
  ScenarioDescriptor,
  SessionInfo,
  StagedRecord,
  TraceEvent,
} from '../models';
import { FIXTURE_SETUP } from './roster';
import { buildSnapshot } from './buildSnapshot';
import type { MockScenarioBundle } from './types';
import { access, contractRef, fixtureHex, present, timelineEntry } from './shared';

const SNAPSHOT_ID = 'mock-d-reference-model';

const REFERENCE_CONTRACT = contractRef(
  'damage_estimate_reference',
  'terra.reference.damage',
  '0.3.0-reference',
  'REFERENCE_MODEL',
  ['fixture://damage_survival_reference', 'fixture://external_behavior_corpus'],
);

const SECOND_CONTRACT = contractRef(
  'survival_reference',
  'terra.reference.survival',
  '0.3.0-reference',
  'REFERENCE_MODEL',
  ['fixture://damage_survival_reference'],
);

const OBLIGATIONS: readonly DependencyObligation[] = [
  {
    schema: 'dependency_obligation/1',
    owner: 'REFERENCE_DAMAGE',
    contractRef: REFERENCE_CONTRACT,
    evidenceMode: 'REFERENCE_MODEL',
    resolution: 'RESOLVED',
    reads: [access('reference:damage_estimate', present({ extent: 'estimate' }))],
    writes: [],
    children: [],
    unknownHandles: [],
  },
  {
    schema: 'dependency_obligation/1',
    owner: 'REFERENCE_SURVIVAL',
    contractRef: SECOND_CONTRACT,
    evidenceMode: 'REFERENCE_MODEL',
    resolution: 'RESOLVED',
    reads: [access('reference:survival_estimate', present({ extent: 'estimate' }))],
    writes: [],
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
    allowedReads: [
      access('reference:damage_estimate', present({ extent: 'estimate' })),
      access('reference:survival_estimate', present({ extent: 'estimate' })),
    ],
    allowedWrites: [],
  },
  rejections: [],
};

const REFERENCE_RECORDS: readonly StagedRecord[] = [
  {
    channel: 'TRACE',
    kind: 'REFERENCE_ESTIMATE',
    payload: {
      note: 'Indicative reference estimate. NOT a native result and NOT executable.',
      estimate_kind: 'damage_estimate',
      value_supplied: false,
    },
  },
  {
    channel: 'EVENT',
    kind: 'REFERENCE_ONLY_NOTICE',
    payload: {
      message: 'Reference-model material cannot be promoted to native execution.',
      contract_id: REFERENCE_CONTRACT.contractId,
    },
  },
];

const SNAPSHOT = buildSnapshot({
  snapshotId: SNAPSHOT_ID,
  revisionCounter: 15,
  rngDrawPosition: 63,
  currentActorId: 'ally-cs',
  selectedTargetId: 'enemy-eg1',
  evidenceMode: 'REFERENCE_MODEL',
  timeline: [
    timelineEntry(1, 'ORDINARY', 'CS-03 ordinary turn', 'ally-cs', 'NATIVE_EVIDENCED', { av: 0 }),
    timelineEntry(2, 'ACTION_TASK', 'CS-03 action task (reference only)', 'ally-cs', 'REFERENCE_MODEL', {
      av: 12,
      detail: 'Reference estimate available; native execution not certified.',
    }),
    timelineEntry(3, 'ORDINARY', 'EG-01 ordinary turn', 'enemy-eg1', 'NATIVE_EVIDENCED', { av: 55 }),
  ],
});

const ACTIONS: readonly AvailableAction[] = [
  {
    id: 'act-reference-skill',
    label: 'Signature action (reference estimate only)',
    actorId: 'ally-cs',
    actorName: 'Caster Unit',
    targetRule: { supplied: true, summary: 'Single declared target', allowedTargetIds: ['enemy-eg1'] },
    evidenceMode: 'REFERENCE_MODEL',
    support: 'REFERENCE_ONLY',
    preflightState: 'CLOSED',
    descriptorOnly: false,
    notes: [
      'Closure is CLOSED but every obligation is REFERENCE_MODEL.',
      'The adapter reports REFERENCE_ONLY — the frontend must not widen this to AVAILABLE.',
    ],
  },
];

const PREVIEWS: Readonly<Record<string, ActionPreview>> = {
  'act-reference-skill': {
    actionId: 'act-reference-skill',
    label: 'Signature action (reference estimate only)',
    evidenceMode: 'REFERENCE_MODEL',
    support: 'REFERENCE_ONLY',
    preflight: PREFLIGHT,
    certificate: {
      status: 'REFUSED',
      certificate: null,
      refusalReason:
        'Certificate refused: every closed obligation must be NATIVE_EVIDENCED. REFERENCE_MODEL evidence is not promoted.',
      sealedAgainstRevision: null,
    },
    rejection: null,
    plan: null,
    delta: null,
    trace: {
      schema: 'terra_staged_trace/1',
      planIdentity: `terra-plan-sha256:${fixtureHex(`${SNAPSHOT_ID}:reference`)}`,
      certificateIdentity: '(none — certificate refused)',
      sourceStateHash: SNAPSHOT.semanticHash,
      allowedWrites: [],
      records: REFERENCE_RECORDS,
      discarded: false,
    },
    rngDraws: [],
    diff: null,
    execution: null,
    // Certification was refused, so no plan and no strict step document exist.
    strictStep: null,
    transactionRng: null,
    notes: [
      'A CLOSED closure is not a certificate. This fixture shows exactly that difference.',
      'Reference values are shown as indicative only and are never written to live state.',
    ],
  },
};

const EXECUTIONS: Readonly<Record<string, ExecutionResult>> = {
  'act-reference-skill': {
    outcome: 'REFERENCE_ONLY',
    actionId: 'act-reference-skill',
    plan: null,
    delta: null,
    trace: {
      schema: 'terra_staged_trace/1',
      planIdentity: `terra-plan-sha256:${fixtureHex(`${SNAPSHOT_ID}:reference`)}`,
      certificateIdentity: '(none — certificate refused)',
      sourceStateHash: SNAPSHOT.semanticHash,
      allowedWrites: [],
      records: REFERENCE_RECORDS,
      discarded: false,
    },
    rngDraws: [],
    commit: null,
    rejection: null,
    strictStep: null,
    transactionRng: null,
    liveStateUnchanged: true,
    // No before/after identity documents supplied — the UI must not assert
    // "live state unchanged" from the REFERENCE_ONLY outcome alone.
    revisionWindow: null,
    message:
      'REFERENCE_ONLY result returned. No certificate was sealed, no transaction was planned, live state unchanged.',
  },
};

const EVENTS: readonly TraceEvent[] = [
  {
    id: 'ev-d-1',
    sequence: 1,
    timestamp: null,
    category: 'STATE',
    summary: `Snapshot ${SNAPSHOT_ID} loaded at revision r15.`,
    evidenceMode: 'REFERENCE_MODEL',
    raw: { snapshot_id: SNAPSHOT_ID, revision: 15, provenance: 'MOCK_DATA' },
  },
  {
    id: 'ev-d-2',
    sequence: 2,
    timestamp: null,
    category: 'PREFLIGHT',
    summary: 'Closure CLOSED with 2 obligations, all REFERENCE_MODEL.',
    evidenceMode: 'REFERENCE_MODEL',
    raw: { outcome: 'CLOSED', obligations: 2, evidence_modes: ['REFERENCE_MODEL'] },
  },
  {
    id: 'ev-d-3',
    sequence: 3,
    timestamp: null,
    category: 'REFERENCE',
    summary: 'Certificate refused: reference evidence cannot certify native execution.',
    evidenceMode: 'REFERENCE_MODEL',
    raw: { certificate_status: 'REFUSED' },
  },
];

const SESSION: SessionInfo = {
  adapterId: 'mock-battle-backend',
  adapterLabel: 'MockBattleBackendAdapter',
  adapterKind: 'MOCK',
  contentVersion: '4.4.54',
  backendMode: 'REFERENCE_MODEL',
  connection: 'CONNECTED',
  connectionDetail: 'In-process mock adapter. No live backend is attached.',
  dataProvenance: 'MOCK_DATA',
  scenarioId: 'D',
  scenarioLabel: 'D · REFERENCE_MODEL result',
  scenarioSummary:
    'Closure closes but carries only reference evidence, so certification is refused and the result stays REFERENCE_ONLY.',
  stateRevisionCounter: 15,
  semanticHash: SNAPSHOT.semanticHash,
  rngDrawPosition: 63,
  transactionState: 'REFERENCE_ONLY',
  notes: [
    'DEMO / MOCK DATA — served by MockBattleBackendAdapter.',
    'Reference results are labelled indicative and are never promoted to executable.',
  ],
};

const DESCRIPTOR: ScenarioDescriptor = {
  id: 'D',
  label: 'D · REFERENCE_MODEL result',
  summary: 'CLOSED closure, REFERENCE_MODEL evidence, certificate refused.',
  backendMode: 'REFERENCE_MODEL',
  category: 'REFERENCE_MODEL',
};

export const SCENARIO_D: MockScenarioBundle = {
  descriptor: DESCRIPTOR,
  session: SESSION,
  setup: FIXTURE_SETUP,
  snapshot: SNAPSHOT,
  actions: ACTIONS,
  previews: PREVIEWS,
  executions: EXECUTIONS,
  events: EVENTS,
};

export const SCENARIO_D_REFERENCE_CONTRACT = REFERENCE_CONTRACT;
