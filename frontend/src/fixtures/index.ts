/**
 * Deterministic mock fixture registry.
 *
 * Every bundle here is MOCK DATA served by `MockBattleBackendAdapter`. Fixtures
 * exist to exercise UI states — they deliberately do NOT encode real Honkai:
 * Star Rail combat semantics.
 */
import type { ScenarioDescriptor } from '../models';
import type { MockScenarioBundle } from './types';
import { SCENARIO_A } from './scenarioAClosedNoOp';
import { SCENARIO_B } from './scenarioBUnknown';
import { SCENARIO_C } from './scenarioCUnsupported';
import { SCENARIO_D } from './scenarioDReference';
import { SCENARIO_E } from './scenarioEStaleRevision';
import { SCENARIO_F } from './scenarioFCommit';
import { SCENARIO_G } from './scenarioGQuarantine';

export const MOCK_SCENARIOS: readonly MockScenarioBundle[] = [
  SCENARIO_A,
  SCENARIO_B,
  SCENARIO_C,
  SCENARIO_D,
  SCENARIO_E,
  SCENARIO_F,
  SCENARIO_G,
];

export const MOCK_SCENARIO_DESCRIPTORS: readonly ScenarioDescriptor[] = MOCK_SCENARIOS.map(
  (bundle) => bundle.descriptor,
);

export function findMockScenario(id: string): MockScenarioBundle | null {
  return MOCK_SCENARIOS.find((bundle) => bundle.descriptor.id === id) ?? null;
}

export { SCENARIO_A, SCENARIO_B, SCENARIO_C, SCENARIO_D, SCENARIO_E, SCENARIO_F, SCENARIO_G };
export type { MockScenarioBundle } from './types';
