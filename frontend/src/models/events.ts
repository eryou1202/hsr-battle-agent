/**
 * Event / trace console entries.
 *
 * Timestamps are only ever rendered when the source supplies one. The frontend
 * does not synthesise wall-clock timestamps for records that lack them.
 */
import type { JsonValue } from './json';
import type { EvidenceMode } from './evidence';

export const EVENT_CATEGORIES = [
  'ALL',
  'STATE',
  'ACTION',
  'PREFLIGHT',
  'BLOCKER',
  'RNG',
  'QUEUE',
  'COMMIT',
  'REFERENCE',
] as const;

export type EventCategory = (typeof EVENT_CATEGORIES)[number];

/** Categories that can appear on a record (ALL is a filter, not a record value). */
export const RECORD_CATEGORIES = [
  'STATE',
  'ACTION',
  'PREFLIGHT',
  'BLOCKER',
  'RNG',
  'QUEUE',
  'COMMIT',
  'REFERENCE',
] as const;

export type RecordCategory = (typeof RECORD_CATEGORIES)[number];

export interface TraceEvent {
  readonly id: string;
  /** Sequence number when the source supplies one. */
  readonly sequence: number | null;
  /** Timestamp string when the source supplies one; otherwise null. */
  readonly timestamp: string | null;
  readonly category: RecordCategory;
  readonly summary: string;
  readonly evidenceMode: EvidenceMode | null;
  readonly raw: JsonValue;
}

export function isRecordCategory(value: unknown): value is RecordCategory {
  return typeof value === 'string' && (RECORD_CATEGORIES as readonly string[]).includes(value);
}
