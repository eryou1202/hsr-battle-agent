import { describe, expect, it } from 'vitest';
import { MockBattleBackendAdapter } from './MockBattleBackendAdapter';
import { BackendNotConnectedError, LiveBattleBackendAdapter } from './LiveBattleBackendAdapter';
import { certificateMatchesRevision } from '../models/certificate';
import { isClosureStatus, isObligationResolution } from '../models/preflight';
import { isEvidenceMode } from '../models/evidence';
import { revision } from '../fixtures/shared';

describe('MockBattleBackendAdapter', () => {
  it('reports itself as mock-only and never as a live connection', async () => {
    const adapter = new MockBattleBackendAdapter();
    const info = adapter.cloneInfo();
    expect(info.adapterKind).toBe('MOCK');
    expect(info.contractStatus).toBe('MOCK_ONLY');
    expect(info.unsupportedMethods).toEqual([]);
    const session = await adapter.getSessionInfo();
    expect(session.dataProvenance).toBe('MOCK_DATA');
    expect(session.connection).toBe('CONNECTED');
  });

  it('serves a snapshot and actions for the loaded scenario', async () => {
    const adapter = new MockBattleBackendAdapter({ scenarioId: 'A' });
    const snapshot = await adapter.getBattleSnapshot();
    const actions = await adapter.getAvailableActions();
    expect(snapshot).not.toBeNull();
    expect(snapshot?.allies.length).toBeGreaterThan(0);
    expect(actions.length).toBeGreaterThan(0);
  });

  it('returns a preview for a known action and the execution record on execute', async () => {
    const adapter = new MockBattleBackendAdapter({ scenarioId: 'A' });
    const preview = await adapter.previewAction({ actionId: 'act-strict-noop', targetId: null });
    expect(preview?.preflight?.outcome).toBe('CLOSED');
    const execution = await adapter.executeAction({ actionId: 'act-strict-noop', targetId: null });
    expect(execution.outcome).toBe('COMMITTED');
    expect(execution.liveStateUnchanged).toBe(false);
    expect(execution.strictStep?.outcome).toBe('COMMITTED');
  });

  it('serves quarantine slots only for the scenario that supplies them', async () => {
    const withQuarantine = new MockBattleBackendAdapter({ scenarioId: 'G' });
    expect((await withQuarantine.getQuarantineEntries()).length).toBeGreaterThan(0);
    const without = new MockBattleBackendAdapter({ scenarioId: 'A' });
    expect(await without.getQuarantineEntries()).toEqual([]);
  });

  it('reports NOT_PERFORMED instead of guessing for an unknown action id', async () => {
    const adapter = new MockBattleBackendAdapter();
    const execution = await adapter.executeAction({ actionId: 'does-not-exist', targetId: null });
    expect(execution.outcome).toBe('NOT_PERFORMED');
    expect(execution.liveStateUnchanged).toBe(true);
  });

  it('switches scenario deterministically', () => {
    const adapter = new MockBattleBackendAdapter();
    expect(adapter.loadScenario('E')).toBe(true);
    expect(adapter.getLoadedScenarioId()).toBe('E');
    expect(adapter.loadScenario('nope')).toBe(false);
    expect(adapter.getLoadedScenarioId()).toBe('E');
  });
});

describe('LiveBattleBackendAdapter', () => {
  it('is explicitly not connected and throws a typed error for every method', async () => {
    const adapter = new LiveBattleBackendAdapter();
    const info = adapter.cloneInfo();
    expect(info.contractStatus).toBe('NOT_CONNECTED');
    expect(info.supportedMethods).toEqual([]);
    expect(info.unsupportedMethods.length).toBeGreaterThan(0);

    await expect(adapter.getSessionInfo()).rejects.toBeInstanceOf(BackendNotConnectedError);
    await expect(adapter.getBattleSnapshot()).rejects.toThrowError(/NOT_CONNECTED/);
    await expect(adapter.getAvailableActions()).rejects.toThrowError(BackendNotConnectedError);
    await expect(
      adapter.executeAction({ actionId: 'x', targetId: null }),
    ).rejects.toThrowError(BackendNotConnectedError);
  });
});

describe('model guards', () => {
  it('accepts only the declared vocabularies', () => {
    expect(isEvidenceMode('NATIVE_EVIDENCED')).toBe(true);
    expect(isEvidenceMode('AVAILABLE')).toBe(false);
    expect(isClosureStatus('BLOCKED_UNKNOWN')).toBe(true);
    expect(isClosureStatus('CLOSED_OK')).toBe(false);
    expect(isObligationResolution('RESOLVED')).toBe(true);
    expect(isObligationResolution('BLOCKED')).toBe(false);
  });

  it('detects a stale certificate rather than silently reusing it', () => {
    const sealed = revision(7, 'snap');
    const live = revision(9, 'snap');
    expect(
      certificateMatchesRevision({ status: 'ISSUED', certificate: null, refusalReason: null, sealedAgainstRevision: null }, live),
    ).toBe('UNKNOWN');
    const view = {
      status: 'ISSUED' as const,
      certificate: {
        schema: 'terra_gate_certificate/1' as const,
        planIdentity: 'p',
        evidenceMode: 'NATIVE_EVIDENCED' as const,
        policyIdentity: null as never,
        inputIdentity: 'i',
        inputRevision: 'r7',
        stateRevision: sealed,
        contractRef: null as never,
        contractRevision: '1',
        closureIdentity: 'c',
        allowedReads: [],
        allowedWrites: [],
        identity: 'id',
      },
      refusalReason: null,
      sealedAgainstRevision: sealed,
    };
    expect(certificateMatchesRevision(view, live)).toBe('STALE');
    expect(certificateMatchesRevision(view, sealed)).toBe('MATCHES');
  });
});
