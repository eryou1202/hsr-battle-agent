/**
 * Mirrors the transaction staging surface:
 * `battle_sandbox.transaction`, `battle_sandbox.staged_trace`,
 * `battle_sandbox.transaction_rng`, `battle_sandbox.atomic_commit`.
 */
import type { JsonValue } from './json';
import type { ObligationAccess } from './preflight';
import type { StateRevision } from './state';
import type { StructuredRejection } from './rejection';
import type { StrictStepResult, TransactionRngDocument } from './strict';

export const TRANSACTION_PLAN_SCHEMA = 'terra_transaction_plan/1' as const;
export const TRANSACTION_OPERATION_SCHEMA = 'terra_transaction_operation/1' as const;
export const STAGED_DELTA_SCHEMA = 'terra_staged_delta/1' as const;
export const STAGED_TRACE_SCHEMA = 'terra_staged_trace/1' as const;
export const ATOMIC_COMMIT_RESULT_SCHEMA = 'terra_atomic_commit_result/1' as const;

export const STAGED_CHANNELS = ['TRACE', 'EVENT', 'QUEUE'] as const;
export type StagedChannel = (typeof STAGED_CHANNELS)[number];

/** One staged write occurrence. */
export interface StagedWrite {
  readonly kind: string;
  readonly target: string;
  readonly payload: JsonValue;
}

/** One staged record on the TRACE / EVENT / QUEUE channel. */
export interface StagedRecord {
  readonly channel: StagedChannel;
  readonly kind: string;
  readonly payload: JsonValue;
}

/** One staged RNG draw. Only ever displayed; never generated client-side. */
export interface StagedRngDraw {
  readonly sequence: number;
  readonly operationId: string | null;
  readonly draw: JsonValue;
}

/** Mirrors `TransactionOperation.to_dict()` — "terra_transaction_operation/1". */
export interface TransactionOperation {
  readonly schema: typeof TRANSACTION_OPERATION_SCHEMA;
  readonly operationId: string;
  readonly payload: JsonValue;
}

export interface TransactionPlan {
  readonly schema: typeof TRANSACTION_PLAN_SCHEMA;
  readonly operations: readonly TransactionOperation[];
  readonly certificateIdentity: string;
  readonly sourceRevision: StateRevision;
  readonly sourceStateHash: string;
  readonly allowedReads: readonly ObligationAccess[];
  readonly allowedWrites: readonly ObligationAccess[];
}

export interface StagedDelta {
  readonly schema: typeof STAGED_DELTA_SCHEMA;
  readonly planIdentity: string;
  readonly certificateIdentity: string;
  readonly sourceRevision: StateRevision;
  readonly sourceStateHash: string;
  readonly allowedWrites: readonly ObligationAccess[];
  readonly writes: readonly StagedWrite[];
  readonly storeNames: readonly string[];
}

export interface StagedTrace {
  readonly schema: typeof STAGED_TRACE_SCHEMA;
  readonly planIdentity: string;
  readonly certificateIdentity: string;
  readonly sourceStateHash: string;
  readonly allowedWrites: readonly ObligationAccess[];
  readonly records: readonly StagedRecord[];
  readonly discarded: boolean;
}

/**
 * Commit observation.
 *
 * `beforeRevision` / `afterRevision` are the live revisions OBSERVED around the
 * commit call. They are labelled as observations because `AtomicCommitResult`
 * itself does not carry them; the frontend never infers them from a rule.
 */
export interface AtomicCommitObservation {
  readonly schema: typeof ATOMIC_COMMIT_RESULT_SCHEMA;
  readonly planIdentity: string;
  readonly certificateIdentity: string;
  readonly beforeRevision: StateRevision;
  readonly afterRevision: StateRevision;
  readonly beforeStateHash: string;
  readonly afterStateHash: string;
  readonly records: readonly StagedRecord[];
  readonly liveStateChanged: boolean;
}

export const EXECUTION_OUTCOMES = [
  'COMMITTED',
  'REJECTED',
  'NO_OP',
  'UNSUPPORTED',
  'REFERENCE_ONLY',
  'NOT_PERFORMED',
] as const;

export type ExecutionOutcome = (typeof EXECUTION_OUTCOMES)[number];

/** Result of an execute request, as reported by the adapter. */
export interface ExecutionResult {
  readonly outcome: ExecutionOutcome;
  readonly actionId: string;
  readonly plan: TransactionPlan | null;
  readonly delta: StagedDelta | null;
  readonly trace: StagedTrace | null;
  readonly rngDraws: readonly StagedRngDraw[];
  readonly commit: AtomicCommitObservation | null;
  readonly rejection: StructuredRejection | null;
  /**
   * The strict step result, when the backend supplies one.
   * `null` means "not supplied" — the UI must not infer an outcome.
   */
  readonly strictStep: StrictStepResult | null;
  /** The private transaction RNG document, when supplied. */
  readonly transactionRng: TransactionRngDocument | null;
  /** True when the adapter reports live state was left untouched. */
  readonly liveStateUnchanged: boolean;
  /**
   * The observed revision window, when the backend supplied BOTH identity
   * documents around the step.
   *
   * `null` means the identities were not supplied, in which case the UI must
   * NOT claim "live state unchanged" — the word REJECTED alone is not evidence.
   */
  readonly revisionWindow: RevisionWindow | null;
  readonly message: string;
}

/** Before/after identity documents observed around one step. */
export interface RevisionWindow {
  readonly before: StateRevision;
  readonly after: StateRevision;
  readonly beforeHash: string | null;
  readonly afterHash: string | null;
}

/**
 * Whether a "live state unchanged" claim is backed by supplied documents.
 *
 * Presentation-level comparison of supplied serialized documents only.
 */
export function liveStateUnchangedVerified(result: ExecutionResult): boolean {
  const window = result.revisionWindow;
  if (!window) return false;
  const revisionsMatch =
    window.before.counter === window.after.counter &&
    window.before.snapshotId === window.after.snapshotId &&
    window.before.lineage === window.after.lineage;
  if (!revisionsMatch) return false;
  if (window.beforeHash !== null && window.afterHash !== null) {
    return window.beforeHash === window.afterHash;
  }
  return true;
}

/**
 * Deltas observed between the pre-commit and published documents.
 *
 * Every field is a comparison of SUPPLIED serialized documents, never a
 * derivation from battle rules.
 */
export interface CommitDeltas {
  readonly beforeRevision: StateRevision | null;
  readonly afterRevision: StateRevision | null;
  readonly revisionAdvanced: boolean | null;
  readonly rngDrawCount: number | null;
  readonly allocatorDeltaSupplied: boolean;
  readonly allocatorDelta: string | null;
  readonly stagedWriteCount: number | null;
  readonly eventCount: number | null;
  readonly queueWriteCount: number | null;
  readonly traceCount: number | null;
}

/** A minimal before/after state diff entry for the compact diff view. */
export interface StateDiffEntry {
  readonly field: string;
  readonly before: JsonValue;
  readonly after: JsonValue;
}

export interface StateDiff {
  readonly beforeRevision: StateRevision;
  readonly afterRevision: StateRevision;
  readonly entries: readonly StateDiffEntry[];
}
