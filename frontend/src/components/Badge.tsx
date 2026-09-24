import type { ReactNode } from 'react';

export type BadgeTone =
  | 'native'
  | 'reference'
  | 'extension'
  | 'unsupported'
  | 'unknown'
  | 'mock'
  | 'ok'
  | 'danger'
  | 'info'
  | 'muted'
  | 'accent';

export interface BadgeProps {
  readonly tone?: BadgeTone;
  readonly children: ReactNode;
  readonly title?: string;
  readonly onClick?: () => void;
  readonly dot?: boolean;
}

export function Badge({ tone = 'muted', children, title, onClick, dot = false }: BadgeProps) {
  const className = `badge badge--${tone}${onClick ? ' badge--button' : ''}`;
  if (onClick) {
    return (
      <button type="button" className={className} onClick={onClick} title={title ?? 'Inspect evidence'}>
        {dot ? <span className="badge__dot" /> : null}
        {children}
      </button>
    );
  }
  return (
    <span className={className} title={title}>
      {dot ? <span className="badge__dot" /> : null}
      {children}
    </span>
  );
}

const EVIDENCE_TONES: Record<string, BadgeTone> = {
  NATIVE_EVIDENCED: 'native',
  REFERENCE_MODEL: 'reference',
  SANDBOX_EXTENSION: 'extension',
  UNSUPPORTED: 'unsupported',
};

export function EvidenceModeBadge({
  mode,
  onClick,
  suffix,
}: {
  readonly mode: string;
  readonly onClick?: () => void;
  readonly suffix?: string;
}) {
  return (
    <Badge tone={EVIDENCE_TONES[mode] ?? 'muted'} onClick={onClick} title={`Evidence mode: ${mode}`}>
      {suffix ? `${mode} ${suffix}` : mode}
    </Badge>
  );
}

export function MockBadge({ label = 'MOCK DATA' }: { readonly label?: string }) {
  return (
    <Badge tone="mock" dot title="Synthetic fixture data — not live native execution">
      {label}
    </Badge>
  );
}
