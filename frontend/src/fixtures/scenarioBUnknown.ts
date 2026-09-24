/**
 * FIXTURE B — UNKNOWN blocker.
 *
 * Demonstrates: an obligation that nobody has answered yet, a BLOCKED_UNKNOWN
 * closure, a structured rejection bound to an UnknownHandle, and NO certificate.
 *
 * MOCK DATA. The handle below is synthetic; it does not describe any real
 * unresolved game mechanic.
 */
import type {
  ActionPreview,
  AvailableAction,
  ClosureBlocker,
  DependencyObligation,
  ExecutionResult,
  PreflightResult,
  ScenarioDescriptor,
  SessionInfo,
  StructuredRejection,
  TraceEvent,
  UnknownHandle,
} from '../models';
import { FIXTURE_SETUP } from './roster';
import { buildSnapshot } from './buildSnapshot';
import type { MockScenarioBundle } from './types';
import { access, childRef, contractRef, present, timelineEntry, unknownHandle } from './shared';

const SNAPSHOT_ID = 'mock-b-unknown-blocker';

const HANDLE: UnknownHandle = unknownHandle({
  blockerId: 'uh-native-modifier-stack-order',
  ownerFamily: 'MODIFIER_LIFECYCLE',
  payload: {
    question: 'Modifier stacking order for the referenced modifier family is not established.',
    observed_field_count: 3,
  },
  provenance: {
    source: 'fixture://battle_semantics/modifier_application_bridge_07',
    content_version: '4.4.54',
    relation: 'CLOSE_VERSION',
    note: 'Synthetic fixture provenance.',
  },
  requiredEvidence: [
    'EXACT_NATIVE modifier stacking-order trace for 4.4.54',
    'Modifier lifecycle contract revision matching the live state revision',
  ],
});

const MODIFIER_CONTRACT = contractRef(
  'modifier_stack_order',
  'terra.battle.modifier',
  '0.9.0-draft',
  'UNSUPPORTED',
  ['fixture://modifier_application_bridge_07'],
);

const READ_CONTRACT = contractRef(
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
    contractRef: READ_CONTRACT,
    evidenceMode: 'NATIVE_EVIDENCED',
    resolution: 'RESOLVED',
    reads: [access('store:unit_hp_current:*', present({ extent: 'full' }))],
    writes: [],
    children: [],
    unknownHandles: [],
  },
  {
    schema: 'dependency_obligation/1',
    owner: 'MODIFIER_LIFECYCLE',
    contractRef: MODIFIER_CONTRACT,
    evidenceMode: 'UNSUPPORTED',
    resolution: 'UNKNOWN',
    reads: [access('store:status_modifier_binding:*', present({ extent: 'declared' }))],
    writes: [],
    children: [childRef('STATE_READ', READ_CONTRACT)],
    unknownHandles: [HANDLE],
  },
];

const BLOCKERS: readonly ClosureBlocker[] = [
  {
    schema: 'dependency_closure_blocker/1',
    status: 'BLOCKED_UNKNOWN',
    owner: 'MODIFIER_LIFECYCLE',
    contractRef: MODIFIER_CONTRACT,
    unknownHandles: [HANDLE],
    occurrencePath: [1],
    evidenceRequest: 'EXACT_NATIVE modifier stacking-order evidence before any execution may be planned',
  },
];

const PREFLIGHT: PreflightResult = {
  schema: 'preflight_result/1',
  outcome: 'REJECTED',
  closure: {
    schema: 'dependency_closure/1',
    status: 'BLOCKED_UNKNOWN',
    obligations: OBLIGATIONS,
    blockers: BLOCKERS,
    allowedReads: [access('store:unit_hp_current:*', present({ extent: 'full' }))],
    allowedWrites: [],
  },
  rejections: [],
};

