/** Structural mirrors of current backend documents. Opaque static source
 * records stay opaque; closed authority vocabularies are checked, never derived.
 */
import { CONTENT_VERSION, PRODUCT_SCHEMAS, REPORT_SCHEMA, SUMMARY_SCHEMAS, type Collection } from './productContract';
import { LosslessInteger, ProductContractError, type ProductObject } from './productJson';
export type Guard = (value: unknown, path: string) => void;
export function fail(path: string): never { throw new ProductContractError(path); }
export function object(value: unknown, path: string): ProductObject {
  if (!value || typeof value !== 'object' || Array.isArray(value) || value instanceof LosslessInteger) fail(path);
  return value as ProductObject;
}
export const text: Guard = (v, p) => { if (typeof v !== 'string') fail(p); };
export const token: Guard = (v, p) => { text(v, p); if (!v) fail(p); };
export const flag: Guard = (v, p) => { if (typeof v !== 'boolean') fail(p); };
export const count: Guard = (v, p) => { if (typeof v !== 'number' || !Number.isSafeInteger(v) || v < 0) fail(p); };
export const raw: Guard = (v, p) => { if (v === undefined) fail(p); };
export const record: Guard = (v, p) => { object(v, p); };
export const literal = (expected: string | number | boolean | null): Guard => (v, p) => { if (v !== expected) fail(p); };
export const choices = (...values: readonly string[]): Guard => (v, p) => { if (typeof v !== 'string' || !values.includes(v)) fail(p); };
export const nullable = (guard: Guard): Guard => (v, p) => { if (v !== null) guard(v, p); };
export const array = (guard: Guard): Guard => (v, p) => {
  if (!Array.isArray(v)) fail(p);
  v.forEach((x, i) => guard(x, `${p}[${i}]`));
};
export const strings = array(text);
export const records = array(record);
export const map = (guard: Guard): Guard => (v, p) => {
  for (const [key, entry] of Object.entries(object(v, p))) guard(entry, `${p}.${key}`);
};
export const fields = (required: Record<string, Guard>, optional: Record<string, Guard> = {}): Guard => (v, p) => {
  const row = object(v, p);
  for (const [key, guard] of Object.entries(required)) {
    if (!Object.hasOwn(row, key)) fail(`${p}.${key}`);
    guard(row[key], `${p}.${key}`);
  }
  for (const [key, guard] of Object.entries(optional)) if (Object.hasOwn(row, key)) guard(row[key], `${p}.${key}`);
};
export const hash: Guard = (v, p) => { if (typeof v !== 'string' || !/^[a-f0-9]{64}$/.test(v)) fail(p); };
export const locale = choices('en', 'ja', 'ko', 'zh');
export const modes = choices('boss', 'maze', 'story');
export const capabilityStatus = choices('M14_REGISTRY_NOT_SUPPLIED', 'NO_STATIC_SKILLS', 'NONE', 'PARTIAL', 'COMPLETE');
const binding = choices('STATIC_ONLY', 'BEHAVIOR_ROOT_BOUND', 'FULL_ACTION_REPRESENTED', 'REFERENCE_SETTLEMENT_BOUND', 'CONTENT_ACTION_EXECUTABLE_REFERENCE');
const support = choices('REPRESENTABLE_BLOCKED', 'BLOCKED_BY_EVIDENCE', 'BLOCKED_BY_REFERENCE_SUPPORT', 'BLOCKED_BY_CONTINUATION', 'NO_SETTLEMENT', 'UNBOUND_STATIC_SKILL');
const readiness = ['SAFE_TO_IMPLEMENT', 'SAFE_TO_REPRESENT_ONLY', 'SAFE_REFERENCE_MODEL_ONLY', 'STRICT_REJECT_UNTIL_NEW_EVIDENCE'];
const blockers = choices('WAIT_ANIM_STATE', 'DAMAGE_PACKET', 'HEAL_PACKET', 'MODIFIER', 'RANDOM_TARGET', 'PREDICATE_CALLBACK', 'SECOND_HOP_CONTINUATION', 'RESOURCE', 'REFERENCE_PACKET_OTHER', 'BEHAVIOR_AFFECTING_NODE_NOT_COMPILED', 'UNKNOWN_OR_UNSUPPORTED');
const reentry = choices('NEW_NATIVE_SPHITRATIO_EVIDENCE', 'WAITANIMSTATE_LOCAL_POLICY_REVIEW', 'MODIFIER_STACKING_EVIDENCE', 'TARGET_RANDOM_CONTRACT', 'PREDICATE_CALLBACK_SUPPORT', 'SECOND_HOP_ORCHESTRATION', 'DAMAGE_PACKET_FIELD_SUPPORT', 'HEAL_PACKET_SUPPORT');
const evidence = choices('NATIVE_EVIDENCED', 'REFERENCE_MODEL', 'SANDBOX_EXTENSION', 'UNSUPPORTED');
const reasons = choices('CONTENT_VERSION_UNAVAILABLE', 'SKILL_NOT_IN_REGISTRY', 'NO_BEHAVIOR_ROOT', 'NO_SETTLEMENT_OBSERVED', 'SECOND_HOP_CONTINUATION_UNRESOLVED', 'BLOCKED_BY_EVIDENCE', 'BLOCKED_BY_REFERENCE_SUPPORT', 'REPRESENTABLE_BUT_NOT_EXECUTABLE', 'UNMAPPED_M14_REASON');
const m14Status = choices('LINKED', 'NO_M14_ROW', 'M14_REGISTRY_NOT_SUPPLIED');
const resolvedKind = choices('MONSTER', 'MONSTER_VARIANT');
const resolution = choices('RESOLVED', 'UNKNOWN');
const no = literal(false);
const yes = literal(true);
const nil = literal(null);
const version = literal(CONTENT_VERSION);
const localized = {
  names: map(text), localized_name: nullable(text), locale: nullable(locale), locale_status: choices('MULTI', 'PRESENT', 'ABSENT'),
};
const display = {
  ...localized, locale_vocabulary: array(locale), available_locales: array(locale), missing_locales: array(locale), locale_fallback_used: no,
};
const descriptiveIdentity = {
  original_game_id: nullable(text), game_id_status: nullable(choices('PRESERVED', 'DERIVED_FROM_PARENT', 'UNRESOLVED')),
  confidence: nullable(text),
  reconstruction_status: nullable(choices('RECONSTRUCTION_READY', 'PARTIAL', 'UNKNOWN', 'UNSUPPORTED')),
  entity_sha256: nullable(hash),
};
const provenance = fields({ entity_provenance: records, entity_provenance_count: count, source: text, invented_provenance: no });
const limitations = { limitations: strings, unresolved_static_references: records };
const common = { game_version: version, provenance: record, unknown: record, runtime_semantics_added: no, product_sha256: hash };
const descriptions = fields({ collection: nullable(text), detail: nullable(text), note: text });
const stageNameKind = choices('STATIC_NUMERIC_ID', 'ABSENT', 'PRESENT');
const stageName: Guard = (v, p) => { if (v !== null && typeof v !== 'string' && typeof v !== 'number' && !(v instanceof LosslessInteger)) fail(p); };
const staticText = fields({ difficulty_name: nullable(text), story_name: nullable(text), maze_context_desc: nullable(text) });

