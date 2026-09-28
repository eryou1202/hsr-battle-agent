/** Static, lazy JSON sources. No live Scenario bridge or compilation callback. */
import type {
  CharacterProduct, CharacterSummary, Collection, DetailChunk, DetailIndex, EncounterProduct, EncounterSummary,
  MonsterProduct, MonsterSummary, ProductByCollection, ProductCatalog, ProductCollection, ScenarioSupportReport, StageProduct, StageSummary,
} from './productContract';
import { decodeDetailChunk, decodeDetailIndex, decodeProductCatalog, decodeProductCollection, decodeScenarioSupportReport,
  productKey, requireVersion, safeLocation } from './productDecode';
import { parseProductJson, ProductContractError } from './productJson';

export interface ProductCatalogSource { catalog(): Promise<ProductCatalog> }
export interface CharacterProductSource { listCharacters(): Promise<readonly CharacterSummary[]>; getCharacter(avatarId: string): Promise<CharacterProduct | null> }
export interface MonsterProductSource { listMonsters(): Promise<readonly MonsterSummary[]>; getMonster(monsterId: string): Promise<MonsterProduct | null> }
export interface StageProductSource { listStages(): Promise<readonly StageSummary[]>; getStage(stageId: string): Promise<StageProduct | null> }
export interface EncounterProductSource { listEncounters(): Promise<readonly EncounterSummary[]>; getEncounter(encounterId: string): Promise<EncounterProduct | null> }
export interface ScenarioSupportReportSource {
  importSupportReport(text: string): ScenarioSupportReport;
  loadExampleSupportReport(key: string): Promise<ScenarioSupportReport>;
}
export type StaticProductTextLoader = (relativeLocation: string) => Promise<string>;
export type ProductDigest = (text: string) => Promise<string>;
export const SCENARIO_COMPILATION_CONNECTION = {
  status: 'NOT_CONNECTED', dynamic_backend_connected: false,
} as const;

async function digestText(text: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, '0')).join('');
}

/** Construction performs no I/O. Root catalog is 3 KB; collections/indexes and
 * detail chunks load only when explicitly requested. At most one cached detail
 * chunk per family bounds retained detail data. Unknown keys return null.
 */
