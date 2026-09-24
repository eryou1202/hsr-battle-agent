/**
 * Live backend adapter skeleton — explicitly NOT CONNECTED.
 *
 * The real backend API does not exist yet. This skeleton therefore does NOT
 * invent an HTTP contract: every method fails with an explicit
 * `BACKEND_NOT_CONNECTED` result so the UI can render its deliberate
 * "backend disconnected" state instead of a generic error.
 *
 * When a real contract is defined, the transport goes here and nowhere else.
 */
import type {
  ActionPreview,
  ActionRequest,
  AvailableAction,
  BattleSetup,
  BattleSnapshot,
  CloneInfo,
  ExecutionResult,
  QuarantineEntry,
  SessionInfo,
  TraceEvent,
} from '../models';
import type { BattleBackendAdapter } from './BattleBackendAdapter';

export class BackendNotConnectedError extends Error {
  readonly code = 'BACKEND_NOT_CONNECTED';

  constructor(method: string) {
    super(
      `${method} is unavailable: LiveBattleBackendAdapter is NOT_CONNECTED. ` +
        'No backend contract has been defined yet, so no request was made.',
    );
    this.name = 'BackendNotConnectedError';
  }
}

export interface LiveAdapterOptions {
  /** Reserved for a future transport endpoint. Unused while NOT_CONNECTED. */
  readonly baseUrl?: string;
}

export class LiveBattleBackendAdapter implements BattleBackendAdapter {
  readonly id = 'live-battle-backend';
  readonly kind = 'LIVE' as const;

  private readonly baseUrl: string | null;

  constructor(options: LiveAdapterOptions = {}) {
    this.baseUrl = options.baseUrl ?? null;
  }

  async getSessionInfo(): Promise<SessionInfo> {
    throw new BackendNotConnectedError('getSessionInfo');
  }

  async getBattleSnapshot(): Promise<BattleSnapshot | null> {
    throw new BackendNotConnectedError('getBattleSnapshot');
  }

  async getBattleSetup(): Promise<BattleSetup | null> {
    throw new BackendNotConnectedError('getBattleSetup');
  }

  async getAvailableActions(): Promise<readonly AvailableAction[]> {
    throw new BackendNotConnectedError('getAvailableActions');
  }

  async previewAction(_request: ActionRequest): Promise<ActionPreview | null> {
    throw new BackendNotConnectedError('previewAction');
  }

  async executeAction(_request: ActionRequest): Promise<ExecutionResult> {
    throw new BackendNotConnectedError('executeAction');
  }

  async getTraceEvents(): Promise<readonly TraceEvent[]> {
    throw new BackendNotConnectedError('getTraceEvents');
  }

  async getQuarantineEntries(): Promise<readonly QuarantineEntry[]> {
    throw new BackendNotConnectedError('getQuarantineEntries');
  }

  async reset(): Promise<SessionInfo> {
    throw new BackendNotConnectedError('reset');
  }

  cloneInfo(): CloneInfo {
    return {
      adapterId: this.id,
      adapterKind: 'LIVE',
      implementation: 'LiveBattleBackendAdapter (NOT_CONNECTED skeleton)',
      contractStatus: 'NOT_CONNECTED',
      supportedMethods: [],
      unsupportedMethods: [
        'getSessionInfo',
        'getBattleSnapshot',
        'getBattleSetup',
        'getAvailableActions',
        'previewAction',
        'executeAction',
        'getTraceEvents',
        'reset',
      ],
      note: this.baseUrl
        ? `Configured base URL ${this.baseUrl} is recorded but unused: no backend contract exists yet.`
        : 'No backend contract has been defined. This adapter intentionally makes no request and invents no endpoint.',
    };
  }
}

export function createLiveAdapter(options: LiveAdapterOptions = {}): LiveBattleBackendAdapter {
  return new LiveBattleBackendAdapter(options);
}
