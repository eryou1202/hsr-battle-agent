/**
 * Battle-setup presentation data (team / enemies / scenario / loadout / mode).
 *
 * These are frontend fixtures for UI development. They carry no game semantics:
 * a slot's `supportState` is an evidence classification, never a computed
 * gameplay verdict.
 */
import type { EvidenceMode } from './evidence';

/**
 * Support classification for a setup entry.
 *
 * `UNKNOWN` is added to the evidence vocabulary on purpose: "nobody has
 * established this yet" is a different display state from every `EvidenceMode`,
 * and collapsing it into `UNSUPPORTED` would lose that distinction.
 */
export type EntitySupportState = EvidenceMode | 'UNKNOWN';

export type LoadoutSlotKind = 'UNIT' | 'EQUIPMENT' | 'SET' | 'CONSUMABLE';

export interface LoadoutSlot {
  readonly id: string;
  readonly kind: LoadoutSlotKind;
  readonly label: string;
  readonly value: string | null;
  readonly supportState: EntitySupportState;
  readonly supplied: boolean;
}

export interface SetupEntity {
  readonly id: string;
  readonly slot: number;
  readonly name: string;
  readonly codename: string;
  readonly level: number | null;
  readonly role: string | null;
  readonly affinity: string | null;
  readonly supportState: EntitySupportState;
  readonly executable: boolean;
  readonly notes: readonly string[];
  readonly loadout: readonly LoadoutSlot[];
}

export interface SetupScenario {
  readonly id: string;
  readonly label: string;
  readonly stageRef: string | null;
  readonly waveCount: number | null;
  readonly cycleLimit: number | null;
  readonly supportState: EvidenceMode;
  readonly notes: readonly string[];
}

export interface SetupModeSelection {
  readonly evidenceMode: EvidenceMode;
  readonly readinessClass: string | null;
  readonly versionRelation: string | null;
  readonly strictExecution: boolean;
  readonly notes: readonly string[];
}

export interface BattleSetup {
  readonly team: readonly SetupEntity[];
  readonly enemies: readonly SetupEntity[];
  readonly scenario: SetupScenario;
  readonly mode: SetupModeSelection;
  readonly loadoutOwnerId: string | null;
}
