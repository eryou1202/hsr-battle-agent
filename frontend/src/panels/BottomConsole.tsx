import { useState } from 'react';
import type { TraceEvent } from '../models';
import { EVENT_CATEGORIES } from '../models/events';
import { Badge } from '../components/Badge';
import { EmptyState } from '../components/EmptyState';
import { JsonViewer } from '../components/JsonViewer';
import { useWorkspace, type ConsoleTab } from '../app/WorkspaceProvider';
import { TransactionView } from './TransactionView';
import { StrictPipeline } from './StrictPipeline';
import { QuarantinePanel } from './QuarantinePanel';
import { JsonImportPanel } from './JsonImportPanel';

const CATEGORY_TONES: Record<string, 'muted' | 'info' | 'danger' | 'unknown' | 'reference' | 'ok' | 'accent'> = {
  STATE: 'info',
  ACTION: 'accent',
  PREFLIGHT: 'ok',
  BLOCKER: 'danger',
  RNG: 'unknown',
  QUEUE: 'reference',
  COMMIT: 'ok',
  REFERENCE: 'reference',
};

function EventRow({ event }: { readonly event: TraceEvent }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="eventrow">
      <div className="eventrow__head">
        <span className="eventrow__seq">{event.sequence === null ? '—' : `#${event.sequence}`}</span>
        <Badge tone={CATEGORY_TONES[event.category] ?? 'muted'}>{event.category}</Badge>
        <span className="eventrow__summary">{event.summary}</span>
        {event.evidenceMode ? <Badge tone="muted">{event.evidenceMode}</Badge> : null}
        {/* No fake timestamp: only render one when the source supplied it. */}
        {event.timestamp === null ? (
          <span className="tiny dim">no timestamp supplied</span>
        ) : (
          <span className="tiny dim mono">{event.timestamp}</span>
        )}
        <button type="button" className="btn btn--ghost" onClick={() => setOpen((value) => !value)}>
          {open ? 'Hide JSON' : 'Raw JSON'}
        </button>
      </div>
      {open ? (
        <div className="eventrow__raw">
          <JsonViewer value={event.raw} />
        </div>
      ) : null}
    </div>
  );
}

const TABS: readonly { readonly id: ConsoleTab; readonly label: string }[] = [
  { id: 'TRACE', label: 'Event / trace' },
  { id: 'PIPELINE', label: 'Strict pipeline' },
  { id: 'TRANSACTION', label: 'Transaction' },
  { id: 'DIFF', label: 'State diff' },
  { id: 'QUARANTINE', label: 'Quarantine' },
  { id: 'IMPORT', label: 'JSON import' },
  { id: 'RAW', label: 'Raw snapshot' },
];

export function BottomConsole() {
  const { state, actions } = useWorkspace();
  const { events, eventFilter, consoleTab } = state;

  const filtered =
    eventFilter === 'ALL' ? events : events.filter((event) => event.category === eventFilter);

  return (
    <section className="console">
      <div className="console__tabs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`tab${consoleTab === tab.id ? ' tab--active' : ''}`}
            onClick={() => actions.setConsoleTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}

        {consoleTab === 'TRACE' ? (
          <div className="console__filters">
            {EVENT_CATEGORIES.map((category) => (
              <button
                key={category}
                type="button"
                className={`tab${eventFilter === category ? ' tab--active' : ''}`}
                onClick={() => actions.setEventFilter(category)}
              >
                {category}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <div className="console__body">
        {consoleTab === 'TRACE' ? (
          filtered.length === 0 ? (
            <EmptyState
              title={events.length === 0 ? 'Empty trace' : `No ${eventFilter} records`}
            >
              {events.length === 0
                ? 'The adapter supplied no trace records. Nothing is synthesised to fill this console.'
                : `Filter ${eventFilter} matched none of the ${events.length} supplied records.`}
            </EmptyState>
          ) : (
            filtered.map((event) => <EventRow key={event.id} event={event} />)
          )
        ) : null}

        {consoleTab === 'PIPELINE' ? <StrictPipeline /> : null}

        {consoleTab === 'QUARANTINE' ? <QuarantinePanel entries={state.quarantine} /> : null}

        {consoleTab === 'IMPORT' ? <JsonImportPanel /> : null}

        {consoleTab === 'TRANSACTION' ? (
          <TransactionView preview={state.preview} execution={state.execution} />
        ) : null}

        {consoleTab === 'DIFF' ? (
          state.preview?.diff ? (
            <table className="table">
              <thead>
                <tr>
                  <th>field</th>
                  <th>before</th>
                  <th>after</th>
                </tr>
              </thead>
              <tbody>
                {state.preview.diff.entries.map((entry) => (
                  <tr
                    key={entry.field}
                    className={
                      JSON.stringify(entry.before) === JSON.stringify(entry.after)
                        ? ''
                        : 'diff-row--changed'
                    }
                  >
                    <td className="mono">{entry.field}</td>
                    <td className="mono diff-cell--before">{JSON.stringify(entry.before)}</td>
                    <td className="mono diff-cell--after">{JSON.stringify(entry.after)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EmptyState title="No state diff supplied">
              Run preflight on an action that carries a diff to compare before/after state fields.
            </EmptyState>
          )
        ) : null}

        {consoleTab === 'RAW' ? (
          state.snapshot ? (
            <JsonViewer value={state.snapshot.raw} />
          ) : (
            <EmptyState title="No raw snapshot">No snapshot is loaded.</EmptyState>
          )
        ) : null}
      </div>
    </section>
  );
}