const REJECTION: StructuredRejection = {
  schema: 'structured_rejection/1',
  reasonCode: 'PREFLIGHT_BLOCKED_UNKNOWN',
  obligationOwner: 'MODIFIER_LIFECYCLE',
  evidenceRequest: 'EXACT_NATIVE modifier stacking-order evidence before any execution may be planned',
  contractRefs: [MODIFIER_CONTRACT],
  unknownHandles: [HANDLE],
  diagnostics: {
    closure_status: 'BLOCKED_UNKNOWN',
    occurrence_path: [1],
    note: 'Structured rejection binds exactly one closure blocker.',
  },
};

const PREFLIGHT_WITH_REJECTION: PreflightResult = { ...PREFLIGHT, rejections: [REJECTION] };

const SNAPSHOT = buildSnapshot({
  snapshotId: SNAPSHOT_ID,
  revisionCounter: 7,
  rngDrawPosition: 18,
  currentActorId: 'ally-cs',
  selectedTargetId: 'enemy-eg1',
  unknownHandles: [HANDLE],
  timeline: [
    timelineEntry(1, 'ORDINARY', 'CS-03 ordinary turn', 'ally-cs', 'NATIVE_EVIDENCED', { av: 0 }),
    timelineEntry(2, 'ACTION_TASK', 'CS-03 action task (pending preflight)', 'ally-cs', 'REFERENCE_MODEL', {
      av: 22,
      detail: 'Blocked by an UNKNOWN dependency obligation.',
    }),
    timelineEntry(3, 'ORDINARY', 'EG-01 ordinary turn', 'enemy-eg1', 'NATIVE_EVIDENCED', { av: 48 }),
  ],
});

const ACTIONS: readonly AvailableAction[] = [
  {
    id: 'act-unknown-skill',
    label: 'Signature action (unknown dependency)',
    actorId: 'ally-cs',
    actorName: 'Caster Unit',
    targetRule: { supplied: true, summary: 'Single declared target', allowedTargetIds: ['enemy-eg1', 'enemy-eg2', 'enemy-eg3'] },
    evidenceMode: 'UNSUPPORTED',
    support: 'UNKNOWN',
    preflightState: 'UNKNOWN',
    descriptorOnly: true,
    notes: [
      'Adapter reports UNKNOWN, not BLOCKED and not AVAILABLE.',
      'The unresolved dependency is named by an explicit UnknownHandle.',
    ],
  },
  {
    id: 'act-unknown-ult',
    label: 'Ultimate request (unknown dependency)',
    actorId: 'ally-cs',
    actorName: 'Caster Unit',
    targetRule: { supplied: false, summary: null, allowedTargetIds: null },
    evidenceMode: 'UNSUPPORTED',
    support: 'UNKNOWN',
    preflightState: 'UNKNOWN',
    descriptorOnly: true,
    notes: ['Same blocking owner; two distinct descriptors.'],
  },
];

function preview(actionId: string, label: string): ActionPreview {
  return {
    actionId,
    label,
    evidenceMode: 'UNSUPPORTED',
    support: 'UNKNOWN',
    preflight: PREFLIGHT_WITH_REJECTION,
    certificate: {
      status: 'NOT_REQUESTED',
      certificate: null,
      refusalReason:
        'Certification was not reached: the closure is BLOCKED_UNKNOWN, so no certificate can be sealed.',
      sealedAgainstRevision: null,
    },
    rejection: REJECTION,
    plan: null,
    delta: null,
    trace: null,
    rngDraws: [],
    diff: null,
    execution: null,
    // A blocked closure never reaches a plan, so no strict step document exists.
    strictStep: null,
    transactionRng: null,
    notes: [
      'UNKNOWN stays UNKNOWN. The frontend offers no fallback target and no degraded estimate.',
      'The handle is rendered verbatim; nothing is substituted for the missing evidence.',
    ],
  };
}

const PREVIEWS: Readonly<Record<string, ActionPreview>> = {
  'act-unknown-skill': preview('act-unknown-skill', 'Signature action (unknown dependency)'),
  'act-unknown-ult': preview('act-unknown-ult', 'Ultimate request (unknown dependency)'),
};

