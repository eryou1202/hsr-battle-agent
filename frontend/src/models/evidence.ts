/**
 * Evidence vocabulary mirrored from `hsr_battle_agent.battle_ir.evidence`.
 *
 * This is a PRESENTATION mirror of the serialized backend vocabulary. It carries
 * no executability claim: `NATIVE_EVIDENCED` here is a provenance label to
 * render, never a permission discovered or granted by the frontend.
 */
import type { JsonValue } from './json';

export const CONTRACT_REF_SCHEMA = 'contract_ref/1' as const;
export const UNKNOWN_HANDLE_SCHEMA = 'unknown_handle/1' as const;
export const PRESENCE_VALUE_SCHEMA = 'presence_value/1' as const;

/** Mirrors `EvidenceMode`. Order is the serialized declaration order. */
export const EVIDENCE_MODES = [
  'NATIVE_EVIDENCED',
  'REFERENCE_MODEL',
  'SANDBOX_EXTENSION',
  'UNSUPPORTED',
] as const;

export type EvidenceMode = (typeof EVIDENCE_MODES)[number];

export function isEvidenceMode(value: unknown): value is EvidenceMode {
  return typeof value === 'string' && (EVIDENCE_MODES as readonly string[]).includes(value);
}

/** Mirrors `VersionRelation`. Absence is NOT modelled as a member. */
export type VersionRelation = 'EXACT_NATIVE' | 'CLOSE_VERSION';

/** Mirrors `ReadinessClass` — a distinct type from `EvidenceMode` on purpose. */
export const READINESS_CLASSES = [
  'SAFE_TO_IMPLEMENT',
  'SAFE_TO_REPRESENT_ONLY',
  'SAFE_REFERENCE_MODEL_ONLY',
  'STRICT_REJECT_UNTIL_NEW_EVIDENCE',
] as const;

export type ReadinessClass = (typeof READINESS_CLASSES)[number];

/**
 * Mirrors `PresenceValue.to_dict()`:
 * `{ schema, presence: "PRESENT" | "ABSENT" | "NULL", value? }`.
 *
 * ABSENT / NULL / PRESENT(empty) stay three distinguishable facts. The frontend
 * must never collapse them into "falsy".
 */
export type Presence =
  | { readonly kind: 'PRESENT'; readonly value: JsonValue }
  | { readonly kind: 'ABSENT' }
  | { readonly kind: 'NULL' };

export interface PresenceDocument {
  readonly schema: typeof PRESENCE_VALUE_SCHEMA;
  readonly presence: 'PRESENT' | 'ABSENT' | 'NULL';
  readonly value?: JsonValue;
}

export function presenceFromDocument(document: PresenceDocument): Presence {
  switch (document.presence) {
    case 'PRESENT':
      return { kind: 'PRESENT', value: document.value ?? null };
    case 'ABSENT':
      return { kind: 'ABSENT' };
    case 'NULL':
      return { kind: 'NULL' };
    default:
      throw new Error(`unknown presence state: ${String(document.presence)}`);
  }
}

/** Mirrors `ContractRef.to_dict()`. */
export interface ContractRef {
  readonly schema: typeof CONTRACT_REF_SCHEMA;
  readonly contractId: string;
  readonly namespace: string;
  readonly schemaVersion: string;
  readonly evidenceMode: EvidenceMode;
  readonly contentSha256: string;
  readonly sourceRefs: readonly string[];
}

/** Audit-only identity string, mirroring `ContractRef.identity()`. */
export function contractIdentity(ref: ContractRef): string {
  return `${ref.namespace}:${ref.contractId}@${ref.schemaVersion}`;
}

/**
 * Mirrors `UnknownHandle.to_dict()`.
 *
 * A handle is unresolved by definition. The frontend renders it and never
 * attempts to resolve, substitute or default it.
 */
export interface UnknownHandle {
  readonly schema: typeof UNKNOWN_HANDLE_SCHEMA;
  readonly blockerId: string;
  readonly ownerFamily: string;
  readonly payload: JsonValue;
  readonly provenance: JsonValue;
  readonly requiredEvidence: readonly string[];
}
