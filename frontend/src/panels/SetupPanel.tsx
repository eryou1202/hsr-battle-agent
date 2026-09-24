import type { SetupEntity, BattleSetup } from '../models';
import { Collapsible } from '../components/Collapsible';
import { Badge, MockBadge } from '../components/Badge';
import { EmptyState } from '../components/EmptyState';
import { KeyValueList } from '../components/KeyValueList';
import { useWorkspace } from '../app/WorkspaceProvider';

const EXECUTABLE_TONES: Record<string, 'ok' | 'reference' | 'unknown' | 'unsupported'> = {
  NATIVE_EVIDENCED: 'ok',
  REFERENCE_MODEL: 'reference',
  SANDBOX_EXTENSION: 'unknown',
  UNSUPPORTED: 'unsupported',
};

function EntityRow({
  entity,
  selected,
  onSelect,
}: {
  readonly entity: SetupEntity;
  readonly selected: boolean;
  readonly onSelect: (id: string) => void;
}) {
  const tone = EXECUTABLE_TONES[entity.supportState] ?? 'unsupported';
  return (
    <Collapsible
      label={`${entity.codename} · ${entity.name}`}
      accessory={
        <span className="row">
          <Badge tone={tone}>{entity.supportState}</Badge>
          {!entity.executable ? <Badge tone="muted">not executable</Badge> : null}
        </span>
      }
      defaultOpen={selected}
    >
      <div className="stack">
        <div className="row">
          <button
            type="button"
            className={`btn${selected ? ' btn--primary' : ' btn--ghost'}`}
            onClick={() => onSelect(entity.id)}
          >
            {selected ? 'Active unit' : 'Set active'}
          </button>
          <span className="tiny dim">{entity.level === null ? 'level not supplied' : `level ${entity.level}`}</span>
        </div>

        <KeyValueList
          entries={[
            { key: 'id', value: entity.id },
            { key: 'slot', value: String(entity.slot) },
            { key: 'role', value: entity.role ?? 'not supplied' },
            { key: 'affinity', value: entity.affinity ?? 'not supplied' },
            { key: 'evidence', value: entity.supportState },
            { key: 'executable', value: entity.executable ? 'yes' : 'no' },
          ]}
        />

        {entity.notes.length > 0 ? (
          <div className="stack stack--tight">
            <span className="section-label">notes</span>
            {entity.notes.map((note) => (
              <span key={note} className="tiny muted">
                {note}
              </span>
            ))}
          </div>
        ) : null}

        <div className="stack stack--tight">
          <span className="section-label">loadout</span>
          {entity.loadout.map((slot) => (
            <div key={slot.id} className="row row--between">
              <span className="tiny">
                <span className="dim">{slot.kind}</span> {slot.label}
              </span>
              <span className="row">
                {slot.supplied ? (
                  <span className="tiny mono">{slot.value}</span>
                ) : (
                  <Badge tone="muted">not supplied</Badge>
                )}
                {slot.supportState !== 'NATIVE_EVIDENCED' ? (
                  <Badge tone={EXECUTABLE_TONES[slot.supportState] ?? 'unsupported'}>
                    {slot.supportState}
                  </Badge>
                ) : null}
              </span>
            </div>
          ))}
        </div>
      </div>
    </Collapsible>
  );
}

function SetupSection({ setup }: { readonly setup: BattleSetup }) {
  return (
    <Collapsible label="Scenario" defaultOpen>
      <div className="stack">
        <KeyValueList
          entries={[
            { key: 'id', value: setup.scenario.id },
            { key: 'label', value: setup.scenario.label },
            { key: 'stage ref', value: setup.scenario.stageRef ?? 'not supplied' },
            { key: 'waves', value: setup.scenario.waveCount === null ? 'not supplied' : String(setup.scenario.waveCount) },
            { key: 'cycle limit', value: setup.scenario.cycleLimit === null ? 'not supplied' : String(setup.scenario.cycleLimit) },
          ]}
        />
        {setup.scenario.notes.map((note) => (
          <span key={note} className="tiny muted">
            {note}
          </span>
        ))}
      </div>
    </Collapsible>
  );
}

function ModeSection({ setup }: { readonly setup: BattleSetup }) {
  return (
    <Collapsible label="Mode / evidence" defaultOpen>
      <div className="stack">
        <KeyValueList
          entries={[
            { key: 'evidence mode', value: setup.mode.evidenceMode },
            { key: 'readiness', value: setup.mode.readinessClass ?? 'not supplied' },
            { key: 'version relation', value: setup.mode.versionRelation ?? 'not supplied' },
            { key: 'strict execution', value: setup.mode.strictExecution ? 'on' : 'off' },
          ]}
        />
        {setup.mode.versionRelation === 'CLOSE_VERSION' ? (
          <EmptyState tone="warning" title="close version — never shown as exact native">
            The selected source version relation is CLOSE_VERSION. The frontend keeps it distinct
            from EXACT_NATIVE and never promotes it.
          </EmptyState>
        ) : null}
        {setup.mode.notes.map((note) => (
          <span key={note} className="tiny muted">
            {note}
          </span>
        ))}
      </div>
    </Collapsible>
  );
}

export function SetupPanel() {
  const { state, actions } = useWorkspace();
  const { setup, selectedUnitId, session } = state;

  if (!setup) {
    return (
      <div className="panel__body">
        <EmptyState title="No scenario loaded">
          The adapter supplied no battle setup. Load a mock scenario, or connect a backend that
          implements <span className="mono">getBattleSetup()</span>.
        </EmptyState>
      </div>
    );
  }

  return (
    <div className="panel__body panel__body--scroll" style={{ flex: '1 1 auto', minHeight: 0, paddingBottom: 16 }}>
      <div className="mock-banner mock-banner--inline">
        <MockBadge label="DEMO / MOCK DATA" />
        <span className="tiny">fixtures, not live execution</span>
      </div>

      <div className="stack">
        <div className="row row--between">
          <span className="section-label" style={{ marginBottom: 0 }}>
            battle setup
          </span>
          <span className="row">
            <button type="button" className="btn btn--ghost" onClick={actions.reset}>
              Reset
            </button>
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => actions.selectScenario('A')}
              disabled={session?.dataProvenance !== 'MOCK_DATA'}
            >
              Load demo A
            </button>
          </span>
        </div>

        <div>
          <span className="section-label">team · {setup.team.length} slots</span>
          <div className="stack stack--tight">
            {setup.team.map((entity) => (
              <EntityRow
                key={entity.id}
                entity={entity}
                selected={selectedUnitId === entity.id}
                onSelect={actions.selectUnit}
              />
            ))}
          </div>
        </div>

        <div>
          <span className="section-label">enemies · {setup.enemies.length} slots</span>
          <div className="stack stack--tight">
            {setup.enemies.map((entity) => (
              <EntityRow
                key={entity.id}
                entity={entity}
                selected={selectedUnitId === entity.id}
                onSelect={actions.selectUnit}
              />
            ))}
          </div>
        </div>

        <SetupSection setup={setup} />
        <ModeSection setup={setup} />
      </div>
    </div>
  );
}
