import type { ReactNode } from 'react';

export interface KeyValueEntry {
  readonly key: string;
  readonly value: ReactNode;
  readonly wrap?: boolean;
}

export function KeyValueList({ entries }: { readonly entries: readonly KeyValueEntry[] }) {
  if (entries.length === 0) return <p className="tiny dim">No fields supplied.</p>;
  return (
    <div className="kv">
      {entries.map((entry) => (
        <div key={entry.key} style={{ display: 'contents' }}>
          <span className="kv__key">{entry.key}</span>
          <span className={`kv__value${entry.wrap ? ' kv__value--wrap' : ''}`}>{entry.value}</span>
        </div>
      ))}
    </div>
  );
}
