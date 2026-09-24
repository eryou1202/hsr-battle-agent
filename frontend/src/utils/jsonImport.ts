/**
 * Development-only JSON import recognizer.
 *
 * A live HTTP backend may not exist yet, so exported backend JSON can be pasted
 * or loaded straight into the workspace. Validation is deliberately
 * CONSERVATIVE:
 *
 *   * a document whose `schema` is not one we know is reported as
 *     UNSUPPORTED SCHEMA — never coerced into a guess;
 *   * unknown fields are PRESERVED and listed, never discarded;
 *   * missing fields are reported, never defaulted.
 *
 * This module classifies documents. It does not interpret battle semantics.
 */
import type { JsonValue } from '../models';
import { isJsonObject } from '../models/json';

export const KNOWN_SCHEMAS = [
  'preflight_result/1',
  'dependency_closure/1',
  'dependency_obligation/1',
  'dependency_closure_blocker/1',
  'structured_rejection/1',
  'terra_gate_certificate/1',
  'terra_transaction_plan/1',
  'terra_transaction_operation/1',
  'terra_staged_delta/1',
  'terra_staged_trace/1',
  'terra_transaction_rng/1',
  'terra_atomic_commit_result/1',
  'terra_strict_step_result/1',
  'terra_modifier_contract_slot/1',
  'terra_battle_state/2',
  'terra_snapshot/2',
  'state_revision/1',
  'revision_and_transaction_sequence/1',
] as const;

export type KnownSchema = (typeof KNOWN_SCHEMAS)[number];

export function isKnownSchema(value: unknown): value is KnownSchema {
  return typeof value === 'string' && (KNOWN_SCHEMAS as readonly string[]).includes(value);
}

/** Required top-level fields per known schema, for conservative reporting. */
const REQUIRED_FIELDS: Partial<Record<KnownSchema, readonly string[]>> = {
  'preflight_result/1': ['schema', 'outcome', 'closure', 'rejections'],
  'dependency_closure/1': ['schema', 'status', 'obligations', 'blockers', 'allowed_reads', 'allowed_writes'],
  'dependency_obligation/1': [
    'schema',
    'owner',
    'contract_ref',
    'evidence_mode',
    'resolution',
    'reads',
    'writes',
    'children',
    'unknown_handles',
  ],
  'dependency_closure_blocker/1': [
    'schema',
    'status',
    'owner',
    'contract_ref',
    'unknown_handles',
    'occurrence_path',
    'evidence_request',
  ],
  'structured_rejection/1': ['schema', 'reason_code', 'obligation_owner', 'evidence_request'],
  'terra_gate_certificate/1': [
    'schema',
    'plan_identity',
    'evidence_mode',
    'policy_identity',
    'input_identity',
    'input_revision',
    'state_revision',
    'contract_ref',
    'contract_revision',
    'closure_identity',
    'allowed_reads',
    'allowed_writes',
  ],
  'terra_transaction_plan/1': ['schema', 'operations', 'certificate_identity', 'source_revision', 'source_state_hash'],
  'terra_staged_delta/1': ['schema', 'plan_identity', 'certificate_identity', 'source_revision'],
  'terra_staged_trace/1': ['schema', 'plan_identity', 'records'],
  'terra_transaction_rng/1': ['schema', 'plan_identity', 'ledger'],
  'terra_atomic_commit_result/1': ['schema', 'state', 'records', 'certificate_identity', 'plan_identity'],
  'terra_strict_step_result/1': ['schema', 'outcome', 'resulting_revision', 'transaction_identity', 'rejections'],
  'terra_modifier_contract_slot/1': ['schema', 'operation', 'contract_id', 'evidence_mode', 'status'],
  'state_revision/1': ['schema', 'counter', 'snapshot_id'],
  'revision_and_transaction_sequence/1': [
    'schema',
    'published_revision',
    'replay_sequence',
    'committed_effect_sequence',
  ],
};

export type ImportKind =
  | 'PREFLIGHT_RESULT'
  | 'DEPENDENCY_CLOSURE'
  | 'DEPENDENCY_OBLIGATION'
  | 'CLOSURE_BLOCKER'
  | 'STRUCTURED_REJECTION'
  | 'GATE_CERTIFICATE'
  | 'TRANSACTION_PLAN'
  | 'STAGED_DELTA'
  | 'STAGED_TRACE'
  | 'TRANSACTION_RNG'
  | 'ATOMIC_COMMIT_RESULT'
  | 'STRICT_STEP_RESULT'
  | 'CONTRACT_SLOT'
  | 'STATE_REVISION'
  | 'REVISION_SEQUENCE'
  | 'BATTLE_STATE'
  | 'SNAPSHOT'
  | 'UNRECOGNIZED';

