import type { StrictStageState, StrictStageView } from '../models';
import { Badge, MockBadge, type BadgeTone } from '../components/Badge';
import { EmptyState } from '../components/EmptyState';
import { useWorkspace } from '../app/WorkspaceProvider';
import { buildStrictStages, isPreCommitStage } from '../utils/strictStages';
import { shortDigest } from '../utils/format';
import { evidenceRecord } from '../models/drawer';

const STATE_TONES: Record<StrictStageState, BadgeTone> = {
  NOT_AVAILABLE: 'muted',
  READY: 'ok',
  BLOCKED: 'danger',
  REJECTED: 'danger',
  UNSUPPORTED: 'unsupported',
  COMMITTED: 'accent',
};

function StageRow({ view, index }: { readonly view: StrictStageView; readonly index: number }) {
  const { actions } = useWorkspace();
  const preCommit = isPreCommitStage(view.id);

  return (
    <div className={`pipeline__stage pipeline__stage--${view.state.toLowerCase()}`}>
      <div className="pipeline__index">{String(index + 1).padStart(2, '0')}</div>
      <div className="pipeline__main">
        <div className="pipeline__head">
          <span className="pipeline__label">{view.label}</span>
          <Badge tone={STATE_TONES[view.state]}>{view.state}</Badge>
          {preCommit ? <Badge tone="reference">pre-commit</Badge> : null}
          {view.id === 'ATOMIC_COMMIT' || view.id === 'STRICT_STEP_RESULT' ? (
            <Badge tone="muted">published</Badge>
          ) : null}
        </div>
        <div className="pipeline__basis">{view.basis}</div>
        {view.identity ? (
          <div className="pipeline__identity mono">{shortDigest(String(view.identity), 18, 6)}</div>
        ) : null}
      </div>
      <button
        type="button"
        className="btn btn--ghost"
        disabled={view.document === null}
        onClick={() => {
          if (view.document === null) return;
          actions.openDrawer(
            evidenceRecord(
              'STAGED_RECORD',
              `${view.label} · ${view.state}`,
              view.document as never,
              {
                revisionLabel: view.identity,
                ownerLabel: preCommit ? 'pre-commit material' : 'published output',
              },
            ),
          );
        }}
      >
        Inspect
      </button>
    </div>
  );
}

export function StrictPipeline() {
  const { state } = useWorkspace();
  const selected = state.actions.find((action) => action.id === state.selectedActionId) ?? null;
  const stages = buildStrictStages({
    requestLabel: selected?.label ?? null,
    preview: state.preview,
    execution: state.execution,
  });

  if (!selected) {
    return (
      <EmptyState title="No request selected">
        Select an action to trace it through the strict execution pipeline.
      </EmptyState>
    );
  }

  const available = stages.filter((view) => view.state !== 'NOT_AVAILABLE').length;

  return (
    <div className="stack">
      <div className="row row--between">
        <span className="row">
          <MockBadge />
          <span className="tiny dim">
            {available}/{stages.length} stages supplied · states read from each stage's own document
          </span>
        </span>
      </div>

      <div className="pipeline">
        {stages.map((view, index) => (
          <div key={view.id} className="pipeline__row">
            <StageRow view={view} index={index} />
          </div>
        ))}
      </div>

      <p className="tiny dim" style={{ margin: 0 }}>
        NOT_AVAILABLE means the backend did not supply that document. The frontend never infers a
        stage transition from the stage before it.
      </p>
    </div>
  );
}
