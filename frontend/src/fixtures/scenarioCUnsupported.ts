/**
 * FIXTURE C — UNSUPPORTED operation.
 *
 * Demonstrates: an obligation settled as a known negative (UNSUPPORTED), a
 * BLOCKED_UNSUPPORTED closure, and an execution that is denied rather than
 * degraded. Inspectable descriptors remain visible.
 *
 * MOCK DATA.
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
} from '../models';
import { FIXTURE_SETUP } from './roster';
import { buildSnapshot } from './buildSnapshot';
import type { MockScenarioBundle } from './types';
import { access, contractRef, present, timelineEntry } from './shared';

const SNAPSHOT_ID = 'mock-c-unsupported';

const UNSUPPORTED_CONTRACT = contractRef(
  'boss_aegis_interaction',
  'terra.battle.content',
  '0.5.0-draft',
  'UNSUPPORTED',
  ['fixture://content_descriptor/EG-03'],
);

const OBLIGATIONS: readonly DependencyObligation[] = [
  {
    schema: 'dependency_obligation/1',
    owner: 'CONTENT_INTERACTION',
    contractRef: UNSUPPORTED_CONTRACT,
    evidenceMode: 'UNSUPPORTED',
    resolution: 'UNSUPPORTED',
    reads: [access('store:status_modifier_binding:EG-03', present({ extent: 'declared' }))],
    writes: [],
    children: [],
    unknownHandles: [],
  },
];

const BLOCKERS: readonly ClosureBlocker[] = [
  {
    schema: 'dependency_closure_blocker/1',
    status: 'BLOCKED_UNSUPPORTED',
    owner: 'CONTENT_INTERACTION',
    contractRef: UNSUPPORTED_CONTRACT,
    unknownHandles: [],
    occurrencePath: [0],
    evidenceRequest:
      'A supported native contract for this content interaction; until then the operation is denied, not approximated',
  },
];

const REJECTION: StructuredRejection = {
  schema: 'structured_rejection/1',
  reasonCode: 'PREFLIGHT_BLOCKED_UNSUPPORTED',
  obligationOwner: 'CONTENT_INTERACTION',
  evidenceRequest:
    'A supported native contract for this content interaction; until then the operation is denied, not approximated',
  contractRefs: [UNSUPPORTED_CONTRACT],
  unknownHandles: [],
  diagnostics: {
    closure_status: 'BLOCKED_UNSUPPORTED',
    occurrence_path: [0],
    note: 'UNSUPPORTED is a settled negative: what is missing is support, not an answer.',
  },
};

const PREFLIGHT: PreflightResult = {
  schema: 'preflight_result/1',
  outcome: 'REJECTED',
  closure: {
    schema: 'dependency_closure/1',
    status: 'BLOCKED_UNSUPPORTED',
    obligations: OBLIGATIONS,
    blockers: BLOCKERS,
    allowedReads: [access('store:status_modifier_binding:EG-03', present({ extent: 'declared' }))],
    allowedWrites: [],
  },
  rejections: [REJECTION],
};

const SNAPSHOT = buildSnapshot({
  snapshotId: SNAPSHOT_ID,
  revisionCounter: 9,
  rngDrawPosition: 27,
  currentActorId: 'ally-vg',
  selectedTargetId: 'enemy-eg3',
  timeline: [
    timelineEntry(1, 'ORDINARY', 'VG-01 ordinary turn', 'ally-vg', 'NATIVE_EVIDENCED', { av: 0 }),
    timelineEntry(2, 'DAMAGE_TASK', 'Pending damage task (unsupported target)', 'ally-vg', 'UNSUPPORTED', {
      av: 15,
      detail: 'Target interaction is UNSUPPORTED; the task cannot be planned.',
    }),
    timelineEntry(3, 'ORDINARY', 'EG-03 ordinary turn', 'enemy-eg3', 'UNSUPPORTED', { av: 40 }),
  ],
});

const ACTIONS: readonly AvailableAction[] = [
  {
    id: 'act-unsupported-strike',
    label: 'Strike (unsupported target interaction)',
    actorId: 'ally-vg',
    actorName: 'Vanguard Unit',
    targetRule: { supplied: true, summary: 'Declared target EG-03', allowedTargetIds: ['enemy-eg3'] },
    evidenceMode: 'UNSUPPORTED',
    support: 'UNSUPPORTED',
    preflightState: 'UNSUPPORTED',
    descriptorOnly: true,
    notes: [
      'Descriptor is inspectable. Execution is denied.',
      'UNSUPPORTED is distinct from UNKNOWN: the disposition is settled.',
    ],
  },
];

const PREVIEWS: Readonly<Record<string, ActionPreview>> = {
  'act-unsupported-strike': {
    actionId: 'act-unsupported-strike',
    label: 'Strike (unsupported target interaction)',
    evidenceMode: 'UNSUPPORTED',
    support: 'UNSUPPORTED',
    preflight: PREFLIGHT,
    certificate: {
      status: 'REFUSED',
      certificate: null,
      refusalReason:
        'Certificate refused: the obligation carries UNSUPPORTED evidence and a non-native contract cannot certify.',
      sealedAgainstRevision: null,
    },
    rejection: REJECTION,
    plan: null,
    delta: null,
    trace: null,
    rngDraws: [],
    diff: null,
    execution: null,
    // An UNSUPPORTED operation never reaches planning or a strict step.
    strictStep: null,
    transactionRng: null,
    notes: ['No reference fallback is offered for an UNSUPPORTED operation.'],
  },
};

const EXECUTIONS: Readonly<Record<string, ExecutionResult>> = {
  'act-unsupported-strike': {
    outcome: 'UNSUPPORTED',
    actionId: 'act-unsupported-strike',
    plan: null,
    delta: null,
    trace: null,
    rngDraws: [],
    commit: null,
    rejection: REJECTION,
    strictStep: null,
    transactionRng: null,
    liveStateUnchanged: true,
    // No before/after identity documents supplied — the UI must not assert
    // "live state unchanged" from the UNSUPPORTED outcome alone.
    revisionWindow: null,
    message:
      'Operation is UNSUPPORTED. Execution denied; no plan, no staged material, live state unchanged.',
  },
};

const EVENTS: readonly TraceEvent[] = [
  {
    id: 'ev-c-1',
    sequence: 1,
    timestamp: null,
    category: 'STATE',
    summary: `Snapshot ${SNAPSHOT_ID} loaded at revision r9.`,
    evidenceMode: 'UNSUPPORTED',
    raw: { snapshot_id: SNAPSHOT_ID, revision: 9, provenance: 'MOCK_DATA' },
  },
  {
    id: 'ev-c-2',
    sequence: 2,
    timestamp: null,
    category: 'PREFLIGHT',
    summary: 'Closure BLOCKED_UNSUPPORTED; obligation resolution UNSUPPORTED.',
    evidenceMode: 'UNSUPPORTED',
    raw: { outcome: 'REJECTED', status: 'BLOCKED_UNSUPPORTED' },
  },
  {
    id: 'ev-c-3',
    sequence: 3,
    timestamp: null,
    category: 'BLOCKER',
    summary: 'CONTENT_INTERACTION denies execution for the selected target.',
    evidenceMode: 'UNSUPPORTED',
    raw: { reason_code: REJECTION.reasonCode, owner: REJECTION.obligationOwner },
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
  scenarioId: 'C',
  scenarioLabel: 'C · UNSUPPORTED operation',
  scenarioSummary:
    'A settled negative: the operation is inspectable but execution is denied. No certificate, no plan.',
  stateRevisionCounter: 9,
  semanticHash: SNAPSHOT.semanticHash,
  rngDrawPosition: 27,
  transactionState: 'UNSUPPORTED',
  notes: [
    'DEMO / MOCK DATA — served by MockBattleBackendAdapter.',
    'UNSUPPORTED is never rendered as a degraded "still available" action.',
  ],
};

const DESCRIPTOR: ScenarioDescriptor = {
  id: 'C',
  label: 'C · UNSUPPORTED operation',
  summary: 'UNSUPPORTED obligation: inspectable, execution denied.',
  backendMode: 'UNSUPPORTED',
  category: 'UNSUPPORTED',
};

export const SCENARIO_C: MockScenarioBundle = {
  descriptor: DESCRIPTOR,
  session: SESSION,
  setup: FIXTURE_SETUP,
  snapshot: SNAPSHOT,
  actions: ACTIONS,
  previews: PREVIEWS,
  executions: EXECUTIONS,
  events: EVENTS,
};
