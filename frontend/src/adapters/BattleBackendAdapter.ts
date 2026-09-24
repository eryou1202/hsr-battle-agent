/**
 * Frontend-facing backend contract.
 *
 * This is an ADAPTER BOUNDARY, not a production HTTP contract. The real backend
 * API does not exist yet, so nothing here invents endpoints, verbs or payload
 * envelopes. Implementations are expected to be either:
 *
 *   - `MockBattleBackendAdapter`  — deterministic fixture data, labelled MOCK
 *   - `LiveBattleBackendAdapter`  — explicit NOT_CONNECTED skeleton
 *
 * The frontend owns presentation and orchestration only. No method here asks the
 * frontend to compute battle semantics.
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

export interface BattleBackendAdapter {
  /** Stable adapter identifier, rendered in the status bar. */
  readonly id: string;

  /** `MOCK` or `LIVE`. Drives the DEMO / MOCK DATA labelling. */
  readonly kind: 'MOCK' | 'LIVE';

  /** Session, connection and mode metadata for the status bar. */
  getSessionInfo(): Promise<SessionInfo>;

  /** Current battle snapshot, or `null` when no scenario is loaded. */
  getBattleSnapshot(): Promise<BattleSnapshot | null>;

  /** Battle setup presentation data (team / enemies / scenario / loadout / mode). */
  getBattleSetup(): Promise<BattleSetup | null>;

  /**
   * Action descriptors with the support state as reported by the backend.
   *
   * An empty array means the backend supplied no legal-action support — the UI
   * must show an honest empty/unsupported state rather than invent one.
   */
  getAvailableActions(): Promise<readonly AvailableAction[]>;

  /**
   * Preflight / evidence / certificate inspection for one action.
   *
   * Returns `null` when the adapter cannot supply a preview.
   */
  previewAction(request: ActionRequest): Promise<ActionPreview | null>;

  /**
   * Request execution of one action.
   *
   * The adapter reports the outcome. The frontend never decides whether an
   * action "should" execute.
   */
  executeAction(request: ActionRequest): Promise<ExecutionResult>;

  /** Trace / event records for the bottom console. */
  getTraceEvents(): Promise<readonly TraceEvent[]>;

  /**
   * FC-02 contract quarantine slots (G01-014), when the backend supplies any.
   *
   * Empty array is a valid answer; it is not an error.
   */
  getQuarantineEntries(): Promise<readonly QuarantineEntry[]>;

  /** Reset the session back to its initial scenario state. */
  reset(): Promise<SessionInfo>;

  /** Adapter self-description, including which methods are unsupported. */
  cloneInfo(): CloneInfo;
}
