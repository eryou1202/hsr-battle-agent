/**
 * Roster / battle-setup fixtures.
 *
 * ORIGINAL GENERIC PLACEHOLDERS ONLY. No official Honkai: Star Rail character
 * names, paths, elements, or artwork are used. Affinity and role strings below
 * are invented labels for UI development.
 */
import type { BattleSetup, SetupEntity, UnitView } from '../models';
import { chip, meter, unit, unsuppliedMeter } from './shared';

export const GENERIC_AFFINITIES = ['THERMAL', 'KINETIC', 'PHASE', 'VOLT', 'AETHER', 'FLUX'] as const;
export const GENERIC_ROLES = ['VANGUARD', 'BULWARK', 'CASTER', 'SUPPORT'] as const;

function loadout(ownerId: string): SetupEntity['loadout'] {
  return [
    {
      id: `${ownerId}-eq`,
      kind: 'EQUIPMENT',
      label: 'Primary equipment',
      value: 'SIGIL-MK-II (placeholder)',
      supportState: 'NATIVE_EVIDENCED',
      supplied: true,
    },
    {
      id: `${ownerId}-set`,
      kind: 'SET',
      label: 'Set bonus',
      value: null,
      supportState: 'UNKNOWN',
      supplied: false,
    },
    {
      id: `${ownerId}-cons`,
      kind: 'CONSUMABLE',
      label: 'Consumable',
      value: null,
      supportState: 'UNSUPPORTED',
      supplied: false,
    },
  ];
}

function entity(options: {
  id: string;
  codename: string;
  name: string;
  slot: number;
  level: number | null;
  role: string | null;
  affinity: string | null;
  supportState: SetupEntity['supportState'];
  executable: boolean;
  notes: readonly string[];
}): SetupEntity {
  return {
    id: options.id,
    slot: options.slot,
    name: options.name,
    codename: options.codename,
    level: options.level,
    role: options.role,
    affinity: options.affinity,
    supportState: options.supportState,
    executable: options.executable,
    notes: options.notes,
    loadout: loadout(options.id),
  };
}

export const FIXTURE_TEAM: readonly SetupEntity[] = [
  entity({
    id: 'ally-vg',
    codename: 'VG-01',
    name: 'Vanguard Unit',
    slot: 1,
    level: 80,
    role: 'VANGUARD',
    affinity: 'KINETIC',
    supportState: 'NATIVE_EVIDENCED',
    executable: true,
    notes: ['Placeholder roster entry.', 'Executable under the selected evidence mode.'],
  }),
  entity({
    id: 'ally-bw',
    codename: 'BW-02',
    name: 'Bulwark Unit',
    slot: 2,
    level: 80,
    role: 'BULWARK',
    affinity: 'PHASE',
    supportState: 'NATIVE_EVIDENCED',
    executable: true,
    notes: ['Placeholder roster entry.'],
  }),
  entity({
    id: 'ally-cs',
    codename: 'CS-03',
    name: 'Caster Unit',
    slot: 3,
    level: 78,
    role: 'CASTER',
    affinity: 'THERMAL',
    supportState: 'REFERENCE_MODEL',
    executable: false,
    notes: [
      'Reference-model evidence only.',
      'Not executable: reference material is never promoted to native execution.',
    ],
  }),
  entity({
    id: 'ally-sp',
    codename: 'SP-04',
    name: 'Support Unit',
    slot: 4,
    level: 75,
    role: 'SUPPORT',
    affinity: 'AETHER',
    supportState: 'UNKNOWN',
    executable: false,
    notes: ['Support state has not been established; shown as UNKNOWN, not AVAILABLE.'],
  }),
];

export const FIXTURE_ENEMIES: readonly SetupEntity[] = [
  entity({
    id: 'enemy-eg1',
    codename: 'EG-01',
    name: 'Elite Adversary',
    slot: 1,
    level: 82,
    role: null,
    affinity: 'VOLT',
    supportState: 'NATIVE_EVIDENCED',
    executable: true,
    notes: ['Placeholder adversary entry.'],
  }),
  entity({
    id: 'enemy-eg2',
    codename: 'EG-02',
    name: 'Swarm Adversary',
    slot: 2,
    level: 79,
    role: null,
    affinity: 'FLUX',
    supportState: 'NATIVE_EVIDENCED',
    executable: true,
    notes: ['Placeholder adversary entry.'],
  }),
  entity({
    id: 'enemy-eg3',
    codename: 'EG-03',
    name: 'Boss Adversary',
    slot: 3,
    level: 85,
    role: null,
    affinity: 'AETHER',
    supportState: 'UNSUPPORTED',
    executable: false,
    notes: ['UNSUPPORTED: inspectable descriptor, execution denied.'],
  }),
];

