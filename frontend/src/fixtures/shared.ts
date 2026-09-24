/**
 * Shared fixture builders.
 *
 * EVERY value produced here is synthetic demo material for UI development.
 * Nothing in this file encodes real Honkai: Star Rail combat semantics — no
 * damage formula, no speed / action-value model, no turn-order rule, no
 * toughness-break rule. Numbers are placeholders chosen to exercise layout.
 */
import type {
  ChildObligationRef,
  ContractRef,
  EvidenceMode,
  JsonValue,
  ObligationAccess,
  MeterView,
  Presence,
  StateRevision,
  StatusChip,
  TimelineEntry,
  TimelineEntryKind,
  UnitView,
  UnknownHandle,
} from '../models';

export const FIXTURE_CONTENT_VERSION = '4.4.54';

/**
 * Deterministic 64-hex "digest-like" label for fixture display only.
 *
 * This is NOT a semantic hash and must never be compared against a real backend
 * digest. It exists so mock screens show stable, plausible-looking identifiers
 * across reloads.
 */
export function fixtureHex(seed: string): string {
  let h1 = 0x811c9dc5;
  let h2 = 0x01000193;
  for (let i = 0; i < seed.length; i += 1) {
    const code = seed.charCodeAt(i);
    h1 = (h1 ^ code) >>> 0;
    h1 = Math.imul(h1, 0x01000193) >>> 0;
    h2 = (h2 + Math.imul(code + i, 0x85ebca6b)) >>> 0;
  }
  let out = '';
  let a = h1;
  let b = h2;
  while (out.length < 64) {
    a = (Math.imul(a, 1103515245) + 12345) >>> 0;
    b = (Math.imul(b ^ (a >>> 3), 2654435761) >>> 0) || 1;
    // `>>> 0` keeps the value unsigned so the hex label never gains a sign.
    out += ((a ^ b) >>> 0).toString(16).padStart(8, '0');
  }
  return out.slice(0, 64);
}

export function abbreviate(value: string, head = 10, tail = 4): string {
  if (value.length <= head + tail + 1) return value;
  return `${value.slice(0, head)}…${value.slice(-tail)}`;
}

export function contractRef(
  contractId: string,
  namespace: string,
  schemaVersion: string,
  evidenceMode: EvidenceMode,
  sourceRefs: readonly string[] = [],
): ContractRef {
  return {
    schema: 'contract_ref/1',
    contractId,
    namespace,
    schemaVersion,
    evidenceMode,
    contentSha256: fixtureHex(`${namespace}/${contractId}@${schemaVersion}`),
    sourceRefs,
  };
}

export function unknownHandle(options: {
  blockerId: string;
  ownerFamily: string;
  payload: unknown;
  provenance: Record<string, unknown>;
  requiredEvidence: readonly string[];
}): UnknownHandle {
  return {
    schema: 'unknown_handle/1',
    blockerId: options.blockerId,
    ownerFamily: options.ownerFamily,
    payload: options.payload as UnknownHandle['payload'],
    provenance: options.provenance as UnknownHandle['provenance'],
    requiredEvidence: options.requiredEvidence,
  };
}

export function revision(counter: number, snapshotId: string, lineage = 'default'): StateRevision {
  return { schema: 'state_revision/1', counter, snapshotId, lineage };
}

export function access(target: string, extent: Presence): ObligationAccess {
  return { schema: 'obligation_access/1', target, extent };
}

export function childRef(owner: string, ref: ContractRef): ChildObligationRef {
  return { schema: 'child_obligation_ref/1', owner, contractRef: ref };
}

export function present(value: JsonValue): Presence {
  return { kind: 'PRESENT', value };
}

export function absent(): Presence {
  return { kind: 'ABSENT' };
}

export function nullExtent(): Presence {
  return { kind: 'NULL' };
}

export function meter(current: number | null, max: number | null, unit: string | null): MeterView {
  const supplied = current !== null && max !== null;
  return { current, max, supplied, unit };
}

export function unsuppliedMeter(label: string): MeterView {
  return { current: null, max: null, supplied: false, unit: label };
}

export function chip(
  id: string,
  label: string,
  evidenceMode: EvidenceMode,
  stacks: number | null = null,
  duration: number | null = null,
): StatusChip {
  return {
    id,
    label,
    evidenceMode,
    stacksSupplied: stacks !== null,
    stacks,
    durationSupplied: duration !== null,
    duration,
  };
}

export function timelineEntry(
  order: number,
  kind: TimelineEntryKind,
  label: string,
  actorId: string | null,
  evidenceMode: EvidenceMode,
  options: { av?: number | null; detail?: string | null } = {},
): TimelineEntry {
  const av = options.av ?? null;
  return {
    id: `tl-${order}-${kind.toLowerCase()}`,
    order,
    kind,
    label,
    actorId,
    avSupplied: av !== null,
    av,
    evidenceMode,
    detail: options.detail ?? null,
  };
}

export function unit(options: {
  id: string;
  name: string;
  codename: string;
  side: UnitView['side'];
  slot: number;
  level: number | null;
  role: string | null;
  affinity: string | null;
  hp: MeterView;
  toughness: MeterView;
  statuses?: readonly StatusChip[];
  supportState: UnitView['supportState'];
  notes?: readonly string[];
}): UnitView {
  return {
    id: options.id,
    name: options.name,
    codename: options.codename,
    side: options.side,
    slot: options.slot,
    level: options.level,
    role: options.role,
    affinity: options.affinity,
    hp: options.hp,
    toughness: options.toughness,
    statuses: options.statuses ?? [],
    supportState: options.supportState,
    notes: options.notes ?? [],
  };
}
