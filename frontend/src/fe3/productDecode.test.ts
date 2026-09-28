import { describe, expect, it, vi } from 'vitest';
import { COLLECTIONS, CONTENT_VERSION, KEY_FIELDS, type Collection } from './productContract';
import { decodeCharacterProduct, decodeDetailChunk, decodeDetailIndex, decodeEncounterProduct, decodeMonsterProduct,
  decodeProductCatalog, decodeProductCollection, decodeScenarioSupportReport, decodeStageProduct } from './productDecode';
import { createFetchProductClient, StaticProductClient } from './productClients';
import { LosslessInteger, parseProductJson, ProductContractError, type ProductObject, type ProductValue } from './productJson';

const VERSION = CONTENT_VERSION;
// Vite loads the real generated files only in this test module. Production
// sources contain no eager glob or static detail import.
const DOCUMENTS = import.meta.glob<string>('../../public/data/product/4.4.54/**/*.json', { eager: true, query: '?raw', import: 'default' });
const load = (location: string): string => {
  const text = DOCUMENTS[`../../public/data/product/4.4.54/${location}`];
  if (text === undefined) throw new Error(`missing generated fixture: ${location}`);
  return text;
};
const parsed = (location: string) => parseProductJson(load(location));
const row = (value: ProductValue | undefined): ProductObject => {
  if (!value || typeof value !== 'object' || Array.isArray(value) || value instanceof LosslessInteger) throw new Error('expected object in fixture');
  return value;
};
const sampleIds = { characters: '1105', monsters: '1002020', stages: '420101', encounters: 'boss:3001:30011:event_id_list1:0' } as const;
const decoders = { characters: decodeCharacterProduct, monsters: decodeMonsterProduct, stages: decodeStageProduct, encounters: decodeEncounterProduct };
function sample(collection: Collection): ProductObject {
  const index = decodeDetailIndex(parsed(`${collection}/detail-index.json`), VERSION, collection);
  const location = index.locations[sampleIds[collection]];
  if (!location) throw new Error('missing sample fixture');
  const chunk = row(parsed(location));
  const docs = chunk.documents as ProductObject[];
  const document = docs.find(doc => row(doc.identity)[collection === 'monsters' ? 'requested_id' : KEY_FIELDS[collection]] === sampleIds[collection]);
  if (!document) throw new Error('missing sample detail');
  return document;
}
const report = (key = 'A_free') => row(parsed(`examples/p4_${key}.json`));
const digest = async (text: string) => {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, '0')).join('');
};

