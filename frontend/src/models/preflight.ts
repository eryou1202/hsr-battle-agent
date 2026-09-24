/**
 * Mirrors the G01 dependency-closure / preflight representations:
 * `battle_sandbox.preflight` and `battle_sandbox.dependency_graph`.
 *
 * Nothing here is execution permission. `resolution: "RESOLVED"` is rendered as
 * the obligation recording itself closed — the frontend does not treat it as a
 * gate outcome and never auto-promotes `REFERENCE_MODEL` material.
 */
import type { JsonValue } from './json';
import type { ContractRef, EvidenceMode, Presence, UnknownHandle } from './evidence';
import type { StructuredRejection } from './rejection';

export const OBLIGATION_ACCESS_SCHEMA = 'obligation_access/1' as const;
export const CHILD_OBLIGATION_REF_SCHEMA = 'child_obligation_ref/1' as const;
export const DEPENDENCY_OBLIGATION_SCHEMA = 'dependency_obligation/1' as const;
/**
 * Mirrors `dependency_graph.CLOSURE_BLOCKER_SCHEMA`.
 * NOTE: the serialized value is "dependency_closure_blocker/1", not a bare
 * "closure_blocker/1" — the frontend must match the real document.
 */
export const CLOSURE_BLOCKER_SCHEMA = 'dependency_closure_blocker/1' as const;
export const DEPENDENCY_CLOSURE_SCHEMA = 'dependency_closure/1' as const;
export const PREFLIGHT_RESULT_SCHEMA = 'preflight_result/1' as const;

/** Mirrors `ObligationResolution`. */
export const OBLIGATION_RESOLUTIONS = ['RESOLVED', 'UNKNOWN', 'UNSUPPORTED'] as const;
export type ObligationResolution = (typeof OBLIGATION_RESOLUTIONS)[number];

export function isObligationResolution(value: unknown): value is ObligationResolution {
  return (
    typeof value === 'string' && (OBLIGATION_RESOLUTIONS as readonly string[]).includes(value)
  );
}

/** Mirrors `ClosureStatus`. */
export const CLOSURE_STATUSES = [
  'CLOSED',
  'BLOCKED_MISSING',
  'BLOCKED_UNKNOWN',
  'BLOCKED_UNSUPPORTED',
  'BLOCKED_CYCLE',
  'BLOCKED_UNBOUNDED',
] as const;
export type ClosureStatus = (typeof CLOSURE_STATUSES)[number];

export function isClosureStatus(value: unknown): value is ClosureStatus {
  return typeof value === 'string' && (CLOSURE_STATUSES as readonly string[]).includes(value);
}

/** Mirrors `PreflightOutcome`. */
export const PREFLIGHT_OUTCOMES = ['CLOSED', 'REJECTED'] as const;
export type PreflightOutcome = (typeof PREFLIGHT_OUTCOMES)[number];

/** One declared read or write of a named dependency. */
export interface ObligationAccess {
  readonly schema: typeof OBLIGATION_ACCESS_SCHEMA;
  readonly target: string;
  readonly extent: Presence;
}

/** A reference to a child obligation — not the obligation itself. */
export interface ChildObligationRef {
  readonly schema: typeof CHILD_OBLIGATION_REF_SCHEMA;
  readonly owner: string;
  readonly contractRef: ContractRef;
}

/** One dependency obligation. Representation only. */
export interface DependencyObligation {
  readonly schema: typeof DEPENDENCY_OBLIGATION_SCHEMA;
  readonly owner: string;
  readonly contractRef: ContractRef;
  readonly evidenceMode: EvidenceMode;
  readonly resolution: ObligationResolution;
  readonly reads: readonly ObligationAccess[];
  readonly writes: readonly ObligationAccess[];
  readonly children: readonly ChildObligationRef[];
  readonly unknownHandles: readonly UnknownHandle[];
}

/** One blocking occurrence found by the conservative traversal. */
export interface ClosureBlocker {
  readonly schema: typeof CLOSURE_BLOCKER_SCHEMA;
  readonly status: ClosureStatus;
  readonly owner: string;
  readonly contractRef: ContractRef;
  readonly unknownHandles: readonly UnknownHandle[];
  /** Traversal path. Rendered verbatim; never re-ordered by the frontend. */
  readonly occurrencePath: readonly number[];
  readonly evidenceRequest: string;
}

/** Complete conservative traversal result. */
export interface DependencyClosure {
  readonly schema: typeof DEPENDENCY_CLOSURE_SCHEMA;
  readonly status: ClosureStatus;
  readonly obligations: readonly DependencyObligation[];
  readonly blockers: readonly ClosureBlocker[];
  readonly allowedReads: readonly ObligationAccess[];
  readonly allowedWrites: readonly ObligationAccess[];
}

/** Complete preflight result: closure plus either zero or every rejection. */
export interface PreflightResult {
  readonly schema: typeof PREFLIGHT_RESULT_SCHEMA;
  readonly outcome: PreflightOutcome;
  readonly closure: DependencyClosure;
  readonly rejections: readonly StructuredRejection[];
}

/** Frontend display helper: is this closure status a blocked one? */
export function isBlockedClosure(status: ClosureStatus): boolean {
  return status !== 'CLOSED';
}

export function formatOccurrencePath(path: readonly number[]): string {
  return path.length === 0 ? '(root)' : path.join(' → ');
}

export function formatExtent(extent: Presence): string {
  switch (extent.kind) {
    case 'ABSENT':
      return 'ABSENT (declared at target level, no extent stated)';
    case 'NULL':
      return 'NULL (extent stated as null)';
    case 'PRESENT':
      return `PRESENT ${JSON.stringify(extent.value)}`;
    default:
      return 'UNKNOWN EXTENT';
  }
}

export function summarizeJson(value: JsonValue, max = 120): string {
  const text = JSON.stringify(value);
  if (text === undefined) return '(unserializable)';
  return text.length <= max ? text : `${text.slice(0, max - 1)}…`;
}