export const summaryRules: Record<Collection, Guard> = {
  characters: fields({ schema: literal(SUMMARY_SCHEMAS.characters), game_version: version, avatar_id: token, ...localized,
    rarity: nullable(count), rarity_code: nullable(text), path: nullable(text), element: nullable(text) }),
  monsters: fields({ schema: literal(SUMMARY_SCHEMAS.monsters), game_version: version, monster_id: token, ...localized,
    rank: nullable(text), monster_camp_id: raw, weaknesses: nullable(strings), variant_count: count, declared_child_count: count }),
  stages: fields({ schema: literal(SUMMARY_SCHEMAS.stages), game_version: version, stage_id: token, stage_name: stageName,
    stage_name_kind: stageNameKind, raw_stage_type: nullable(text), encounter_source_modes: array(modes),
    topology_counts_included: no, wave_count: nil, enemy_placement_count: nil, stage_buff_count: nil, unknown_reference_count: nil }),
  encounters: fields({ schema: literal(SUMMARY_SCHEMAS.encounters), game_version: version, encounter_id: token,
    source_mode: nullable(modes), related_stage_count: count, related_stage_ids: strings, static_display_text: staticText }),
};

const m14Capability = fields({
  authority: literal('content_support.SkillCapability (M14)'), recomputed_by_product_layer: no,
  avatar_id: token, skill_id: token, content_version: version, binding_level: binding, support_status: support,
  representation_readiness: nullable(choices(...readiness, 'NOT_REPRESENTED', 'NOT_APPLICABLE')),
  execution_readiness: choices(...readiness, 'NOT_EXECUTABLE_NO_SETTLEMENT'), settlement_present: flag,
  settlement_kinds: array(choices('DAMAGE_REQUEST', 'HEAL_REQUEST', 'MODIFY_TEAM_SP', 'MODIFY_WEAKNESS')),
  blocker_classes: array(blockers), primary_blocker: nullable(blockers), reentry_hints: array(reentry),
  entry_ability: nullable(text), prepare_ability: nullable(text), version_relation: nullable(choices('EXACT_NATIVE', 'CLOSE_VERSION')),
});
const eligibility = fields({
  authority: literal('content_support.real_content_execution_eligibility (M14)'), recomputed_by_product_layer: no,
  avatar_id: token, skill_id: token, content_version: version, outcome: literal('NOT_ELIGIBLE'),
  reason_code: token, reason_detail: text, execution_evidence_mode: evidence, representation_evidence_mode: evidence,
  satisfies_gate_certificate: no, satisfies_native_evidenced: no,
});
const skillLink = { skill_id: token, m14_status: m14Status, m14_capability: nullable(m14Capability), m14_execution_eligibility: nullable(eligibility) };
const characterSkill = fields({ ...skillLink, skill_numeric_id: nullable(count), name: nullable(text), desc: nullable(text),
  simple_desc: nullable(text), tag: nullable(text), sp_base: raw, bp_add: raw, bp_need: raw, show_stance_list: nullable(array(raw)),
  skill_combo_value_delta: raw, max_level: nullable(count), levels: array(fields({ level: raw, param_list: array(raw) })) });
