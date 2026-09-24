import type {
  ActionPreview,
  AvailableAction,
  BattleSetup,
  BattleSnapshot,
  ExecutionResult,
  QuarantineEntry,
  ScenarioDescriptor,
  SessionInfo,
  TraceEvent,
} from '../models';

/** One complete deterministic mock scenario bundle. */
export interface MockScenarioBundle {
  readonly descriptor: ScenarioDescriptor;
  readonly session: SessionInfo;
  readonly setup: BattleSetup;
  readonly snapshot: BattleSnapshot;
  readonly actions: readonly AvailableAction[];
  /** Previews keyed by action id. */
  readonly previews: Readonly<Record<string, ActionPreview>>;
  /** Execution outcomes keyed by action id. */
  readonly executions: Readonly<Record<string, ExecutionResult>>;
  readonly events: readonly TraceEvent[];
  /** FC-02 contract quarantine slots, when the scenario supplies them. */
  readonly quarantine?: readonly QuarantineEntry[];
}
