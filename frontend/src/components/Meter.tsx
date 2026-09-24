import type { MeterView } from '../models';
import { formatNullableNumber } from '../utils/format';

export interface MeterProps {
  readonly label: string;
  readonly meter: MeterView;
  readonly variant?: 'hp' | 'toughness';
}

/**
 * Renders a bar ONLY from supplied figures. When the adapter did not supply the
 * values the track is drawn as an explicit "not supplied" pattern — no width is
 * computed and no default is substituted.
 */
export function Meter({ label, meter, variant = 'hp' }: MeterProps) {
  const ratio =
    meter.supplied && meter.current !== null && meter.max !== null && meter.max > 0
      ? Math.max(0, Math.min(1, meter.current / meter.max))
      : null;
  const low = ratio !== null && ratio < 0.3;

  return (
    <div className={`meter${meter.supplied ? '' : ' meter--unsupplied'}`}>
      <div className="meter__head">
        <span>{label}</span>
        {meter.supplied ? (
          <span className="meter__value">
            {formatNullableNumber(meter.current)} / {formatNullableNumber(meter.max)}
          </span>
        ) : (
          <span className="meter__value dim">not supplied</span>
        )}
      </div>
      <div className="meter__track">
        {ratio === null ? null : (
          <div
            className={`meter__fill${variant === 'toughness' ? ' meter__fill--toughness' : ''}${
              low ? ' meter__fill--low' : ''
            }`}
            style={{ width: `${(ratio * 100).toFixed(2)}%` }}
          />
        )}
      </div>
    </div>
  );
}
