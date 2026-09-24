/**
 * Snapshot assembly for fixtures. Kept in one place so every scenario builds its
 * state document the same way.
 */
import type {
  BattleSnapshot,
  SnapshotPolicyIdentity,
  StateRevision,
  TimelineEntry,
  UnitView,
  UnknownHandle,
} from '../models';
import { baseBoardUnits } from './roster';
import { fixtureHex, revision } from './shared';

export interface SnapshotOptions {
  readonly snapshotId: string;
  readonly revisionCounter: number;
  readonly rngDrawPosition: number | null;
  readonly units?: readonly UnitView[];
  readonly timeline: readonly TimelineEntry[];
  readonly currentActorId: string | null;
  readonly selectedTargetId: string | null;
  readonly unknownHandles?: readonly UnknownHandle[];
  readonly evidenceMode?: SnapshotPolicyIdentity['evidenceMode'];
  readonly replaySequence?: number | null;
  readonly committedEffectSequence?: number | null;
}

export function policyIdentity(
  evidenceMode: SnapshotPolicyIdentity['evidenceMode'],
): SnapshotPolicyIdentity {
  return {
    schema: 'snapshot_policy_identity/1',
    evidenceMode,
    evidenceVocabularyVersion: 'astra-evidence-v1',
    profileId: 'terra-strict-profile',
    profileVersion: '1.0.0',
    profileContentSha256: fixtureHex('terra-strict-profile@1.0.0'),
    ruleSetId: 'terra-gate-ruleset',
    ruleSetVersion: '4.4.54',
    ruleSetContentSha256: fixtureHex('terra-gate-ruleset@4.4.54'),
  };
}

export function buildSnapshot(options: SnapshotOptions): BattleSnapshot {
  const units = options.units ?? baseBoardUnits();
  const published: StateRevision = revision(options.revisionCounter, options.snapshotId);
  const evidenceMode = options.evidenceMode ?? 'NATIVE_EVIDENCED';
  const semanticHash = `terra-semantic-sha256:${fixtureHex(
    `${options.snapshotId}#${options.revisionCounter}#${evidenceMode}`,
  )}`;
  const allies = units.filter((entry) => entry.side === 'ALLY');
  const enemies = units.filter((entry) => entry.side === 'ENEMY');

  return {
    schema: 'terra_battle_state/2',
    revision: published,
    revisionSequence: {
      publishedRevision: published,
      replaySequence: options.replaySequence ?? null,
      committedEffectSequence: options.committedEffectSequence ?? null,
    },
    semanticHash,
    policyIdentity: policyIdentity(evidenceMode),
    rng: {
      schema: 'sandbox_rng_state/1',
      algorithm: 'PYTHON_RANDOM_MT19937',
      version: '1',
      drawPosition: options.rngDrawPosition,
      internalStateSummary: `mt19937 state vector (${options.rngDrawPosition ?? 0} draws consumed)`,
      gaussNextSupplied: false,
    },
    allies,
    enemies,
    timeline: options.timeline,
    currentActorId: options.currentActorId,
    selectedTargetId: options.selectedTargetId,
    stores: [
      { name: 'unit_hp_current', ownerComponent: 'typed_store', entryCount: units.length, opaque: false, unresolvedHandleCount: 0 },
      { name: 'unit_hp_max', ownerComponent: 'typed_store', entryCount: units.length, opaque: false, unresolvedHandleCount: 0 },
      { name: 'status_modifier_binding', ownerComponent: 'typed_store', entryCount: 4, opaque: false, unresolvedHandleCount: 0 },
      { name: 'turn_order_av', ownerComponent: 'typed_store', entryCount: options.timeline.length, opaque: false, unresolvedHandleCount: 0 },
      { name: 'skill_point_pool', ownerComponent: 'typed_store', entryCount: 1, opaque: false, unresolvedHandleCount: 0 },
      { name: 'native_damage_pipeline', ownerComponent: 'opaque_stores', entryCount: null, opaque: true, unresolvedHandleCount: 1 },
      { name: 'native_rng_semantics', ownerComponent: 'opaque_stores', entryCount: null, opaque: true, unresolvedHandleCount: 2 },
      { name: 'native_toughness_break', ownerComponent: 'opaque_stores', entryCount: null, opaque: true, unresolvedHandleCount: 1 },
      { name: 'allocator', ownerComponent: 'allocator', entryCount: units.length, opaque: false, unresolvedHandleCount: 0 },
      { name: 'rng_state', ownerComponent: 'rng_state', entryCount: 1, opaque: false, unresolvedHandleCount: 0 },
      { name: 'revision_sequence', ownerComponent: 'revision_sequence', entryCount: 1, opaque: false, unresolvedHandleCount: 0 },
    ],
    unknownHandles: options.unknownHandles ?? [],
    raw: {
      note: 'MOCK DATA — abbreviated fixture view of terra_battle_state/2.',
      snapshot_id: options.snapshotId,
      revision: {
        schema: published.schema,
        counter: published.counter,
        snapshot_id: published.snapshotId,
        lineage: published.lineage,
      },
      unit_count: units.length,
      timeline_entry_count: options.timeline.length,
      stores: [
        { name: 'native_damage_pipeline', opaque: true, unresolved_handles: 1 },
        { name: 'native_rng_semantics', opaque: true, unresolved_handles: 2 },
        { name: 'native_toughness_break', opaque: true, unresolved_handles: 1 },
      ],
    },
  };
}
