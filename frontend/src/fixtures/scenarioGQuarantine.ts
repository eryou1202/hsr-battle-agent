/**
 * FIXTURE G — FC-02 modifier lifecycle contract quarantine.
 *
 * Mirrors `battle_sandbox.contract_registry` (G01-014): a corrected native
 * Refresh slot that stays BLOCKED_NATIVE, the preserved legacy Refresh fixture
 * label kept on the REFERENCE_MODEL side only, and a separately blocked Replace
 * slot.
 *
 * This fixture DOES NOT encode a universal modifier rule. The quarantine is
 * modelled as data — one slot per operation — so a different operation with a
 * different status renders differently without any frontend change.
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
  QuarantineEntry,
  ScenarioDescriptor,
  SessionInfo,
  StrictStepResult,
  TraceEvent,
} from '../models';
import { FIXTURE_SETUP } from './roster';
import { buildSnapshot } from './buildSnapshot';
import type { MockScenarioBundle } from './types';
import { access, contractRef, present, revision, timelineEntry, unknownHandle } from './shared';

const SNAPSHOT_ID = 'mock-g-fc02-quarantine';
const LIVE_REVISION = revision(21, SNAPSHOT_ID);

/** Mirrors `LEGACY_REFRESH_FIXTURE_LABEL`, retained on the reference side only. */
export const LEGACY_REFRESH_FIXTURE_LABEL =
  'battle.ir.modifier.lifecycle_process_redd:Refresh';
export const CORRECTED_REFRESH_CONTRACT_ID = 'terra.modifier.refresh.corrected/1';
export const REPLACE_CONTRACT_ID = 'terra.modifier.replace/1';

const REFRESH_BLOCKERS: readonly string[] = [
  'missing Stacking remains UNKNOWN',
  'Refresh is distinct from Replace-family Count/OnReplace writes',
  'Layer is distinct from Count and application count',
  'provider identity is distinct from caster identity',
  'lifecycle callback/property ordering is unresolved',
];

const CORRECTED_REFRESH_CONTRACT = contractRef(
  CORRECTED_REFRESH_CONTRACT_ID,
  'terra.modifier',
  '1.0.0-draft',
  'NATIVE_EVIDENCED',
  ['fixture://contract_registry/corrected_refresh_slot'],
);

const REPLACE_CONTRACT = contractRef(
  REPLACE_CONTRACT_ID,
  'terra.modifier',
  '1.0.0-draft',
  'NATIVE_EVIDENCED',
  ['fixture://contract_registry/replace_slot'],
);

/**
 * FC-02 quarantine entries.
 *
 * Each entry binds an operation to its slot status and evidence mode. The UI
 * derives every badge from these values; nothing is hardcoded per modifier.
 */
export const QUARANTINE_ENTRIES: readonly QuarantineEntry[] = [
  {
    slot: {
      schema: 'terra_modifier_contract_slot/1',
      operation: 'Refresh',
      contractId: CORRECTED_REFRESH_CONTRACT_ID,
      evidenceMode: 'NATIVE_EVIDENCED',
      status: 'BLOCKED_NATIVE',
      blockers: REFRESH_BLOCKERS,
      legacyFixtureLabel: null,
    },
    reference: null,
    contractRef: CORRECTED_REFRESH_CONTRACT,
    rejection: {
      schema: 'structured_rejection/1',
      reasonCode: 'FC_02_REFRESH_NATIVE_QUARANTINED',
      obligationOwner: 'MODIFIER_REFRESH',
      evidenceRequest:
        'complete corrected Refresh contract with independent stacking, lifetime, source-role and lifecycle-hook bindings',
      contractRefs: [CORRECTED_REFRESH_CONTRACT],
      unknownHandles: [
        unknownHandle({
          blockerId: 'fc-02-refresh-stacking-order',
          ownerFamily: 'MODIFIER_LIFECYCLE',
          payload: {
            question: 'Modifier stacking order for Refresh remains unresolved.',
            contradicted_legacy_label: LEGACY_REFRESH_FIXTURE_LABEL,
          },
          provenance: {
            source: 'fixture://contract_registry/corrected_refresh_slot',
            content_version: '4.4.54',
            relation: 'CLOSE_VERSION',
          },
          requiredEvidence: [
            'EXACT_NATIVE Refresh stacking and lifetime trace for 4.4.54',
            'Source-role and lifecycle-hook bindings distinct from caster identity',
          ],
        }),
      ],
      diagnostics: {
        legacy_fixture_label: LEGACY_REFRESH_FIXTURE_LABEL,
        corrected_slot: CORRECTED_REFRESH_CONTRACT_ID,
        blockers: [...REFRESH_BLOCKERS],
      },
    },
  },
  {
    slot: {
      schema: 'terra_modifier_contract_slot/1',
      operation: 'Refresh',
      contractId: CORRECTED_REFRESH_CONTRACT_ID,
      evidenceMode: 'REFERENCE_MODEL',
      status: 'REFERENCE_ONLY',
      blockers: [],
      legacyFixtureLabel: LEGACY_REFRESH_FIXTURE_LABEL,
    },
    reference: {
      descriptorId: 'fc-02.legacy-refresh-reference',
      profile: {
        referenceId: 'fixture://reference_profile/legacy-refresh',
        evidenceMode: 'REFERENCE_MODEL',
        assumptions: ['legacy fixture label is retained verbatim', 'native_usable is False'],
        exclusions: ['no native execution', 'no GateCertificate'],
      },
      payload: {
        operation: 'Refresh',
        legacy_fixture_label: LEGACY_REFRESH_FIXTURE_LABEL,
        native_usable: false,
      },
    },
    contractRef: null,
    rejection: null,
  },
  {
    slot: {
      schema: 'terra_modifier_contract_slot/1',
      operation: 'Replace',
      contractId: REPLACE_CONTRACT_ID,
      evidenceMode: 'NATIVE_EVIDENCED',
      status: 'BLOCKED_NATIVE',
      blockers: ['separate Replace contract is required'],
      legacyFixtureLabel: null,
    },
    reference: null,
    contractRef: REPLACE_CONTRACT,
    rejection: null,
  },
];

