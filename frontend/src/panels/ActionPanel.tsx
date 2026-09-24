import type { AvailableAction } from '../models';
import { Badge, EvidenceModeBadge, MockBadge, type BadgeTone } from '../components/Badge';
import { EmptyState } from '../components/EmptyState';
import { useWorkspace } from '../app/WorkspaceProvider';

const SUPPORT_TONES: Record<string, BadgeTone> = {
  AVAILABLE: 'ok',
  BLOCKED: 'danger',
  UNKNOWN: 'unknown',
  UNSUPPORTED: 'unsupported',
  REFERENCE_ONLY: 'reference',
  COMMITTED: 'accent',
};

const PREFLIGHT_TONES: Record<string, BadgeTone> = {
  NOT_RUN: 'muted',
  CLOSED: 'ok',
  REJECTED: 'danger',
  UNKNOWN: 'unknown',
  UNSUPPORTED: 'unsupported',
  STALE: 'danger',
};

function WhyLine({ action }: { readonly action: AvailableAction }) {
  switch (action.support) {
    case 'AVAILABLE':
      return (
        <div className="actioncard__why">
          <Badge tone="ok">why</Badge>
          <span>
            Adapter reports AVAILABLE for this action. Legality comes from the backend, never from
            the presence of a descriptor.
          </span>
        </div>
      );
    case 'BLOCKED':
      return (
        <div className="actioncard__why">
          <Badge tone="danger">why not</Badge>
          <span>
            {action.preflightState === 'STALE'
              ? 'Blocked: the certificate is stale against the live revision.'
              : 'Blocked by the preflight result — open the inspector for the blocker detail.'}
          </span>
        </div>
      );
    case 'UNKNOWN':
      return (
        <div className="actioncard__why">
          <Badge tone="unknown">why unknown</Badge>
          <span>
            Support state is UNKNOWN. No legality is inferred client-side; see the unresolved handle
            in the inspector.
          </span>
        </div>
      );
    case 'UNSUPPORTED':
      return (
        <div className="actioncard__why">
          <Badge tone="unsupported">why not</Badge>
          <span>UNSUPPORTED operation: inspectable descriptor, execution denied by evidence.</span>
        </div>
      );
    case 'REFERENCE_ONLY':
      return (
        <div className="actioncard__why">
          <Badge tone="reference">why not</Badge>
          <span>
            REFERENCE_ONLY: a reference estimate is available but it is never promoted to execution.
          </span>
        </div>
      );
    case 'COMMITTED':
      return (
        <div className="actioncard__why">
          <Badge tone="accent">result</Badge>
          <span>Committed — see the transaction tab for before/after revision.</span>
        </div>
      );
    default:
      return null;
  }
}

export function ActionPanel({ actions: available }: { readonly actions: readonly AvailableAction[] }) {
  const { state, actions } = useWorkspace();

  if (available.length === 0) {
    return (
      <div className="panel__body">
        <EmptyState title="No legal actions supplied">
          The adapter returned no action with declared legal-action support. This is an honest
          unsupported state — the frontend does not derive AVAILABLE from descriptor presence.
        </EmptyState>
      </div>
    );
  }

  const selected = available.find((action) => action.id === state.selectedActionId) ?? null;

  return (
    <div className="panel__body">
      <div className="stack">
        <div className="row row--between">
          <span className="row">
            <MockBadge />
            <span className="tiny dim">{available.length} action descriptors</span>
          </span>
          <span className="row">
            <button
              type="button"
              className="btn"
              onClick={actions.previewSelected}
              disabled={!selected || state.loading}
            >
              Run preflight
            </button>
            <button
              type="button"
              className="btn btn--primary"
              onClick={actions.executeSelected}
              disabled={!selected || state.loading}
            >
              Execute
            </button>
          </span>
        </div>

        <div className="actions">
          {available.map((action) => {
            const isSelected = action.id === state.selectedActionId;
            const disabled =
              action.support === 'UNSUPPORTED' ||
              action.support === 'UNKNOWN' ||
              action.support === 'REFERENCE_ONLY';
            return (
              <button
                key={action.id}
                type="button"
                className={`actioncard${isSelected ? ' actioncard--selected' : ''}`}
                onClick={() => actions.selectAction(action.id)}
                disabled={disabled}
                title={disabled ? 'Execution is not supported for this action' : 'Select action'}
              >
                <span className="actioncard__head">
                  <span className="actioncard__label">{action.label}</span>
                  <Badge tone={SUPPORT_TONES[action.support] ?? 'muted'}>{action.support}</Badge>
                  <EvidenceModeBadge mode={action.evidenceMode} />
                  <Badge tone={PREFLIGHT_TONES[action.preflightState] ?? 'muted'}>
                    preflight {action.preflightState}
                  </Badge>
                  {action.descriptorOnly ? <Badge tone="muted">descriptor only</Badge> : null}
                </span>

                <span className="actioncard__meta">
                  <span>actor {action.actorName}</span>
                  <span>
                    target rule: {action.targetRule.supplied ? action.targetRule.summary : 'not supplied'}
                  </span>
                </span>

                <WhyLine action={action} />

                {action.notes.length > 0 ? (
                  <span className="actioncard__notes">
                    {action.notes.map((note) => (
                      <span key={note}>· {note}</span>
                    ))}
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
