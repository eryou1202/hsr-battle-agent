#!/usr/bin/env node
/**
 * Reject JSON files containing duplicate object keys.
 *
 * Usage:
 *   node tools/control/validate_json_no_duplicate_keys.mjs <file> [...]
 *
 * This parser records duplicate locations before ordinary JSON parsing can
 * discard earlier values. It has no external dependencies and performs no
 * writes.
 */
import fs from "node:fs";

function inspectJson(text, file) {
  let offset = 0;
  const duplicates = [];

  const skipWhitespace = () => {
    while (offset < text.length && /\s/.test(text[offset])) offset += 1;
  };

  const parseString = () => {
    const start = offset;
    offset += 1;
    let value = "";
    while (offset < text.length) {
      const character = text[offset++];
      if (character === '"') return { value, start, end: offset };
      if (character !== "\\") {
        value += character;
        continue;
      }
      const escape = text[offset++];
      if (escape === "u") {
        const hex = text.slice(offset, offset + 4);
        if (!/^[0-9a-fA-F]{4}$/.test(hex)) {
          throw new SyntaxError(`invalid unicode escape at offset ${offset}`);
        }
        value += String.fromCharCode(Number.parseInt(hex, 16));
        offset += 4;
        continue;
      }
      const escapes = {
        '"': '"',
        "\\": "\\",
        "/": "/",
        b: "\b",
        f: "\f",
        n: "\n",
        r: "\r",
        t: "\t",
      };
      if (!(escape in escapes)) {
        throw new SyntaxError(`invalid escape at offset ${offset - 1}`);
      }
      value += escapes[escape];
    }
    throw new SyntaxError(`unterminated string at offset ${start}`);
  };

  const renderLocation = (path) =>
    "$" +
    path
      .map((part) =>
        typeof part === "number"
          ? `[${part}]`
          : /^[A-Za-z_$][A-Za-z0-9_$]*$/.test(part)
            ? `.${part}`
            : `[${JSON.stringify(part)}]`,
      )
      .join("");

  const parseValue = (path) => {
    skipWhitespace();
    const start = offset;
    const character = text[offset];
    if (character === "{") return parseObject(path, start);
    if (character === "[") return parseArray(path, start);
    if (character === '"') {
      const parsed = parseString();
      return { value: parsed.value, start, end: offset };
    }
    const token = text
      .slice(offset)
      .match(/^(true|false|null|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)/);
    if (!token) throw new SyntaxError(`invalid token at offset ${offset}`);
    offset += token[0].length;
    return { value: JSON.parse(token[0]), start, end: offset };
  };

  const parseObject = (path, start) => {
    offset += 1;
    skipWhitespace();
    const value = {};
    const seen = new Map();
    if (text[offset] === "}") {
      offset += 1;
      return { value, start, end: offset };
    }
    while (true) {
      skipWhitespace();
      if (text[offset] !== '"') {
        throw new SyntaxError(`object key expected at offset ${offset}`);
      }
      const key = parseString().value;
      skipWhitespace();
      if (text[offset++] !== ":") {
        throw new SyntaxError(`colon expected at offset ${offset - 1}`);
      }
      const child = parseValue([...path, key]);
      if (seen.has(key)) {
        const first = seen.get(key);
        duplicates.push({
          file,
          location: renderLocation(path),
          key,
          firstValue: first.value,
          secondValue: child.value,
          identical: JSON.stringify(first.value) === JSON.stringify(child.value),
          ordinaryParserLosesInformation: true,
        });
      } else {
        seen.set(key, child);
      }
      value[key] = child.value;
      skipWhitespace();
      if (text[offset] === ",") {
        offset += 1;
        continue;
      }
      if (text[offset] === "}") {
        offset += 1;
        break;
      }
      throw new SyntaxError(`object separator expected at offset ${offset}`);
    }
    return { value, start, end: offset };
  };

  const parseArray = (path, start) => {
    offset += 1;
    skipWhitespace();
    const value = [];
    if (text[offset] === "]") {
      offset += 1;
      return { value, start, end: offset };
    }
    let index = 0;
    while (true) {
      value.push(parseValue([...path, index]));
      index += 1;
      skipWhitespace();
      if (text[offset] === ",") {
        offset += 1;
        continue;
      }
      if (text[offset] === "]") {
        offset += 1;
        break;
      }
      throw new SyntaxError(`array separator expected at offset ${offset}`);
    }
    return { value, start, end: offset };
  };

  parseValue([]);
  skipWhitespace();
  if (offset !== text.length) {
    throw new SyntaxError(`trailing data at offset ${offset}`);
  }
  return duplicates;
}

const files = process.argv.slice(2);
if (files.length === 0) {
  console.error("usage: validate_json_no_duplicate_keys.mjs <file> [...]");
  process.exit(64);
}

let failed = false;
for (const file of files) {
  try {
    const duplicates = inspectJson(fs.readFileSync(file, "utf8"), file);
    if (duplicates.length > 0) {
      failed = true;
      console.error(JSON.stringify({ file, duplicates }, null, 2));
    } else {
      console.log(`PASS ${file}`);
    }
  } catch (error) {
    failed = true;
    console.error(`FAIL ${file}: ${error.message}`);
  }
}
process.exit(failed ? 2 : 0);
