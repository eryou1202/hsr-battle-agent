import { describe, expect, it } from 'vitest';
import {
  classifyDocument,
  isKnownSchema,
  parseImportedJson,
  resetImportCounterForTests,
} from './jsonImport';

describe('json import recognizer', () => {
  it('recognizes a known strict step schema', () => {
    resetImportCounterForTests();
    const outcome = parseImportedJson(
      JSON.stringify({
        schema: 'terra_strict_step_result/1',
        outcome: 'REJECTED',
        resulting_revision: null,
        transaction_identity: null,
        rejections: [],
      }),
      'paste',
    );
    expect(outcome.ok).toBe(true);
    if (!outcome.ok) return;
    expect(outcome.document.kind).toBe('STRICT_STEP_RESULT');
    expect(outcome.document.recognized).toBe(true);
    expect(outcome.document.missingFields).toEqual([]);
  });

  it('reports an unknown schema instead of guessing', () => {
    const outcome = parseImportedJson(
      JSON.stringify({ schema: 'vendor.mystery/9', anything: true }),
      'paste',
    );
    expect(outcome.ok).toBe(true);
    if (!outcome.ok) return;
    expect(outcome.document.recognized).toBe(false);
    expect(outcome.document.kind).toBe('UNRECOGNIZED');
    // Unknown fields are preserved, not discarded.
    expect(outcome.document.unknownFields).toContain('anything');
    expect(outcome.document.raw).toEqual({ schema: 'vendor.mystery/9', anything: true });
  });

  it('lists missing required fields without defaulting them', () => {
    const outcome = parseImportedJson(
      JSON.stringify({ schema: 'terra_gate_certificate/1', plan_identity: 'p' }),
      'paste',
    );
    expect(outcome.ok).toBe(true);
    if (!outcome.ok) return;
    expect(outcome.document.missingFields).toContain('evidence_mode');
    expect(outcome.document.missingFields).toContain('state_revision');
  });

  it('preserves unknown extra fields on a known schema', () => {
    const outcome = parseImportedJson(
      JSON.stringify({
        schema: 'terra_gate_certificate/1',
        plan_identity: 'p',
        evidence_mode: 'NATIVE_EVIDENCED',
        policy_identity: {},
        input_identity: 'i',
        input_revision: 'r1',
        state_revision: { schema: 'state_revision/1', counter: 1, snapshot_id: 's', lineage: 'default' },
        contract_ref: {},
        contract_revision: '1',
        closure_identity: 'c',
        allowed_reads: [],
        allowed_writes: [],
        vendor_extension: 'kept',
      }),
      'paste',
    );
    expect(outcome.ok).toBe(true);
    if (!outcome.ok) return;
    expect(outcome.document.unknownFields).toEqual(['vendor_extension']);
    expect((outcome.document.raw as Record<string, unknown>)['vendor_extension']).toBe('kept');
  });

  it('rejects malformed JSON and non-object roots without throwing', () => {
    expect(parseImportedJson('{not json', 'x').ok).toBe(false);
    expect(parseImportedJson('', 'x').ok).toBe(false);
    expect(parseImportedJson('[]', 'x').ok).toBe(false);
    const string = parseImportedJson('"hello"', 'x');
    expect(string.ok).toBe(false);
  });

  it('knows the real backend schema spellings', () => {
    expect(isKnownSchema('terra_gate_certificate/1')).toBe(true);
    expect(isKnownSchema('dependency_closure_blocker/1')).toBe(true);
    // The earlier placeholder spellings must not be accepted.
    expect(isKnownSchema('gate_certificate/1')).toBe(false);
    expect(isKnownSchema('closure_blocker/1')).toBe(false);
  });

  it('classifies a document object directly', () => {
    const outcome = classifyDocument({ schema: 'preflight_result/1' }, 'direct');
    expect(outcome.ok).toBe(true);
    if (!outcome.ok) return;
    expect(outcome.document.kind).toBe('PREFLIGHT_RESULT');
    expect(outcome.document.missingFields).toContain('outcome');
  });
});