describe('P5A real product transport', () => {
  it('imports the root unchanged, with explicit schemas and no dynamic backend', () => {
    const input = parsed('catalog.json');
    const catalog = decodeProductCatalog(input, VERSION);
    expect(catalog).toBe(input);
    expect(catalog.counts).toEqual({ characters: 97, monsters: 628, stages: 1459, encounters: 1543 });
    expect(catalog.dynamic_backend_connected).toBe(false);
    expect(catalog.scenario_compilation).toBe('NOT_CONNECTED');
    expect(catalog.example_support_reports.every(item => item.examples_only && !item.production_default)).toBe(true);
  });
  it.each(COLLECTIONS)('decodes every real %s summary and full detail without inference', collection => {
    const browse = decodeProductCollection(parsed(`${collection}/catalog.json`), VERSION, collection);
    const index = decodeDetailIndex(parsed(`${collection}/detail-index.json`), VERSION, collection);
    const keys: string[] = [];
    for (const metadata of index.chunks) {
      const input = parsed(metadata.location);
      const chunk = decodeDetailChunk(input, VERSION, collection);
      expect(chunk).toBe(input);
      expect(chunk.documents).toHaveLength(metadata.document_count);
      for (const document of chunk.documents) {
        expect(document.runtime_semantics_added).toBe(false);
        expect(document).not.toHaveProperty('supported');
        expect(document).not.toHaveProperty('legal_actions');
        keys.push(row(document.identity)[collection === 'monsters' ? 'requested_id' : KEY_FIELDS[collection]] as string);
      }
    }
    expect(keys).toHaveLength(browse.count);
    expect(new Set(keys)).toEqual(new Set(Object.keys(index.locations)));
  });
  it.each(['A_free', 'B_stage_backed', 'C_m14_missing'])('imports all P4 sections in %s unchanged', key => {
    const input = report(key);
    const decoded = decodeScenarioSupportReport(input, VERSION);
    expect(decoded).toBe(input);
    for (const section of ['static_resolution', 'avatar_content_support', 'real_content_execution_admission', 'loadout_static_support',
      'monster_static_support', 'monster_runtime_support', 'stage_static_support', 'stage_runtime_support', 'unresolved_content',
      'unsupported_runtime_mechanisms', 'non_claims']) expect(decoded).toHaveProperty(section);
    expect(decoded.monster_runtime_support.scope).toBe('FAMILY_LEVEL_ONLY');
    expect(decoded.stage_runtime_support.scope).toBe('FAMILY_LEVEL_ONLY');
    expect(decoded.real_content_execution_admission.results.every(item => item.outcome === 'REJECTED')).toBe(true);
    expect(decoded.non_claims.scenario_is_executable).toBe(false);
    expect(decoded).not.toHaveProperty('supported');
    expect(decoded).not.toHaveProperty('score');
  });
  it('preserves absent memosprite fields, nullable values and free-stage optional fields', () => {
    const character = decodeCharacterProduct(sample('characters'), VERSION);
    expect(character.memosprite).toEqual({ present: false });
    expect(Object.hasOwn(character.memosprite, 'name')).toBe(false);
    expect(character.display.locale).toBeNull();
    expect(character.display.localized_name).toBeNull();
    const monster = decodeMonsterProduct(sample('monsters'), VERSION);
    expect(monster.context.level).toBeNull();
    expect(monster.context.formation).toBeNull();
    const free = decodeScenarioSupportReport(report(), VERSION);
    expect(free.stage_static_support.stage_id).toBeNull();
    expect(Object.hasOwn(free.stage_static_support, 'wave_count')).toBe(false);
    const missing = decodeScenarioSupportReport(report('C_m14_missing'), VERSION);
    const characterBlock = (missing.avatar_content_support.characters as ProductObject[])[0];
    expect((characterBlock?.skills as ProductObject[]).every(skill => skill.m14_capability === null && skill.m14_execution_eligibility === null)).toBe(true);
  });
  it('keeps 64-bit numeric source IDs exact and rejects rounded native JSON.parse input', () => {
    const input = sample('stages');
    const stage = decodeStageProduct(input, VERSION);
    expect(row(stage.display).stage_name).toBeInstanceOf(LosslessInteger);
    expect((stage.display.stage_name as LosslessInteger).decimal).toBe('1653639074891422479');
    const index = decodeDetailIndex(parsed('stages/detail-index.json'), VERSION, 'stages');
    expect(() => decodeDetailChunk(JSON.parse(load(index.locations['420101']!)), VERSION, 'stages')).toThrow(ProductContractError);
  });
});

