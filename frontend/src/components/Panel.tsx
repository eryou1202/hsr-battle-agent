import type { ReactNode } from 'react';

export interface PanelProps {
  readonly title: string;
  readonly children: ReactNode;
  readonly actions?: ReactNode;
  readonly accessory?: ReactNode;
  readonly scroll?: boolean;
  readonly grow?: boolean;
}

export function Panel({
  title,
  children,
  actions,
  accessory,
  scroll = false,
  grow = false,
}: PanelProps) {
  return (
    <section className="panel" style={grow ? { flex: '1 1 auto', minHeight: 0 } : undefined}>
      <header className="panel__header">
        <span className="panel__title">{title}</span>
        {accessory}
        {actions ? <div className="panel__actions">{actions}</div> : null}
      </header>
      <div
        className={`panel__body${scroll ? ' panel__body--scroll' : ''}`}
        style={grow ? { flex: '1 1 auto', minHeight: 0, overflowY: 'auto' } : undefined}
      >
        {children}
      </div>
    </section>
  );
}
