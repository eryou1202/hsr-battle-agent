import type { BackendMode, SessionInfo, TransactionState } from '../models';
import { Badge, MockBadge, type BadgeTone } from '../components/Badge';
import { formatCounter, shortDigest } from '../utils/format';
import { useWorkspace } from '../app/WorkspaceProvider';
import { MOCK_SCENARIO_DESCRIPTORS } from '../fixtures';

const MODE_TONES: Record<BackendMode, BadgeTone> = {
  MOCK: 'mock',
  NATIVE_EVIDENCED: 'native',
  REFERENCE_MODEL: 'reference',
  SANDBOX_EXTENSION: 'extension',
  UNSUPPORTED: 'unsupported',
};

const TRANSACTION_TONES: Record<TransactionState, BadgeTone> = {
  NO_TRANSACTION: 'muted',
  IDLE: 'muted',
  PLANNED: 'info',
  STAGED: 'info',
  COMMITTED: 'ok',
  REJECTED: 'danger',
  UNSUPPORTED: 'unsupported',
  REFERENCE_ONLY: 'reference',
};

function ConnectionBadge({ session }: { readonly session: SessionInfo }) {
  if (session.connection === 'CONNECTED') {
    return (
      <Badge tone={session.adapterKind === 'MOCK' ? 'mock' : 'ok'} dot>
        {session.adapterKind === 'MOCK' ? 'mock adapter' : 'connected'}
      </Badge>
    );
  }
  if (session.connection === 'NOT_CONNECTED') return <Badge tone="danger" dot>not connected</Badge>;
  if (session.connection === 'DEGRADED') return <Badge tone="unknown" dot>degraded</Badge>;
  return <Badge tone="muted" dot>unknown</Badge>;
}

function Metric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="metric">
      <span className="metric__label">{label}</span>
      <span className="metric__value">{value}</span>
    </div>
  );
}

export function TopStatusBar() {
  const { state, actions } = useWorkspace();
  const { session, adapterKind, scenarioId } = state;

  return (
    <header className="statusbar">
      <div className="statusbar__brand">
        <span className="statusbar__title">HSR Battle Agent</span>
        <span className="statusbar__subtitle">evidence-gated battle workspace</span>
      </div>

      <div className="statusbar__group">
        <span className="metric__label">content</span>
        <Badge tone="accent">{session?.contentVersion ?? '4.4.54'}</Badge>
      </div>

      {session ? (
        <div className="statusbar__group">
          <span className="metric__label">mode</span>
          <Badge tone={MODE_TONES[session.backendMode]} dot>
            {session.backendMode}
          </Badge>
          {/* The mode badge alone must never imply real native execution. */}
          {session.dataProvenance === 'MOCK_DATA' ? <MockBadge /> : null}
        </div>
      ) : (
        <div className="statusbar__group">
          <span className="metric__label">mode</span>
          <Badge tone="danger" dot>
            {adapterKind === 'LIVE' ? 'BACKEND NOT CONNECTED' : 'NO SESSION'}
          </Badge>
        </div>
      )}

      <div className="statusbar__metrics">
        {session ? (
          <>
            <Metric label="state revision" value={formatCounter(session.stateRevisionCounter)} />
            <Metric
              label="semantic hash"
              value={shortDigest(session.semanticHash)}
            />
            <Metric
              label="rng draw pos"
              value={session.rngDrawPosition === null ? 'not supplied' : String(session.rngDrawPosition)}
            />
            <div className="metric">
              <span className="metric__label">transaction</span>
              <Badge tone={TRANSACTION_TONES[session.transactionState]}>
                {session.transactionState}
              </Badge>
            </div>
            <div className="metric">
              <span className="metric__label">connection</span>
              <ConnectionBadge session={session} />
            </div>
          </>
        ) : (
          <div className="metric">
            <span className="metric__label">state</span>
            <span className="metric__value dim">no scenario loaded</span>
          </div>
        )}

        <div className="metric">
          <span className="metric__label">scenario</span>
          <select
            className="select"
            value={scenarioId}
            onChange={(event) => actions.selectScenario(event.target.value)}
            disabled={adapterKind !== 'MOCK'}
            title={adapterKind === 'MOCK' ? 'Load a demo mock scenario' : 'Mock scenarios require the mock adapter'}
          >
            {MOCK_SCENARIO_DESCRIPTORS.map((descriptor) => (
              <option key={descriptor.id} value={descriptor.id}>
                {descriptor.label}
              </option>
            ))}
          </select>
        </div>

        <div className="metric">
          <span className="metric__label">adapter</span>
          <select
            className="select"
            value={adapterKind}
            onChange={(event) => actions.setAdapterKind(event.target.value === 'LIVE' ? 'LIVE' : 'MOCK')}
          >
            <option value="MOCK">MOCK (fixtures)</option>
            <option value="LIVE">LIVE (not connected)</option>
          </select>
        </div>
      </div>
    </header>
  );
}