describe('P5A fail-closed imports', () => {
  it.each(COLLECTIONS)('rejects unknown schema/version and malformed %s fields', collection => {
    const decode = decoders[collection];
    let input = sample(collection);
    input.schema = 'future_product/2';
    expect(() => decode(input, VERSION)).toThrow(ProductContractError);
    input = sample(collection);
    input.game_version = '4.5.54';
    expect(() => decode(input, VERSION)).toThrow(ProductContractError);
    input = sample(collection);
    input.identity = [];
    expect(() => decode(input, VERSION)).toThrow(ProductContractError);
    for (const field of Object.keys(sample(collection))) {
      input = sample(collection);
      delete input[field];
      expect(() => decode(input, VERSION), `missing ${collection}.${field}`).toThrow(ProductContractError);
    }
  });
  it('rejects unknown root/report/transport schemas, missing sections and nonexplicit versions', () => {
    const root = row(parsed('catalog.json'));
    root.schema = 'future/2';
    expect(() => decodeProductCatalog(root, VERSION)).toThrow(ProductContractError);
    for (const version of ['', 'latest', '4.5.54']) {
      expect(() => decodeProductCatalog(parsed('catalog.json'), version)).toThrow(ProductContractError);
      expect(() => new StaticProductClient(version, async () => '')).toThrow(ProductContractError);
    }
    for (const field of Object.keys(report())) {
      const input = report();
      delete input[field];
      expect(() => decodeScenarioSupportReport(input, VERSION), `missing report.${field}`).toThrow(ProductContractError);
    }
    const unknown = report(); unknown.schema = 'scenario_support_report/2';
    expect(() => decodeScenarioSupportReport(unknown, VERSION)).toThrow(ProductContractError);
    const index = row(parsed('characters/detail-index.json')); index.schema = 'future/1';
    expect(() => decodeDetailIndex(index, VERSION, 'characters')).toThrow(ProductContractError);
    const browse = row(parsed('monsters/catalog.json')); browse.schema = 'future/1';
    expect(() => decodeProductCollection(browse, VERSION, 'monsters')).toThrow(ProductContractError);
  });
  it('requires even nullable nested fields and never fills missing values', () => {
    const input = sample('monsters');
    delete row(input.context).level;
    expect(() => decodeMonsterProduct(input, VERSION)).toThrow(ProductContractError);
    const character = sample('characters');
    delete row(character.display).localized_name;
    expect(() => decodeCharacterProduct(character, VERSION)).toThrow(ProductContractError);
    const reportInput = report('C_m14_missing');
    const characters = row(reportInput.avatar_content_support).characters as ProductObject[];
    delete (characters[0]!.skills as ProductObject[])[0]!.m14_execution_eligibility;
    expect(() => decodeScenarioSupportReport(reportInput, VERSION)).toThrow(ProductContractError);
  });
  it('rejects unknown closed M14 vocabularies, eligibility promotions and mismatched identities', () => {
    for (const field of ['binding_level', 'support_status', 'representation_readiness', 'execution_readiness', 'primary_blocker', 'version_relation']) {
      const input = sample('characters');
      row((input.skills as ProductObject[])[0]!.m14_capability)[field] = 'FUTURE_POSITIVE';
      expect(() => decodeCharacterProduct(input, VERSION)).toThrow(ProductContractError);
    }
    const input = sample('characters');
    row((input.skills as ProductObject[])[0]!.m14_execution_eligibility).outcome = 'ELIGIBLE';
    expect(() => decodeCharacterProduct(input, VERSION)).toThrow(ProductContractError);
    const identity = sample('characters');
    row((identity.skills as ProductObject[])[0]!.m14_capability).avatar_id = 'different';
    expect(() => decodeCharacterProduct(identity, VERSION)).toThrow(ProductContractError);
    const status = sample('characters'); (status.skills as ProductObject[])[0]!.m14_status = 'READY';
    expect(() => decodeCharacterProduct(status, VERSION)).toThrow(ProductContractError);
    const source = sample('encounters'); row(source.identity).source_mode = 'canonical-battle-mode';
    expect(() => decodeEncounterProduct(source, VERSION)).toThrow(ProductContractError);
  });
  it('rejects future positive M15 states and permission/non-effect changes', () => {
    for (const [field, value] of [['expected_outcome', 'ADMITTED'], ['future_outcome_auto_extension', true], ['accepted_outcomes', ['REJECTED', 'ADMITTED']]] as const) {
      const input = report();
      row(input.real_content_execution_admission)[field] = Array.isArray(value) ? [...value] : value as ProductValue;
      expect(() => decodeScenarioSupportReport(input, VERSION)).toThrow(ProductContractError);
    }
    for (const field of ['outcome', 'may_create_reference_action_envelope', 'may_enter_player_legal_actions', 'may_expand_planner_successor', 'may_mutate_state']) {
      const input = report();
      const result = (row(input.real_content_execution_admission).results as ProductObject[])[0]!;
      result[field] = field === 'outcome' ? 'ADMITTED' : true;
      expect(() => decodeScenarioSupportReport(input, VERSION)).toThrow(ProductContractError);
    }
    const input = report(); row(row(input.real_content_execution_admission).non_effects).rng_draws = 1;
    expect(() => decodeScenarioSupportReport(input, VERSION)).toThrow(ProductContractError);
    const summary = report(); row(row(summary.summary).m15_admission_outcome_counts).ADMITTED = 1;
    expect(() => decodeScenarioSupportReport(summary, VERSION)).toThrow(ProductContractError);
    const metadata = report(); row(metadata.real_content_execution_admission).admission_outcome_vocabulary = ['REJECTED', 'ADMITTED'];
    expect(decodeScenarioSupportReport(metadata, VERSION).real_content_execution_admission.expected_outcome).toBe('REJECTED');
  });
  it('rejects per-entity runtime claims and canonical mode inference', () => {
    for (const section of ['monster_runtime_support', 'stage_runtime_support']) {
      const input = report(); row(input[section]).scope = 'PER_ENTITY';
      expect(() => decodeScenarioSupportReport(input, VERSION)).toThrow(ProductContractError);
      const positive = report(); row(positive[section]).per_entity_claim_emitted = true;
      expect(() => decodeScenarioSupportReport(positive, VERSION)).toThrow(ProductContractError);
    }
    const monster = sample('monsters'); row(monster.runtime_support).monster_ai = 'SUPPORTED';
    expect(() => decodeMonsterProduct(monster, VERSION)).toThrow(ProductContractError);
    const stage = sample('stages'); row(stage.mode).canonical_mode = 'MemoryOfChaos';
    expect(() => decodeStageProduct(stage, VERSION)).toThrow(ProductContractError);
    const ready = report(); row(ready.non_claims).scenario_is_executable = true;
    expect(() => decodeScenarioSupportReport(ready, VERSION)).toThrow(ProductContractError);
  });
  it.each(['{"a":1,"a":2}', '[1,]', '{"a":1,}', '01', '1e999', '1 trailing', '{"a":undefined}', '"unclosed'])('rejects malformed JSON %s', text => {
    expect(() => parseProductJson(text)).toThrow(ProductContractError);
  });
});

