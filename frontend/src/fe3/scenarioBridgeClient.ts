/** Two explicit dynamic calls; static P5A sources and UI remain independent. */
import { decodeScenarioSupportReport, requireVersion } from './productDecode';
import { assertProductValue, LosslessInteger, parseProductJson, ProductContractError, type ProductValue } from './productJson';
import type { ScenarioSupportReport } from './productContract';
import type { BridgeInfo, FrontendBridgeError, ScenarioCompileRequest, ScenarioCompileSource, ScenarioPackage, ScenarioSupportSource } from './scenarioBridgeContract';
import { decodeBridgeInfo, decodeFrontendBridgeError, decodeScenarioPackage, importScenarioPackage, scenarioPackageWireText } from './scenarioBridgeDecode';

export class ScenarioBridgeConnectionError extends Error {
  readonly status = 'NOT_CONNECTED' as const;
  constructor() { super('LOCAL_SCENARIO_BRIDGE_NOT_CONNECTED'); }
}
export class ScenarioBridgeRequestError extends Error {
  constructor(readonly document: FrontendBridgeError, readonly httpStatus: number) {
    super(`${document.code}: ${document.message}`);
  }
}

/** Transport serialization preserves imported backend numeric tokens. It
 * computes no package hash, reference resolution or Scenario semantic value.
 */
export function serializeScenarioBridgeJson(value: unknown): string {
  assertProductValue(value);
  function encode(entry: ProductValue): string {
    if (entry instanceof LosslessInteger) return entry.decimal;
    if (entry === null || typeof entry !== 'object') return JSON.stringify(entry);
    if (Array.isArray(entry)) return `[${entry.map(encode).join(',')}]`;
    return `{${Object.entries(entry).map(([key, child]) => `${JSON.stringify(key)}:${encode(child)}`).join(',')}}`;
  }
  return encode(value);
}

function loopbackBase(value: string): string {
  let url: URL;
  try { url = new URL(value); } catch { throw new ProductContractError('bridge.base_url'); }
  if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(url.hostname) || url.username || url.password ||
      (url.pathname !== '' && url.pathname !== '/') || url.search || url.hash) throw new ProductContractError('bridge.base_url: explicit loopback HTTP origin required');
  return url.origin;
}

export class LocalScenarioBridgeClient implements ScenarioCompileSource, ScenarioSupportSource {
  readonly baseUrl: string;
  private infoPromise: Promise<BridgeInfo> | undefined;
  private connectionStatus: 'NOT_CONNECTED' | 'CONNECTED' = 'NOT_CONNECTED';
  get status() { return this.connectionStatus; }
  constructor(readonly contentVersion: string, baseUrl: string, private readonly fetcher: typeof fetch = fetch) {
    requireVersion(contentVersion);
    this.baseUrl = loopbackBase(baseUrl);
  }
  private async request(path: string, body?: string): Promise<string> {
    let response: Response;
    let text: string;
    try {
      response = await this.fetcher(`${this.baseUrl}${path}`, {
        method: body === undefined ? 'GET' : 'POST',
        ...(body === undefined ? {} : { body, headers: { 'Content-Type': 'application/json' } }),
        credentials: 'omit', redirect: 'error', cache: 'no-store', signal: AbortSignal.timeout(15_000),
      });
      text = await response.text();
    } catch {
      this.connectionStatus = 'NOT_CONNECTED';
      this.infoPromise = undefined;
      throw new ScenarioBridgeConnectionError();
    }
    if (!response.ok) throw new ScenarioBridgeRequestError(decodeFrontendBridgeError(parseProductJson(text)), response.status);
    return text;
  }
  info(): Promise<BridgeInfo> {
    if (!this.infoPromise) {
      const promise = this.request('/api/v1/info').then(text => {
        const info = decodeBridgeInfo(parseProductJson(text), this.contentVersion);
        this.connectionStatus = 'CONNECTED';
        return info;
      });
      this.infoPromise = promise;
      void promise.catch(() => { this.connectionStatus = 'NOT_CONNECTED'; if (this.infoPromise === promise) this.infoPromise = undefined; });
    }
    return this.infoPromise;
  }
  async compile(request: ScenarioCompileRequest): Promise<ScenarioPackage> {
    if (request.game_version !== this.contentVersion) throw new ProductContractError('request.game_version');
    const body = serializeScenarioBridgeJson(request);
    await this.info();
    return importScenarioPackage(await this.request('/api/v1/scenario/compile', body), this.contentVersion);
  }
  async support(scenario: ScenarioPackage): Promise<ScenarioSupportReport> {
    decodeScenarioPackage(scenario, this.contentVersion);
    const body = scenarioPackageWireText(scenario);
    await this.info();
    return decodeScenarioSupportReport(parseProductJson(await this.request('/api/v1/scenario/support', body)), this.contentVersion);
  }
}

/** Optional Vite environment configuration; missing configuration is explicit.
 * This helper is invoked by future UI wiring, never automatically at startup.
 */
export function createConfiguredScenarioBridgeClient(version: string, configuredUrl: unknown = import.meta.env.VITE_HSR_BRIDGE_URL,
  fetcher: typeof fetch = fetch): LocalScenarioBridgeClient {
  requireVersion(version);
  if (typeof configuredUrl !== 'string' || !configuredUrl.trim()) throw new ScenarioBridgeConnectionError();
  return new LocalScenarioBridgeClient(version, configuredUrl, fetcher);
}