const capability = fields({ registry_loaded: flag, registry_content_version: nullable(version), source: text, status: capabilityStatus,
  counts_available: flag, static_skill_count: count, skills_with_m14_row: nullable(count), skills_without_m14_row: nullable(count),
  skills_with_m14_row_ids: strings, skills_without_m14_row_ids: strings, execution_eligibility_source: text,
  execution_eligibility_available: flag, skills_with_execution_eligibility: nullable(count), execution_eligibility_outcomes: array(literal('NOT_ELIGIBLE')),
  policy_authority: text, execution_claimed: no });
export const monsterRuntime = fields({ evidence_scope: literal('FAMILY_LEVEL_ONLY'), per_entity_readiness_claim: literal('NONE'),
  monster_ai: literal('NOT_SUPPLIED_BY_THIS_PRODUCT'), monster_skill_execution: literal('NOT_SUPPLIED_BY_THIS_PRODUCT'),
  phase_or_body_part_runtime: literal('NOT_SUPPLIED_BY_THIS_PRODUCT'), battle_state_construction: literal('NOT_SUPPLIED_BY_THIS_PRODUCT'), statement: text });
const formation = fields({ group_index: raw, slot: raw });
const statFields = ['hp_base', 'attack_base', 'defence_base', 'speed_base', 'critical_damage_base', 'stance_base', 'stance_count', 'status_resistance_base', 'initial_delay_ratio', 'minimum_fatigue_ratio'];
const stats = fields(Object.fromEntries(statFields.map(key => [key, raw])));
const variant = fields({ variant_id: nullable(text), is_self_variant: flag, elite_group: raw, hard_level_group: raw,
  stance_weak_list: nullable(array(raw)), damage_type_resistance: nullable(records), skill_ids: strings,
  hp_modify_ratio: raw, attack_modify_ratio: raw, defence_modify_ratio: raw, speed_modify_ratio: raw, speed_modify_value: raw,
  stance_modify_ratio: raw, stance_modify_value: raw });
