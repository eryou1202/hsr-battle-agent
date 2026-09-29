import { describe, expect, it, vi } from 'vitest';
import { CONTENT_VERSION } from './productContract';
import { LosslessInteger, parseProductJson, ProductContractError, type ProductObject, type ProductValue } from './productJson';
import { BRIDGE_ERROR_CODES, BRIDGE_ERROR_SCHEMA, type ScenarioCompileRequest } from './scenarioBridgeContract';
import { decodeBridgeInfo, decodeFrontendBridgeError, decodeScenarioPackage, importScenarioPackage, scenarioPackageWireText } from './scenarioBridgeDecode';
import { createConfiguredScenarioBridgeClient, LocalScenarioBridgeClient, ScenarioBridgeConnectionError,
  ScenarioBridgeRequestError, serializeScenarioBridgeJson } from './scenarioBridgeClient';

// Real authority output, imported only by tests. No runtime eager fixtures.
const FIXTURES = import.meta.glob<string>('./scenarioBridgeFixtures/*.json', { eager: true, query: '?raw', import: 'default' });
function source(name: string): string {
  const value = FIXTURES[`./scenarioBridgeFixtures/${name}.json`];
  if (value === undefined) throw new Error(`missing P5B fixture ${name}`);
  return value;
}
function row(value: ProductValue | undefined): ProductObject {
  if (!value || typeof value !== 'object' || Array.isArray(value) || value instanceof LosslessInteger) throw new Error('fixture object required');
  return value;
}
const info = () => row(parseProductJson(source('info')));
const error = (code: typeof BRIDGE_ERROR_CODES[number] = 'SCENARIO_COMPILE_REJECTED') => ({
  schema: BRIDGE_ERROR_SCHEMA, code, message: 'Authority rejected the request.', request_kind: 'SCENARIO_COMPILE',
});
const draft = () => parseProductJson(source('free.request')) as unknown as ScenarioCompileRequest;
const packageDocument = (name = 'free') => importScenarioPackage(source(`${name}.package`), CONTENT_VERSION);
const response = (body: string, status = 200) => new Response(body, { status, headers: { 'Content-Type': 'application/json' } });
function mockBridge() {
  const fetcher = vi.fn<typeof fetch>(async url => {
    const path = new URL(String(url)).pathname;
    if (path === '/api/v1/info') return response(source('info'));
    if (path === '/api/v1/scenario/compile') return response(source('free.package'));
    if (path === '/api/v1/scenario/support') return response(source('free.report'));
    throw new Error('unexpected endpoint');
  });
  const client = new LocalScenarioBridgeClient(CONTENT_VERSION, 'http://127.0.0.1:8765', fetcher);
  const paths = () => fetcher.mock.calls.map(([url]) => new URL(String(url)).pathname);
  return { fetcher, client, paths };
}

