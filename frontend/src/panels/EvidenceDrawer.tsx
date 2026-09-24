import { useEffect } from 'react';
import type { EvidenceRecord } from '../models';
import { Badge, EvidenceModeBadge, MockBadge } from '../components/Badge';
import { JsonViewer } from '../components/JsonViewer';
import { KeyValueList } from '../components/KeyValueList';
import { useWorkspace } from '../app/WorkspaceProvider';
import { shortDigest } from '../utils/format';

const KIND_TONES: Record<string, 'info' | 'unknown' | 'danger' | 'accent' | 'muted' | 'reference'> = {
  CONTRACT: 'info',
  UNKNOWN_HANDLE: 'unknown',
  CLOSURE_BLOCKER: 'danger',
  CERTIFICATE: 'accent',
  REJECTION: 'danger',
  STATE: 'muted',
  ACTION: 'muted',
  STAGED_RECORD: 'muted',
  RNG_DRAW: 'reference',
};

export function EvidenceDrawer({ record }: { readonly record: EvidenceRecord }) {
  const { actions, state } = useWorkspace();

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') actions.closeDrawer();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [actions]);

  return (
    <>
      <div className="drawer-backdrop" onClick={actions.closeDrawer} role="presentation" />
      <aside className="drawer" aria-label="Evidence drawer">
        <header className="drawer__header">
          <Badge tone={KIND_TONES[record.kind] ?? 'muted'}>{record.kind}</Badge>
          <span className="drawer__title">{record.title}</span>
          <button type="button" className="btn btn--ghost" onClick={actions.closeDrawer}>
            Close
          </button>
        </header>

        <div className="drawer__body">
          <div className="row">
            <MockBadge />
            {record.evidenceMode ? <EvidenceModeBadge mode={record.evidenceMode} /> : null}
          </div>

          <KeyValueList
            entries={[
              { key: 'record kind', value: record.kind },
              { key: 'evidence mode', value: record.evidenceMode ?? 'not supplied' },
              { key: 'contract id', value: record.contractId ?? 'not applicable' },
              { key: 'namespace', value: record.namespace ?? 'not applicable' },
              { key: 'contract revision', value: record.contractRevision ?? 'not applicable' },
              { key: 'owner', value: record.ownerLabel ?? 'not supplied' },
              { key: 'revision', value: record.revisionLabel ?? 'not supplied', wrap: true },
            ]}
          />

          <div className="stack stack--tight">
            <span className="section-label">source refs ({record.sourceRefs.length})</span>
            {record.sourceRefs.length === 0 ? (
              <span className="tiny dim">No source references supplied.</span>
            ) : (
              record.sourceRefs.map((ref) => (
                <div key={ref} className="row">
                  <span className="mono tiny">{shortDigest(ref, 40, 8)}</span>
                </div>
              ))
            )}
          </div>

          <div className="stack stack--tight">
            <span className="section-label">raw structured record</span>
            <div className="eventrow__raw">
              <JsonViewer value={record.raw} defaultOpen />
            </div>
          </div>

          <p className="tiny dim" style={{ margin: 0 }}>
            Drawer contents are rendered verbatim from the adapter record. Source:{' '}
            {state.session?.adapterLabel ?? 'unknown adapter'} ·{' '}
            {state.session?.dataProvenance ?? 'unknown provenance'}.
          </p>
        </div>
      </aside>
    </>
  );
}