export const FIXTURE_SETUP: BattleSetup = {
  team: FIXTURE_TEAM,
  enemies: FIXTURE_ENEMIES,
  scenario: {
    id: 'scenario-sandbox-01',
    label: 'Sandbox scenario 01 (placeholder)',
    stageRef: null,
    waveCount: null,
    cycleLimit: null,
    supportState: 'NATIVE_EVIDENCED',
    notes: [
      'Stage progression is NOT invented by the frontend.',
      'Wave / cycle figures shown only when the backend supplies them.',
    ],
  },
  mode: {
    evidenceMode: 'NATIVE_EVIDENCED',
    readinessClass: 'SAFE_TO_REPRESENT_ONLY',
    versionRelation: 'CLOSE_VERSION',
    strictExecution: true,
    notes: [
      'CLOSE_VERSION is never displayed as EXACT_NATIVE.',
      'Strict execution is on: an unresolved obligation blocks, it does not degrade.',
    ],
  },
  loadoutOwnerId: 'ally-vg',
};

/**
 * Base battle-board units. HP / toughness numbers are placeholders supplied by
 * the "backend"; the frontend draws bars from them and computes nothing.
 */
export function baseBoardUnits(): readonly UnitView[] {
  return [
    unit({
      id: 'ally-vg',
      name: 'Vanguard Unit',
      codename: 'VG-01',
      side: 'ALLY',
      slot: 1,
      level: 80,
      role: 'VANGUARD',
      affinity: 'KINETIC',
      hp: meter(7420, 9000, 'HP'),
      toughness: meter(0, 60, 'TOUGH'),
      statuses: [
        chip('st-vg-1', 'Forward Stance', 'NATIVE_EVIDENCED', 2, 3),
        chip('st-vg-2', 'Momentum', 'REFERENCE_MODEL', null, null),
      ],
      supportState: 'NATIVE_EVIDENCED',
    }),
    unit({
      id: 'ally-bw',
      name: 'Bulwark Unit',
      codename: 'BW-02',
      side: 'ALLY',
      slot: 2,
      level: 80,
      role: 'BULWARK',
      affinity: 'PHASE',
      hp: meter(9100, 9600, 'HP'),
      toughness: meter(30, 80, 'TOUGH'),
      statuses: [chip('st-bw-1', 'Barrier', 'NATIVE_EVIDENCED', 1, 2)],
      supportState: 'NATIVE_EVIDENCED',
    }),
    unit({
      id: 'ally-cs',
      name: 'Caster Unit',
      codename: 'CS-03',
      side: 'ALLY',
      slot: 3,
      level: 78,
      role: 'CASTER',
      affinity: 'THERMAL',
      hp: meter(5210, 6800, 'HP'),
      toughness: unsuppliedMeter('TOUGH'),
      statuses: [chip('st-cs-1', 'Resonance (reference)', 'REFERENCE_MODEL', null, null)],
      supportState: 'REFERENCE_MODEL',
      notes: ['Reference-model unit: inspectable, not executable.'],
    }),
    unit({
      id: 'ally-sp',
      name: 'Support Unit',
      codename: 'SP-04',
      side: 'ALLY',
      slot: 4,
      level: 75,
      role: 'SUPPORT',
      affinity: 'AETHER',
      hp: meter(6100, 7200, 'HP'),
      toughness: unsuppliedMeter('TOUGH'),
      statuses: [],
      supportState: 'UNKNOWN',
      notes: ['Support state unknown; no legality is inferred.'],
    }),
    unit({
      id: 'enemy-eg1',
      name: 'Elite Adversary',
      codename: 'EG-01',
      side: 'ENEMY',
      slot: 1,
      level: 82,
      role: null,
      affinity: 'VOLT',
      hp: meter(18400, 24000, 'HP'),
      toughness: meter(6, 12, 'TOUGH'),
      statuses: [chip('st-eg1-1', 'Overcharge', 'NATIVE_EVIDENCED', 3, null)],
      supportState: 'NATIVE_EVIDENCED',
    }),
    unit({
      id: 'enemy-eg2',
      name: 'Swarm Adversary',
      codename: 'EG-02',
      side: 'ENEMY',
      slot: 2,
      level: 79,
      role: null,
      affinity: 'FLUX',
      hp: meter(4300, 9000, 'HP'),
      toughness: meter(2, 6, 'TOUGH'),
      statuses: [],
      supportState: 'NATIVE_EVIDENCED',
    }),
    unit({
      id: 'enemy-eg3',
      name: 'Boss Adversary',
      codename: 'EG-03',
      side: 'ENEMY',
      slot: 3,
      level: 85,
      role: null,
      affinity: 'AETHER',
      hp: meter(61200, 98000, 'HP'),
      toughness: unsuppliedMeter('TOUGH'),
      statuses: [chip('st-eg3-1', 'Aegis (unsupported)', 'UNSUPPORTED', null, null)],
      supportState: 'UNSUPPORTED',
      notes: ['UNSUPPORTED content: descriptor only.'],
    }),
  ];
}