const OBLIGATIONS: readonly DependencyObligation[] = [
  {
    schema: 'dependency_obligation/1',
    owner: 'MODIFIER_REFRESH',
    contractRef: CORRECTED_REFRESH_CONTRACT,
    evidenceMode: 'NATIVE_EVIDENCED',
    resolution: 'UNKNOWN',
    reads: [access('store:status_modifier_binding:*', present({ extent: 'declared' }))],
    writes: [],
    children: [],
    unknownHandles: QUARANTINE_ENTRIES[0]?.rejection?.unknownHandles ?? [],
  },
];

const BLOCKERS: readonly ClosureBlocker[] = [
  {
    // Real serialized value: "dependency_closure_blocker/1".
    schema: 'dependency_closure_blocker/1',
    status: 'BLOCKED_UNKNOWN',
    owner: 'MODIFIER_REFRESH',
    contractRef: CORRECTED_REFRESH_CONTRACT,
    unknownHandles: QUARANTINE_ENTRIES[0]?.rejection?.unknownHandles ?? [],
    occurrencePath: [0],
    evidenceRequest:
      'complete corrected Refresh contract; the legacy Refresh label is quarantined and cannot bind a native obligation',
  },
];

const REJECTION = QUARANTINE_ENTRIES[0]?.rejection ?? null;

const PREFLIGHT: PreflightResult = {
  schema: 'preflight_result/1',
  outcome: 'REJECTED',
  closure: {
    schema: 'dependency_closure/1',
    status: 'BLOCKED_UNKNOWN',
    obligations: OBLIGATIONS,
    blockers: BLOCKERS,
    allowedReads: [access('store:status_modifier_binding:*', present({ extent: 'declared' }))],
    allowedWrites: [],
  },
  rejections: REJECTION ? [REJECTION] : [],
};

const STRICT_STEP: StrictStepResult = {
  schema: 'terra_strict_step_result/1',
  outcome: 'REJECTED',
  resultingRevision: null,
  transactionIdentity: null,
  rejections: REJECTION ? [REJECTION] : [],
};

const SNAPSHOT = buildSnapshot({
  snapshotId: SNAPSHOT_ID,
  revisionCounter: 21,
  rngDrawPosition: 74,
  currentActorId: 'ally-cs',
  selectedTargetId: 'enemy-eg1',
  timeline: [
    timelineEntry(1, 'ORDINARY', 'CS-03 ordinary turn', 'ally-cs', 'NATIVE_EVIDENCED', { av: 0 }),
    timelineEntry(2, 'ACTION_TASK', 'Refresh lifecycle request (quarantined)', 'ally-cs', 'NATIVE_EVIDENCED', {
      av: 9,
      detail: 'BLOCKED_NATIVE: corrected Refresh contract is incomplete.',
    }),
    timelineEntry(3, 'ORDINARY', 'EG-01 ordinary turn', 'enemy-eg1', 'NATIVE_EVIDENCED', { av: 33 }),
  ],
});

const ACTIONS: readonly AvailableAction[] = [
  {
    id: 'act-fc02-refresh',
    label: 'Refresh (FC-02 quarantine)',
    actorId: 'ally-cs',
    actorName: 'Caster Unit',
    targetRule: { supplied: true, summary: 'Modifier lifecycle target', allowedTargetIds: ['ally-vg'] },
    evidenceMode: 'NATIVE_EVIDENCED',
    support: 'BLOCKED',
    preflightState: 'REJECTED',
    descriptorOnly: false,
    notes: [
      'Quarantine is modelled as registry data, not as a universal modifier rule.',
      'The same operation carries a separate REFERENCE_MODEL slot below.',
    ],
  },
];

