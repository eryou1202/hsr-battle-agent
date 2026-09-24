/**
 * Frontend-facing action descriptors.
 *
 * The frontend NEVER derives legality. `support` is whatever the adapter reports.
 * When the adapter does not report a support state the value is `UNKNOWN` and the
 * UI shows an honest unsupported/unknown state — it must not fall back to
 * "AVAILABLE" just because a descriptor exists.
 */
import type { EvidenceMode } from './evidence';
import type { CertificateView } from './certificate';
import type {
  ExecutionResult,
  StateDiff,
  StagedDelta,
  StagedRngDraw,
  StagedTrace,
  TransactionPlan,
} from './transaction';
import type { PreflightResult } from './preflight';
import type { StructuredRejection } from './rejection';
import type { StrictStepResult, TransactionRngDocument } from './strict';

/** Support state reported by the adapter for one action. */
export const ACTION_SUPPORT_STATES = [
  'AVAILABLE',
  'BLOCKED',
  'UNKNOWN',
  'UNSUPPORTED',
  'REFERENCE_ONLY',
  'COMMITTED',
] as const;

export type ActionSupportState = (typeof ACTION_SUPPORT_STATES)[number];

/** Preflight state reported by the adapter for one action. */
export const PREFLIGHT_STATES = [
  'NOT_RUN',
  'CLOSED',
  'REJECTED',
  'UNKNOWN',
  'UNSUPPORTED',
  'STALE',
] as const;

export type PreflightState = (typeof PREFLIGHT_STATES)[number];

/** Target rule summary. `supplied: false` means the adapter stated nothing. */
export interface TargetRuleSummary {
  readonly supplied: boolean;
  readonly summary: string | null;
  readonly allowedTargetIds: readonly string[] | null;
}

export interface AvailableAction {
  readonly id: string;
  readonly label: string;
  readonly actorId: string;
  readonly actorName: string;
  readonly targetRule: TargetRuleSummary;
  readonly evidenceMode: EvidenceMode;
  readonly support: ActionSupportState;
  readonly preflightState: PreflightState;
  /** True when only a descriptor exists and no legal-action support is supplied. */
  readonly descriptorOnly: boolean;
  readonly notes: readonly string[];
}

export interface ActionRequest {
  readonly actionId: string;
  readonly targetId: string | null;
}

/** Everything the inspector needs to answer "why can or can't this execute?". */
export interface ActionPreview {
  readonly actionId: string;
  readonly label: string;
  readonly evidenceMode: EvidenceMode;
  readonly support: ActionSupportState;
  readonly preflight: PreflightResult | null;
  readonly certificate: CertificateView;
  readonly rejection: StructuredRejection | null;
  readonly plan: TransactionPlan | null;
  readonly delta: StagedDelta | null;
  readonly trace: StagedTrace | null;
  readonly rngDraws: readonly StagedRngDraw[];
  readonly diff: StateDiff | null;
  readonly execution: ExecutionResult | null;
  /** Strict step result supplied alongside the preview, when available. */
  readonly strictStep: StrictStepResult | null;
  /** Private transaction RNG document, when supplied. */
  readonly transactionRng: TransactionRngDocument | null;
  readonly notes: readonly string[];
}
