/** Fail-closed imports return the validated authority document unchanged. */
import {
  COLLECTIONS, CONTENT_VERSION, KEY_FIELDS, PRODUCT_SCHEMAS, REPORT_SCHEMA, SUMMARY_SCHEMAS,
  type CharacterProduct, type Collection, type DetailChunk, type DetailIndex, type EncounterProduct,
  type MonsterProduct, type ProductByCollection, type ProductCatalog, type ProductCollection,
  type ScenarioSupportReport, type StageProduct,
} from './productContract';
import { assertProductValue, type ProductObject } from './productJson';
import { array, choices, count, fail, fields, flag, hash, literal, map, object, productRules,
  reportRule, strings, summaryRules, text, token } from './productImportRules';

export function requireVersion(version: string): asserts version is typeof CONTENT_VERSION {
  if (version !== CONTENT_VERSION) fail('content_version: explicit 4.4.54 required');
}
export function safeLocation(value: unknown, path: string): asserts value is string {
  token(value, path);
  if (typeof value !== 'string' || !/^[A-Za-z0-9_./-]+\.json$/.test(value) || value.startsWith('/') ||
      value.split('/').some(part => part === '.' || part === '..' || part === '')) fail(path);
}
function unique(values: string[], path: string) {
  if (new Set(values).size !== values.length) fail(`${path}: duplicate key`);
}

export function decodeProductCatalog(value: unknown, version: string): ProductCatalog {
  requireVersion(version);
  assertProductValue(value);
  fields({ schema: literal('hsr_battle_agent.fe3_product_catalog/1'), content_version: literal(version),
    available_collections: array(choices(...COLLECTIONS)), counts: map(count), collections: object,
    document_schemas: map(text), generation_provenance: fields({ starting_head: token, content_version: literal(version),
      generator: token, locale: literal(null), m14_registry_supplied: literal(true),
      authorities: array(fields({ path: token, sha256: hash })) }),
    version_fallback: literal('NONE'), dynamic_backend_connected: literal(false), scenario_compilation: literal('NOT_CONNECTED'),
    detail_transport: literal('ON_DEMAND_INDEXED_CHUNKS'),
    example_support_reports: array(fields({ key: token, location: safeLocation, examples_only: literal(true),
      production_default: literal(false), document_schema: literal(REPORT_SCHEMA), sha256: hash })) })(value, '$');
  const catalog = value as unknown as ProductCatalog;
  if (catalog.available_collections.length !== COLLECTIONS.length) fail('$.available_collections');
  unique(catalog.available_collections, '$.available_collections');
  unique(catalog.example_support_reports.map(item => item.key), '$.example_support_reports');
  for (const name of COLLECTIONS) {
    count(catalog.counts[name], `$.counts.${name}`);
    literal(PRODUCT_SCHEMAS[name])(catalog.document_schemas[name], `$.document_schemas.${name}`);
    fields({ catalog_location: safeLocation, detail_index_location: safeLocation, key_field: literal(KEY_FIELDS[name]),
      summary_schema: literal(SUMMARY_SCHEMAS[name]), document_schema: literal(PRODUCT_SCHEMAS[name]) })(catalog.collections[name], `$.collections.${name}`);
  }
  literal(REPORT_SCHEMA)(catalog.document_schemas.scenario_support_report, '$.document_schemas.scenario_support_report');
  return catalog;
}

export function decodeProductCollection<C extends Collection>(value: unknown, version: string, collection: C): ProductCollection<C> {
  requireVersion(version);
  assertProductValue(value);
  fields({ schema: literal('hsr_battle_agent.fe3_product_collection/1'), content_version: literal(version), collection: literal(collection),
    row_schema: literal(SUMMARY_SCHEMAS[collection]), count, rows: array(summaryRules[collection]) })(value, '$');
  const catalog = value as unknown as ProductCollection<C>;
  if (catalog.rows.length !== catalog.count) fail('$.count');
  unique(catalog.rows.map(row => row[KEY_FIELDS[collection]] as string), '$.rows');
  return catalog;
}

