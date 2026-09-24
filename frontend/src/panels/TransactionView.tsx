import type {
  ActionPreview,
  ExecutionResult,
  RngDraw,
  StateDiff,
  StagedDelta,
  StagedTrace,
  TransactionPlan,
  TransactionRngDocument,
} from '../models';
import { Badge, EvidenceModeBadge, MockBadge } from '../components/Badge';
import { EmptyState, Notice } from '../components/EmptyState';
import { JsonViewer } from '../components/JsonViewer';
import { KeyValueList } from '../components/KeyValueList';
import { Collapsible } from '../components/Collapsible';
import { useWorkspace } from '../app/WorkspaceProvider';
import { evidenceRecord } from '../models/drawer';
import { formatRevision } from '../models/state';
import { formatExtent } from '../models/preflight';
import { liveStateUnchangedVerified } from '../models/transaction';
import { asJson, shortDigest } from '../utils/format';

/**
 * Stage tag separating PRE-COMMIT material from PUBLISHED output.
 *
 * A user must be able to tell at a glance that staged material is not live yet.
 */
function StageTag({ tone, text }: { readonly tone: 'pre-commit' | 'published'; readonly text: string }) {
  const className = tone === 'pre-commit' ? 'stage-tag stage-tag--pre' : 'stage-tag stage-tag--pub';
  const label = tone === 'pre-commit' ? 'PRE-COMMIT · NOT LIVE' : 'PUBLISHED';
  return (
    <div className={className}>
      <span className="stage-tag__badge">{label}</span>
      <span className="stage-tag__text">{text}</span>
    </div>
  );
}

