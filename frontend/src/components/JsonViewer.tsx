import { useState } from 'react';
import type { JsonValue } from '../models';

function isObject(value: JsonValue): value is { [key: string]: JsonValue } {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function Scalar({ value }: { readonly value: JsonValue }) {
  if (value === null) return <span className="json__scalar json__scalar--null">null</span>;
  if (typeof value === 'string')
    return <span className="json__scalar json__scalar--string">&quot;{value}&quot;</span>;
  if (typeof value === 'number')
    return <span className="json__scalar json__scalar--number">{String(value)}</span>;
  if (typeof value === 'boolean')
    return <span className="json__scalar json__scalar--bool">{value ? 'true' : 'false'}</span>;
  return <span className="json__scalar">{String(value)}</span>;
}

interface NodeProps {
  readonly name: string | null;
  readonly value: JsonValue;
  readonly depth: number;
  readonly defaultOpen: boolean;
}

function Node({ name, value, depth, defaultOpen }: NodeProps) {
  const branch = isObject(value) || Array.isArray(value);
  const [open, setOpen] = useState(defaultOpen ? depth < 2 : false);

  if (!branch) {
    return (
      <div className="json__row">
        {name !== null ? <span className="json__key">{name}: </span> : null}
        <Scalar value={value} />
      </div>
    );
  }

  const entries: readonly [string, JsonValue][] = Array.isArray(value)
    ? value.map((item, index) => [String(index), item])
    : Object.entries(value);

  return (
    <div className="json__row">
      <button
        type="button"
        className="json__toggle"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
      >
        {open ? '▾' : '▸'}
      </button>
      <span style={{ minWidth: 0 }}>
        {name !== null ? <span className="json__key">{name}: </span> : null}
        <span className="json__scalar">{Array.isArray(value) ? '[' : '{'}</span>
        {!open ? (
          <span className="json__preview">
            {' '}
            {entries.length} {Array.isArray(value) ? 'items' : 'fields'}{' '}
            {Array.isArray(value) ? ']' : '}'}
          </span>
        ) : null}
        {open ? (
          <div className="json__children">
            {entries.map(([key, child]) => (
              <Node key={key} name={Array.isArray(value) ? null : key} value={child} depth={depth + 1} defaultOpen={defaultOpen} />
            ))}
          </div>
        ) : null}
        {open ? (
          <span className="json__scalar">{Array.isArray(value) ? ']' : '}'}</span>
        ) : null}
      </span>
    </div>
  );
}

export interface JsonViewerProps {
  readonly value: JsonValue;
  readonly defaultOpen?: boolean;
}

export function JsonViewer({ value, defaultOpen = true }: JsonViewerProps) {
  return (
    <div className="json">
      <Node name={null} value={value} depth={0} defaultOpen={defaultOpen} />
    </div>
  );
}
