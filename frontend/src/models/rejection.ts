/**
 * Mirrors `hsr_battle_agent.battle_sandbox.errors.StructuredRejection`.
 */
import type { JsonValue } from './json';
import type { ContractRef, UnknownHandle } from './evidence';

export const REJECTION_SCHEMA = 'structured_rejection/1' as const;

export interface StructuredRejection {
  readonly schema: typeof REJECTION_SCHEMA;
  readonly reasonCode: string;
  readonly obligationOwner: string;
  readonly evidenceRequest: string;
  readonly contractRefs: readonly ContractRef[];
  readonly unknownHandles: readonly UnknownHandle[];
  /** Diagnostics are excluded from backend identity; rendered verbatim here. */
  readonly diagnostics: Readonly<Record<string, JsonValue>>;
}

/** Mirrors `StructuredRejection.describe()` — display only, never identity. */
export function describeRejection(rejection: StructuredRejection): string {
  return `${rejection.reasonCode}: owned by ${rejection.obligationOwner}; requires ${rejection.evidenceRequest}`;
}
