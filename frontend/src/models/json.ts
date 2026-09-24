/**
 * Raw JSON boundary types.
 *
 * These are the ONLY `unknown`/permissive types in the frontend. Everything that
 * crosses the adapter boundary is either a typed model or an opaque `JsonValue`
 * rendered verbatim. The frontend never interprets a raw JSON payload in order
 * to derive battle semantics.
 */
export type JsonPrimitive = string | number | boolean | null;

export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };

export type JsonObject = { [key: string]: JsonValue };

export function isJsonObject(value: JsonValue): value is JsonObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
