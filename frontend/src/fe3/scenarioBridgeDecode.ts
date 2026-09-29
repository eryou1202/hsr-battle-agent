/** Import checks only; backend rule/identity/provenance records are unchanged. */
import { CONTENT_VERSION, REPORT_SCHEMA } from './productContract';
import { requireVersion } from './productDecode';
import { assertProductValue, parseProductJson, ProductContractError } from './productJson';
import { array, choices, fields, flag, hash, literal, nullable, raw, record, records, text, token } from './productImportRules';
import { BRIDGE_ERROR_CODES, BRIDGE_ERROR_SCHEMA, BRIDGE_INFO_SCHEMA, SCENARIO_PACKAGE_SCHEMA,
  type BridgeInfo, type FrontendBridgeError, type ScenarioPackage } from './scenarioBridgeContract';

export function decodeBridgeInfo(value: unknown, version: string): BridgeInfo {
  requireVersion(version);
  assertProductValue(value);
  fields({ schema: literal(BRIDGE_INFO_SCHEMA), bridge_version: literal('1'), content_version: literal(version), host_scope: literal('LOOPBACK_ONLY'),
    capabilities: fields({ scenario_compile: literal(true), scenario_support_report: literal(true), battle_execution: literal(false),
      planner: literal(false), native_execution: literal(false) }),
    accepted_input: fields({ scenario_compile: literal('ScenarioCompiler request'), scenario_support_report: literal(SCENARIO_PACKAGE_SCHEMA) }),
    produced_documents: fields({ scenario_compile: literal(SCENARIO_PACKAGE_SCHEMA), scenario_support_report: literal(REPORT_SCHEMA) }) })(value, '$');
  return value as BridgeInfo;
}
export function decodeFrontendBridgeError(value: unknown): FrontendBridgeError {
  assertProductValue(value);
  fields({ schema: literal(BRIDGE_ERROR_SCHEMA), code: choices(...BRIDGE_ERROR_CODES), message: token,
    request_kind: choices('INFO', 'SCENARIO_COMPILE', 'SCENARIO_SUPPORT', 'UNKNOWN', 'STARTUP') })(value, '$');
  return value as FrontendBridgeError;
}
const origin = choices('TEMPLATE', 'TEMPLATE_WITH_CALLER_OVERRIDE', 'CALLER');
const policy = choices('reject', 'opaque-disabled');
const integer = (value: unknown, path: string) => {
  if (typeof value !== 'number' || !Number.isSafeInteger(value)) throw new ProductContractError(path, 'INVALID_SCENARIO_INTEGER');
};
const entity = fields({ game_version: literal(CONTENT_VERSION), entity_id: token, original_game_id: nullable(text),
  game_id_status: text, confidence: text, reconstruction_status: text, data: record, provenance: records, canonical_sha256: hash });
const rule = fields({ requested_id: nullable(text), resolution_status: choices('UNKNOWN', 'UNSPECIFIED'),
  resolved_rule: literal(null), authority: literal(null), execution_semantics: literal('NONE') });
const resolution = fields({ requested_id: token, resolved_kind: choices('MONSTER', 'MONSTER_VARIANT'), canonical_monster_id: nullable(text),
  variant_id: nullable(text) });

export function decodeScenarioPackage(value: unknown, version: string): ScenarioPackage {
  requireVersion(version);
  assertProductValue(value);
  fields({ schema: literal(SCENARIO_PACKAGE_SCHEMA), game_version: literal(version), scenario_id: token, mode: text,
    source_stage: nullable(fields({ stage_id: nullable(text), stage: nullable(entity), source_refs: records,
      template_wave_count: integer, template_buff_count: integer })),
    players: array(fields({ instance_id: text, slot: text, avatar_id: token, avatar: entity,
      loadout: fields({ schema: literal('hsr_battle_agent.static_loadout/1'), game_version: literal(version) }),
      skill_levels: record, trace_state: record, initial_state: record })),
    waves: array(fields({ wave_index: integer, wave_id: nullable(text), origin, override_applied: flag,
      provenance: fields({ source_stage_id: nullable(text), template_wave_id: nullable(text), template_wave_index: nullable(integer),
        caller_wave_index: nullable(integer), caller_wave_id: nullable(text) }),
      enemies: array(fields({ instance_id: text, monster_id: token, level: integer, monster: entity, resolution,
        initial_state_overrides: record, template_position: fields({ group_index: raw, slot: raw }), origin })) })),
    buff_bindings: array(fields({ binding_id: text, buff_id: token, scope: text, owner_or_target: raw, activation: text,
      parameter_overrides: record, template_resolution: nullable(choices('RESOLVED', 'UNKNOWN')), buff: entity })),
    rules: fields({ rng_seed: raw, unsupported_policy: policy, victory_rule: rule, defeat_rule: rule }),
    unresolved_behavior: array(fields({ kind: choices('AvatarBehavior', 'MonsterBehavior', 'StageBuffBehavior'), entity_id: token,
      status: literal('BEHAVIOR_COMPILATION_REQUIRED') })), unsupported_policy: policy,
    // BEHAVIOR_RESOLVED/positive future statuses require a separate reviewed
    // execution contract. This local client imports only current inspection states.
    execution_status: choices('STATIC_READY_BEHAVIOR_COMPILATION_REQUIRED', 'DEBUG_OPAQUE_DISABLED_ONLY'),
    reconstruction_status: literal('STATIC_RECONSTRUCTION_READY'), golden_eligible: literal(false),
    provenance_policy: text, package_sha256: hash })(value, '$');
  return value as ScenarioPackage;
}

// Keep the exact Python JSON number spellings (98.0 versus 98) for P4's hash
// verification. Metadata stays outside the authoritative backend document.
const packageWireSources = new WeakMap<ScenarioPackage, { text: string; snapshot: string }>();
export function importScenarioPackage(text: string, version: string): ScenarioPackage {
  const document = decodeScenarioPackage(parseProductJson(text), version);
  packageWireSources.set(document, { text, snapshot: JSON.stringify(document) });
  return document;
}
export function scenarioPackageWireText(document: ScenarioPackage): string {
  const source = packageWireSources.get(document);
  if (!source) throw new ProductContractError('scenario.package', 'ORIGINAL_PACKAGE_JSON_REQUIRED');
  if (JSON.stringify(document) !== source.snapshot) throw new ProductContractError('scenario.package', 'PACKAGE_CHANGED_RECOMPILE_REQUIRED');
  return source.text;
}
