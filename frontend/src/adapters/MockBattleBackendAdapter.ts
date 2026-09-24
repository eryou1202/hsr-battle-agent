/**
 * Deterministic in-process mock adapter.
 *
 * Serves the fixtures under `src/fixtures`. Every response is explicitly marked
 * as MOCK DATA; the UI is required to label it as such and must never present it
 * as live native execution.
 *
 * The adapter performs NO semantic work: it looks up pre-built fixture documents
 * and returns them. It does not compute damage, turn order, target legality or
 * RNG behaviour.
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
  TransactionState,
} from '../models';
import type { BattleBackendAdapter } from './BattleBackendAdapter';
import type { MockScenarioBundle } from '../fixtures/types';
import { MOCK_SCENARIOS, findMockScenario } from '../fixtures';

const SUPPORTED_METHODS: readonly string[] = [
  'getSessionInfo',
  'getBattleSnapshot',
  'getBattleSetup',
  'getAvailableActions',
  'previewAction',
  'executeAction',
  'getTraceEvents',
  'reset',
  'cloneInfo',
];

export interface MockAdapterOptions {
  /** Scenario id to load initially. Defaults to the first fixture. */
  readonly scenarioId?: string;
}

export class MockBattleBackendAdapter implements BattleBackendAdapter {
  readonly id = 'mock-battle-backend';
  readonly kind = 'MOCK' as const;

  private scenario: MockScenarioBundle;
  private executionCount = 0;

  constructor(options: MockAdapterOptions = {}) {
    const initial =
      (options.scenarioId ? findMockScenario(options.scenarioId) : null) ?? MOCK_SCENARIOS[0] ?? null;
    if (!initial) {
      throw new Error('MockBattleBackendAdapter requires at least one fixture scenario');
    }
    this.scenario = initial;
  }

  /** Load a different fixture scenario. Resets execution history. */
  loadScenario(scenarioId: string): boolean {
    const next = findMockScenario(scenarioId);
    if (!next) return false;
    this.scenario = next;
    this.executionCount = 0;
    return true;
  }

  getLoadedScenarioId(): string {
    return this.scenario.descriptor.id;
  }

  async getSessionInfo(): Promise<SessionInfo> {
    return this.session();
  }

  async getBattleSnapshot(): Promise<BattleSnapshot | null> {
    return this.scenario.snapshot;
  }

  async getBattleSetup(): Promise<BattleSetup | null> {
    return this.scenario.setup;
  }

  async getAvailableActions(): Promise<readonly AvailableAction[]> {
    return this.scenario.actions;
  }

  async previewAction(request: ActionRequest): Promise<ActionPreview | null> {
    return this.scenario.previews[request.actionId] ?? null;
  }

  async executeAction(request: ActionRequest): Promise<ExecutionResult> {
    this.executionCount += 1;
    const execution = this.scenario.executions[request.actionId] ?? null;
    if (!execution) {
      return {
        outcome: 'NOT_PERFORMED',
        actionId: request.actionId,
        plan: null,
        delta: null,
        trace: null,
        rngDraws: [],
        commit: null,
        rejection: null,
        strictStep: null,
        transactionRng: null,
        liveStateUnchanged: true,
        revisionWindow: null,
        message:
          'The adapter supplied no execution record for this action. Nothing was performed and live state is unchanged.',
      };
    }
    return execution;
  }

  async getTraceEvents(): Promise<readonly TraceEvent[]> {
    return this.scenario.events;
  }

  async getQuarantineEntries(): Promise<readonly QuarantineEntry[]> {
    return this.scenario.quarantine ?? [];
  }

  async reset(): Promise<SessionInfo> {
    this.executionCount = 0;
    return this.session();
  }

  cloneInfo(): CloneInfo {
    return {
      adapterId: this.id,
      adapterKind: 'MOCK',
      implementation: 'MockBattleBackendAdapter (in-process fixtures)',
      contractStatus: 'MOCK_ONLY',
      supportedMethods: SUPPORTED_METHODS,
      unsupportedMethods: [],
      note:
        'Deterministic fixture data for UI development. No live backend is attached and no battle semantics are evaluated.',
    };
  }

  private session(): SessionInfo {
    const base = this.scenario.session;
    const transactionState = this.transactionState();
    return { ...base, transactionState };
  }

  private transactionState(): TransactionState {
    if (this.executionCount === 0) return this.scenario.session.transactionState;
    const firstAction = this.scenario.actions[0];
    if (!firstAction) return this.scenario.session.transactionState;
    const execution = this.scenario.executions[firstAction.id];
    if (!execution) return this.scenario.session.transactionState;
    switch (execution.outcome) {
      case 'COMMITTED':
        return 'COMMITTED';
      case 'REJECTED':
        return 'REJECTED';
      case 'UNSUPPORTED':
        return 'UNSUPPORTED';
      case 'REFERENCE_ONLY':
        return 'REFERENCE_ONLY';
      case 'NO_OP':
      case 'NOT_PERFORMED':
      default:
        return 'IDLE';
    }
  }
}

export function createMockAdapter(options: MockAdapterOptions = {}): MockBattleBackendAdapter {
  return new MockBattleBackendAdapter(options);
}
