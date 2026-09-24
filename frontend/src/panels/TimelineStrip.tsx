import type { TimelineEntry, TimelineEntryKind } from '../models';
import { EmptyState } from '../components/EmptyState';
import { useWorkspace } from '../app/WorkspaceProvider';
import { evidenceRecord } from '../models/drawer';

/**
 * Timeline row kinds stay visually and structurally distinct. They are never
 * merged into one UI type even though they share a row component.
 */
const KIND_LABELS: Record<TimelineEntryKind, string> = {
  ORDINARY: 'ORDINARY',
  INSERTED: 'INSERTED',
  ACTION_TASK: 'ACTION TASK',
  DAMAGE_TASK: 'DAMAGE TASK',
  ULTIMATE_REQUEST: 'ULT REQUEST',
  IMMEDIATE: 'IMMEDIATE',
};

const KIND_COLORS: Record<TimelineEntryKind, string> = {
  ORDINARY: 'var(--c-native)',
  INSERTED: 'var(--c-extension)',
  ACTION_TASK: 'var(--c-info)',
  DAMAGE_TASK: 'var(--c-danger)',
  ULTIMATE_REQUEST: 'var(--c-reference)',
  IMMEDIATE: '#ff7ab8',
};

export function TimelineStrip({ timeline }: { readonly timeline: readonly TimelineEntry[] }) {
  const { actions } = useWorkspace();

  if (timeline.length === 0) {
    return (
      <div className="panel__body">
        <EmptyState title="No timeline supplied">
          The adapter supplied no scheduled entries. The frontend never computes turn order or
          action values, so nothing is drawn here.
        </EmptyState>
      </div>
    );
  }

  return (
    <div className="panel__body">
      <div className="timeline">
        <div className="timeline__strip">
          {timeline.map((entry) => {
            const current = entry.actorId !== null;
            return (
              <button
                key={entry.id}
                type="button"
                className={`timeline__row timeline__row--${entry.kind}${
                  current ? ' timeline__row--current' : ''
                }`}
                onClick={() => {
                  actions.openDrawer(
                    evidenceRecord('STATE', `Timeline · ${KIND_LABELS[entry.kind]} #${entry.order}`, {
                      id: entry.id,
                      order: entry.order,
                      kind: entry.kind,
                      label: entry.label,
                      actor_id: entry.actorId,
                      av_supplied: entry.avSupplied,
                      av: entry.av,
                      evidence_mode: entry.evidenceMode,
                      detail: entry.detail,
                    }, {
                      evidenceMode: entry.evidenceMode,
                      revisionLabel: `position ${entry.order} (supplied order)`,
                      ownerLabel: entry.actorId,
                    }),
                  );
                }}
                title={entry.detail ?? entry.label}
              >
                <span className="timeline__row-head">
                  <span className="timeline__order">#{entry.order}</span>
                  <span className="timeline__kind">{KIND_LABELS[entry.kind]}</span>
                </span>
                <span className="timeline__label">{entry.label}</span>
                <span className="timeline__meta">
                  {entry.avSupplied && entry.av !== null ? `av ${entry.av}` : 'av not supplied'}
                </span>
              </button>
            );
          })}
        </div>

        <div className="timeline__legend">
          {(Object.keys(KIND_LABELS) as TimelineEntryKind[]).map((kind) => (
            <span key={kind} className="timeline__legend-item">
              <span className="timeline__swatch" style={{ background: KIND_COLORS[kind] }} />
              {KIND_LABELS[kind]}
            </span>
          ))}
        </div>
        <p className="tiny dim" style={{ margin: 0 }}>
          Order rendered exactly as supplied. No scheduler ordering is calculated client-side.
        </p>
      </div>
    </div>
  );
}