function execution(actionId: string): ExecutionResult {
  return {
    outcome: 'NOT_PERFORMED',
    actionId,
    plan: null,
    delta: null,
    trace: null,
    rngDraws: [],
    commit: null,
    rejection: REJECTION,
    strictStep: null,
    transactionRng: null,
    liveStateUnchanged: true,
    // No before/after identity documents were supplied, so the UI must not
    // assert "live state unchanged" from the REJECTED outcome alone.
    revisionWindow: null,
    message:
      'Preflight rejected with PREFLIGHT_BLOCKED_UNKNOWN. No plan was produced and live state was not touched.',
  };
}

const EXECUTIONS: Readonly<Record<string, ExecutionResult>> = {
  'act-unknown-skill': execution('act-unknown-skill'),
  'act-unknown-ult': execution('act-unknown-ult'),
};

const EVENTS: readonly TraceEvent[] = [
  {
    id: 'ev-b-1',
    sequence: 1,
    timestamp: null,
    category: 'STATE',
    summary: `Snapshot ${SNAPSHOT_ID} loaded at revision r7.`,
    evidenceMode: 'NATIVE_EVIDENCED',
    raw: { snapshot_id: SNAPSHOT_ID, revision: 7, provenance: 'MOCK_DATA' },
  },
  {
    id: 'ev-b-2',
    sequence: 2,
    timestamp: null,
    category: 'PREFLIGHT',
    summary: 'Closure BLOCKED_UNKNOWN after 2 obligations; 1 blocker retained.',
    evidenceMode: 'UNSUPPORTED',
    raw: { outcome: 'REJECTED', status: 'BLOCKED_UNKNOWN', blockers: 1 },
  },
  {
    id: 'ev-b-3',
    sequence: 3,
    timestamp: null,
    category: 'BLOCKER',
    summary: `UnknownHandle ${HANDLE.blockerId} owned by ${HANDLE.ownerFamily}.`,
    evidenceMode: 'UNSUPPORTED',
    raw: {
      blocker_id: HANDLE.blockerId,
      owner_family: HANDLE.ownerFamily,
      required_evidence: [...HANDLE.requiredEvidence],
    },
  },
  {
    id: 'ev-b-4',
    sequence: 4,
    timestamp: null,
    category: 'ACTION',
    summary: 'Execution refused: no certificate, no plan, live state unchanged.',
    evidenceMode: 'UNSUPPORTED',
    raw: { reason_code: REJECTION.reasonCode },
  },
];

const SESSION: SessionInfo = {
  adapterId: 'mock-battle-backend',
  adapterLabel: 'MockBattleBackendAdapter',
  adapterKind: 'MOCK',
  contentVersion: '4.4.54',
  backendMode: 'UNSUPPORTED',
  connection: 'CONNECTED',
  connectionDetail: 'In-process mock adapter. No live backend is attached.',
  dataProvenance: 'MOCK_DATA',
  scenarioId: 'B',
  scenarioLabel: 'B · UNKNOWN blocker',
  scenarioSummary:
    'An UNKNOWN obligation carrying an explicit UnknownHandle blocks the closure; no certificate, no plan.',
  stateRevisionCounter: 7,
  semanticHash: SNAPSHOT.semanticHash,
  rngDrawPosition: 18,
  transactionState: 'REJECTED',
  notes: [
    'DEMO / MOCK DATA — served by MockBattleBackendAdapter.',
    'UNKNOWN is rendered as unresolved. It is never silently treated as BLOCKED or AVAILABLE.',
  ],
};

const DESCRIPTOR: ScenarioDescriptor = {
  id: 'B',
  label: 'B · UNKNOWN blocker',
  summary: 'UNKNOWN obligation + structured rejection; no certificate.',
  backendMode: 'UNSUPPORTED',
  category: 'UNKNOWN',
};

export const SCENARIO_B: MockScenarioBundle = {
  descriptor: DESCRIPTOR,
  session: SESSION,
  setup: FIXTURE_SETUP,
  snapshot: SNAPSHOT,
  actions: ACTIONS,
  previews: PREVIEWS,
  executions: EXECUTIONS,
  events: EVENTS,
};

export const SCENARIO_B_UNKNOWN_HANDLE: UnknownHandle = HANDLE;