describe('P5B transport document guards', () => {
  it('imports real deterministic loopback info unchanged', () => {
    const input = info();
    expect(decodeBridgeInfo(input, CONTENT_VERSION)).toBe(input);
    expect(row(input.capabilities)).toEqual({ scenario_compile: true, scenario_support_report: true,
      battle_execution: false, planner: false, native_execution: false });
    expect(input).not.toHaveProperty('path');
  });
  it.each(['schema', 'bridge_version', 'content_version', 'host_scope', 'capabilities', 'accepted_input', 'produced_documents'])('rejects missing info %s', key => {
    const input = info(); delete input[key];
    expect(() => decodeBridgeInfo(input, CONTENT_VERSION)).toThrow(ProductContractError);
  });
  it('rejects unknown schemas, wrong versions and positive server capabilities', () => {
    for (const change of [{ schema: 'hsr_battle_agent.frontend_bridge_info/2' }, { content_version: 'latest' }, { host_scope: 'REMOTE' }]) {
      expect(() => decodeBridgeInfo({ ...info(), ...change }, CONTENT_VERSION)).toThrow(ProductContractError);
    }
    for (const capability of ['battle_execution', 'planner', 'native_execution']) {
      const input = info(); row(input.capabilities)[capability] = true;
      expect(() => decodeBridgeInfo(input, CONTENT_VERSION)).toThrow(ProductContractError);
    }
  });
  it.each(BRIDGE_ERROR_CODES)('imports transport error %s without semantic defaults', code => {
    const input = error(code);
    expect(decodeFrontendBridgeError(input)).toBe(input);
  });
  it('rejects unknown or incomplete error documents', () => {
    for (const change of [{ schema: 'bridge_error/99' }, { code: 'EXECUTION_ADMITTED' }, { message: null }, { request_kind: 'BATTLE_STEP' }]) {
      expect(() => decodeFrontendBridgeError({ ...error(), ...change })).toThrow(ProductContractError);
    }
    for (const key of ['schema', 'code', 'message', 'request_kind']) {
      const input: ProductObject = error(); delete input[key];
      expect(() => decodeFrontendBridgeError(input)).toThrow(ProductContractError);
    }
  });
});

