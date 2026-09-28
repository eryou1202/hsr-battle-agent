/** Lossless import for backend integer tokens (including 64-bit Stage metadata).
 * The backend number stays a number in the source JSON. This wrapper preserves
 * its exact spelling in the presentation DTO; it is never a calculated value.
 */
export class LosslessInteger {
  constructor(readonly decimal: string) {
    if (!/^-?(0|[1-9]\d*)$/.test(decimal)) throw new Error('INVALID_INTEGER_TOKEN');
    Object.freeze(this);
  }
}
export type ProductValue = null | boolean | string | number | LosslessInteger | ProductValue[] | ProductObject;
export interface ProductObject { [key: string]: ProductValue }

export class ProductContractError extends Error {
  constructor(readonly path: string, detail = 'INVALID_PRODUCT_DOCUMENT') {
    super(`${detail}: ${path}`);
  }
}

/** Parse JSON without rounding unsafe integer tokens or accepting duplicate keys. */
export function parseProductJson(text: string): ProductValue {
  let position = 0;
  function fail(): never { throw new ProductContractError(`text[${position}]`, 'INVALID_PRODUCT_JSON'); }
  function whitespace() { while (/[\x20\t\r\n]/.test(text[position] ?? '') && position < text.length) position++; }
  function string(): string {
    const start = position++;
    while (position < text.length) {
      const character = text[position++];
      if (character === '\\') position++;
      else if (character === '"') {
        try { return JSON.parse(text.slice(start, position)) as string; } catch { fail(); }
      }
    }
    return fail();
  }
  function value(depth: number): ProductValue {
    if (depth > 128) fail();
    whitespace();
    const first = text[position];
    if (first === '"') return string();
    if (first === '{') {
      position++;
      const record: ProductObject = Object.create(null) as ProductObject;
      whitespace();
      if (text[position] === '}') { position++; return record; }
      while (position < text.length) {
        whitespace();
        if (text[position] !== '"') fail();
        const key = string();
        if (Object.hasOwn(record, key)) fail();
        whitespace();
        if (text[position++] !== ':') fail();
        record[key] = value(depth + 1);
        whitespace();
        const separator = text[position++];
        if (separator === '}') return record;
        if (separator !== ',') fail();
      }
      return fail();
    }
    if (first === '[') {
      position++;
      const entries: ProductValue[] = [];
      whitespace();
      if (text[position] === ']') { position++; return entries; }
      while (position < text.length) {
        entries.push(value(depth + 1));
        whitespace();
        const separator = text[position++];
        if (separator === ']') return entries;
        if (separator !== ',') fail();
      }
      return fail();
    }
    for (const [token, result] of [['true', true], ['false', false], ['null', null]] as const) {
      if (text.startsWith(token, position)) { position += token.length; return result; }
    }
    const token = /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/.exec(text.slice(position))?.[0];
    if (!token) fail();
    position += token.length;
    const number = Number(token);
    if (!Number.isFinite(number)) fail();
    if (/^-?\d+$/.test(token) && !Number.isSafeInteger(number)) return new LosslessInteger(token);
    // Unsafe exponent/decimal integer tokens are outside this DTO's import contract.
    if (Number.isInteger(number) && !Number.isSafeInteger(number)) fail();
    return number;
  }
  const parsed = value(0);
  whitespace();
  if (position !== text.length) fail();
  return parsed;
}

export function assertProductValue(value: unknown, path = '$', depth = 0): asserts value is ProductValue {
  if (depth > 128) throw new ProductContractError(path);
  if (value === null || typeof value === 'string' || typeof value === 'boolean' || value instanceof LosslessInteger) return;
  if (typeof value === 'number' && Number.isFinite(value) &&
      (!Number.isInteger(value) || Number.isSafeInteger(value))) return;
  if (Array.isArray(value)) {
    value.forEach((entry, index) => assertProductValue(entry, `${path}[${index}]`, depth + 1));
    return;
  }
  if (typeof value === 'object' && value &&
      [null, Object.prototype].includes(Object.getPrototypeOf(value) as object | null)) {
    for (const [key, entry] of Object.entries(value)) assertProductValue(entry, `${path}.${key}`, depth + 1);
    return;
  }
  throw new ProductContractError(path, 'INVALID_OR_ROUNDED_PRODUCT_VALUE');
}
