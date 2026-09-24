/** Evidence drawer payload. One uniform record shape for every inspectable item. */
import type { EvidenceMode } from './evidence';
import type { JsonValue } from './json';

export type EvidenceRecordKind =
  | 'CONTRACT'
  | 'UNKNOWN_HANDLE'
  | 'CLOSURE_BLOCKER'
  | 'CERTIFICATE'
  | 'REJECTION'
  | 'STATE'
  | 'ACTION'
  | 'STAGED_RECORD'
  | 'RNG_DRAW';

export interface EvidenceRecord {
  readonly kind: EvidenceRecordKind;
  readonly title: string;
  readonly evidenceMode: EvidenceMode | null;
  readonly contractId: string | null;
  readonly namespace: string | null;
  readonly contractRevision: string | null;
  readonly sourceRefs: readonly string[];
  /** Human-readable revision context, or null when not applicable. */
  readonly revisionLabel: string | null;
  readonly ownerLabel: string | null;
  readonly raw: JsonValue;
}

export function evidenceRecord(
  kind: EvidenceRecordKind,
  title: string,
  raw: JsonValue,
  extra: Partial<Omit<EvidenceRecord, 'kind' | 'title' | 'raw'>> = {},
): EvidenceRecord {
  return {
    kind,
    title,
    evidenceMode: extra.evidenceMode ?? null,
    contractId: extra.contractId ?? null,
    namespace: extra.namespace ?? null,
    contractRevision: extra.contractRevision ?? null,
    sourceRefs: extra.sourceRefs ?? [],
    revisionLabel: extra.revisionLabel ?? null,
    ownerLabel: extra.ownerLabel ?? null,
    raw,
  };
}