const SCHEMA_TO_KIND: Record<KnownSchema, ImportKind> = {
  'preflight_result/1': 'PREFLIGHT_RESULT',
  'dependency_closure/1': 'DEPENDENCY_CLOSURE',
  'dependency_obligation/1': 'DEPENDENCY_OBLIGATION',
  'dependency_closure_blocker/1': 'CLOSURE_BLOCKER',
  'structured_rejection/1': 'STRUCTURED_REJECTION',
  'terra_gate_certificate/1': 'GATE_CERTIFICATE',
  'terra_transaction_plan/1': 'TRANSACTION_PLAN',
  'terra_transaction_operation/1': 'TRANSACTION_PLAN',
  'terra_staged_delta/1': 'STAGED_DELTA',
  'terra_staged_trace/1': 'STAGED_TRACE',
  'terra_transaction_rng/1': 'TRANSACTION_RNG',
  'terra_atomic_commit_result/1': 'ATOMIC_COMMIT_RESULT',
  'terra_strict_step_result/1': 'STRICT_STEP_RESULT',
  'terra_modifier_contract_slot/1': 'CONTRACT_SLOT',
  'terra_battle_state/2': 'BATTLE_STATE',
  'terra_snapshot/2': 'SNAPSHOT',
  'state_revision/1': 'STATE_REVISION',
  'revision_and_transaction_sequence/1': 'REVISION_SEQUENCE',
};

export interface ImportedDocument {
  readonly id: string;
  readonly sourceLabel: string;
  readonly kind: ImportKind;
  readonly schema: string | null;
  /** False when the schema is missing or not one we know. */
  readonly recognized: boolean;
  readonly missingFields: readonly string[];
  /** Extra fields are preserved in `raw` and listed here. */
  readonly unknownFields: readonly string[];
  readonly raw: JsonValue;
}

export type ImportOutcome =
  | { readonly ok: true; readonly document: ImportedDocument }
  | { readonly ok: false; readonly error: string };

let counter = 0;

function nextId(): string {
  counter += 1;
  return `import-${counter}`;
}

export function classifyDocument(value: JsonValue, sourceLabel: string): ImportOutcome {
  if (!isJsonObject(value)) {
    return { ok: false, error: 'Top-level JSON value must be an object with a "schema" field.' };
  }
  const schemaValue = value['schema'];
  const schema = typeof schemaValue === 'string' ? schemaValue : null;

  if (!isKnownSchema(schema)) {
    // Unknown schema is reported, never guessed.
    return {
      ok: true,
      document: {
        id: nextId(),
        sourceLabel,
        kind: 'UNRECOGNIZED',
        schema,
        recognized: false,
        missingFields: [],
        unknownFields: Object.keys(value),
        raw: value,
      },
    };
  }

  const required = REQUIRED_FIELDS[schema] ?? [];
  const present = new Set(Object.keys(value));
  const missingFields = required.filter((field) => !present.has(field));
  const unknownFields = Object.keys(value).filter((field) => !required.includes(field));

  return {
    ok: true,
    document: {
      id: nextId(),
      sourceLabel,
      kind: SCHEMA_TO_KIND[schema],
      schema,
      recognized: true,
      missingFields,
      unknownFields,
      raw: value,
    },
  };
}

export function parseImportedJson(text: string, sourceLabel: string): ImportOutcome {
  const trimmed = text.trim();
  if (!trimmed) return { ok: false, error: 'Nothing to import: the input is empty.' };
  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed) as unknown;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return { ok: false, error: `Invalid JSON: ${message}` };
  }
  const value = parsed as JsonValue;
  if (!isJsonObject(value)) {
    return { ok: false, error: 'Top-level JSON value must be an object.' };
  }
  return classifyDocument(value, sourceLabel);
}

/** Reset the id counter; used by tests only. */
export function resetImportCounterForTests(): void {
  counter = 0;
}

export function listTopLevelFields(value: JsonValue): readonly string[] {
  return isJsonObject(value) ? Object.keys(value) : [];
}
