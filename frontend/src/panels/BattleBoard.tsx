import type { BattleSnapshot, UnitView } from '../models';
import { UnitCard } from '../components/UnitCard';
import { EmptyState } from '../components/EmptyState';
import { Badge, MockBadge } from '../components/Badge';
import { useWorkspace } from '../app/WorkspaceProvider';

function BoardRow({
  title,
  units,
  selectedUnitId,
  targetUnitId,
  currentActorId,
  onSelect,
  onTarget,
}: {
  readonly title: string;
  readonly units: readonly UnitView[];
  readonly selectedUnitId: string | null;
  readonly targetUnitId: string | null;
  readonly currentActorId: string | null;
  readonly onSelect: (id: string) => void;
  readonly onTarget: (id: string) => void;
}) {
  return (
    <div className="board__row">
      <div className="board__row-head">
        <span>{title}</span>
        <span className="tiny dim">{units.length}</span>
      </div>
      <div className="board__units">
        {units.map((unit) => (
          <UnitCard
            key={unit.id}
            unit={unit}
            selected={selectedUnitId === unit.id}
            targeted={targetUnitId === unit.id}
            isCurrentActor={currentActorId === unit.id}
            onSelect={onSelect}
            onTarget={onTarget}
          />
        ))}
      </div>
    </div>
  );
}

export function BattleBoard({ snapshot }: { readonly snapshot: BattleSnapshot | null }) {
  const { state, actions } = useWorkspace();

  if (!snapshot) {
    return (
      <div className="panel__body">
        <EmptyState title="No battle snapshot">
          No snapshot is loaded, so no board can be rendered. The frontend does not fabricate a
          board from setup data.
        </EmptyState>
      </div>
    );
  }

  const target = snapshot.enemies.find((unit) => unit.id === state.targetUnitId) ?? null;

  return (
    <div className="panel__body">
      <div className="stack">
        <div className="row row--between">
          <span className="row">
            <Badge tone="info">actor {snapshot.currentActorId ?? 'not supplied'}</Badge>
            <Badge tone={target ? 'danger' : 'muted'}>
              target {target ? target.codename : 'not supplied'}
            </Badge>
            <MockBadge />
          </span>
          <span className="tiny dim">
            values rendered verbatim from adapter data; nothing is computed client-side
          </span>
        </div>

        <div className="board">
          <BoardRow
            title="Allied units"
            units={snapshot.allies}
            selectedUnitId={state.selectedUnitId}
            targetUnitId={state.targetUnitId}
            currentActorId={snapshot.currentActorId}
            onSelect={actions.selectUnit}
            onTarget={actions.setTarget}
          />
          <BoardRow
            title="Enemy units"
            units={snapshot.enemies}
            selectedUnitId={state.selectedUnitId}
            targetUnitId={state.targetUnitId}
            currentActorId={snapshot.currentActorId}
            onSelect={actions.selectUnit}
            onTarget={actions.setTarget}
          />
        </div>
      </div>
    </div>
  );
}
