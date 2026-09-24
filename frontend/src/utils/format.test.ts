import { describe, expect, it } from 'vitest';
import {
  abbreviateMiddle,
  asJson,
  digestPrefix,
  formatCounter,
  formatList,
  formatNullableNumber,
  pluralize,
  shortDigest,
  stableJson,
  truncateText,
} from './format';

describe('format helpers', () => {
  it('abbreviates only when the value is long enough', () => {
    expect(abbreviateMiddle('abcdef', 3, 2)).toBe('abcdef');
    expect(abbreviateMiddle('0123456789abcdef', 4, 4)).toBe('0123…cdef');
  });

  it('strips a scheme prefix when shortening a digest', () => {
    const value = 'terra-semantic-sha256:' + 'a'.repeat(64);
    expect(shortDigest(value, 6, 4)).toBe('aaaaaa…aaaa');
    expect(digestPrefix(value)).toBe('terra-semantic-sha256');
    expect(digestPrefix('a'.repeat(64))).toBeNull();
  });

  it('formats counters and nullable numbers without inventing defaults', () => {
    expect(formatCounter(12)).toBe('r12');
    expect(formatNullableNumber(null)).toBe('—');
    expect(formatNullableNumber(0)).toBe('0');
  });

  it('formats lists and plurals', () => {
    expect(formatList([], 'none')).toBe('none');
    expect(formatList(['a', 'b'])).toBe('a, b');
    expect(pluralize(1, 'obligation')).toBe('1 obligation');
    expect(pluralize(2, 'obligation')).toBe('2 obligations');
  });

  it('truncates text with an ellipsis', () => {
    expect(truncateText('abc', 5)).toBe('abc');
    expect(truncateText('abcdefgh', 4)).toBe('abc…');
  });

  it('projects structured records to display JSON', () => {
    const projected = asJson({ a: 1, b: [true, null], c: { d: 'x' } });
    expect(projected).toEqual({ a: 1, b: [true, null], c: { d: 'x' } });
    expect(asJson(undefined)).toBeNull();
  });

  it('stableJson never throws on structured input', () => {
    expect(() => stableJson({ a: [1, 2, { b: null }] })).not.toThrow();
    expect(stableJson({ a: 1 })).toContain('"a"');
  });
});
