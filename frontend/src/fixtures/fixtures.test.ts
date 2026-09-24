import { describe, expect, it } from 'vitest';
import { MOCK_SCENARIOS, findMockScenario } from './index';
import { fixtureHex } from './shared';
import { BACKEND_MODES, isBackendMode } from '../models';
import { liveStateUnchangedVerified } from '../models/transaction';

describe('fixture registry', () => {
  it('exposes the seven required demo scenarios', () => {
    expect(MOCK_SCENARIOS.map((bundle) => bundle.descriptor.id)).toEqual([
      'A',
      'B',
      'C',
      'D',
      'E',
      'F',
      'G',
    ]);
  });

  it('covers every required mock category', () => {
    const categories = MOCK_SCENARIOS.map((bundle) => bundle.descriptor.category);
    expect(categories).toContain('CLOSED_NOOP');
    expect(categories).toContain('UNKNOWN');
    expect(categories).toContain('UNSUPPORTED');
    expect(categories).toContain('REFERENCE_MODEL');
    expect(categories).toContain('STALE_REVISION');
    expect(categories).toContain('COMMIT');
    expect(categories).toContain('QUARANTINE');
  });

  it('marks every scenario as mock data', () => {
    for (const bundle of MOCK_SCENARIOS) {
      expect(bundle.session.dataProvenance).toBe('MOCK_DATA');
      expect(bundle.session.adapterKind).toBe('MOCK');
      expect(bundle.session.contentVersion).toBe('4.4.54');
      expect(isBackendMode(bundle.session.backendMode)).toBe(true);
      expect(BACKEND_MODES).toContain(bundle.session.backendMode);
    }
  });

  it('supplies a preview and execution record for every action', () => {
    for (const bundle of MOCK_SCENARIOS) {
      expect(bundle.actions.length).toBeGreaterThan(0);
      for (const action of bundle.actions) {
        expect(bundle.previews[action.id], `preview for ${action.id}`).toBeDefined();
        expect(bundle.executions[action.id], `execution for ${action.id}`).toBeDefined();
      }
    }
  });

  it('mirrors the real serialized schema strings', () => {
    // The real backend values — not the earlier placeholder spellings.
    for (const bundle of MOCK_SCENARIOS) {
      const preflight = bundle.previews[bundle.actions[0]?.id ?? '']?.preflight;
      for (const blocker of preflight?.closure.blockers ?? []) {
        expect(blocker.schema).toBe('dependency_closure_blocker/1');
      }
      const cert = bundle.previews[bundle.actions[0]?.id ?? '']?.certificate.certificate;
      if (cert) expect(cert.schema).toBe('terra_gate_certificate/1');
    }
  });

  it('never marks an UNKNOWN or UNSUPPORTED action as AVAILABLE', () => {
    for (const bundle of MOCK_SCENARIOS) {
      for (const action of bundle.actions) {
        const preview = bundle.previews[action.id];
        if (action.support === 'UNKNOWN' || action.support === 'UNSUPPORTED') {
          expect(preview?.certificate.status).not.toBe('ISSUED');
          expect(preview?.certificate.certificate).toBeNull();
        }
        if (action.support === 'REFERENCE_ONLY') {
          expect(preview?.certificate.status).toBe('REFUSED');
        }
      }
    }
  });

  it('keeps a CLOSED closure and a sealed certificate distinct', () => {
    expect(findMockScenario('A')?.previews['act-strict-noop']?.certificate.status).toBe('ISSUED');
    expect(findMockScenario('D')?.previews['act-reference-skill']?.certificate.status).toBe('REFUSED');
  });

  it('claims live state unchanged only when identities actually match', () => {
    for (const bundle of MOCK_SCENARIOS) {
      for (const action of bundle.actions) {
        const execution = bundle.executions[action.id];
        if (!execution) continue;
        const verified = liveStateUnchangedVerified(execution);
        // A claim is only allowed when a revision window was supplied AND the
        // before/after documents match.
        if (execution.revisionWindow === null) expect(verified).toBe(false);
        if (verified) {
          expect(execution.revisionWindow?.before.counter).toBe(
            execution.revisionWindow?.after.counter,
          );
        }
      }
    }
    // Scenario E is the only atomic rejection with a matching window.
    const stale = findMockScenario('E')?.executions['act-stale-strike'];
    expect(stale).toBeDefined();
    if (stale) expect(liveStateUnchangedVerified(stale)).toBe(true);

    // Scenario G is rejected but supplies no window, so no claim is possible.
    const quarantined = findMockScenario('G')?.executions['act-fc02-refresh'];
    expect(quarantined).toBeDefined();
    if (quarantined) expect(liveStateUnchangedVerified(quarantined)).toBe(false);
  });

  it('leaves live state unchanged for rejected and unsupported executions', () => {
    for (const bundle of MOCK_SCENARIOS) {
      for (const action of bundle.actions) {
        const execution = bundle.executions[action.id];
        if (!execution) continue;
        if (
          execution.outcome === 'REJECTED' ||
          execution.outcome === 'UNSUPPORTED' ||
          execution.outcome === 'NOT_PERFORMED'
        ) {
          expect(execution.liveStateUnchanged).toBe(true);
          expect(execution.commit).toBeNull();
        }
      }
    }
  });

  it('models FC-02 quarantine as data, one slot per operation and mode', () => {
    const quarantine = findMockScenario('G')?.quarantine ?? [];
    expect(quarantine.length).toBe(3);
    const refreshNative = quarantine.filter(
      (entry) => entry.slot.operation === 'Refresh' && entry.slot.evidenceMode === 'NATIVE_EVIDENCED',
    );
    const refreshReference = quarantine.filter(
      (entry) => entry.slot.operation === 'Refresh' && entry.slot.evidenceMode === 'REFERENCE_MODEL',
    );
    expect(refreshNative[0]?.slot.status).toBe('BLOCKED_NATIVE');
    expect(refreshNative[0]?.slot.blockers.length).toBeGreaterThan(0);
    expect(refreshReference[0]?.slot.status).toBe('REFERENCE_ONLY');
    expect(refreshReference[0]?.slot.legacyFixtureLabel).toBeTruthy();
    // The future corrected slot stays blocked rather than being promoted.
    const replace = quarantine.find((entry) => entry.slot.operation === 'Replace');
    expect(replace?.slot.status).toBe('BLOCKED_NATIVE');
  });

  it('produces stable fixture digests across calls', () => {
    expect(fixtureHex('seed')).toBe(fixtureHex('seed'));
    expect(fixtureHex('seed')).not.toBe(fixtureHex('other'));
    expect(fixtureHex('seed')).toMatch(/^[0-9a-f]{64}$/);
  });
});