const noLocale = { localized: no, locale_vocabulary: array(locale), locale_status: literal('NO_LOCALE_STRUCTURE'), note: text };
export const productRules: Record<Collection, Guard> = {
  characters: fields({ ...common, schema: literal(PRODUCT_SCHEMAS.characters),
    identity: fields({ avatar_id: token, ...descriptiveIdentity }),
    display: fields({ ...display, descriptions, rarity: nullable(count), rarity_code: nullable(text), path: nullable(text),
      element: nullable(text), icon: nullable(text), description: nullable(text) }),
    progression: fields({ promotion_keys: strings, promotion_count: count, promotion_stat_tables: map(record),
      level_domain: fields({ explicit_level_cap: nil, max_promotion_key: nullable(text), note: text }) }),
    skills: array(characterSkill),
    traces: array(fields({ trace_id: token, point: text, level: raw, point_id: raw, point_type: raw, point_trigger_key: raw,
      anchor: raw, max_level: raw, pre_point: array(raw), status_add_list: array(raw), level_up_skill_id: strings,
      avatar_level_limit: raw, avatar_promotion_limit: raw, default_unlock: raw, icon: raw })),
    eidolons: array(fields({ rank: raw, eidolon_id: nullable(text), name: nullable(text), desc: nullable(text), param_list: array(raw), icon: raw })),
    equipment: fields({ compatible_lightcone_ids: strings, compatible_lightcone_count: count, relic_reference: nullable(record) }),
    memosprite: (v, p) => {
      fields({ present: flag })(v, p);
      if (object(v, p).present === true) fields({ name: nullable(text), static_skill_ids: strings, hp_skill: raw,
        icon: nullable(text), m14_coverage: literal('NOT_COVERED_BY_AVATAR_SKILL_M14_LINKAGE') })(v, p);
    },
    capability, provenance,
    unknown: fields({ ...limitations, unavailable_sections: strings, missing_locales: array(locale),
      static_skills_without_m14_row: nullable(strings), m14_registry_supplied: flag, execution_eligibility_available: flag,
      skills_without_execution_eligibility: strings }),
  }),
  monsters: fields({ ...common, schema: literal(PRODUCT_SCHEMAS.monsters),
    identity: fields({ requested_id: token, resolved_kind: resolvedKind, canonical_monster_id: nullable(text), variant_id: nullable(text),
      ...descriptiveIdentity, parent_resolved: flag }),
    display: fields({ ...display, names_source: token, descriptions, icon: nullable(text), rank: nullable(text), rank_source: token }),
    static_stats: stats, static_stats_basis: choices('SELF', 'CANONICAL_PARENT', 'UNAVAILABLE'), static_stats_source_monster_id: nullable(text),
    combat_descriptors: fields({ weaknesses: nullable(array(raw)), weaknesses_source: token, damage_type_resistance: nullable(records),
      rank: nullable(text), elite_group: raw, hard_level_group: raw, monster_camp_id: raw, phase_list: nullable(array(raw)), max_monster_phase: raw }),
    skills: array(fields({ skill_id: token, skill_name: raw, skill_desc: raw, damage_type: raw, sp_hit_base: raw, source: token })),
    variant_descriptors: array(variant), context: fields({ level: nullable(count), level_source: choices('CALLER', 'NOT_SUPPLIED'),
      formation: nullable(formation), note: text }), runtime_support: monsterRuntime,
    provenance: fields({ sources: array(fields({ role: choices('SELF', 'REQUESTED_ENTITY', 'CANONICAL_PARENT'), entity_id: token,
      ...descriptiveIdentity, provenance: records, provenance_count: count })), field_sources: map(text), entity_provenance_count: count,
      source: text, invented_provenance: no, parent_provenance_available: flag }),
    unknown: fields({ ...limitations, missing_locales: array(locale), missing_static_stats: strings, damage_type_resistance_supplied: flag }),
  }),
  stages: fields({ ...common, schema: literal(PRODUCT_SCHEMAS.stages),
    identity: fields({ stage_id: token, stage_package_id: nullable(text), ...descriptiveIdentity }),
    display: fields({ ...noLocale, stage_name: stageName, stage_name_kind: stageNameKind, raw_stage_type: nullable(text) }),
    mode: fields({ raw_stage_type: nullable(text), encounter_source_modes: array(modes), canonical_mode: nil,
      canonical_mode_established: no, inference_performed: no, note: text }),
    topology: fields({ authority: text, package_schema: nullable(literal('hsr_battle_agent.stage_package/1')), package_sha256: nullable(hash),
      wave_count: nullable(count), enemy_placement_count: nullable(count), waves: nullable(array(fields({ wave_id: token, wave_index: count,
        enemy_groups: array(fields({ monster_id: raw, level: raw, group_index: raw, slot: raw, resolution_status: resolution })) }))),
      stage_buff_count: nullable(count), stage_buffs: nullable(array(fields({ buff_id: token, resolution_status: resolution }, { detail_source: raw }))),
      encounter_contexts: nullable(array(fields({ encounter_id: token, source_mode: modes, context: record }))),
      unknown_reference_count: nullable(count), unknown_references: nullable(records) }),
    monster_placements: array(fields({ wave_id: nullable(text), wave_index: raw, group_index: raw, slot: raw, monster_id: nullable(text), level: raw,
      resolution_status: resolution, resolved_kind: nullable(resolvedKind), canonical_monster_id: nullable(text),
      monster_product_ref: fields({ service: literal('ContentProductService.get_monster'), monster_id: nullable(text) }) })),
    rules: fields({ authority: text, rule_metadata: record, win_condition_count: count, lose_condition_count: count,
      win_conditions_interpreted: no, mapped_to_scenario_rule_ids: no, execution_semantics: literal('NOT_SUPPLIED') }),
    static_source_metadata: fields({ classification: literal('STATIC_SOURCE_METADATA_ONLY'), note: text, non_interpreted_fields: strings,
      fields_present: strings, fields_absent: strings, stage_name: stageName, stage_name_kind: stageNameKind, stage_type: raw,
      field_values: fields(Object.fromEntries(['stage_name', 'stage_type', 'stage_ability_config', 'monster_list', 'sub_level_graphs',
        'trial_avatar_list', 'forbid_exit_battle', 'hard_level_group', 'monster_warning_ratio', 'level_graph_path', 'elite_group',
        'battle_scoring_group', 'level', 'release', 'stage_config_data'].map(key => [key, raw]))) }),
    provenance: fields({ package_source_refs: records, package_source_ref_count: count, raw_stage_entity_provenance: records,
      raw_stage_entity_provenance_count: count, source: text, invented_source_relationships: no }),
    unknown: fields({ ...limitations, stage_package_unknown_references: records, stage_package_unknown_reference_count: count,
      stage_package_available: flag, raw_stage_available: flag }),
  }),
  encounters: fields({ ...common, schema: literal(PRODUCT_SCHEMAS.encounters),
    identity: fields({ encounter_id: token, source_mode: nullable(modes), ...descriptiveIdentity }),
    display: fields({ ...noLocale, static_display_text: staticText, static_text_fields_present: strings }),
    static_context: fields({ source_mode: nullable(modes), common_fields_present: strings, mode_context_fields_present: strings,
      unrecognised_fields: strings, context_fields_present: strings, static_context: record, context_merged_across_encounters: no }),
    related_stages: array(fields({ stage_id: token, order_supplied: no, stage_exists_in_content: flag,
      stage_product_ref: fields({ service: literal('ContentProductService.get_stage'), stage_id: token }) })),
    related_stage_ids: strings, provenance,
    unknown: fields({ ...limitations, stage_reference_supplied: flag, multiple_stage_identities_supplied: flag, context_merged_across_encounters: no }),
  }),
};

