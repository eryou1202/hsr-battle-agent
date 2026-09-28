/** Presentation mirrors of P2/P3/P4 authority; no browser policy or execution. */
import type { LosslessInteger, ProductObject, ProductValue } from './productJson';
export const CONTENT_VERSION = '4.4.54' as const;
export const COLLECTIONS = ['characters', 'monsters', 'stages', 'encounters'] as const;
export type Collection = typeof COLLECTIONS[number];
export const PRODUCT_SCHEMAS = {
  characters: 'hsr_battle_agent.character_product/1',
  monsters: 'hsr_battle_agent.monster_product/1',
  stages: 'hsr_battle_agent.stage_product/1',
  encounters: 'hsr_battle_agent.encounter_product/1',
} as const;
export const SUMMARY_SCHEMAS = {
  characters: 'hsr_battle_agent.character_summary/1',
  monsters: 'hsr_battle_agent.monster_summary/1',
  stages: 'hsr_battle_agent.stage_summary/1',
  encounters: 'hsr_battle_agent.encounter_summary/1',
} as const;
export const KEY_FIELDS = { characters: 'avatar_id', monsters: 'monster_id', stages: 'stage_id', encounters: 'encounter_id' } as const;
export const REPORT_SCHEMA = 'hsr_battle_agent.scenario_support_report/1' as const;
export type Locale = 'en' | 'ja' | 'ko' | 'zh';
export type LocaleStatus = 'MULTI' | 'PRESENT' | 'ABSENT';
export type SourceMode = 'boss' | 'maze' | 'story';
export type M14Status = 'LINKED' | 'NO_M14_ROW' | 'M14_REGISTRY_NOT_SUPPLIED';
export type CapabilityStatus = 'M14_REGISTRY_NOT_SUPPLIED' | 'NO_STATIC_SKILLS' | 'NONE' | 'PARTIAL' | 'COMPLETE';
export type BindingLevel = 'STATIC_ONLY' | 'BEHAVIOR_ROOT_BOUND' | 'FULL_ACTION_REPRESENTED' | 'REFERENCE_SETTLEMENT_BOUND' | 'CONTENT_ACTION_EXECUTABLE_REFERENCE';
export type SupportStatus = 'REPRESENTABLE_BLOCKED' | 'BLOCKED_BY_EVIDENCE' | 'BLOCKED_BY_REFERENCE_SUPPORT' | 'BLOCKED_BY_CONTINUATION' | 'NO_SETTLEMENT' | 'UNBOUND_STATIC_SKILL';
export interface LocalizedDisplay extends ProductObject {
  names: ProductObject; localized_name: string | null; locale: Locale | null; locale_status: LocaleStatus;
}
export interface CharacterSummary extends LocalizedDisplay {
  schema: typeof SUMMARY_SCHEMAS.characters; game_version: typeof CONTENT_VERSION; avatar_id: string;
  rarity: number | null; rarity_code: string | null; path: string | null; element: string | null;
}
export interface MonsterSummary extends LocalizedDisplay {
  schema: typeof SUMMARY_SCHEMAS.monsters; game_version: typeof CONTENT_VERSION; monster_id: string;
  rank: string | null; monster_camp_id: ProductValue; weaknesses: ProductValue;
  variant_count: number; declared_child_count: number;
}
export interface StageSummary extends ProductObject {
  schema: typeof SUMMARY_SCHEMAS.stages; game_version: typeof CONTENT_VERSION; stage_id: string;
  stage_name: number | LosslessInteger | string | null; stage_name_kind: 'STATIC_NUMERIC_ID' | 'ABSENT' | 'PRESENT';
  raw_stage_type: string | null; encounter_source_modes: SourceMode[]; topology_counts_included: false;
  wave_count: null; enemy_placement_count: null; stage_buff_count: null; unknown_reference_count: null;
}
export interface EncounterSummary extends ProductObject {
  schema: typeof SUMMARY_SCHEMAS.encounters; game_version: typeof CONTENT_VERSION; encounter_id: string;
  source_mode: SourceMode | null; related_stage_count: number; related_stage_ids: string[]; static_display_text: ProductObject;
}
export interface SummaryByCollection {
  characters: CharacterSummary; monsters: MonsterSummary; stages: StageSummary; encounters: EncounterSummary;
}
export interface ProductCollection<C extends Collection> extends ProductObject {
  schema: 'hsr_battle_agent.fe3_product_collection/1'; content_version: typeof CONTENT_VERSION;
  collection: C; row_schema: typeof SUMMARY_SCHEMAS[C]; count: number; rows: SummaryByCollection[C][];
}
export interface ProductLocation extends ProductObject {
  catalog_location: string; detail_index_location: string; key_field: string; summary_schema: string; document_schema: string;
}
export interface ExampleSupportReport extends ProductObject {
  key: string; location: string; examples_only: true; production_default: false; document_schema: typeof REPORT_SCHEMA; sha256: string;
}
export interface ProductCatalog extends ProductObject {
  schema: 'hsr_battle_agent.fe3_product_catalog/1'; content_version: typeof CONTENT_VERSION;
  available_collections: Collection[]; counts: ProductObject & Record<Collection, number>;
  collections: ProductObject & Record<Collection, ProductLocation>; document_schemas: ProductObject;
  generation_provenance: ProductObject; version_fallback: 'NONE'; dynamic_backend_connected: false;
  scenario_compilation: 'NOT_CONNECTED'; detail_transport: 'ON_DEMAND_INDEXED_CHUNKS'; example_support_reports: ExampleSupportReport[];
}
export interface ExecutionEligibility extends ProductObject {
  outcome: 'NOT_ELIGIBLE'; avatar_id: string; skill_id: string; content_version: typeof CONTENT_VERSION;
  satisfies_gate_certificate: false; satisfies_native_evidenced: false;
}
export interface CharacterSkill extends ProductObject {
  skill_id: string; m14_status: M14Status; m14_capability: ProductObject | null;
  m14_execution_eligibility: ExecutionEligibility | null;
}
interface ProductBase extends ProductObject {
  game_version: typeof CONTENT_VERSION; identity: ProductObject; display: ProductObject;
  provenance: ProductObject; unknown: ProductObject; runtime_semantics_added: false; product_sha256: string;
}
export interface CharacterProduct extends ProductBase {
  schema: typeof PRODUCT_SCHEMAS.characters; identity: ProductObject & { avatar_id: string };
  display: LocalizedDisplay & { rarity: number | null; path: string | null; element: string | null };
  progression: ProductObject; skills: CharacterSkill[]; traces: ProductObject[]; eidolons: ProductObject[];
  equipment: ProductObject; memosprite: ProductObject;
  capability: ProductObject & { status: CapabilityStatus; execution_claimed: false };
}
export interface MonsterRuntimeSupport extends ProductObject {
  evidence_scope: 'FAMILY_LEVEL_ONLY'; per_entity_readiness_claim: 'NONE';
  monster_ai: 'NOT_SUPPLIED_BY_THIS_PRODUCT'; monster_skill_execution: 'NOT_SUPPLIED_BY_THIS_PRODUCT';
  phase_or_body_part_runtime: 'NOT_SUPPLIED_BY_THIS_PRODUCT'; battle_state_construction: 'NOT_SUPPLIED_BY_THIS_PRODUCT';
}
export interface MonsterProduct extends ProductBase {
  schema: typeof PRODUCT_SCHEMAS.monsters; identity: ProductObject & { requested_id: string; resolved_kind: 'MONSTER' | 'MONSTER_VARIANT'; canonical_monster_id: string | null; variant_id: string | null };
  display: LocalizedDisplay; static_stats: ProductObject; combat_descriptors: ProductObject;
  skills: ProductObject[]; variant_descriptors: ProductObject[]; context: ProductObject & { level: number | null; formation: ProductObject | null };
  runtime_support: MonsterRuntimeSupport;
}
export interface StageProduct extends ProductBase {
  schema: typeof PRODUCT_SCHEMAS.stages; identity: ProductObject & { stage_id: string };
  mode: ProductObject & { canonical_mode: null; canonical_mode_established: false; inference_performed: false; encounter_source_modes: SourceMode[] };
  topology: ProductObject; monster_placements: ProductObject[]; rules: ProductObject; static_source_metadata: ProductObject;
}
export interface EncounterProduct extends ProductBase {
  schema: typeof PRODUCT_SCHEMAS.encounters; identity: ProductObject & { encounter_id: string; source_mode: SourceMode | null };
  static_context: ProductObject; related_stages: ProductObject[]; related_stage_ids: string[];
}
export interface ProductByCollection { characters: CharacterProduct; monsters: MonsterProduct; stages: StageProduct; encounters: EncounterProduct }
export interface DetailChunk<C extends Collection> extends ProductObject {
  schema: 'hsr_battle_agent.fe3_product_detail_chunk/1'; content_version: typeof CONTENT_VERSION;
  collection: C; document_schema: typeof PRODUCT_SCHEMAS[C]; documents: ProductByCollection[C][];
}
export interface ChunkLocation extends ProductObject {
  location: string; size_bytes: number; sha256: string; document_count: number; oversize_single_document: boolean;
}
export interface DetailIndex<C extends Collection> extends ProductObject {
  schema: 'hsr_battle_agent.fe3_product_detail_index/1'; content_version: typeof CONTENT_VERSION; collection: C;
  document_schema: typeof PRODUCT_SCHEMAS[C]; key_field: typeof KEY_FIELDS[C]; count: number;
  locations: ProductObject & Record<string, string>; chunks: ChunkLocation[]; chunk_target_bytes: number;
  product_documents_total_bytes: number; transport_total_bytes: number;
}
export interface FamilyRuntimeSupport extends ProductObject {
  scope: 'FAMILY_LEVEL_ONLY'; per_entity_runtime_claim_available: false; per_entity_claim_emitted: false;
}
export interface RejectedAdmission extends ProductObject {
  schema: 'content_planner_admission/1'; content_version: typeof CONTENT_VERSION; outcome: 'REJECTED';
  may_create_reference_action_envelope: false; may_enter_player_legal_actions: false;
  may_expand_planner_successor: false; may_mutate_state: false; non_effects: ProductObject;
}
export interface ScenarioSupportReport extends ProductObject {
  schema: typeof REPORT_SCHEMA; identity: ProductObject & { content_version: typeof CONTENT_VERSION };
  summary: ProductObject; static_resolution: ProductObject; avatar_content_support: ProductObject;
  real_content_execution_admission: ProductObject & { expected_outcome: 'REJECTED'; results: RejectedAdmission[] };
  loadout_static_support: ProductObject; monster_static_support: ProductObject; monster_runtime_support: FamilyRuntimeSupport;
  stage_static_support: ProductObject; stage_runtime_support: FamilyRuntimeSupport;
  unresolved_content: ProductObject; unsupported_runtime_mechanisms: ProductObject; non_claims: ProductObject;
  runtime_semantics_added: false; report_sha256: string;
}
