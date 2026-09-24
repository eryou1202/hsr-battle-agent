import { describe, expect, it } from 'vitest';
import { buildStrictStages, isPreCommitStage, type StrictPipelineInput } from './strictStages';
import { findMockScenario } from '../fixtures';
import type { ActionPreview, StrictStageState } from '../models';

function stateOf(stages: readonly { id: string; state: StrictStageState }[], id: string) {
  return stages.find((stage) => stage.id === id)?.state;
}

const EMPTY_INPUT: StrictPipelineInput = {
  requestLabel: null,
  preview: null,
  execution: null,
};

describe('strict pipeline stages', () => {
  it('reports NOT_AVAILABLE for every stage when nothing is supplied', () => {
    const stages = buildStrictStages(EMPTY_INPUT);
    expect(stages).toHaveLength(11);
    for (const stage of stages) expect(stage.state).toBe('NOT_AVAILABLE');
  });

  it('does not infer later stages from earlier ones', () => {
    // A request exists but no documents at all: only REQUEST may be READY.
    const stages = buildStrictStages({ requestLabel: 'act', preview: null, execution: null });
    expect(stateOf(stages, 'REQUEST')).toBe('READY');
    expect(stateOf(stages, 'DEPENDENCY_OBLIGATION')).toBe('NOT_AVAILABLE');
    expect(stateOf(stages, 'GATE_CERTIFICATE')).toBe('NOT_AVAILABLE');
    expect(stateOf(stages, 'STRICT_STEP_RESULT')).toBe('NOT_AVAILABLE');
  });

  it('classifies obligations with UNKNOWN as BLOCKED and UNSUPPORTED as UNSUPPORTED', () => {
    const unknown = buildStrictStages({
      requestLabel: 'b',
      preview: findMockScenario('B')?.previews['act-unknown-skill'] as ActionPreview,
      execution: null,
    });
    expect(stateOf(unknown, 'DEPENDENCY_OBLIGATION')).toBe('BLOCKED');
    expect(stateOf(unknown, 'DEPENDENCY_CLOSURE')).toBe('BLOCKED');
    expect(stateOf(unknown, 'PREFLIGHT_RESULT')).toBe('REJECTED');
    expect(stateOf(unknown, 'GATE_CERTIFICATE')).toBe('NOT_AVAILABLE');

    const unsupported = buildStrictStages({
      requestLabel: 'c',
      preview: findMockScenario('C')?.previews['act-unsupported-strike'] as ActionPreview,
      execution: null,
    });
    expect(stateOf(unsupported, 'DEPENDENCY_OBLIGATION')).toBe('UNSUPPORTED');
    expect(stateOf(unsupported, 'DEPENDENCY_CLOSURE')).toBe('BLOCKED');
  });

  it('keeps a CLOSED closure distinct from a sealed certificate', () => {
    const stages = buildStrictStages({
      requestLabel: 'd',
      preview: findMockScenario('D')?.previews['act-reference-skill'] as ActionPreview,
      execution: null,
    });
    expect(stateOf(stages, 'DEPENDENCY_CLOSURE')).toBe('READY');
    expect(stateOf(stages, 'PREFLIGHT_RESULT')).toBe('READY');
    // Reference evidence does not certify.
    expect(stateOf(stages, 'GATE_CERTIFICATE')).toBe('REJECTED');
    expect(stateOf(stages, 'TRANSACTION_PLAN')).toBe('NOT_AVAILABLE');
  });

  it('marks a stale certificate as BLOCKED, not READY', () => {
    const stages = buildStrictStages({
      requestLabel: 'e',
      preview: findMockScenario('E')?.previews['act-stale-strike'] as ActionPreview,
      execution: findMockScenario('E')?.executions['act-stale-strike'] ?? null,
    });
    expect(stateOf(stages, 'GATE_CERTIFICATE')).toBe('BLOCKED');
    expect(stateOf(stages, 'ATOMIC_COMMIT')).toBe('NOT_AVAILABLE');
    expect(stateOf(stages, 'STRICT_STEP_RESULT')).toBe('REJECTED');
  });

  it('reaches COMMITTED only from a supplied strict step document', () => {
    const stages = buildStrictStages({
      requestLabel: 'a',
      preview: findMockScenario('A')?.previews['act-strict-noop'] as ActionPreview,
      execution: findMockScenario('A')?.executions['act-strict-noop'] ?? null,
    });
    expect(stateOf(stages, 'DEPENDENCY_CLOSURE')).toBe('READY');
    expect(stateOf(stages, 'GATE_CERTIFICATE')).toBe('READY');
    expect(stateOf(stages, 'TRANSACTION_PLAN')).toBe('READY');
    expect(stateOf(stages, 'ATOMIC_COMMIT')).toBe('COMMITTED');
    expect(stateOf(stages, 'STRICT_STEP_RESULT')).toBe('COMMITTED');
  });

  it('flags the pre-commit stages', () => {
    expect(isPreCommitStage('STAGED_DELTA')).toBe(true);
    expect(isPreCommitStage('TRANSACTION_RNG')).toBe(true);
    expect(isPreCommitStage('STAGED_TRACE')).toBe(true);
    expect(isPreCommitStage('ATOMIC_COMMIT')).toBe(false);
    expect(isPreCommitStage('STRICT_STEP_RESULT')).toBe(false);
  });
});