const permissions = { may_create_reference_action_envelope: no, may_enter_player_legal_actions: no, may_expand_planner_successor: no, may_mutate_state: no };
const nonEffects = fields(Object.fromEntries(['reference_action_envelopes', 'player_legal_actions', 'planner_successors', 'state_mutations',
  'rng_draws', 'allocator_tickets', 'scheduler_entries', 'execution_traces', 'gate_certificates', 'transaction_plans', 'staged_deltas'].map(key => [key, literal(0)])));
const admission = fields({ schema: literal('content_planner_admission/1'), content_version: version, skill_key: token, outcome: literal('REJECTED'),
  reason_code: reasons, reason_detail: text, m14_reason_code: nullable(text), binding_level: nullable(binding), support_status: nullable(support),
  blocker_classes: array(blockers), reentry_hints: array(reentry), frontier_packet_field: nullable(text), ...permissions, non_effects: nonEffects,
  m14_row_present: flag, m14_execution_eligibility_present: flag, m14_status: m14Status,
  consumed_from_public_api: literal('admit_content_for_planner'), private_helpers_used: strings });
const outcomeCounts: Guard = (v, p) => {
  for (const [key, entry] of Object.entries(object(v, p))) { literal('REJECTED')(key, `${p}.${key}`); count(entry, `${p}.${key}`); }
};
const reasonCounts: Guard = (v, p) => {
  for (const [key, entry] of Object.entries(object(v, p))) { reasons(key, `${p}.${key}`); count(entry, `${p}.${key}`); }
};
const family = { scope: literal('FAMILY_LEVEL_ONLY'), per_entity_runtime_claim_available: no, per_entity_claim_emitted: no,
  family_facts: records, runtime_mechanisms_not_implemented: strings, non_claims: strings };