export class StaticProductClient implements ProductCatalogSource, CharacterProductSource, MonsterProductSource,
  StageProductSource, EncounterProductSource, ScenarioSupportReportSource {
  readonly scenarioCompilationConnection = SCENARIO_COMPILATION_CONNECTION;
  private root: Promise<ProductCatalog> | undefined;
  private readonly collections = new Map<Collection, Promise<ProductCollection<Collection>>>();
  private readonly indexes = new Map<Collection, Promise<DetailIndex<Collection>>>();
  private readonly chunks = new Map<Collection, { location: string; promise: Promise<DetailChunk<Collection>> }>();
  constructor(readonly contentVersion: string, private readonly loadText: StaticProductTextLoader,
    private readonly digest: ProductDigest = digestText) {
    requireVersion(contentVersion);
  }
  private async read(location: string): Promise<string> {
    safeLocation(location, 'location');
    return this.loadText(location);
  }
  catalog(): Promise<ProductCatalog> {
    if (!this.root) {
      this.root = this.read('catalog.json').then(text => decodeProductCatalog(parseProductJson(text), this.contentVersion));
      void this.root.catch(() => { this.root = undefined; });
    }
    return this.root;
  }
  private async browse<C extends Collection>(collection: C): Promise<ProductCollection<C>> {
    const root = await this.catalog();
    let promise = this.collections.get(collection);
    if (!promise) {
      promise = this.read(root.collections[collection].catalog_location).then(text => {
        const catalog = decodeProductCollection(parseProductJson(text), this.contentVersion, collection);
        if (catalog.count !== root.counts[collection]) throw new ProductContractError('collection.count');
        return catalog;
      });
      this.collections.set(collection, promise);
      void promise.catch(() => { this.collections.delete(collection); });
    }
    return promise as Promise<ProductCollection<C>>;
  }
  private async index<C extends Collection>(collection: C): Promise<DetailIndex<C>> {
    const root = await this.catalog();
    let promise = this.indexes.get(collection);
    if (!promise) {
      promise = this.read(root.collections[collection].detail_index_location).then(text => {
        const index = decodeDetailIndex(parseProductJson(text), this.contentVersion, collection);
        if (index.count !== root.counts[collection]) throw new ProductContractError('index.count');
        return index;
      });
      this.indexes.set(collection, promise);
      void promise.catch(() => { this.indexes.delete(collection); });
    }
    return promise as Promise<DetailIndex<C>>;
  }
  private async detail<C extends Collection>(collection: C, key: string): Promise<ProductByCollection[C] | null> {
    const index = await this.index(collection);
    if (!Object.hasOwn(index.locations, key)) return null;
    const location = index.locations[key];
    if (!location) throw new ProductContractError('detail.location');
    let cached = this.chunks.get(collection);
    if (!cached || cached.location !== location) {
      const promise = this.read(location).then(async text => {
        const metadata = index.chunks.find(chunk => chunk.location === location);
        if (!metadata || new TextEncoder().encode(text).length !== metadata.size_bytes ||
            await this.digest(text) !== metadata.sha256) throw new ProductContractError('detail.chunk.integrity');
        const chunk = decodeDetailChunk(parseProductJson(text), this.contentVersion, collection);
        if (chunk.documents.length !== metadata.document_count ||
            chunk.documents.some(document => index.locations[productKey(collection, document)] !== location)) {
          throw new ProductContractError('detail.chunk.index');
        }
        return chunk;
      });
      cached = { location, promise };
      this.chunks.set(collection, cached);
      void promise.catch(() => { if (this.chunks.get(collection)?.promise === promise) this.chunks.delete(collection); });
    }
    const chunk = await cached.promise;
    const document = chunk.documents.find(item => productKey(collection, item) === key);
    if (!document) throw new ProductContractError('detail.key');
    return document as ProductByCollection[C];
  }
  async listCharacters() { return (await this.browse('characters')).rows; }
  async listMonsters() { return (await this.browse('monsters')).rows; }
  async listStages() { return (await this.browse('stages')).rows; }
  async listEncounters() { return (await this.browse('encounters')).rows; }
  getCharacter(avatarId: string) { return this.detail('characters', avatarId); }
  getMonster(monsterId: string) { return this.detail('monsters', monsterId); }
  getStage(stageId: string) { return this.detail('stages', stageId); }
  getEncounter(encounterId: string) { return this.detail('encounters', encounterId); }
  importSupportReport(text: string) {
    return decodeScenarioSupportReport(parseProductJson(text), this.contentVersion);
  }
  async loadExampleSupportReport(key: string): Promise<ScenarioSupportReport> {
    const root = await this.catalog();
    const example = root.example_support_reports.find(row => row.key === key);
    if (!example) throw new ProductContractError('example.key', 'EXAMPLE_NOT_FOUND');
    const text = await this.read(example.location);
    if (await this.digest(text) !== example.sha256) throw new ProductContractError('example.integrity');
    return this.importSupportReport(text);
  }
}

/** Fetch only existing JSON assets from an explicitly selected versioned base.
 * This supplies no endpoint for compilation, admission or runtime execution.
 */
export function createFetchProductClient(version: string, versionedBaseUrl: string, fetcher: typeof fetch = fetch): StaticProductClient {
  requireVersion(version);
  if (!versionedBaseUrl.endsWith(`/${version}/`)) throw new ProductContractError('base_url.version');
  return new StaticProductClient(version, async location => {
    const response = await fetcher(`${versionedBaseUrl}${location}`);
    if (!response.ok) throw new ProductContractError(location, `STATIC_DOCUMENT_HTTP_${response.status}`);
    return response.text();
  });
}
