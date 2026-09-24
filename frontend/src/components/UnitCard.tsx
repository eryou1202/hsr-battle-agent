import type { UnitView } from '../models';
import { Meter } from './Meter';
import { Badge } from './Badge';

export interface UnitCardProps {
  readonly unit: UnitView;
  readonly selected: boolean;
  readonly targeted: boolean;
  readonly isCurrentActor: boolean;
  readonly onSelect: (unitId: string) => void;
  readonly onTarget: (unitId: string) => void;
}

function initials(codename: string): string {
  return codename.replace(/[^A-Za-z0-9]/g, '').slice(0, 4).toUpperCase();
}

function chipTone(mode: string): string {
  switch (mode) {
    case 'NATIVE_EVIDENCED':
      return 'chip chip--native';
    case 'REFERENCE_MODEL':
      return 'chip chip--reference';
    case 'SANDBOX_EXTENSION':
      return 'chip chip--extension';
    default:
      return 'chip chip--unsupported';
  }
}

export function UnitCard({ unit, selected, targeted, isCurrentActor, onSelect, onTarget }: UnitCardProps) {
  const className = [
    'unitcard',
    selected ? 'unitcard--selected' : '',
    targeted ? 'unitcard--targeted' : '',
    isCurrentActor ? 'unitcard--actor' : '',
    unit.supportState === 'UNSUPPORTED' ? 'unitcard--unsupported' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <button
      type="button"
      className={className}
      onClick={() => onSelect(unit.id)}
      onDoubleClick={() => onTarget(unit.id)}
      title="Click to inspect · double-click to set as target"
    >
      <span className="unitcard__avatar">{initials(unit.codename)}</span>
      <span className="unitcard__main">
        <span className="unitcard__top">
          <span className="unitcard__name">{unit.name}</span>
          <span className="unitcard__level">{unit.level === null ? 'lv —' : `lv ${unit.level}`}</span>
        </span>
        <span className="unitcard__tags">
          <span className="chip">{unit.codename}</span>
          {unit.role ? <span className="chip">{unit.role}</span> : null}
          {unit.affinity ? <span className="chip">{unit.affinity}</span> : null}
          {isCurrentActor ? <Badge tone="info">actor</Badge> : null}
          {targeted ? <Badge tone="danger">target</Badge> : null}
        </span>
        <span className="unitcard__bars">
          <Meter label="HP" meter={unit.hp} />
          <Meter label="TOUGHNESS" meter={unit.toughness} variant="toughness" />
        </span>
        {unit.statuses.length > 0 ? (
          <span className="unitcard__tags">
            {unit.statuses.map((status) => (
              <span key={status.id} className={chipTone(status.evidenceMode)}>
                {status.label}
                {status.stacksSupplied && status.stacks !== null ? (
                  <span className="chip__count">×{status.stacks}</span>
                ) : null}
                {status.durationSupplied && status.duration !== null ? (
                  <span className="chip__count">{status.duration}t</span>
                ) : null}
              </span>
            ))}
          </span>
        ) : null}
        {unit.notes.length > 0 ? (
          <span className="unitcard__tags">
            {unit.notes.map((note) => (
              <span key={note} className="tiny dim">
                {note}
              </span>
            ))}
          </span>
        ) : null}
      </span>
    </button>
  );
}
