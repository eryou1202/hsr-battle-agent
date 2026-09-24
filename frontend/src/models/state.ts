/**
 * Mirrors the Terra state/snapshot read surface:
 * `battle_sandbox.revision`, `battle_sandbox.state_v2`, `battle_sandbox.rng`.
 *
 * The frontend renders ONLY fields supplied by the adapter. Every optional field
 * below models "not supplied" explicitly so the UI can show an honest gap rather
 * than a computed default.
 */
import type { JsonValue } from './json';
import type { EvidenceMode, UnknownHandle } from './evidence';

export const STATE_REVISION_SCHEMA = 'state_revision/1' as const;
export const REVISION_SEQUENCE_SCHEMA = 'revision_and_transaction_sequence/1' as const;
export const RNG_STATE_SCHEMA = 'sandbox_rng_state/1' as const;

export const SANDBOX_RNG_ALGORITHM = 'PYTHON_RANDOM_MT19937' as const;

/** Mirrors `StateRevision.to_dict()`. */
export interface StateRevision {
  readonly schema: typeof STATE_REVISION_SCHEMA;
  readonly counter: number;
  readonly snapshotId: string;
  readonly lineage: string;
}

export function formatRevision(revision: StateRevision): string {
  return `r${revision.counter} · ${revision.snapshotId}`;
}

/** Mirrors `RevisionAndTransactionSequence.to_dict()`. */
export interface RevisionSequence {
  readonly schema: typeof REVISION_SEQUENCE_SCHEMA;
  readonly publishedRevision: StateRevision;
  readonly replaySequence: number;
  readonly committedEffectSequence: number;
}

/**
 * Presentation-level equality of two revision documents.
 *
 * This compares ONLY the supplied serialized fields. It is used to decide
 * whether "LIVE STATE UNCHANGED" may be shown; it derives nothing from battle
 * rules.
 */
export function sameRevisionDocument(a: StateRevision | null, b: StateRevision | null): boolean {
  if (!a || !b) return false;
  return (
    a.counter === b.counter && a.snapshotId === b.snapshotId && a.lineage === b.lineage
  );
}

/** Mirrors the `rng_state` component of `TerraBattleState.to_dict()`. */
export interface RngStateView {
  readonly schema: typeof RNG_STATE_SCHEMA;
  /** The declared sandbox algorithm. Client-native RNG is a different thing. */
  readonly algorithm: string;
  readonly version: string;
  /** Draw position as supplied. `null` means "not supplied" — never guessed. */
  readonly drawPosition: number | null;
  readonly internalStateSummary: string;
  readonly gaussNextSupplied: boolean;
}

/** Mirrors `SnapshotPolicyIdentity.to_dict()`. */
export interface SnapshotPolicyIdentity {
  readonly schema: 'snapshot_policy_identity/1';
  readonly evidenceMode: EvidenceMode;
  readonly evidenceVocabularyVersion: string;
  readonly profileId: string;
  readonly profileVersion: string;
  readonly profileContentSha256: string;
  readonly ruleSetId: string;
  readonly ruleSetVersion: string;
  readonly ruleSetContentSha256: string;
}

/** Status/modifier chip rendered from adapter-supplied data. */
export interface StatusChip {
  readonly id: string;
  readonly label: string;
  readonly evidenceMode: EvidenceMode;
  /** Stacking/duration are NOT computed client-side; only supplied values show. */
  readonly stacksSupplied: boolean;
  readonly stacks: number | null;
  readonly durationSupplied: boolean;
  readonly duration: number | null;
}

/** A numeric bar. `null` values mean the adapter did not supply the figure. */
export interface MeterView {
  readonly current: number | null;
  readonly max: number | null;
  readonly supplied: boolean;
  readonly unit: string | null;
}

export type UnitSide = 'ALLY' | 'ENEMY';

/** One unit row on the battle board. */
export interface UnitView {
  readonly id: string;
  readonly name: string;
  readonly codename: string;
  readonly side: UnitSide;
  readonly slot: number;
  readonly level: number | null;
  readonly role: string | null;
  readonly affinity: string | null;
  readonly hp: MeterView;
  readonly toughness: MeterView;
  readonly statuses: readonly StatusChip[];
  /**
   * Support classification for this unit. `UNKNOWN` means nobody established it
   * yet and is kept distinct from `UNSUPPORTED`.
   */
  readonly supportState: EvidenceMode | 'UNKNOWN';
  readonly notes: readonly string[];
}

/**
 * Timeline entry kinds. These stay DISTINCT on purpose — the frontend must not
 * merge inserted / action-task / damage-task / ultimate-request / immediate
 * entries into one convenient UI type.
 */
export const TIMELINE_ENTRY_KINDS = [
  'ORDINARY',
  'INSERTED',
  'ACTION_TASK',
  'DAMAGE_TASK',
  'ULTIMATE_REQUEST',
  'IMMEDIATE',
] as const;

export type TimelineEntryKind = (typeof TIMELINE_ENTRY_KINDS)[number];

export interface TimelineEntry {
  readonly id: string;
  /** 1-based render position. Order is supplied; never sorted client-side. */
  readonly order: number;
  readonly kind: TimelineEntryKind;
  readonly label: string;
  readonly actorId: string | null;
  /** Action-value style figure, ONLY when the adapter supplies it. */
  readonly avSupplied: boolean;
  readonly av: number | null;
  readonly evidenceMode: EvidenceMode;
  readonly detail: string | null;
}

/** One summarized store in the state aggregate. */
export interface StoreSummary {
  readonly name: string;
  readonly ownerComponent: 'typed_store' | 'opaque_stores' | 'allocator' | 'rng_state' | 'revision_sequence';
  readonly entryCount: number | null;
  readonly opaque: boolean;
  readonly unresolvedHandleCount: number;
}

/** Adapter-facing battle snapshot. */
export interface BattleSnapshot {
  readonly schema: 'terra_battle_state/2';
  readonly revision: StateRevision;
  /** Complete revision/transaction sequence as supplied. */
  readonly revisionSequence: {
    readonly publishedRevision: StateRevision;
    readonly replaySequence: number | null;
    readonly committedEffectSequence: number | null;
  };
  readonly semanticHash: string;
  readonly policyIdentity: SnapshotPolicyIdentity | null;
  readonly rng: RngStateView;
  readonly allies: readonly UnitView[];
  readonly enemies: readonly UnitView[];
  readonly timeline: readonly TimelineEntry[];
  readonly currentActorId: string | null;
  readonly selectedTargetId: string | null;
  readonly stores: readonly StoreSummary[];
  readonly unknownHandles: readonly UnknownHandle[];
  /** Opaque verbatim payload for the raw-JSON inspector. */
  readonly raw: JsonValue;
}