export function productKey(collection: Collection, document: ProductByCollection[Collection]): string {
  return document.identity[collection === 'monsters' ? 'requested_id' : KEY_FIELDS[collection]] as string;
}
function validateLinkIdentity(skills: unknown, avatarId: unknown, path: string) {
  if (!Array.isArray(skills)) fail(path);
  for (const [index, skill] of skills.entries()) {
    const row = object(skill, `${path}[${index}]`);
    for (const name of ['m14_capability', 'm14_execution_eligibility']) {
      if (row[name] !== null) {
        const linked = object(row[name], `${path}[${index}].${name}`);
        if (linked.avatar_id !== avatarId || linked.skill_id !== row.skill_id) fail(`${path}[${index}].${name}.identity`);
      }
    }
  }
}
export function decodeProduct<C extends Collection>(value: unknown, version: string, collection: C): ProductByCollection[C] {
  requireVersion(version);
  assertProductValue(value);
  productRules[collection](value, '$');
  const document = value as unknown as ProductByCollection[C];
  if (collection === 'characters') validateLinkIdentity(document.skills, document.identity.avatar_id, '$.skills');
  return document;
}
export const decodeCharacterProduct = (value: unknown, version: string): CharacterProduct => decodeProduct(value, version, 'characters');
export const decodeMonsterProduct = (value: unknown, version: string): MonsterProduct => decodeProduct(value, version, 'monsters');
export const decodeStageProduct = (value: unknown, version: string): StageProduct => decodeProduct(value, version, 'stages');
export const decodeEncounterProduct = (value: unknown, version: string): EncounterProduct => decodeProduct(value, version, 'encounters');

export function decodeDetailIndex<C extends Collection>(value: unknown, version: string, collection: C): DetailIndex<C> {
  requireVersion(version);
  assertProductValue(value);
  fields({ schema: literal('hsr_battle_agent.fe3_product_detail_index/1'), content_version: literal(version), collection: literal(collection),
    document_schema: literal(PRODUCT_SCHEMAS[collection]), key_field: literal(KEY_FIELDS[collection]), count,
    locations: map(safeLocation), chunks: array(fields({ location: safeLocation, size_bytes: count, sha256: hash,
      document_count: count, oversize_single_document: flag })), chunk_target_bytes: count, product_documents_total_bytes: count,
    transport_total_bytes: count })(value, '$');
  const index = value as unknown as DetailIndex<C>;
  if (Object.keys(index.locations).length !== index.count) fail('$.count');
  unique(index.chunks.map(chunk => chunk.location), '$.chunks');
  if (index.chunk_target_bytes < 256) fail('$.chunk_target_bytes');
  const counts = new Map<string, number>();
  for (const [key, location] of Object.entries(index.locations)) {
    token(key, '$.locations.key');
    counts.set(location, (counts.get(location) ?? 0) + 1);
  }
  for (const chunk of index.chunks) {
    if (chunk.document_count === 0 || counts.get(chunk.location) !== chunk.document_count ||
        chunk.oversize_single_document !== (chunk.size_bytes > index.chunk_target_bytes) ||
        (chunk.oversize_single_document && chunk.document_count !== 1)) fail('$.chunks');
    counts.delete(chunk.location);
  }
  if (counts.size || index.transport_total_bytes !== index.chunks.reduce((sum, chunk) => sum + chunk.size_bytes, 0)) fail('$.chunks');
  return index;
}

export function decodeDetailChunk<C extends Collection>(value: unknown, version: string, collection: C): DetailChunk<C> {
  requireVersion(version);
  assertProductValue(value);
  fields({ schema: literal('hsr_battle_agent.fe3_product_detail_chunk/1'), content_version: literal(version), collection: literal(collection),
    document_schema: literal(PRODUCT_SCHEMAS[collection]), documents: array(productRules[collection]) })(value, '$');
  const chunk = value as unknown as DetailChunk<C>;
  unique(chunk.documents.map(document => productKey(collection, document)), '$.documents');
  if (collection === 'characters') {
    for (const document of chunk.documents) validateLinkIdentity(document.skills, document.identity.avatar_id, '$.documents.skills');
  }
  return chunk;
}

export function decodeScenarioSupportReport(value: unknown, version: string): ScenarioSupportReport {
  requireVersion(version);
  assertProductValue(value);
  reportRule(value, '$');
  const report = value as unknown as ScenarioSupportReport;
  const characters = report.avatar_content_support.characters as ProductObject[];
  characters.forEach(character => validateLinkIdentity(character.skills, character.avatar_id, '$.avatar_content_support.characters.skills'));
  // Authority vocabulary is metadata. Widening it cannot widen accepted outcomes.
  const accepted = report.real_content_execution_admission.accepted_outcomes;
  if (!Array.isArray(accepted) || accepted.length !== 1 || accepted[0] !== 'REJECTED') fail('$.real_content_execution_admission.accepted_outcomes');
  strings(report.real_content_execution_admission.admission_outcome_vocabulary, '$.real_content_execution_admission.admission_outcome_vocabulary');
  return report;
}
