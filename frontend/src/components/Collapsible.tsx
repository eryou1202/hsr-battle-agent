import { useState, type ReactNode } from 'react';

export interface CollapsibleProps {
  readonly label: string;
  readonly children: ReactNode;
  readonly defaultOpen?: boolean;
  readonly accessory?: ReactNode;
}

export function Collapsible({ label, children, defaultOpen = false, accessory }: CollapsibleProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="collapsible">
      <button
        type="button"
        className="collapsible__trigger"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <span className={`collapsible__caret${open ? ' collapsible__caret--open' : ''}`}>▶</span>
        <span className="collapsible__label">{label}</span>
        {accessory}
      </button>
      {open ? <div className="collapsible__body">{children}</div> : null}
    </div>
  );
}
