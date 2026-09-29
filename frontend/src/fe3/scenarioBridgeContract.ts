/** Structural transport DTOs only. Compilation and reporting remain in Python. */
import type { ProductObject, ProductValue } from './productJson';
import type { CONTENT_VERSION, ScenarioSupportReport } from './productContract';

export const BRIDGE_INFO_SCHEMA = 'hsr_battle_agent.frontend_bridge_info/1' as const;
export const BRIDGE_ERROR_SCHEMA = 'hsr_battle_agent.frontend_bridge_error/1' as const;
export const SCENARIO_PACKAGE_SCHEMA = 'hsr_battle_agent.scenario_package/2' as const;
export const BRIDGE_ERROR_CODES = ['INVALID_JSON', 'REQUEST_TOO_LARGE', 'UNSUPPORTED_CONTENT_VERSION',
  'SCENARIO_COMPILE_REJECTED', 'SUPPORT_REPORT_REJECTED', 'METHOD_NOT_ALLOWED', 'NOT_FOUND',
  'UNSUPPORTED_MEDIA_TYPE', 'ORIGIN_NOT_ALLOWED', 'INTERNAL_ERROR'] as const;
export type BridgeErrorCode = typeof BRIDGE_ERROR_CODES[number];
export type BridgeRequestKind = 'INFO' | 'SCENARIO_COMPILE' | 'SCENARIO_SUPPORT' | 'UNKNOWN' | 'STARTUP';

export interface BridgeInfo extends ProductObject {
  schema: typeof BRIDGE_INFO_SCHEMA; bridge_version: '1'; content_version: typeof CONTENT_VERSION; host_scope: 'LOOPBACK_ONLY';
  capabilities: ProductObject & { scenario_compile: true; scenario_support_report: true; battle_execution: false; planner: false; native_execution: false };
  accepted_input: ProductObject; produced_documents: ProductObject;
}
export interface FrontendBridgeError extends ProductObject {
  schema: typeof BRIDGE_ERROR_SCHEMA; code: BridgeErrorCode; message: string; request_kind: BridgeRequestKind;
}

export interface ScenarioPlayerDraft {
  slot?: string | number; instance_id?: string;
  avatar: { avatar_id: string | number; level?: number; promotion?: number; eidolon?: number;
    skill_levels?: ProductObject; trace_state?: ProductObject };
  lightcone?: { lightcone_id: string | number; level?: number; promotion?: number; superimposition?: number } | null;
  relics?: ProductObject[]; initial_state?: ProductObject;
}
export interface ScenarioEnemyWaveDraft {
  wave_index?: number; wave_id?: string | null;
  enemies: { instance_id?: string; monster_id: string | number; level?: number;
    initial_state_overrides?: ProductObject; group_index?: number | null; slot?: string | null }[];
}
export interface ScenarioBuffBindingDraft {
  binding_id?: string; buff_id: string | number; scope?: string; owner_or_target?: ProductValue;
  activation?: string; parameter_overrides?: ProductObject;
}
/** No local bounds, reference resolution, loadout evaluation or wave overlay. */
export interface ScenarioCompileRequest {
  game_version: typeof CONTENT_VERSION; scenario_id: string; mode?: string; source_stage_id?: string | number | null;
  player_team: ScenarioPlayerDraft[]; enemy_waves?: ScenarioEnemyWaveDraft[] | null;
  buff_bindings?: ScenarioBuffBindingDraft[];
  rules: { rng_seed: ProductValue; unsupported_policy?: 'reject' | 'opaque-disabled';
    victory_rule_id?: string | null; defeat_rule_id?: string | null };
}

export type ScenarioWaveOrigin = 'TEMPLATE' | 'TEMPLATE_WITH_CALLER_OVERRIDE' | 'CALLER';
export type ScenarioInspectionStatus = 'STATIC_READY_BEHAVIOR_COMPILATION_REQUIRED' | 'DEBUG_OPAQUE_DISABLED_ONLY';
export interface ScenarioRuleResolution extends ProductObject {
  requested_id: string | null; resolution_status: 'UNKNOWN' | 'UNSPECIFIED'; resolved_rule: null; authority: null; execution_semantics: 'NONE';
}
export interface ScenarioMonsterResolution extends ProductObject {
  requested_id: string; resolved_kind: 'MONSTER' | 'MONSTER_VARIANT'; canonical_monster_id: string | null;
  variant_id: string | null;
}
export interface ScenarioPlayer extends ProductObject {
  instance_id: string; slot: string; avatar_id: string; avatar: ProductObject; loadout: ProductObject;
  skill_levels: ProductObject; trace_state: ProductObject; initial_state: ProductObject;
}
export interface ScenarioWave extends ProductObject {
  wave_index: number; wave_id: string | null; origin: ScenarioWaveOrigin; override_applied: boolean; provenance: ProductObject;
  enemies: (ProductObject & { instance_id: string; monster_id: string; level: number; monster: ProductObject;
    resolution: ScenarioMonsterResolution; initial_state_overrides: ProductObject; template_position: ProductObject; origin: ScenarioWaveOrigin })[];
}
/** Importable static document only. No execution permission accessor exists. */
export interface ScenarioPackage extends ProductObject {
  schema: typeof SCENARIO_PACKAGE_SCHEMA; game_version: typeof CONTENT_VERSION; scenario_id: string; mode: string;
  source_stage: ProductObject | null; players: ScenarioPlayer[]; waves: ScenarioWave[]; buff_bindings: ProductObject[];
  rules: ProductObject & { rng_seed: ProductValue; unsupported_policy: 'reject' | 'opaque-disabled';
    victory_rule: ScenarioRuleResolution; defeat_rule: ScenarioRuleResolution };
  unresolved_behavior: ProductObject[]; unsupported_policy: 'reject' | 'opaque-disabled';
  execution_status: ScenarioInspectionStatus; reconstruction_status: 'STATIC_RECONSTRUCTION_READY';
  golden_eligible: false; provenance_policy: string; package_sha256: string;
}

export interface ScenarioCompileSource {
  info(): Promise<BridgeInfo>;
  compile(request: ScenarioCompileRequest): Promise<ScenarioPackage>;
}
export interface ScenarioSupportSource { support(scenario: ScenarioPackage): Promise<ScenarioSupportReport> }
