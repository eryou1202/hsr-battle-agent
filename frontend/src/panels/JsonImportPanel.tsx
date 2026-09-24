/**
 * Development-only JSON import tool.
 *
 * Lets a developer paste or load exported backend JSON when no live HTTP
 * backend exists. Unknown schemas are reported as UNSUPPORTED SCHEMA instead of
 * being guessed, and unknown fields are preserved and shown in the raw view
 * rather than discarded.
 */
import { useRef, useState } from 'react';
import type { ImportedDocument } from '../utils/jsonImport';
import { parseImportedJson } from '../utils/jsonImport';
import { Badge, MockBadge, type BadgeTone } from '../components/Badge';
import { EmptyState, Notice } from '../components/EmptyState';
import { JsonViewer } from '../components/JsonViewer';
import { KeyValueList } from '../components/KeyValueList';
import { useWorkspace } from '../app/WorkspaceProvider';

const KIND_TONES: Record<string, BadgeTone> = {
  PREFLIGHT_RESULT: 'ok',
  DEPENDENCY_CLOSURE: 'info',
  DEPENDENCY_OBLIGATION: 'info',
  CLOSURE_BLOCKER: 'danger',
  STRUCTURED_REJECTION: 'danger',
  GATE_CERTIFICATE: 'accent',
  TRANSACTION_PLAN: 'info',
  STAGED_DELTA: 'reference',
  STAGED_TRACE: 'reference',
  TRANSACTION_RNG: 'reference',
  ATOMIC_COMMIT_RESULT: 'accent',
  STRICT_STEP_RESULT: 'accent',
  CONTRACT_SLOT: 'unknown',
  STATE_REVISION: 'muted',
  REVISION_SEQUENCE: 'muted',
  BATTLE_STATE: 'muted',
  SNAPSHOT: 'muted',
  UNRECOGNIZED: 'unsupported',
};

const SAMPLE = `{
  "schema": "terra_strict_step_result/1",
  "outcome": "REJECTED",
  "resulting_revision": null,
  "transaction_identity": null,
  "rejections": [
    {
      "schema": "structured_rejection/1",
      "reason_code": "STRICT_TRANSACTION_REJECTED",
      "obligation_owner": "STRICT_STEP",
      "evidence_request": "unchanged certified source state",
      "contract_refs": [],
      "unknown_handles": [],
      "diagnostics": { "detail": "source revision is stale" }
    }
  ],
  "vendor_extension_field": "preserved, not discarded"
}`;

export function JsonImportPanel() {
  const { actions } = useWorkspace();
  const [text, setText] = useState('');
  const [document_, setDocument] = useState<ImportedDocument | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement | null>(null);

  const ingest = (raw: string, sourceLabel: string) => {
    const outcome = parseImportedJson(raw, sourceLabel);
    if (!outcome.ok) {
      setDocument(null);
      setError(outcome.error);
      return;
    }
    setError(null);
    setDocument(outcome.document);
  };

  return (
    <div className="stack">
      <div className="row">
        <MockBadge />
        <Badge tone="muted">dev tool</Badge>
        <span className="tiny dim">
          paste or load exported backend JSON · no live HTTP backend required
        </span>
      </div>

      <div className="row">
        <button type="button" className="btn btn--ghost" onClick={() => setText(SAMPLE)}>
          Load sample
        </button>
        <button type="button" className="btn btn--ghost" onClick={() => fileInput.current?.click()}>
          Load file…
        </button>
        <button
          type="button"
          className="btn"
          onClick={() => ingest(text, 'pasted JSON')}
          disabled={text.trim().length === 0}
        >
          Validate &amp; import
        </button>
        <button
          type="button"
          className="btn btn--ghost"
          onClick={() => {
            setText('');
            setDocument(null);
            setError(null);
          }}
        >
          Clear
        </button>
        <input
          ref={fileInput}
          type="file"
          accept=".json,application/json"
          style={{ display: 'none' }}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (!file) return;
            void file.text().then((content) => {
              setText(content);
              ingest(content, file.name);
            });
          }}
        />
      </div>

      <textarea
        className="import__textarea"
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder='{ "schema": "preflight_result/1", … }'
        spellCheck={false}
        rows={7}
      />

      {error ? (
        <Notice tone="danger" title="Import failed">
          {error}
        </Notice>
      ) : null}

      {document_ ? (
        <div className="stack">
          {!document_.recognized ? (
            <Notice tone="danger" title="UNSUPPORTED SCHEMA">
              Schema <span className="mono">{document_.schema ?? '(missing)'}</span> is not one this
              frontend knows. The document is preserved in the raw view below and nothing was
              guessed from it.
            </Notice>
          ) : (
            <div className="row">
              <Badge tone={KIND_TONES[document_.kind] ?? 'muted'}>{document_.kind}</Badge>
              <span className="tiny mono">{document_.schema}</span>
              <span className="tiny dim">from {document_.sourceLabel}</span>
            </div>
          )}

          <KeyValueList
            entries={[
              { key: 'recognized', value: document_.recognized ? 'yes' : 'no' },
              { key: 'kind', value: document_.kind },
              { key: 'schema', value: document_.schema ?? 'not supplied' },
              {
                key: 'missing fields',
                value:
                  document_.missingFields.length === 0
                    ? 'none'
                    : document_.missingFields.join(', '),
                wrap: true,
              },
              {
                key: 'unknown fields',
                value:
                  document_.unknownFields.length === 0
                    ? 'none'
                    : document_.unknownFields.join(', '),
                wrap: true,
              },
            ]}
          />

          {document_.unknownFields.length > 0 ? (
            <span className="tiny dim">
              Unknown fields are preserved and shown in the raw view — nothing was discarded.
            </span>
          ) : null}

          <div className="stack stack--tight">
            <span className="section-label">raw imported document</span>
            <div className="eventrow__raw">
              <JsonViewer value={document_.raw} defaultOpen />
            </div>
          </div>

          <button
            type="button"
            className="btn btn--ghost"
            onClick={() =>
              actions.openDrawer({
                kind: 'CONTRACT',
                title: `Imported ${document_.kind}`,
                evidenceMode: null,
                contractId: null,
                namespace: null,
                contractRevision: null,
                sourceRefs: [],
                revisionLabel: document_.schema,
                ownerLabel: document_.sourceLabel,
                raw: document_.raw,
              })
            }
          >
            Open in evidence drawer
          </button>
        </div>
      ) : (
        !error && (
          <EmptyState title="No document imported">
            Import a PreflightResult, GateCertificate or strict-step / transaction diagnostics
            document to inspect it here.
          </EmptyState>
        )
      )}
    </div>
  );
}