const stageStaticRequired = { authority: text, source_stage_present: flag, stage_id: nullable(text), stage_product_sha256: nullable(hash),
  stage_absent_is_not_an_error: flag, unknown_reference_count: count, stage_package_topology_present: flag,
  encounter_source_modes: array(modes), stage_buff_references: array(fields({ buff_id: nullable(text), resolution_status: nullable(resolution) })),
  rule_metadata_present: flag, f9_retained_static_metadata_present: flag, canonical_mode: nil, canonical_mode_established: no };
const stageStaticPresent = { stage_package_sha256: nullable(hash), wave_count: nullable(count), enemy_placement_count: nullable(count), raw_stage_type: nullable(text),
  rule_metadata_interpreted: no, win_condition_count: count, lose_condition_count: count, unknown_references: records,
  f9_fields_present: strings, f9_fields_absent: strings, template_provenance: record };
const unresolvedEntries = { count, entries: records, source: text };
const loadoutEffects = array(fields({ kind: token, status: literal('UNAPPLIED_CONTEXTUAL') }));
export const reportRule = fields({ schema: literal(REPORT_SCHEMA), runtime_semantics_added: no, report_sha256: hash,
  identity: fields({ content_version: version, scenario_id: nullable(text), scenario_mode: nullable(text),
    scenario_package_schema: literal('hsr_battle_agent.scenario_package/2'), scenario_package_sha256: hash,
    scenario_package_hash_verified: yes, source_stage_id: nullable(text), source_stage_present: flag, rng_seed: raw,
    rng_seed_role: text, report_schema: literal(REPORT_SCHEMA) }),
  summary: fields({ player_count: count, wave_count: count, enemy_instance_count: count, variant_enemy_occurrence_count: count,
    static_avatar_skill_count: count, m14_row_count: count, missing_m14_row_count: count, m15_admission_result_count: count,
    m15_admission_outcome_counts: outcomeCounts, m15_reason_code_counts: reasonCounts, stage_unknown_reference_count: count,
    scenario_unresolved_behavior_count: count, unapplied_loadout_effect_count: count }),
  static_resolution: fields({ authority: text, players: array(fields({ instance_id: nullable(text), slot: raw, avatar_id: nullable(text),
    skill_levels: record, trace_state: record, initial_state: record, static_loadout_present: flag,
    static_loadout_schema: nullable(literal('hsr_battle_agent.static_loadout/1')) })),
    waves: array(fields({ wave_id: raw, wave_index: raw, origin: nullable(choices('CALLER', 'TEMPLATE', 'TEMPLATE_WITH_CALLER_OVERRIDE')), override_applied: flag,
      enemies: array(fields({ instance_id: raw, requested_monster_id: nullable(text), level: raw, origin: nullable(choices('CALLER', 'TEMPLATE', 'TEMPLATE_WITH_CALLER_OVERRIDE')),
        resolution: fields({ requested_id: nullable(text), resolved_kind: nullable(resolvedKind), canonical_monster_id: nullable(text), variant_id: nullable(text) }),
        template_position: record })) })),
    buff_bindings: records, buff_binding_count: count, rules: record, unsupported_policy: nullable(choices('reject', 'opaque-disabled')),
    execution_status: nullable(choices('STATIC_READY_BEHAVIOR_COMPILATION_REQUIRED', 'DEBUG_OPAQUE_DISABLED_ONLY', 'BEHAVIOR_RESOLVED')),
    reconstruction_status: nullable(literal('STATIC_RECONSTRUCTION_READY')),
    golden_eligible: nullable(flag), provenance_policy: nullable(text), rule_records_reinterpreted: no,
    unresolved_behavior_distinct_from_missing_static_entities: yes }),
  avatar_content_support: fields({ authority: text, registry_loaded: yes, registry_content_version: version,
    characters: array(fields({ avatar_id: nullable(text), instance_id: nullable(text), slot: raw, character_product_available: flag,
      character_product_sha256: nullable(hash), static_skill_count: count,
      capability: fields({ registry_loaded: flag, status: nullable(capabilityStatus), skills_with_m14_row: nullable(count),
        skills_without_m14_row: nullable(count), skills_without_m14_row_ids: strings, policy_authority: nullable(text) }),
      skills: array(fields(skillLink)), capability_recomputed_here: no, m13_raw_json_read: no })) }),
  real_content_execution_admission: fields({ authority: text, api_used: text, planner_facade_referenced: no, private_helpers_used: strings,
    admission_outcome_vocabulary: strings, accepted_outcomes: array(literal('REJECTED')), future_outcome_auto_extension: no,
    outcome_vocabulary_is_authority_metadata_only: yes, expected_outcome: literal('REJECTED'), unexpected_outcome_handling: text,
    results: array(admission), outcome_counts: outcomeCounts, reason_code_counts: reasonCounts, non_effects: nonEffects,
    non_effects_source: text, permission_fields: fields(permissions) }),
  loadout_static_support: fields({ authority: text, re_evaluated_here: no, contextual_effects_applied_here: no,
    retained_status_vocabulary: array(literal('UNAPPLIED_CONTEXTUAL')),
    players: array(fields({ instance_id: nullable(text), slot: raw, avatar_id: nullable(text), static_loadout_schema: nullable(literal('hsr_battle_agent.static_loadout/1')),
      static_loadout_present: flag, avatar_level: raw, avatar_promotion: raw, eidolon_rank: raw, lightcone_id: nullable(text),
      final_properties: nullable(record), unapplied_contextual_effects: loadoutEffects, unapplied_contextual_count: count,
      all_unapplied_statuses_canonical: yes, contextual_effects_applied_here: no })) }),
  monster_static_support: fields({ authority: text, occurrence_identity_kept_separate_from_monster_identity: yes,
    monster_ai_claimed: no, monster_skill_execution_claimed: no,
    occurrences: array(fields({ wave_id: raw, wave_index: raw, instance_id: raw, requested_monster_id: nullable(text),
      resolved_kind: nullable(resolvedKind), canonical_monster_id: nullable(text), variant_id: nullable(text), level: raw, level_supplied: flag,
      formation: record, formation_source: text, monster_product_available: flag, monster_product_sha256: nullable(hash),
      static_stats_available: flag, missing_static_stats: strings, runtime_support: nullable(monsterRuntime),
      variant_identity_is_static_identity: yes, runtime_support_success_implied: no })) }),
  monster_runtime_support: fields({ ...family, reason: text, exact_static_entity_link_count: nullable(count),
    per_static_monster_behavior_join_available: no, per_static_monster_ai_ledger: fields({ available: flag }) }),
  stage_static_support: (v, p) => {
    fields(stageStaticRequired, stageStaticPresent)(v, p);
    if (object(v, p).source_stage_present === true) fields(stageStaticPresent)(v, p);
    else fields({ note: text })(v, p);
  },
  stage_runtime_support: fields({ ...family, stage_runtime_implemented: no, golden_block: fields({ available: flag }),
    coverage_ledger: fields({ available: flag }), not_inferred_from: strings }),
  unresolved_content: fields({ categories: strings, categories_kept_distinct: yes,
    scenario_unresolved_behavior: fields({ ...unresolvedEntries, meaning: text, is_missing_static_entity: no }),
    stage_unknown_references: fields({ ...unresolvedEntries, stage_present: flag }),
    character_static_skill_without_m14_row: fields(unresolvedEntries),
    m14_blocker_classes_and_reentry_hints: fields({ count, source: text, blocker_class_count: count, blocker_classes: array(blockers),
      reentry_hint_count: count, reentry_hints: array(reentry) }),
    m15_rejection_reasons: fields({ count, source: text, reason_code_counts: reasonCounts }),
    loadout_unapplied_contextual_effects: fields({ ...unresolvedEntries, entries: array(fields({ avatar_id: nullable(text), effects: loadoutEffects })) }),
    monster_static_missing_fields: fields(unresolvedEntries) }),
  unsupported_runtime_mechanisms: fields({ built_from_existing_authorities_only: yes, character_product_limitations: strings,
    monster_product_limitations: strings, stage_product_limitations: strings, m14_blocker_classes: array(blockers), m15_reason_codes: array(reasons),
    m15_non_effect_fields: strings, new_readiness_hierarchy_introduced: no, monster_family_scope: literal('FAMILY_LEVEL_ONLY'),
    stage_family_scope: literal('FAMILY_LEVEL_ONLY'), stage_canonical_mode_established: no }),
  non_claims: fields({ real_content_execution_performed: no, reference_action_envelopes_created: literal(0), player_legal_actions_created: literal(0),
    planner_invoked: no, battle_state_created: no, native_evidence_promoted: no, golden_claimed: no, scenario_is_executable: no,
    scenario_is_planner_ready: no, approximates_game_behavior: no, m15_rejection_proves_game_behavior: no,
    family_level_runtime_evidence_applies_to_an_individual_monster_or_stage: no, non_effects_are_all_zero: yes }),
});
