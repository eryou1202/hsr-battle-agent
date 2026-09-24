import type { ReactNode } from 'react';

export interface EmptyStateProps {
  readonly title: string;
  readonly children?: ReactNode;
  readonly tone?: 'neutral' | 'danger' | 'warning' | 'reference' | 'ok';
}

export function EmptyState({ title, children, tone = 'neutral' }: EmptyStateProps) {
  if (tone === 'neutral') {
    return (
      <div className="empty">
        <span className="empty__title muted">{title}</span>
        {children ? <div className="empty__body">{children}</div> : null}
      </div>
    );
  }
  return (
    <div className={`notice notice--${tone}`}>
      <span className="notice__title">{title}</span>
      {children ? <div className="notice__body">{children}</div> : null}
    </div>
  );
}

export interface NoticeProps {
  readonly title: ReactNode;
  readonly tone?: 'danger' | 'warning' | 'reference' | 'ok';
  readonly children?: ReactNode;
}

export function Notice({ title, tone = 'warning', children }: NoticeProps) {
  return (
    <div className={`notice notice--${tone}`}>
      <span className="notice__title">{title}</span>
      {children ? <div className="notice__body">{children}</div> : null}
    </div>
  );
}
