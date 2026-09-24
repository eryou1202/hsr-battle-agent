/**
 * Strict execution pipeline models (G01-007 / G01-012 / G01-014).
 *
 * Mirrored read-only from:
 *   battle_sandbox.strict_executor   -> StrictStepResult   "terra_strict_step_result/1"
 *   battle_sandbox.transaction_rng   -> TransactionRng     "terra_transaction_rng/1"
 *   battle_sandbox.contract_registry -> ContractSlot       "terra_modifier_contract_slot/1"
 *   battle_sandbox.evidence_boundary -> ReferenceProfile / ReferenceDescriptor
 *
 * The frontend renders these documents verbatim. It never decides an outcome,
 * never promotes reference material and never computes a delta from battle
 * rules — only presentation-level comparison of supplied documents.
 */
import type { JsonValue } from './json';
import type { ContractRef, EvidenceMode } from './evidence';
import type { StructuredRejection } from './rejection';
import type { StateRevision } from './state';

export const STRICT_STEP_RESULT_SCHEMA = 'terra_strict_step_result/1' as const;
export const TRANSACTION_RNG_SCHEMA = 'terra_transaction_rng/1' as const;
export const CONTRACT_SLOT_SCHEMA = 'terra_modifier_contract_slot/1' as const;

/** Mirrors `STRICT_NO_OP_ACTION`. */
export const STRICT_NO_OP_ACTION = 'terra.strict.no_op/1' as const;

/** Mirrors `StrictStepOutcome`. Exactly three members; no truthiness. */
export const STRICT_STEP_OUTCOMES = ['COMMITTED', 'REJECTED', 'UNSUPPORTED'] as const;
export type StrictStepOutcome = (typeof STRICT_STEP_OUTCOMES)[number];

export function isStrictStepOutcome(value: unknown): value is StrictStepOutcome {
  return typeof value === 'string' && (STRICT_STEP_OUTCOMES as readonly string[]).includes(value);
}

/**
 * Mirrors `StrictStepResult.to_dict()`.
 *
 * `resulting_revision` and `transaction_identity` are non-null ONLY for
 * COMMITTED. The frontend must not read a revision out of a rejected result.
 */
export interface StrictStepResult {
  readonly schema: typeof STRICT_STEP_RESULT_SCHEMA;
  readonly outcome: StrictStepOutcome;
  readonly resultingRevision: StateRevision | null;
  readonly transactionIdentity: string | null;
  readonly rejections: readonly StructuredRejection[];
}

/** Mirrors `RngDraw.to_dict()`. Methods are exactly three. */
export const RNG_DRAW_METHODS = ['next_u64', 'randint', 'uniform'] as const;
export type RngDrawMethod = (typeof RNG_DRAW_METHODS)[number];

export interface RngDraw {
  readonly method: RngDrawMethod;
  readonly arguments: JsonValue;
  readonly result: JsonValue;
}

/** Mirrors `TransactionRng.to_dict()`. Private until an atomic commit consumes it. */
export interface TransactionRngDocument {
  readonly schema: typeof TRANSACTION_RNG_SCHEMA;
  readonly planIdentity: string;
  readonly certificateIdentity: string;
  readonly sourceRevision: StateRevision;
  readonly sourceStateHash: string;
  /** The sandbox Rng document, carried verbatim. */
  readonly rng: JsonValue;
  readonly ledger: readonly RngDraw[];
  readonly consumed: boolean;
}

/** Mirrors `ContractSlotStatus`. */
export const CONTRACT_SLOT_STATUSES = [
  'BLOCKED_NATIVE',
  'REFERENCE_ONLY',
  'SEPARATELY_CERTIFIED',
] as const;
export type ContractSlotStatus = (typeof CONTRACT_SLOT_STATUSES)[number];

export function isContractSlotStatus(value: unknown): value is ContractSlotStatus {
  return (
    typeof value === 'string' && (CONTRACT_SLOT_STATUSES as readonly string[]).includes(value)
  );
}

/**
 * Mirrors `ContractSlot.to_dict()` (FC-02 quarantine registry).
 *
 * This is availability RECORDING, not permission. `BLOCKED_NATIVE` is rendered
 * as blocked/quarantined; it is deliberately not modelled as a universal
 * modifier rule — the data decides, per operation.
 */
export interface ContractSlot {
  readonly schema: typeof CONTRACT_SLOT_SCHEMA;
  readonly operation: string;
  readonly contractId: string;
  readonly evidenceMode: EvidenceMode;
  readonly status: ContractSlotStatus;
  readonly blockers: readonly string[];
  readonly legacyFixtureLabel: string | null;
}

/** Mirrors `ReferenceProfile`. Never native. */
export interface ReferenceProfile {
  readonly referenceId: string;
  readonly evidenceMode: EvidenceMode;
  readonly assumptions: readonly string[];
  readonly exclusions: readonly string[];
}

/** Mirrors `ReferenceDescriptor`. Describes quarantined reference material. */
export interface ReferenceDescriptor {
  readonly descriptorId: string;
  readonly profile: ReferenceProfile;
  readonly payload: JsonValue;
}

/** One strict pipeline stage, for the end-to-end pipeline view. */
export const STRICT_PIPELINE_STAGES = [
  'REQUEST',
  'DEPENDENCY_OBLIGATION',
  'DEPENDENCY_CLOSURE',
  'PREFLIGHT_RESULT',
  'GATE_CERTIFICATE',
  'TRANSACTION_PLAN',
  'STAGED_DELTA',
  'TRANSACTION_RNG',
  'STAGED_TRACE',
  'ATOMIC_COMMIT',
  'STRICT_STEP_RESULT',
] as const;

export type StrictPipelineStageId = (typeof STRICT_PIPELINE_STAGES)[number];

/**
 * Stage state. `NOT_AVAILABLE` means the backend simply did not supply this
 * stage — the frontend never infers a transition from the previous stage.
 */
export const STRICT_STAGE_STATES = [
  'NOT_AVAILABLE',
  'READY',
  'BLOCKED',
  'REJECTED',
  'UNSUPPORTED',
  'COMMITTED',
] as const;

export type StrictStageState = (typeof STRICT_STAGE_STATES)[number];

export interface StrictStageView {
  readonly id: StrictPipelineStageId;
  readonly label: string;
  readonly state: StrictStageState;
  /** Why this state was assigned, in terms of the supplied document. */
  readonly basis: string;
  /** Document identity shown next to the stage, when supplied. */
  readonly identity: string | null;
  /** Raw document for the drawer, when supplied. */
  readonly document: JsonValue | null;
}

/** Contract reference carried on a quarantine slot, when supplied. */
export interface QuarantineEntry {
  readonly slot: ContractSlot;
  readonly reference: ReferenceDescriptor | null;
  readonly contractRef: ContractRef | null;
  readonly rejection: StructuredRejection | null;
}
