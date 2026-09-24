/**
 * Strict pipeline stage derivation.
 *
 * Every stage reads ONLY the document supplied for THAT stage. No stage is
 * inferred from the stage before it: if a document is absent the stage is
 * `NOT_AVAILABLE`, never "probably fine".
 *
 * This file performs presentation-level classification of supplied serialized
 * documents. It computes no battle semantics.
 */
import type {
  ActionPreview,
  ExecutionResult,
  JsonValue,
  StrictPipelineStageId,
  StrictStageState,
  StrictStageView,
} from '../models';
import { asJson } from './format';

export interface StrictPipelineInput {
  /** The selected action label, when an action is selected. */
  readonly requestLabel: string | null;
  readonly preview: ActionPreview | null;
  readonly execution: ExecutionResult | null;
}

const STAGE_LABELS: Record<StrictPipelineStageId, string> = {
  REQUEST: 'Action / Request',
  DEPENDENCY_OBLIGATION: 'DependencyObligation',
  DEPENDENCY_CLOSURE: 'DependencyClosure',
  PREFLIGHT_RESULT: 'PreflightResult',
  GATE_CERTIFICATE: 'GateCertificate',
  TRANSACTION_PLAN: 'TransactionPlan',
  STAGED_DELTA: 'StagedDelta',
  TRANSACTION_RNG: 'TransactionRng',
  STAGED_TRACE: 'StagedTrace',
  ATOMIC_COMMIT: 'AtomicCommit',
  STRICT_STEP_RESULT: 'StrictStepResult',
};

function stage(
  id: StrictPipelineStageId,
  state: StrictStageState,
  basis: string,
  identity: string | null = null,
  document: JsonValue | null = null,
): StrictStageView {
  return { id, label: STAGE_LABELS[id], state, basis, identity, document };
}

function notAvailable(id: StrictPipelineStageId, basis: string): StrictStageView {
  return stage(id, 'NOT_AVAILABLE', basis);
}