function PlanSection({ plan }: { readonly plan: TransactionPlan }) {
  return (
    <Collapsible label={`TransactionPlan · ${plan.operations.length} operations`} defaultOpen>
      <div className="stack">
        <StageTag tone="pre-commit" text="pre-commit · plan bound to the source revision" />
        <KeyValueList
          entries={[
            { key: 'schema', value: plan.schema },
            { key: 'certificate id', value: shortDigest(plan.certificateIdentity, 12, 6) },
            { key: 'source revision', value: formatRevision(plan.sourceRevision) },
            { key: 'source hash', value: shortDigest(plan.sourceStateHash, 12, 6) },
          ]}
        />
        <div className="stack stack--tight">
          <span className="section-label">operations</span>
          {plan.operations.length === 0 ? (
            <span className="tiny dim">No operations — this is a no-op plan.</span>
          ) : (
            plan.operations.map((operation) => (
              <div key={operation.operationId} className="tree__node">
                <div className="tree__node-body" style={{ borderTop: 'none' }}>
                  <span className="mono tiny">{operation.operationId}</span>
                  <JsonViewer value={operation.payload} />
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </Collapsible>
  );
}

function DeltaSection({ delta }: { readonly delta: StagedDelta }) {
  return (
    <Collapsible label={`StagedDelta · ${delta.writes.length} staged writes`}>
      <div className="stack">
        <StageTag tone="pre-commit" text="private replacement material · not published to live state" />
        <KeyValueList
          entries={[
            { key: 'schema', value: delta.schema },
            { key: 'plan identity', value: shortDigest(delta.planIdentity, 12, 6) },
            { key: 'certificate id', value: shortDigest(delta.certificateIdentity, 12, 6) },
            { key: 'source revision', value: formatRevision(delta.sourceRevision) },
            { key: 'stores', value: delta.storeNames.join(', ') || 'none' },
          ]}
        />
        {delta.writes.map((write, index) => (
          <div key={`${write.target}-${index}`} className="tree__node">
            <div className="tree__node-body" style={{ borderTop: 'none' }}>
              <div className="row">
                <Badge tone="info">{write.kind}</Badge>
                <span className="mono tiny">{write.target}</span>
              </div>
              <JsonViewer value={write.payload} />
            </div>
          </div>
        ))}
        <div className="stack stack--tight">
          <span className="section-label">allowed writes</span>
          {delta.allowedWrites.map((access, index) => (
            <div key={`${access.target}-${index}`} className="tiny">
              <span className="mono">{access.target}</span>
              <span className="dim"> — {formatExtent(access.extent)}</span>
            </div>
          ))}
        </div>
      </div>
    </Collapsible>
  );
}

/**
 * Private RNG draw ledger, rendered from the supplied `TransactionRng` document.
 *
 * The frontend never generates a draw and never predicts a result: it lists the
 * method / arguments / result triples exactly as supplied.
 */
function RngSection({
  rng,
  onInspect,
}: {
  readonly rng: TransactionRngDocument;
  readonly onInspect: (draw: RngDraw, sequence: number) => void;
}) {
  return (
    <Collapsible label={`Private RNG ledger · ${rng.ledger.length} draws`}>
      <div className="stack">
        <StageTag
          tone="pre-commit"
          text={rng.consumed ? 'ledger consumed by a commit' : 'private until a commit consumes it'}
        />
        <KeyValueList
          entries={[
            { key: 'schema', value: rng.schema },
            { key: 'plan identity', value: shortDigest(rng.planIdentity, 12, 6) },
            { key: 'certificate id', value: shortDigest(rng.certificateIdentity, 12, 6) },
            { key: 'source revision', value: formatRevision(rng.sourceRevision) },
            { key: 'source hash', value: shortDigest(rng.sourceStateHash, 12, 6) },
            { key: 'consumed', value: rng.consumed ? 'yes' : 'no' },
          ]}
        />
        <span className="tiny dim">
          Sandbox RNG only. Client-native RNG behaviour is unknown and is never simulated here.
        </span>
        {rng.ledger.length === 0 ? (
          <span className="tiny dim">No draws in the ledger (no-op).</span>
        ) : (
          rng.ledger.map((draw, index) => (
            <div key={`${draw.method}-${index}`} className="tree__node">
              <button
                type="button"
                className="tree__node-header"
                onClick={() => onInspect(draw, index + 1)}
              >
                <Badge tone="info">draw {index + 1}</Badge>
                <span className="tree__node-title mono">{draw.method}</span>
              </button>
              <div className="tree__node-body">
                <KeyValueList
                  entries={[
                    { key: 'arguments', value: JSON.stringify(draw.arguments) },
                    { key: 'result', value: JSON.stringify(draw.result) },
                  ]}
                />
              </div>
            </div>
          ))
        )}
      </div>
    </Collapsible>
  );
}

function TraceSection({ trace }: { readonly trace: StagedTrace }) {
  const groups: readonly { readonly label: string; readonly channel: 'TRACE' | 'EVENT' | 'QUEUE' }[] = [
    { label: 'trace', channel: 'TRACE' },
    { label: 'events', channel: 'EVENT' },
    { label: 'queue writes', channel: 'QUEUE' },
  ];

  return (
    <Collapsible label={`StagedTrace · ${trace.records.length} records`}>
      <div className="stack">
        <StageTag tone="pre-commit" text="staged trace / events / queue writes · private until commit" />
        <KeyValueList
          entries={[
            { key: 'schema', value: trace.schema },
            { key: 'plan identity', value: shortDigest(trace.planIdentity, 12, 6) },
            { key: 'certificate id', value: String(trace.certificateIdentity) },
            { key: 'discarded', value: trace.discarded ? 'yes' : 'no' },
          ]}
        />
        {trace.discarded ? (
          <Notice tone="danger" title="staged output discarded">
            A discarded staged trace can never be committed.
          </Notice>
        ) : null}
        {groups.map((group) => {
          const records = trace.records.filter((record) => record.channel === group.channel);
          if (records.length === 0) return null;
          return (
            <div key={group.channel} className="stack stack--tight">
              <span className="section-label">
                {group.label} ({records.length})
              </span>
              {records.map((record, index) => (
                <div key={`${record.kind}-${index}`} className="tree__node">
                  <div className="tree__node-header" style={{ cursor: 'default' }}>
                    <Badge tone={group.channel === 'QUEUE' ? 'reference' : 'muted'}>{record.channel}</Badge>
                    <span className="tree__node-title">{record.kind}</span>
                  </div>
                  <div className="tree__node-body">
                    <JsonViewer value={record.payload} />
                  </div>
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </Collapsible>
  );
}

function DiffSection({ diff }: { readonly diff: StateDiff }) {
  return (
    <Collapsible label="State diff" defaultOpen>
      <table className="table">
        <thead>
          <tr>
            <th>field</th>
            <th>before</th>
            <th>after</th>
          </tr>
        </thead>
        <tbody>
          {diff.entries.map((entry) => {
            const changed = JSON.stringify(entry.before) !== JSON.stringify(entry.after);
            return (
              <tr key={entry.field} className={changed ? 'diff-row--changed' : ''}>
                <td className="mono">{entry.field}</td>
                <td className="mono diff-cell--before">
                  {entry.before === null ? '—' : shortDigest(JSON.stringify(entry.before), 18, 6)}
                </td>
                <td className="mono diff-cell--after">
                  {entry.after === null ? '—' : shortDigest(JSON.stringify(entry.after), 18, 6)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Collapsible>
  );
}

/**
 * Deltas for a rejected / unsupported step.
 *
 * Every row compares SUPPLIED serialized documents. Nothing is derived from
 * battle rules, and a missing document is shown as "not supplied" rather than
 * as a zero.
 */
function DeltasSection({ execution }: { readonly execution: ExecutionResult }) {
  const window = execution.revisionWindow;
  const rng = execution.transactionRng;
  const trace = execution.trace;
  const delta = execution.delta;

  const counts = {
    trace: trace ? trace.records.filter((record) => record.channel === 'TRACE').length : null,
    events: trace ? trace.records.filter((record) => record.channel === 'EVENT').length : null,
    queue: trace ? trace.records.filter((record) => record.channel === 'QUEUE').length : null,
  };

  return (
    <div className="stack stack--tight">
      <span className="section-label">deltas</span>
      <table className="table">
        <thead>
          <tr>
            <th>delta</th>
            <th>before</th>
            <th>after</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>revision</td>
            <td className="mono diff-cell--before">
              {window ? formatRevision(window.before) : 'not supplied'}
            </td>
            <td className="mono diff-cell--after">
              {window ? formatRevision(window.after) : 'not supplied'}
            </td>
          </tr>
          <tr>
            <td>state hash</td>
            <td className="mono diff-cell--before">
              {window?.beforeHash ? shortDigest(window.beforeHash, 12, 6) : 'not supplied'}
            </td>
            <td className="mono diff-cell--after">
              {window?.afterHash ? shortDigest(window.afterHash, 12, 6) : 'not supplied'}
            </td>
          </tr>
          <tr>
            <td>rng draw ledger</td>
            <td className="mono diff-cell--before">0</td>
            <td className="mono diff-cell--after">
              {rng ? String(rng.ledger.length) : 'not supplied'}
            </td>
          </tr>
          <tr>
            <td>allocator delta</td>
            <td className="mono diff-cell--before">—</td>
            <td className="mono diff-cell--after">
              {delta ? `${delta.writes.length} staged writes` : 'not supplied'}
            </td>
          </tr>
          <tr>
            <td>staged trace</td>
            <td className="mono diff-cell--before">0</td>
            <td className="mono diff-cell--after">
              {counts.trace === null ? 'not supplied' : String(counts.trace)}
            </td>
          </tr>
          <tr>
            <td>staged events</td>
            <td className="mono diff-cell--before">0</td>
            <td className="mono diff-cell--after">
              {counts.events === null ? 'not supplied' : String(counts.events)}
            </td>
          </tr>
          <tr>
            <td>queue writes</td>
            <td className="mono diff-cell--before">0</td>
            <td className="mono diff-cell--after">
              {counts.queue === null ? 'not supplied' : String(counts.queue)}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function ExecutionSection({ execution }: { readonly execution: ExecutionResult }) {
  const { actions } = useWorkspace();
  const commit = execution.commit;
  const verified = liveStateUnchangedVerified(execution);
  const rejected = execution.outcome === 'REJECTED' || execution.outcome === 'UNSUPPORTED';

  return (
    <div className="stack">
      <div className="row row--between">
        <span className="row">
          <Badge
            tone={
              execution.outcome === 'COMMITTED'
                ? 'ok'
                : rejected
                  ? 'danger'
                  : execution.outcome === 'REFERENCE_ONLY'
                    ? 'reference'
                    : 'muted'
            }
          >
            {execution.outcome}
          </Badge>
          {commit ? (
            <Badge tone="accent">
              {formatRevision(commit.beforeRevision)} → {formatRevision(commit.afterRevision)}
            </Badge>
          ) : null}
          {execution.revisionWindow ? (
            <Badge tone={execution.revisionWindow.before.counter === execution.revisionWindow.after.counter ? 'muted' : 'accent'}>
              {formatRevision(execution.revisionWindow.before)} →{' '}
              {formatRevision(execution.revisionWindow.after)}
            </Badge>
          ) : (
            <Badge tone="muted">revision window not supplied</Badge>
          )}
        </span>
      </div>

      {/*
        "LIVE STATE UNCHANGED" is shown ONLY when the supplied before/after
        identity documents actually match. The word REJECTED is not evidence.
      */}
      {rejected ? (
        verified ? (
          <Notice tone="ok" title="LIVE STATE UNCHANGED (verified)">
            The supplied before and after identity documents match, so live state was unchanged.
            Automatic retry is forbidden.
          </Notice>
        ) : (
          <Notice tone="warning" title="Live state change NOT verifiable from supplied documents">
            The step was rejected, but no matching before/after identity documents were supplied.
            The frontend does not infer "unchanged" from the outcome name.
          </Notice>
        )
      ) : null}

      <Notice tone={execution.outcome === 'COMMITTED' ? 'ok' : rejected ? 'danger' : 'warning'} title={execution.outcome}>
        {execution.message}
      </Notice>

      {rejected ? <DeltasSection execution={execution} /> : null}

      {execution.strictStep ? (
        <div className="stack stack--tight">
          <span className="section-label">strict step result</span>
          <KeyValueList
            entries={[
              { key: 'schema', value: execution.strictStep.schema },
              { key: 'outcome', value: execution.strictStep.outcome },
              {
                key: 'resulting revision',
                value: execution.strictStep.resultingRevision
                  ? formatRevision(execution.strictStep.resultingRevision)
                  : 'none — not committed',
              },
              {
                key: 'transaction identity',
                value: execution.strictStep.transactionIdentity ?? 'none — not committed',
              },
              { key: 'rejections', value: String(execution.strictStep.rejections.length) },
            ]}
          />
          {execution.strictStep.rejections.map((rejection, index) => (
            <div key={`${rejection.reasonCode}-${index}`} className="row">
              <button
                type="button"
                className="badge badge--button badge--danger"
                onClick={() =>
                  actions.openDrawer(
                    evidenceRecord(
                      'REJECTION',
                      `Strict step rejection · ${rejection.reasonCode}`,
                      asJson(rejection),
                      {
                        ownerLabel: rejection.obligationOwner,
                        revisionLabel: 'no resulting revision — step not committed',
                      },
                    ),
                  )
                }
              >
                {rejection.reasonCode}
              </button>
              <span className="tiny muted">{rejection.evidenceRequest}</span>
            </div>
          ))}
        </div>
      ) : null}

      {execution.rejection ? (
        <div className="stack stack--tight">
          <span className="section-label">rejection</span>
          <div className="row">
            <button
              type="button"
              className="badge badge--button badge--danger"
              onClick={() =>
                actions.openDrawer(
                  evidenceRecord(
                    'REJECTION',
                    `Rejection · ${execution.rejection?.reasonCode ?? ''}`,
                    {
                      reason_code: execution.rejection?.reasonCode ?? null,
                      obligation_owner: execution.rejection?.obligationOwner ?? null,
                      evidence_request: execution.rejection?.evidenceRequest ?? null,
                      contract_refs:
                        execution.rejection?.contractRefs.map((ref) => ({
                          contract_id: ref.contractId,
                          namespace: ref.namespace,
                          schema_version: ref.schemaVersion,
                          evidence_mode: ref.evidenceMode,
                        })) ?? [],
                      diagnostics: execution.rejection?.diagnostics ?? {},
                    } as never,
                    {
                      ownerLabel: execution.rejection?.obligationOwner ?? null,
                      revisionLabel: 'no revision advanced — commit refused',
                    },
                  ),
                )
              }
            >
              {execution.rejection.reasonCode}
            </button>
          </div>
          <KeyValueList
            entries={[
              { key: 'owner', value: execution.rejection.obligationOwner },
              { key: 'evidence request', value: execution.rejection.evidenceRequest, wrap: true },
            ]}
          />
          <JsonViewer value={execution.rejection.diagnostics as never} />
        </div>
      ) : null}

      {commit ? (
        <div className="stack stack--tight">
          <StageTag tone="published" text="atomic commit published output" />
          <span className="section-label">atomic commit result</span>
          <KeyValueList
            entries={[
              { key: 'before revision', value: formatRevision(commit.beforeRevision) },
              { key: 'after revision', value: formatRevision(commit.afterRevision) },
              { key: 'before hash', value: shortDigest(commit.beforeStateHash, 12, 6) },
              { key: 'after hash', value: shortDigest(commit.afterStateHash, 12, 6) },
              { key: 'plan identity', value: shortDigest(commit.planIdentity, 12, 6) },
              { key: 'certificate id', value: shortDigest(commit.certificateIdentity, 12, 6) },
              { key: 'records', value: String(commit.records.length) },
            ]}
          />
        </div>
      ) : null}
    </div>
  );
}

export function TransactionView({
  preview,
  execution,
}: {
  readonly preview: ActionPreview | null;
  readonly execution: ExecutionResult | null;
}) {
  const { state, actions } = useWorkspace();

  if (!preview && !execution) {
    return (
      <EmptyState title="No transaction material">
        Run preflight or execute an action to populate the transaction view. The frontend stages
        nothing on its own.
      </EmptyState>
    );
  }

  const plan = execution?.plan ?? preview?.plan ?? null;
  const delta = execution?.delta ?? preview?.delta ?? null;
  const trace = execution?.trace ?? preview?.trace ?? null;
  const rng = execution?.transactionRng ?? preview?.transactionRng ?? null;
  const diff = preview?.diff ?? null;

  return (
    <div className="stack">
      <div className="row">
        <MockBadge />
        <span className="tiny dim">
          transaction state {state.session?.transactionState ?? 'not supplied'}
        </span>
        {preview ? <EvidenceModeBadge mode={preview.evidenceMode} /> : null}
        {execution ? null : <Badge tone="reference">pre-commit view</Badge>}
      </div>

      {execution ? <ExecutionSection execution={execution} /> : null}

      <div className="stack stack--tight">
        <span className="section-label">pre-commit material (staged · not live)</span>
        {plan ? <PlanSection plan={plan} /> : <span className="tiny dim">No plan supplied.</span>}
        {delta ? <DeltaSection delta={delta} /> : <span className="tiny dim">No staged delta supplied.</span>}
        {rng ? (
          <RngSection
            rng={rng}
            onInspect={(draw, sequence) =>
              actions.openDrawer(
                evidenceRecord(
                  'RNG_DRAW',
                  `Private RNG draw ${sequence} · ${draw.method}`,
                  { method: draw.method, arguments: draw.arguments, result: draw.result },
                  {
                    revisionLabel: 'sandbox RNG — not client-native',
                    ownerLabel: draw.method,
                  },
                ),
              )
            }
          />
        ) : (
          <span className="tiny dim">No transaction RNG document supplied.</span>
        )}
        {trace ? <TraceSection trace={trace} /> : <span className="tiny dim">No staged trace supplied.</span>}
      </div>

      {diff ? (
        <div className="stack stack--tight">
          <span className="section-label">supplied state diff</span>
          <DiffSection diff={diff} />
        </div>
      ) : null}
    </div>
  );
}
