import type {
  ActionPreview,
  CertificateView,
  ClosureBlocker,
  ContractRef,
  DependencyObligation,
  EvidenceMode,
  GateCertificate,
  ObligationAccess,
  PreflightResult,
  StructuredRejection,
  UnknownHandle,
} from '../models';
import { Badge, EvidenceModeBadge, MockBadge, type BadgeTone } from '../components/Badge';
import { EmptyState } from '../components/EmptyState';
import { JsonViewer } from '../components/JsonViewer';
import { KeyValueList } from '../components/KeyValueList';
import { Collapsible } from '../components/Collapsible';
import { useWorkspace } from '../app/WorkspaceProvider';
import { evidenceRecord } from '../models/drawer';
import { contractIdentity } from '../models/evidence';
import { CERTIFICATE_PANEL_LABEL } from '../models/certificate';
import { formatExtent, formatOccurrencePath } from '../models/preflight';
import { formatRevision } from '../models/state';
import { asJson, shortDigest } from '../utils/format';

const CLOSURE_TONES: Record<string, BadgeTone> = {
  CLOSED: 'ok',
  BLOCKED_MISSING: 'unknown',
  BLOCKED_UNKNOWN: 'unknown',
  BLOCKED_UNSUPPORTED: 'unsupported',
  BLOCKED_CYCLE: 'danger',
  BLOCKED_UNBOUNDED: 'danger',
};

const RESOLUTION_TONES: Record<string, BadgeTone> = {
  RESOLVED: 'ok',
  UNKNOWN: 'unknown',
  UNSUPPORTED: 'unsupported',
};

function ContractLine({
  contract,
  onInspect,
}: {
  readonly contract: ContractRef;
  readonly onInspect: () => void;
}) {
  return (
    <div className="row">
      <button type="button" className="badge badge--button badge--info" onClick={onInspect}>
        {contractIdentity(contract)}
      </button>
      <EvidenceModeBadge mode={contract.evidenceMode} />
      <span className="tiny dim mono">{shortDigest(contract.contentSha256, 8, 4)}</span>
    </div>
  );
}

function AccessList({
  title,
  accesses,
}: {
  readonly title: string;
  readonly accesses: readonly ObligationAccess[];
}) {
  if (accesses.length === 0) return null;
  return (
    <Collapsible label={`${title} (${accesses.length})`}>
      <div className="stack stack--tight">
        {accesses.map((access, index) => (
          <div key={`${access.target}-${index}`} className="tree__node" style={{ background: 'var(--bg-2)' }}>
            <div style={{ padding: '5px 7px' }}>
              <div className="mono tiny" style={{ color: 'var(--text-0)' }}>
                {access.target}
              </div>
              <div className="tiny dim">{formatExtent(access.extent)}</div>
            </div>
          </div>
        ))}
      </div>
    </Collapsible>
  );
}

function HandleNode({
  handle,
  onInspect,
}: {
  readonly handle: UnknownHandle;
  readonly onInspect: () => void;
}) {
  return (
    <div className="tree__node">
      <button type="button" className="tree__node-header" onClick={onInspect}>
        <Badge tone="unknown">unknown handle</Badge>
        <span className="tree__node-title">{handle.blockerId}</span>
        <span className="tiny dim">{handle.ownerFamily}</span>
      </button>
    </div>
  );
}