describe('P5B real ScenarioPackage/2 import', () => {
  it.each(['free', 'stage', 'overlay'])('imports %s verbatim and retains its original wire JSON', name => {
    const input = parseProductJson(source(`${name}.package`));
    expect(decodeScenarioPackage(input, CONTENT_VERSION)).toBe(input);
    const document = packageDocument(name);
    expect(document).toEqual(input);
    expect(scenarioPackageWireText(document)).toBe(source(`${name}.package`));
    expect(document.golden_eligible).toBe(false);
    expect(document).not.toHaveProperty('supported');
    expect(document).not.toHaveProperty('legal_actions');
    expect(document).not.toHaveProperty('battle_state');
  });
  it('preserves P0 variants, P1 template provenance and unknown rule records', () => {
    const stage = packageDocument('stage');
    const wave = stage.waves[0]!;
    expect(wave.origin).toBe('TEMPLATE');
    expect(wave.wave_id).toBe('420101:1');
    expect(wave.provenance.source_stage_id).toBe('420101');
    expect(wave.enemies[0]!.resolution).toEqual({ requested_id: '100401401', resolved_kind: 'MONSTER_VARIANT',
      canonical_monster_id: '1004014', variant_id: '100401401' });
    const overlay = packageDocument('overlay');
    expect(overlay.waves[0]!.origin).toBe('TEMPLATE_WITH_CALLER_OVERRIDE');
    expect(overlay.waves[0]!.override_applied).toBe(true);
    expect(overlay.rules.victory_rule).toEqual({ requested_id: 'caller-reference', resolution_status: 'UNKNOWN',
      resolved_rule: null, authority: null, execution_semantics: 'NONE' });
  });
  it('preserves nullable and absent fields without filling a source Stage', () => {
    expect(packageDocument().source_stage).toBeNull();
    const stage = row(packageDocument('stage').source_stage);
    expect(stage.stage).toBeNull();
    const free = packageDocument();
    expect(free.rules.victory_rule.requested_id).toBeNull();
    expect(free.waves[0]!.wave_id).toBeNull();
    expect(Object.hasOwn(free.players[0]!.initial_state, 'hp')).toBe(false);
  });
  it.each(['schema', 'game_version', 'players', 'waves', 'buff_bindings', 'rules', 'unresolved_behavior',
    'execution_status', 'golden_eligible', 'package_sha256'])('rejects missing Scenario %s', key => {
    const input: ProductObject = packageDocument(); delete input[key];
    expect(() => decodeScenarioPackage(input, CONTENT_VERSION)).toThrow(ProductContractError);
  });
  it('rejects malformed structures and unknown nested identities/statuses', () => {
    const changes = [
      (doc: ReturnType<typeof packageDocument>) => { doc.schema = 'hsr_battle_agent.scenario_package/1' as typeof doc.schema; },
      (doc: ReturnType<typeof packageDocument>) => { doc.game_version = '4.5.54' as typeof doc.game_version; },
      (doc: ReturnType<typeof packageDocument>) => { doc.players = null as unknown as typeof doc.players; },
      (doc: ReturnType<typeof packageDocument>) => { doc.players[0]!.loadout.schema = 'loadout/2'; },
      (doc: ReturnType<typeof packageDocument>) => { doc.waves[0]!.origin = 'RUNTIME' as typeof doc.waves[0]['origin']; },
      (doc: ReturnType<typeof packageDocument>) => { delete doc.waves[0]!.provenance.source_stage_id; },
      (doc: ReturnType<typeof packageDocument>) => { doc.waves[0]!.enemies[0]!.level = '80' as unknown as number; },
      (doc: ReturnType<typeof packageDocument>) => { delete (doc.waves[0]!.enemies[0]!.resolution as ProductObject).variant_id; },
      (doc: ReturnType<typeof packageDocument>) => { doc.rules.victory_rule.execution_semantics = 'EXECUTABLE' as 'NONE'; },
      (doc: ReturnType<typeof packageDocument>) => { doc.unresolved_behavior[0]!.status = 'EXECUTION_READY'; },
      (doc: ReturnType<typeof packageDocument>) => { doc.buff_bindings = [{}]; },
      (doc: ReturnType<typeof packageDocument>) => { doc.package_sha256 = 'invalid'; },
    ];
    for (const change of changes) {
      const input = packageDocument(); change(input);
      expect(() => decodeScenarioPackage(input, CONTENT_VERSION)).toThrow(ProductContractError);
    }
  });
  it.each(['BEHAVIOR_RESOLVED', 'EXECUTABLE', 'NATIVE_READY'])('fails closed on execution-positive state %s', state => {
    expect(() => decodeScenarioPackage({ ...packageDocument(), execution_status: state }, CONTENT_VERSION)).toThrow(ProductContractError);
  });
  it('fails closed on positive golden eligibility and preserves the debug inspection state', () => {
    expect(() => decodeScenarioPackage({ ...packageDocument(), golden_eligible: true }, CONTENT_VERSION)).toThrow(ProductContractError);
    const debug = { ...packageDocument(), unsupported_policy: 'opaque-disabled', execution_status: 'DEBUG_OPAQUE_DISABLED_ONLY' };
    expect(decodeScenarioPackage(debug, CONTENT_VERSION)).toBe(debug);
  });
  it('validates hash shape only; P4 remains the package integrity authority', () => {
    const input = { ...packageDocument(), package_sha256: '0'.repeat(64) };
    expect(decodeScenarioPackage(input, CONTENT_VERSION)).toBe(input);
  });
  it('requires original imported JSON and rejects document mutation before support', () => {
    const parsed = decodeScenarioPackage(parseProductJson(source('free.package')), CONTENT_VERSION);
    expect(() => scenarioPackageWireText(parsed)).toThrow('ORIGINAL_PACKAGE_JSON_REQUIRED');
    const imported = packageDocument(); imported.scenario_id = 'edited-after-compile';
    expect(() => scenarioPackageWireText(imported)).toThrow('PACKAGE_CHANGED_RECOMPILE_REQUIRED');
  });
});

