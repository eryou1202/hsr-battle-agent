/** Display formatting helpers. Pure functions, no battle semantics. */
import type { JsonValue } from '../models';

export function abbreviateMiddle(value: string, head = 10, tail = 4): string {
  if (value.length <= head + tail + 1) return value;
  return `${value.slice(0, head)}…${value.slice(-tail)}`;
}

/** Strip a `scheme:` prefix before abbreviating a digest-like string. */
export function shortDigest(value: string, head = 12, tail = 6): string {
  const separator = value.indexOf(':');
  const body = separator > 0 && separator < 40 ? value.slice(separator + 1) : value;
  return abbreviateMiddle(body, head, tail);
}

export function digestPrefix(value: string): string | null {
  const separator = value.indexOf(':');
  return separator > 0 && separator < 40 ? value.slice(0, separator) : null;
}

export function formatCounter(counter: number): string {
  return `r${counter}`;
}

export function formatNullableNumber(value: number | null): string {
  return value === null ? '—' : String(value);
}

export function formatList(values: readonly string[], empty = 'none'): string {
  return values.length === 0 ? empty : values.join(', ');
}

export function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

/** Stable stringify for raw-JSON display; never used for identity. */
export function stableJson(value: unknown): string {
  return JSON.stringify(value, replacer, 2) ?? '(unserializable)';

  function replacer(_key: string, inner: unknown): unknown {
    if (typeof inner === 'bigint') return inner.toString();
    return inner;
  }
}

export function truncateText(value: string, max: number): string {
  return value.length <= max ? value : `${value.slice(0, max - 1)}…`;
}

/**
 * Display-only JSON projection of a structured record.
 *
 * Used solely to hand typed model objects to the raw-JSON viewer. It is never
 * used for identity, comparison or any semantic purpose.
 */
export function asJson(value: unknown): JsonValue {
  return JSON.parse(JSON.stringify(value ?? null)) as JsonValue;
}