export function buildStrictStages(input: StrictPipelineInput): readonly StrictStageView[] {
  const { preview, execution } = input;

  // -- 1. REQUEST ---------------------------------------------------------
  const request = input.requestLabel
    ? stage('REQUEST', 'READY', `Selected request: ${input.requestLabel}`, input.requestLabel, {
        action_label: input.requestLabel,
      })
    : notAvailable('REQUEST', 'No action selected.');

  // -- 2. DEPENDENCY_OBLIGATION ------------------------------------------
  const obligations = preview?.preflight?.closure.obligations ?? null;
  const obligationStage = (): StrictStageView => {
    if (!obligations) return notAvailable('DEPENDENCY_OBLIGATION', 'No PreflightResult supplied.');
    if (obligations.length === 0) {
      return notAvailable('DEPENDENCY_OBLIGATION', 'Closure supplied zero obligations.');
    }
    const hasUnknown = obligations.some((item) => item.resolution === 'UNKNOWN');
    const hasUnsupported = obligations.some((item) => item.resolution === 'UNSUPPORTED');
    if (hasUnknown) {
      return stage(
        'DEPENDENCY_OBLIGATION',
        'BLOCKED',
        `${obligations.length} obligations; at least one is UNKNOWN.`,
        `${obligations.length} obligations`,
        asJson(obligations),
      );
    }
    if (hasUnsupported) {
      return stage(
        'DEPENDENCY_OBLIGATION',
        'UNSUPPORTED',
        `${obligations.length} obligations; at least one is UNSUPPORTED.`,
        `${obligations.length} obligations`,
        asJson(obligations),
      );
    }
    return stage(
      'DEPENDENCY_OBLIGATION',
      'READY',
      `${obligations.length} obligations, every resolution RESOLVED.`,
      `${obligations.length} obligations`,
      asJson(obligations),
    );
  };

  // -- 3. DEPENDENCY_CLOSURE ---------------------------------------------
  const closure = preview?.preflight?.closure ?? null;
  const closureStage = closure
    ? closure.status === 'CLOSED'
      ? stage(
          'DEPENDENCY_CLOSURE',
          'READY',
          `Closure status is CLOSED with ${closure.blockers.length} blockers.`,
          closure.status,
          asJson(closure),
        )
      : stage(
          'DEPENDENCY_CLOSURE',
          'BLOCKED',
          `Closure status is ${closure.status} with ${closure.blockers.length} blockers.`,
          closure.status,
          asJson(closure),
        )
    : notAvailable('DEPENDENCY_CLOSURE', 'No closure supplied.');

  // -- 4. PREFLIGHT_RESULT ------------------------------------------------
  const preflight = preview?.preflight ?? null;
  const preflightStage = preflight
    ? preflight.outcome === 'CLOSED'
      ? stage(
          'PREFLIGHT_RESULT',
          'READY',
          'Preflight outcome is CLOSED with zero rejections.',
          preflight.outcome,
          asJson(preflight),
        )
      : stage(
          'PREFLIGHT_RESULT',
          'REJECTED',
          `Preflight outcome is REJECTED with ${preflight.rejections.length} rejections.`,
          preflight.outcome,
          asJson(preflight),
        )
    : notAvailable('PREFLIGHT_RESULT', 'No PreflightResult supplied.');

  // -- 5. GATE_CERTIFICATE -------------------------------------------------
  const certView = preview?.certificate ?? null;
  const certificateStage = (): StrictStageView => {
    if (!certView) return notAvailable('GATE_CERTIFICATE', 'No certificate view supplied.');
    switch (certView.status) {
      case 'ISSUED':
        return stage(
          'GATE_CERTIFICATE',
          'READY',
          'Local strict certificate issued.',
          certView.certificate?.identity ?? null,
          certView.certificate ? asJson(certView.certificate) : null,
        );
      case 'REFUSED':
        return stage(
          'GATE_CERTIFICATE',
          'REJECTED',
          certView.refusalReason ?? 'Certificate refused.',
          null,
          null,
        );
      case 'STALE':
        return stage(
          'GATE_CERTIFICATE',
          'BLOCKED',
          certView.refusalReason ?? 'Certificate is stale against the live revision.',
          certView.certificate?.identity ?? null,
          certView.certificate ? asJson(certView.certificate) : null,
        );
      default:
        return notAvailable('GATE_CERTIFICATE', 'Certification was not reached.');
    }
  };

  // -- 6. TRANSACTION_PLAN --------------------------------------------------
  const plan = execution?.plan ?? preview?.plan ?? null;
  const planStage = plan
    ? stage(
        'TRANSACTION_PLAN',
        'READY',
        `Plan supplied with ${plan.operations.length} operations.`,
        plan.certificateIdentity,
        asJson(plan),
      )
    : notAvailable('TRANSACTION_PLAN', 'No TransactionPlan supplied.');

  // -- 7. STAGED_DELTA ------------------------------------------------------
  const delta = execution?.delta ?? preview?.delta ?? null;
  const deltaStage = delta
    ? stage(
        'STAGED_DELTA',
        'READY',
        `Staged delta supplied with ${delta.writes.length} staged writes (pre-commit).`,
        delta.certificateIdentity,
        asJson(delta),
      )
    : notAvailable('STAGED_DELTA', 'No StagedDelta supplied.');

  // -- 8. TRANSACTION_RNG ---------------------------------------------------
  const rng = execution?.transactionRng ?? preview?.transactionRng ?? null;
  const rngStage = rng
    ? stage(
        'TRANSACTION_RNG',
        'READY',
        `Private RNG ledger supplied with ${rng.ledger.length} draws (pre-commit).`,
        rng.certificateIdentity,
        asJson(rng),
      )
    : notAvailable('TRANSACTION_RNG', 'No TransactionRng document supplied.');

  // -- 9. STAGED_TRACE ------------------------------------------------------
  const trace = execution?.trace ?? preview?.trace ?? null;
  const traceStage = (): StrictStageView => {
    if (!trace) return notAvailable('STAGED_TRACE', 'No StagedTrace supplied.');
    if (trace.discarded) {
      return stage('STAGED_TRACE', 'REJECTED', 'Staged output was discarded.', null, asJson(trace));
    }
    return stage(
      'STAGED_TRACE',
      'READY',
      `Staged trace supplied with ${trace.records.length} records (pre-commit).`,
      trace.certificateIdentity,
      asJson(trace),
    );
  };

  // -- 10. ATOMIC_COMMIT ----------------------------------------------------
  const commit = execution?.commit ?? null;
  const commitStage = commit
    ? stage(
        'ATOMIC_COMMIT',
        'COMMITTED',
        'Atomic commit published.',
        commit.certificateIdentity,
        asJson(commit),
      )
    : notAvailable('ATOMIC_COMMIT', 'No atomic commit observation supplied.');

  // -- 11. STRICT_STEP_RESULT ----------------------------------------------
  const strictStep = execution?.strictStep ?? preview?.strictStep ?? null;
  const strictStage = (): StrictStageView => {
    if (!strictStep) return notAvailable('STRICT_STEP_RESULT', 'No StrictStepResult supplied.');
    switch (strictStep.outcome) {
      case 'COMMITTED':
        return stage(
          'STRICT_STEP_RESULT',
          'COMMITTED',
          'Strict step result outcome is COMMITTED.',
          strictStep.transactionIdentity,
          asJson(strictStep),
        );
      case 'REJECTED':
        return stage(
          'STRICT_STEP_RESULT',
          'REJECTED',
          `Strict step rejected with ${strictStep.rejections.length} rejections.`,
          strictStep.rejections[0]?.reasonCode ?? null,
          asJson(strictStep),
        );
      default:
        return stage(
          'STRICT_STEP_RESULT',
          'UNSUPPORTED',
          `Strict step outcome is UNSUPPORTED with ${strictStep.rejections.length} rejections.`,
          strictStep.rejections[0]?.reasonCode ?? null,
          asJson(strictStep),
        );
    }
  };

  return [
    request,
    obligationStage(),
    closureStage,
    preflightStage,
    certificateStage(),
    planStage,
    deltaStage,
    rngStage,
    traceStage(),
    commitStage,
    strictStage(),
  ];
}

/** Stages that hold PRE-COMMIT material rather than published output. */
export const PRE_COMMIT_STAGES: readonly StrictPipelineStageId[] = [
  'STAGED_DELTA',
  'TRANSACTION_RNG',
  'STAGED_TRACE',
];

export function isPreCommitStage(id: StrictPipelineStageId): boolean {
  return PRE_COMMIT_STAGES.includes(id);
}
