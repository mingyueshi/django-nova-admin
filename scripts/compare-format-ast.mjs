// One-off formatting audit. Both directories must contain the same JS modules.
// Uses the parser bundled with the exact pinned Prettier version; not a runtime API.
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import * as prettier from 'prettier';

const [before, after] = process.argv.slice(2);
if (!before || !after) {
  throw new Error('Usage: node scripts/compare-format-ast.mjs BEFORE_DIRECTORY AFTER_DIRECTORY');
}
const metadata = new Set([
  'start', 'end', 'loc', 'range', 'extra', 'tokens', 'comments',
  'leadingComments', 'trailingComments', 'innerComments', '__contentEnd',
]);
function semantic(value) {
  if (Array.isArray(value)) return value.map(semantic);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value)
      .filter(([key]) => !metadata.has(key))
      .map(([key, item]) => [key, semantic(item)]));
  }
  return value;
}
const names = (await fs.readdir(before)).filter(name => name.endsWith('.js')).sort();
assert.deepEqual((await fs.readdir(after)).filter(name => name.endsWith('.js')).sort(), names);
for (const name of names) {
  const oldCode = await fs.readFile(path.join(before, name), 'utf8');
  const newCode = await fs.readFile(path.join(after, name), 'utf8');
  const oldAst = await prettier.__debug.parse(oldCode, { parser: 'babel' });
  const newAst = await prettier.__debug.parse(newCode, { parser: 'babel' });
  assert.deepEqual(semantic(newAst.ast), semantic(oldAst.ast), name);
}
console.log(`PASS: ${names.length} semantic ASTs match (Prettier ${prettier.version})`);
console.log('Position/comment/formatting metadata excluded; template raw/cooked values retained.');
