import type { ContractSlot, QuarantineEntry } from '../models';
import { Badge, EvidenceModeBadge, MockBadge, type BadgeTone } from '../components/Badge';
import { EmptyState } from '../components/EmptyState';
import { KeyValueList } from '../components/KeyValueList';
import { JsonViewer } from '../components/JsonViewer';
import { Collapsible } from '../components/Collapsible';
import { useWorkspace } from '../app/WorkspaceProvider';
import { evidenceRecord } from '../models/drawer';
import { asJson } from '../utils/format';

/**
 * Generic quarantine badge.
 *
 * The badge is derived entirely from the supplied contract slot: status +
 * evidence mode. Nothing here is a hardcoded modifier rule, so an operation
 * with a different status renders differently without any code change.
 */
function QuarantineBadge({ slot }: { readonly slot: ContractSlot }) {
  if (slot.status === 'BLOCKED_NATIVE' && slot.evidenceMode === 'NATIVE_EVIDENCED') {
    return <Badge tone="danger" dot>BLOCKED / QUARANTINED</Badge>;
  }
  if (slot.status === 'REFERENCE_ONLY' && slot.evidenceMode === 'REFERENCE_MODEL') {
    return <Badge tone="reference" dot>REFERENCE ONLY</Badge>;
  }
  if (slot.status === 'SEPARATELY_CERTIFIED') {
    return <Badge tone="ok" dot>SEPARATELY CERTIFIED</Badge>;
  }
  const tone: BadgeTone =
    slot.status === 'BLOCKED_NATIVE' ? 'danger' : slot.status === 'REFERENCE_ONLY' ? 'reference' : 'muted';
  return <Badge tone={tone} dot>{slot.status}</Badge>;
}

function QuarantineRow({ entry, index }: { readonly entry: QuarantineEntry; readonly index: number }) {
  const { actions } = useWorkspace();
  const { slot, reference, rejection } = entry;

  return (
    <div className="tree__node">
      <div className="tree__node-header" style={{ cursor: 'default' }}>
        <QuarantineBadge slot={slot} />
        <span className="tree__node-title">
          {slot.operation} · {slot.contractId}
        </span>
        <EvidenceModeBadge mode={slot.evidenceMode} />
      </div>
      <div className="tree__node-body">
        <KeyValueList
          entries={[
            { key: 'schema', value: slot.schema },
            { key: 'operation', value: slot.operation },
            { key: 'contract id', value: slot.contractId },
            { key: 'status', value: slot.status },
            {
              key: 'legacy label',
              value: slot.legacyFixtureLabel ?? 'not supplied',
              wrap: true,
            },
          ]}
        />

        {slot.blockers.length > 0 ? (
          <div className="stack stack--tight">
            <span className="section-label">blockers ({slot.blockers.length})</span>
            {slot.blockers.map((blocker) => (
              <span key={blocker} className="tiny muted">
                · {blocker}
              </span>
            ))}
          </div>
        ) : null}

        {reference ? (
          <div className="stack stack--tight">
            <span className="section-label">reference descriptor</span>
            <KeyValueList
              entries={[
                { key: 'descriptor id', value: reference.descriptorId },
                { key: 'reference id', value: reference.profile.referenceId },
                { key: 'assumptions', value: reference.profile.assumptions.join('; '), wrap: true },
                { key: 'exclusions', value: reference.profile.exclusions.join('; '), wrap: true },
              ]}
            />
            <JsonViewer value={reference.payload} />
          </div>
        ) : null}

        {rejection ? (
          <div className="stack stack--tight">
            <span className="section-label">rejection</span>
            <div className="row">
              <button
                type="button"
                className="badge badge--button badge--danger"
                onClick={() =>
                  actions.openDrawer(
                    evidenceRecord(
                      'CLOSURE_BLOCKER',
                      `Quarantine rejection · ${rejection.reasonCode}`,
                      asJson(rejection),
                      {
                        evidenceMode: slot.evidenceMode,
                        ownerLabel: rejection.obligationOwner,
                        revisionLabel: 'no revision — quarantined operation',
                        sourceRefs: rejection.contractRefs.map((ref) => ref.contractId),
                      },
                    ),
                  )
                }
              >
                {rejection.reasonCode}
              </button>
            </div>
            <span className="tiny muted">{rejection.evidenceRequest}</span>
          </div>
        ) : null}

        <button
          type="button"
          className="btn btn--ghost"
          onClick={() =>
            actions.openDrawer(
              evidenceRecord('CONTRACT', `Contract slot · ${slot.operation}`, asJson(slot), {
                evidenceMode: slot.evidenceMode,
                contractId: slot.contractId,
                revisionLabel: `status ${slot.status}`,
                ownerLabel: slot.operation,
                sourceRefs: entry.contractRef?.sourceRefs ?? [],
              }),
            )
          }
        >
          Inspect raw slot #{index + 1}
        </button>
      </div>
    </div>
  );
}

export function QuarantinePanel({ entries }: { readonly entries: readonly QuarantineEntry[] }) {
  if (entries.length === 0) {
    return (
      <EmptyState title="No quarantine slots supplied">
        The adapter supplied no FC-02 contract slots. Nothing is quarantined by the frontend —
        quarantine is registry data, not a client-side rule.
      </EmptyState>
    );
  }

  return (
    <div className="stack">
      <div className="row">
        <MockBadge />
        <span className="tiny dim">
          {entries.length} contract slots · badges derived from slot status + evidence mode
        </span>
      </div>
      {entries.map((entry, index) => (
        <QuarantineRow key={`${entry.slot.operation}-${index}`} entry={entry} index={index} />
      ))}
      <Collapsible label="How these badges are derived">
        <div className="stack stack--tight tiny muted">
          <span>· BLOCKED_NATIVE + NATIVE_EVIDENCED → BLOCKED / QUARANTINED</span>
          <span>· REFERENCE_ONLY + REFERENCE_MODEL → REFERENCE ONLY (never promoted)</span>
          <span>· SEPARATELY_CERTIFIED → separately certified slot</span>
          <span>
            The mapping reads the slot document only, so a different operation with a different
            status renders differently without a code change.
          </span>
        </div>
      </Collapsible>
    </div>
  );
}