const PREVIEWS: Readonly<Record<string, ActionPreview>> = {
  'act-fc02-refresh': {
    actionId: 'act-fc02-refresh',
    label: 'Refresh (FC-02 quarantine)',
    evidenceMode: 'NATIVE_EVIDENCED',
    support: 'BLOCKED',
    preflight: PREFLIGHT,
    certificate: {
      status: 'REFUSED',
      certificate: null,
      refusalReason:
        'Certificate refused: the Refresh obligation carries UNKNOWN resolution and an explicit UnknownHandle.',
      sealedAgainstRevision: null,
    },
    rejection: REJECTION,
    plan: null,
    delta: null,
    trace: null,
    rngDraws: [],
    diff: null,
    execution: null,
    strictStep: STRICT_STEP,
    transactionRng: null,
    notes: [
      'NATIVE_EVIDENCED Refresh shows BLOCKED / QUARANTINED.',
      'REFERENCE_MODEL Refresh shows REFERENCE ONLY — never promoted.',
      'The future corrected slot stays BLOCKED until its complete contract arrives.',
    ],
  },
};

const EXECUTIONS: Readonly<Record<string, ExecutionResult>> = {
  'act-fc02-refresh': {
    outcome: 'REJECTED',
    actionId: 'act-fc02-refresh',
    plan: null,
    delta: null,
    trace: null,
    rngDraws: [],
    commit: null,
    rejection: REJECTION,
    strictStep: STRICT_STEP,
    transactionRng: null,
    liveStateUnchanged: true,
    // The strict step supplies no before/after identity documents, so the UI
    // must NOT claim "live state unchanged" from the REJECTED outcome alone.
    revisionWindow: null,
    message:
      'FC_02_REFRESH_NATIVE_QUARANTINED. Strict step REJECTED; no before/after identity documents were supplied.',
  },
};

const EVENTS: readonly TraceEvent[] = [
  {
    id: 'ev-g-1',
    sequence: 1,
    timestamp: null,
    category: 'STATE',
    summary: `Snapshot ${SNAPSHOT_ID} loaded at revision r21.`,
    evidenceMode: 'NATIVE_EVIDENCED',
    raw: { snapshot_id: SNAPSHOT_ID, revision: 21, provenance: 'MOCK_DATA' },
  },
  {
    id: 'ev-g-2',
    sequence: 2,
    timestamp: null,
    category: 'BLOCKER',
    summary: 'Contract slot Refresh → BLOCKED_NATIVE (5 blockers).',
    evidenceMode: 'NATIVE_EVIDENCED',
    raw: { operation: 'Refresh', status: 'BLOCKED_NATIVE', blockers: REFRESH_BLOCKERS.length },
  },
  {
    id: 'ev-g-3',
    sequence: 3,
    timestamp: null,
    category: 'REFERENCE',
    summary: `Legacy label ${LEGACY_REFRESH_FIXTURE_LABEL} retained as REFERENCE_MODEL only.`,
    evidenceMode: 'REFERENCE_MODEL',
    raw: { legacy_fixture_label: LEGACY_REFRESH_FIXTURE_LABEL, native_usable: false },
  },
  {
    id: 'ev-g-4',
    sequence: 4,
    timestamp: null,
    category: 'ACTION',
    summary: 'StrictStepResult REJECTED · FC_02_REFRESH_NATIVE_QUARANTINED.',
    evidenceMode: 'NATIVE_EVIDENCED',
    raw: { outcome: 'REJECTED', reason_code: 'FC_02_REFRESH_NATIVE_QUARANTINED' },
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
  scenarioId: 'G',
  scenarioLabel: 'G · FC-02 quarantine',
  scenarioSummary:
    'Corrected Refresh slot BLOCKED_NATIVE, legacy label REFERENCE_MODEL only, separate Replace slot blocked.',
  stateRevisionCounter: 21,
  semanticHash: SNAPSHOT.semanticHash,
  rngDrawPosition: 74,
  transactionState: 'REJECTED',
  notes: [
    'DEMO / MOCK DATA — served by MockBattleBackendAdapter.',
    'Quarantine badges come from contract-slot data; no modifier rule is hardcoded.',
  ],
};

const DESCRIPTOR: ScenarioDescriptor = {
  id: 'G',
  label: 'G · FC-02 quarantine',
  summary: 'Modifier contract quarantine: blocked native, reference-only legacy label.',
  backendMode: 'NATIVE_EVIDENCED',
  category: 'QUARANTINE',
};

export const SCENARIO_G: MockScenarioBundle = {
  descriptor: DESCRIPTOR,
  session: SESSION,
  setup: FIXTURE_SETUP,
  snapshot: SNAPSHOT,
  actions: ACTIONS,
  previews: PREVIEWS,
  executions: EXECUTIONS,
  events: EVENTS,
  quarantine: QUARANTINE_ENTRIES,
};

export const SCENARIO_G_LIVE_REVISION = LIVE_REVISION;