function ObligationNode({
  obligation,
  onInspectContract,
  onInspectHandle,
}: {
  readonly obligation: DependencyObligation;
  readonly onInspectContract: (contract: ContractRef) => void;
  readonly onInspectHandle: (handle: UnknownHandle) => void;
}) {
  return (
    <Collapsible
      label={`${obligation.owner} · ${obligation.resolution}`}
      accessory={
        <span className="row">
          <Badge tone={RESOLUTION_TONES[obligation.resolution] ?? 'muted'}>
            {obligation.resolution}
          </Badge>
          <EvidenceModeBadge mode={obligation.evidenceMode} />
        </span>
      }
    >
      <div className="stack">
        <ContractLine
          contract={obligation.contractRef}
          onInspect={() => onInspectContract(obligation.contractRef)}
        />

        {obligation.unknownHandles.length > 0 ? (
          <div className="stack stack--tight">
            <span className="section-label">unknown handles ({obligation.unknownHandles.length})</span>
            {obligation.unknownHandles.map((handle) => (
              <HandleNode key={handle.blockerId} handle={handle} onInspect={() => onInspectHandle(handle)} />
            ))}
          </div>
        ) : null}

        <AccessList title="reads" accesses={obligation.reads} />
        <AccessList title="writes" accesses={obligation.writes} />

        {obligation.children.length > 0 ? (
          <div className="stack stack--tight">
            <span className="section-label">children ({obligation.children.length})</span>
            {obligation.children.map((child, index) => (
              <div key={`${child.owner}-${index}`} className="row">
                <span className="tiny dim">{child.owner}</span>
                <button
                  type="button"
                  className="badge badge--button badge--info"
                  onClick={() => onInspectContract(child.contractRef)}
                >
                  {contractIdentity(child.contractRef)}
                </button>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </Collapsible>
  );
}

function BlockerNode({
  blocker,
  index,
  onInspectContract,
  onInspectHandle,
}: {
  readonly blocker: ClosureBlocker;
  readonly index: number;
  readonly onInspectContract: (contract: ContractRef) => void;
  readonly onInspectHandle: (handle: UnknownHandle) => void;
}) {
  return (
    <div className="tree__node">
      <div className="tree__node-header" style={{ cursor: 'default' }}>
        <Badge tone={CLOSURE_TONES[blocker.status] ?? 'danger'}>{blocker.status}</Badge>
        <span className="tree__node-title">#{index + 1} · {blocker.owner}</span>
      </div>
      <div className="tree__node-body">
        <KeyValueList
          entries={[
            { key: 'reason code', value: blocker.status },
            { key: 'owner', value: blocker.owner },
            { key: 'occurrence path', value: formatOccurrencePath(blocker.occurrencePath) },
            { key: 'evidence request', value: blocker.evidenceRequest, wrap: true },
          ]}
        />
        <div className="stack stack--tight">
          <span className="section-label">contract ref</span>
          <ContractLine
            contract={blocker.contractRef}
            onInspect={() => onInspectContract(blocker.contractRef)}
          />
        </div>
        {blocker.unknownHandles.length > 0 ? (
          <div className="stack stack--tight">
            <span className="section-label">unknown handles</span>
            {blocker.unknownHandles.map((handle) => (
              <HandleNode key={handle.blockerId} handle={handle} onInspect={() => onInspectHandle(handle)} />
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function RejectionNode({
  rejection,
  onInspectContract,
  onInspectHandle,
}: {
  readonly rejection: StructuredRejection;
  readonly onInspectContract: (contract: ContractRef) => void;
  readonly onInspectHandle: (handle: UnknownHandle) => void;
}) {
  return (
    <div className="tree__node">
      <div className="tree__node-header" style={{ cursor: 'default' }}>
        <Badge tone="danger">{rejection.reasonCode}</Badge>
        <span className="tree__node-title">{rejection.obligationOwner}</span>
      </div>
      <div className="tree__node-body">
        <KeyValueList
          entries={[
            { key: 'reason code', value: rejection.reasonCode },
            { key: 'owner', value: rejection.obligationOwner },
            { key: 'evidence request', value: rejection.evidenceRequest, wrap: true },
          ]}
        />
        {rejection.contractRefs.length > 0 ? (
          <div className="stack stack--tight">
            <span className="section-label">contract refs</span>
            {rejection.contractRefs.map((contract) => (
              <ContractLine key={contractIdentity(contract)} contract={contract} onInspect={() => onInspectContract(contract)} />
            ))}
          </div>
        ) : null}
        {rejection.unknownHandles.length > 0 ? (
          <div className="stack stack--tight">
            <span className="section-label">unknown handles</span>
            {rejection.unknownHandles.map((handle) => (
              <HandleNode key={handle.blockerId} handle={handle} onInspect={() => onInspectHandle(handle)} />
            ))}
          </div>
        ) : null}
        <div className="stack stack--tight">
          <span className="section-label">diagnostics (excluded from identity)</span>
          <JsonViewer value={rejection.diagnostics as never} defaultOpen />
        </div>
      </div>
    </div>
  );
}

function CertificateSection({
  view,
  liveRevisionLabel,
  onInspect,
}: {
  readonly view: CertificateView;
  readonly liveRevisionLabel: string | null;
  readonly onInspect: () => void;
}) {
  const cert: GateCertificate | null = view.certificate;

  if (view.status !== 'ISSUED' || !cert) {
    return (
      <EmptyState tone={view.status === 'REFUSED' ? 'reference' : 'danger'} title={`certificate ${view.status}`}>
        {view.refusalReason ?? 'No certificate was supplied.'}
      </EmptyState>
    );
  }

  const stale = liveRevisionLabel !== null && formatRevision(cert.stateRevision) !== liveRevisionLabel;

  return (
    <div className="stack">
      {stale ? (
        <EmptyState tone="danger" title="certificate STALE">
          Sealed against {formatRevision(cert.stateRevision)} but the live revision is{' '}
          {liveRevisionLabel}. A stale certificate is never silently reused.
        </EmptyState>
      ) : null}

      <KeyValueList
        entries={[
          { key: 'status', value: view.status },
          { key: 'evidence mode', value: cert.evidenceMode },
          { key: 'identity', value: shortDigest(cert.identity, 12, 6) },
          { key: 'plan identity', value: shortDigest(cert.planIdentity, 12, 6) },
          { key: 'closure identity', value: shortDigest(cert.closureIdentity, 12, 6) },
          { key: 'input identity', value: shortDigest(cert.inputIdentity, 12, 6) },
          { key: 'input revision', value: cert.inputRevision },
          { key: 'state revision', value: formatRevision(cert.stateRevision) },
          { key: 'contract revision', value: cert.contractRevision },
        ]}
      />

      <div className="row">
        <button type="button" className="btn btn--ghost" onClick={onInspect}>
          Inspect certificate evidence
        </button>
      </div>

      <AccessList title="allowed reads" accesses={cert.allowedReads} />
      <AccessList title="allowed writes" accesses={cert.allowedWrites} />
    </div>
  );
}

function PreflightBody({ preview }: { readonly preview: ActionPreview }) {
  const { state, actions } = useWorkspace();

  const openContract = (contract: ContractRef, context: string) => {
    actions.openDrawer(
      evidenceRecord(
        'CONTRACT',
        `Contract · ${contractIdentity(contract)}`,
        {
          contract_id: contract.contractId,
          namespace: contract.namespace,
          schema_version: contract.schemaVersion,
          evidence_mode: contract.evidenceMode,
          content_sha256: contract.contentSha256,
          source_refs: [...contract.sourceRefs],
        },
        {
          evidenceMode: contract.evidenceMode,
          contractId: contract.contractId,
          namespace: contract.namespace,
          contractRevision: contract.schemaVersion,
          sourceRefs: contract.sourceRefs,
          revisionLabel: `contract schema ${contract.schemaVersion}`,
          ownerLabel: context,
        },
      ),
    );
  };

  const openHandle = (handle: UnknownHandle) => {
    actions.openDrawer(
      evidenceRecord(
        'UNKNOWN_HANDLE',
        `UnknownHandle · ${handle.blockerId}`,
        {
          blocker_id: handle.blockerId,
          owner_family: handle.ownerFamily,
          payload: handle.payload,
          provenance: handle.provenance,
          required_evidence: [...handle.requiredEvidence],
        },
        {
          evidenceMode: 'UNSUPPORTED',
          ownerLabel: handle.ownerFamily,
          revisionLabel: 'unresolved — no revision binds a handle',
          sourceRefs: handle.requiredEvidence,
        },
      ),
    );
  };

  const result: PreflightResult | null = preview.preflight;
  const liveRevisionLabel = state.snapshot ? formatRevision(state.snapshot.revision) : null;

  if (!result) {
    return (
      <EmptyState title="No preflight result supplied">
        The adapter returned no preflight result for this action. Nothing is inferred client-side.
      </EmptyState>
    );
  }

  return (
    <div className="stack">
      <div className="row row--between">
        <span className="row">
          <Badge tone={result.outcome === 'CLOSED' ? 'ok' : 'danger'}>{result.outcome}</Badge>
          <Badge tone={CLOSURE_TONES[result.closure.status] ?? 'danger'}>
            closure {result.closure.status}
          </Badge>
          <EvidenceModeBadge mode={preview.evidenceMode} />
          <MockBadge />
        </span>
      </div>

      <KeyValueList
        entries={[
          { key: 'obligations', value: String(result.closure.obligations.length) },
          { key: 'blockers', value: String(result.closure.blockers.length) },
          { key: 'rejections', value: String(result.rejections.length) },
          { key: 'allowed reads', value: String(result.closure.allowedReads.length) },
          { key: 'allowed writes', value: String(result.closure.allowedWrites.length) },
        ]}
      />

      {result.closure.blockers.length > 0 ? (
        <div className="stack stack--tight">
          <span className="section-label">blockers</span>
          {result.closure.blockers.map((blocker, index) => (
            <BlockerNode
              key={`${blocker.owner}-${index}`}
              blocker={blocker}
              index={index}
              onInspectContract={(contract) => openContract(contract, blocker.owner)}
              onInspectHandle={openHandle}
            />
          ))}
        </div>
      ) : null}

      {result.rejections.length > 0 ? (
        <div className="stack stack--tight">
          <span className="section-label">structured rejections</span>
          {result.rejections.map((rejection, index) => (
            <RejectionNode
              key={`${rejection.reasonCode}-${index}`}
              rejection={rejection}
              onInspectContract={(contract) => openContract(contract, rejection.obligationOwner)}
              onInspectHandle={openHandle}
            />
          ))}
        </div>
      ) : null}

      <div className="stack stack--tight">
        <span className="section-label">
          dependency obligations ({result.closure.obligations.length})
        </span>
        {result.closure.obligations.map((obligation, index) => (
          <ObligationNode
            key={`${obligation.owner}-${index}`}
            obligation={obligation}
            onInspectContract={(contract) => openContract(contract, obligation.owner)}
            onInspectHandle={openHandle}
          />
        ))}
      </div>

      <div className="divider" />

      <div className="stack stack--tight">
        {/*
          Deliberate label. The backend certificate is LOCAL STRICT integrity
          infrastructure — never an official client or native game certificate.
        */}
        <span className="section-label">{CERTIFICATE_PANEL_LABEL}</span>
        <span className="tiny dim">
          Local strict integrity binding. Not an official client certificate and not a native game
          certificate.
        </span>
        <CertificateSection
          view={preview.certificate}
          liveRevisionLabel={liveRevisionLabel}
          onInspect={() => {
            const cert = preview.certificate.certificate;
            if (!cert) return;
            actions.openDrawer(
              evidenceRecord(
                'CERTIFICATE',
                `GateCertificate · ${shortDigest(cert.identity, 12, 6)}`,
                {
                  plan_identity: cert.planIdentity,
                  evidence_mode: cert.evidenceMode,
                  input_identity: cert.inputIdentity,
                  input_revision: cert.inputRevision,
                  state_revision: asJson(cert.stateRevision),
                  contract_ref: asJson(cert.contractRef),
                  contract_revision: cert.contractRevision,
                  closure_identity: cert.closureIdentity,
                  allowed_reads: asJson(cert.allowedReads),
                  allowed_writes: asJson(cert.allowedWrites),
                },
                {
                  evidenceMode: cert.evidenceMode as EvidenceMode,
                  contractId: cert.contractRef.contractId,
                  namespace: cert.contractRef.namespace,
                  contractRevision: cert.contractRevision,
                  sourceRefs: cert.contractRef.sourceRefs,
                  revisionLabel: `state ${formatRevision(cert.stateRevision)} · input ${cert.inputRevision}`,
                  ownerLabel: cert.contractRef.contractId,
                },
              ),
            );
          }}
        />
      </div>

      {preview.notes.length > 0 ? (
        <div className="stack stack--tight">
          <span className="section-label">notes</span>
          {preview.notes.map((note) => (
            <span key={note} className="tiny muted">
              {note}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function PreflightInspector({ preview }: { readonly preview: ActionPreview | null }) {
  const { state } = useWorkspace();

  if (!state.snapshot) {
    return (
      <div className="panel__body">
        <EmptyState title="No scenario loaded">Load a scenario to inspect preflight evidence.</EmptyState>
      </div>
    );
  }

  if (!preview) {
    return (
      <div className="panel__body">
        <EmptyState title="Preflight not run">
          Select an action and run preflight to see dependency obligations, closure status, blockers
          and the certificate.
        </EmptyState>
      </div>
    );
  }

  return (
    <div className="panel__body panel__body--scroll" style={{ flex: '1 1 auto', minHeight: 0 }}>
      <PreflightBody preview={preview} />
    </div>
  );
}
