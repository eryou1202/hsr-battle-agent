import { TopStatusBar } from '../panels/TopStatusBar';
import { SetupPanel } from '../panels/SetupPanel';
import { BattleBoard } from '../panels/BattleBoard';
import { TimelineStrip } from '../panels/TimelineStrip';
import { ActionPanel } from '../panels/ActionPanel';
import { PreflightInspector } from '../panels/PreflightInspector';
import { BottomConsole } from '../panels/BottomConsole';
import { EvidenceDrawer } from '../panels/EvidenceDrawer';
import { Panel } from '../components/Panel';
import { EmptyState } from '../components/EmptyState';
import { Badge } from '../components/Badge';
import { useWorkspace } from './WorkspaceProvider';

/** Deliberate "backend disconnected" screen — not a generic error message. */
function BackendDisconnected({ message }: { readonly message: string }) {
  return (
    <div className="panel__body">
      <EmptyState tone="danger" title="Backend disconnected">
        <div className="stack stack--tight">
          <span>{message}</span>
          <span>
            The live adapter is a NOT_CONNECTED skeleton: no backend contract has been defined, so
            no request was made and no endpoint was invented. Switch the adapter selector to MOCK
            to inspect deterministic demo fixtures.
          </span>
        </div>
      </EmptyState>
    </div>
  );
}

function CenterColumn() {
  const { state } = useWorkspace();

  if (state.failureCode && !state.snapshot) {
    return <BackendDisconnected message={state.failureMessage ?? state.failureCode} />;
  }

  return (
    <>
      <Panel title="Battle board" accessory={<Badge tone="muted">data-driven</Badge>}>
        <BattleBoard snapshot={state.snapshot} />
      </Panel>
      <Panel title="Turn / AV timeline" accessory={<Badge tone="muted">supplied order</Badge>}>
        <TimelineStrip timeline={state.snapshot?.timeline ?? []} />
      </Panel>
      <Panel
        title="Action controls"
        accessory={
          <span className="tiny dim">
            {state.loading ? 'working…' : `${state.actions.length} descriptors`}
          </span>
        }
      >
        <ActionPanel actions={state.actions} />
      </Panel>
    </>
  );
}

function RightColumn() {
  const { state } = useWorkspace();

  if (state.failureCode && !state.snapshot) {
    return (
      <Panel title="Preflight / evidence inspector">
        <BackendDisconnected message={state.failureMessage ?? state.failureCode} />
      </Panel>
    );
  }

  return (
    <Panel
      title="Preflight / evidence inspector"
      accessory={<Badge tone="muted">{state.preview ? 'preview loaded' : 'not run'}</Badge>}
      grow
    >
      <PreflightInspector preview={state.preview} />
    </Panel>
  );
}

function LeftColumn() {
  const { state } = useWorkspace();

  if (state.failureCode && !state.snapshot) {
    return (
      <Panel title="Battle setup">
        <BackendDisconnected message={state.failureMessage ?? state.failureCode} />
      </Panel>
    );
  }

  return (
    <Panel title="Battle setup" accessory={<Badge tone="muted">fixtures</Badge>} grow>
      <SetupPanel />
    </Panel>
  );
}

export function App() {
  const { state } = useWorkspace();

  return (
    <div className="workspace">
      <TopStatusBar />
      <div className="workspace__body">
        <div className="workspace__column">
          {state.session?.dataProvenance === 'MOCK_DATA' ? (
            <div className="mock-banner">
              <span>DEMO / MOCK DATA — not live native execution</span>
            </div>
          ) : null}
          <LeftColumn />
        </div>

        <div className="workspace__column workspace__column--center">
          <div className="column-scroll">
            <CenterColumn />
          </div>
        </div>

        <div className="workspace__column workspace__column--right">
          <RightColumn />
        </div>
      </div>
      <BottomConsole />
      {state.drawer ? <EvidenceDrawer record={state.drawer} /> : null}
    </div>
  );
}