describe('P5A static sources', () => {
  it('loads only root on catalog request and only the requested browse collection', async () => {
    const loader = vi.fn(async (location: string) => load(location));
    const client = new StaticProductClient(VERSION, loader, digest);
    expect(loader).not.toHaveBeenCalled();
    await client.catalog();
    expect(loader.mock.calls.map(call => call[0])).toEqual(['catalog.json']);
    expect(await client.listStages()).toHaveLength(1459);
    expect(loader.mock.calls.map(call => call[0])).toEqual(['catalog.json', 'stages/catalog.json']);
    expect(client.scenarioCompilationConnection.status).toBe('NOT_CONNECTED');
    expect(client).not.toHaveProperty('compileScenario');
  });
  it('loads details lazily, reuses a chunk and returns null for unknown keys', async () => {
    const loader = vi.fn(async (location: string) => load(location));
    const client = new StaticProductClient(VERSION, loader, digest);
    expect((await client.getCharacter('1105'))?.identity.avatar_id).toBe('1105');
    expect(loader).toHaveBeenCalledTimes(3);
    await client.getCharacter('1105');
    expect(loader).toHaveBeenCalledTimes(3);
    expect(await client.getCharacter('missing')).toBeNull();
    expect(loader).toHaveBeenCalledTimes(3);
    expect((await client.getMonster('1002020'))?.context.level).toBeNull();
    expect((await client.getStage('420101'))?.mode.canonical_mode).toBeNull();
    expect((await client.getEncounter(sampleIds.encounters))?.identity.source_mode).toBe('boss');
  });
  it('imports reports independently and loads only explicitly chosen examples', async () => {
    const loader = vi.fn(async (location: string) => load(location));
    const client = new StaticProductClient(VERSION, loader, digest);
    client.importSupportReport(load('examples/p4_A_free.json'));
    expect(loader).not.toHaveBeenCalled();
    expect((await client.loadExampleSupportReport('C_m14_missing')).stage_runtime_support.scope).toBe('FAMILY_LEVEL_ONLY');
    expect(loader.mock.calls.map(call => call[0])).toEqual(['catalog.json', 'examples/p4_C_m14_missing.json']);
    await expect(client.loadExampleSupportReport('production-default')).rejects.toThrow('EXAMPLE_NOT_FOUND');
  });
  it('rejects tampered chunks, unsafe paths and mismatched bases without a fallback', async () => {
    const client = new StaticProductClient(VERSION, async location => load(location) + (location.includes('details-') ? ' ' : ''), digest);
    await expect(client.getCharacter('1105')).rejects.toThrow('detail.chunk.integrity');
    const root = JSON.parse(load('catalog.json')) as ProductObject;
    row(row(root.collections).stages).catalog_location = '../content_index.json';
    expect(() => decodeProductCatalog(root, VERSION)).toThrow(ProductContractError);
    const fetcher = vi.fn<typeof fetch>();
    expect(() => createFetchProductClient(VERSION, '/data/product/latest/', fetcher)).toThrow(ProductContractError);
    const fetched = createFetchProductClient(VERSION, '/data/product/4.4.54/', fetcher);
    expect(fetcher).not.toHaveBeenCalled();
    fetcher.mockResolvedValueOnce(new Response('unavailable', { status: 404 }));
    await expect(fetched.catalog()).rejects.toThrow('STATIC_DOCUMENT_HTTP_404');
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