describe('P5B explicit fetch client', () => {
  it('connects only on demand and decodes version/capabilities before compile', async () => {
    const { client, fetcher, paths } = mockBridge();
    expect(client.status).toBe('NOT_CONNECTED'); expect(fetcher).not.toHaveBeenCalled();
    const compiled = await client.compile(draft());
    expect(paths()).toEqual(['/api/v1/info', '/api/v1/scenario/compile']);
    expect(client.status).toBe('CONNECTED');
    expect(compiled).toEqual(packageDocument());
    const options = fetcher.mock.calls[1]![1]!;
    expect(options.method).toBe('POST');
    expect(options.headers).toEqual({ 'Content-Type': 'application/json' });
    expect(parseProductJson(String(options.body))).toEqual(parseProductJson(source('free.request')));
    expect(options.credentials).toBe('omit'); expect(options.redirect).toBe('error');
  });
  it('compile never auto-calls support; explicit second call returns unchanged P4 authority', async () => {
    const { client, fetcher, paths } = mockBridge();
    const compiled = await client.compile(draft());
    expect(paths()).not.toContain('/api/v1/scenario/support');
    const report = await client.support(compiled);
    expect(paths()).toEqual(['/api/v1/info', '/api/v1/scenario/compile', '/api/v1/scenario/support']);
    expect(report).toEqual(parseProductJson(source('free.report')));
    // Python's integral float spelling survives the browser round trip.
    expect(source('free.package')).toContain('98.0');
    expect(JSON.stringify(compiled)).not.toBe(source('free.package'));
    expect(fetcher.mock.calls[2]![1]!.body).toBe(source('free.package'));
    expect(report.non_claims.planner_invoked).toBe(false);
    expect(report.real_content_execution_admission.results.every(item => item.outcome === 'REJECTED')).toBe(true);
    expect(report.monster_runtime_support.scope).toBe('FAMILY_LEVEL_ONLY');
    expect(report.stage_runtime_support.scope).toBe('FAMILY_LEVEL_ONLY');
  });
  it('support import never calls compile, planner or an execution endpoint', async () => {
    const { client, paths } = mockBridge();
    await client.support(packageDocument());
    expect(paths()).toEqual(['/api/v1/info', '/api/v1/scenario/support']);
  });
  it('forwards unresolved drafts to the compiler without local content or rule resolution', async () => {
    const { client, fetcher } = mockBridge();
    fetcher.mockImplementation(async url => new URL(String(url)).pathname === '/api/v1/info'
      ? response(source('info')) : response(JSON.stringify(error()), 422));
    const request = draft(); request.player_team[0]!.avatar.avatar_id = 'unknown-static-avatar';
    request.rules.victory_rule_id = 'unknown-rule';
    await expect(client.compile(request)).rejects.toBeInstanceOf(ScenarioBridgeRequestError);
    expect(parseProductJson(String(fetcher.mock.calls[1]![1]!.body))).toEqual(request);
  });
  it('rejects wrong server/request versions before compile transport', async () => {
    const { client, fetcher, paths } = mockBridge();
    fetcher.mockResolvedValue(response(JSON.stringify({ ...info(), content_version: '4.5.54' })));
    await expect(client.compile(draft())).rejects.toBeInstanceOf(ProductContractError);
    expect(paths()).toEqual(['/api/v1/info']); expect(client.status).toBe('NOT_CONNECTED');
    await expect(client.compile({ ...draft(), game_version: 'latest' as '4.4.54' })).rejects.toBeInstanceOf(ProductContractError);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(() => new LocalScenarioBridgeClient('latest', 'http://127.0.0.1:8765')).toThrow(ProductContractError);
  });
  it('returns explicit NOT_CONNECTED on network failure, with no remote fallback, and permits retry', async () => {
    const { client, fetcher, paths } = mockBridge();
    fetcher.mockRejectedValueOnce(new TypeError('fetch failed'));
    await expect(client.compile(draft())).rejects.toMatchObject({ status: 'NOT_CONNECTED', message: 'LOCAL_SCENARIO_BRIDGE_NOT_CONNECTED' });
    expect(client.status).toBe('NOT_CONNECTED');
    await client.compile(draft());
    expect(paths()).toEqual(['/api/v1/info', '/api/v1/info', '/api/v1/scenario/compile']);
    expect(fetcher.mock.calls.every(([url]) => String(url).startsWith('http://127.0.0.1:8765/'))).toBe(true);
  });
  it('decodes typed backend errors and refuses unknown error schemas', async () => {
    const { client, fetcher } = mockBridge();
    fetcher.mockImplementation(async url => new URL(String(url)).pathname === '/api/v1/info'
      ? response(source('info')) : response(JSON.stringify(error()), 422));
    await expect(client.compile(draft())).rejects.toMatchObject({ httpStatus: 422, document: error() });
    fetcher.mockResolvedValue(response('{"schema":"future_error/2"}', 500));
    await expect(client.compile(draft())).rejects.toBeInstanceOf(ProductContractError);
  });
  it('fails closed on unknown compile/report response schemas and future positive M15', async () => {
    for (const path of ['/api/v1/scenario/compile', '/api/v1/scenario/support']) {
      const { client, fetcher } = mockBridge();
      fetcher.mockImplementation(async url => new URL(String(url)).pathname === '/api/v1/info'
        ? response(source('info')) : response('{"schema":"future_response/2"}'));
      await expect(path.endsWith('compile') ? client.compile(draft()) : client.support(packageDocument())).rejects.toBeInstanceOf(ProductContractError);
    }
    const { client, fetcher } = mockBridge();
    const report = row(parseProductJson(source('free.report')));
    row(row(report.real_content_execution_admission).permission_fields).may_mutate_state = true;
    fetcher.mockImplementation(async url => new URL(String(url)).pathname === '/api/v1/info'
      ? response(source('info')) : response(JSON.stringify(report)));
    await expect(client.support(packageDocument())).rejects.toBeInstanceOf(ProductContractError);
  });
  it('refuses edited packages before any support request and never recalculates hashes', async () => {
    const { client, fetcher } = mockBridge();
    const edited = packageDocument(); edited.scenario_id = 'edited';
    await expect(client.support(edited)).rejects.toThrow('PACKAGE_CHANGED_RECOMPILE_REQUIRED');
    expect(fetcher).not.toHaveBeenCalled();
  });
  it.each(['https://remote.example', 'http://0.0.0.0:8765', 'http://192.168.1.2:8765', 'http://user@localhost:8765',
    'http://localhost:8765/path', 'http://localhost:8765?url=remote', 'http://localhost:8765#remote', ''])('refuses non-explicit loopback origin %s', base => {
    expect(() => new LocalScenarioBridgeClient(CONTENT_VERSION, base)).toThrow(ProductContractError);
  });
  it('requires explicit environment configuration without process launch or connection', () => {
    const { fetcher } = mockBridge();
    expect(() => createConfiguredScenarioBridgeClient(CONTENT_VERSION, '', fetcher)).toThrow(ScenarioBridgeConnectionError);
    expect(() => createConfiguredScenarioBridgeClient(CONTENT_VERSION, null, fetcher)).toThrow(ScenarioBridgeConnectionError);
    const configured = createConfiguredScenarioBridgeClient(CONTENT_VERSION, 'http://localhost:8765/', fetcher);
    expect(configured.baseUrl).toBe('http://localhost:8765');
    expect(configured.status).toBe('NOT_CONNECTED'); expect(fetcher).not.toHaveBeenCalled();
  });
  it('preserves 64-bit draft numeric tokens and rejects rounded/undefined JSON values', () => {
    const request = { ...draft(), rules: { rng_seed: new LosslessInteger('9223372036854775807') } };
    const text = serializeScenarioBridgeJson(request);
    expect(text).toContain('"rng_seed":9223372036854775807');
    expect(row(row(parseProductJson(text)).rules).rng_seed).toEqual(new LosslessInteger('9223372036854775807'));
    expect(() => serializeScenarioBridgeJson({ invalid: undefined })).toThrow(ProductContractError);
    expect(() => serializeScenarioBridgeJson({ invalid: Number.MAX_SAFE_INTEGER + 1 })).toThrow(ProductContractError);
  });
});
