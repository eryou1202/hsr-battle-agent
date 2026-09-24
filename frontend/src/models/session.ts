/**
 * Session / connection / scenario metadata shown in the top status bar.
 *
 * `backendMode` is a deliberately loud label. The frontend must never show
 * `NATIVE_EVIDENCED` merely because data happens to be available.
 */
import type { EvidenceMode } from './evidence';

/**
 * Transport + evidence mode of the data source.
 *
 * `MOCK` is a transport fact (fixture data). The remaining members are the
 * serialized `EvidenceMode` vocabulary. They are kept in ONE badge type so the
 * status bar cannot accidentally show a native-looking badge for mock data.
 */
export const BACKEND_MODES = [
  'MOCK',
  'REFERENCE_MODEL',
  'NATIVE_EVIDENCED',
  'SANDBOX_EXTENSION',
  'UNSUPPORTED',
] as const;

export type BackendMode = (typeof BACKEND_MODES)[number];

export function isBackendMode(value: unknown): value is BackendMode {
  return typeof value === 'string' && (BACKEND_MODES as readonly string[]).includes(value);
}

/** `MOCK` is the only transport-level mode; the rest are evidence modes. */
export function isEvidenceBackendMode(mode: BackendMode): mode is Exclude<BackendMode, 'MOCK'> {
  return mode !== 'MOCK';
}

export function backendModeToEvidenceMode(mode: Exclude<BackendMode, 'MOCK'>): EvidenceMode {
  return mode;
}

export const CONNECTION_STATUSES = [
  'CONNECTED',
  'NOT_CONNECTED',
  'DEGRADED',
  'UNKNOWN',
] as const;

export type ConnectionStatus = (typeof CONNECTION_STATUSES)[number];

export const TRANSACTION_STATES = [
  'NO_TRANSACTION',
  'IDLE',
  'PLANNED',
  'STAGED',
  'COMMITTED',
  'REJECTED',
  'UNSUPPORTED',
  'REFERENCE_ONLY',
] as const;

export type TransactionState = (typeof TRANSACTION_STATES)[number];

export const DATA_PROVENANCES = ['MOCK_DATA', 'LIVE'] as const;
export type DataProvenance = (typeof DATA_PROVENANCES)[number];

export interface SessionInfo {
  readonly adapterId: string;
  readonly adapterLabel: string;
  readonly adapterKind: 'MOCK' | 'LIVE';
  readonly contentVersion: string;
  readonly backendMode: BackendMode;
  readonly connection: ConnectionStatus;
  readonly connectionDetail: string;
  readonly dataProvenance: DataProvenance;
  readonly scenarioId: string;
  readonly scenarioLabel: string;
  readonly scenarioSummary: string;
  readonly stateRevisionCounter: number;
  readonly semanticHash: string;
  readonly rngDrawPosition: number | null;
  readonly transactionState: TransactionState;
  readonly notes: readonly string[];
}

/** Adapter self-description, exposed through `cloneInfo()`. */
export interface CloneInfo {
  readonly adapterId: string;
  readonly adapterKind: 'MOCK' | 'LIVE';
  readonly implementation: string;
  readonly contractStatus: 'MOCK_ONLY' | 'NOT_CONNECTED' | 'CONNECTED';
  readonly supportedMethods: readonly string[];
  readonly unsupportedMethods: readonly string[];
  readonly note: string;
}

export interface ScenarioDescriptor {
  readonly id: string;
  readonly label: string;
  readonly summary: string;
  readonly backendMode: BackendMode;
  readonly category:
    | 'CLOSED_NOOP'
    | 'UNKNOWN'
    | 'UNSUPPORTED'
    | 'REFERENCE_MODEL'
    | 'STALE_REVISION'
    | 'COMMIT'
    | 'QUARANTINE';
}
