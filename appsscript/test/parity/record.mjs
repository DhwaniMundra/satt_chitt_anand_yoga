// Re-records recorded.json from this backend, after a deliberate change to the API's answers: run it, read the diff of
// recorded.json, and commit the two together. One answer per line, spaced as ", " and ": ", so the diff shows what
// changed.
//
//   node appsscript/test/parity/record.mjs
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { answers, HERE } from './run.mjs';

/** The answer as one line; login tokens and the step's random values written as "<varies>". */
function spaced(value, skip) {
  if (Array.isArray(value)) return '[' + value.map((v) => spaced(v, skip)).join(', ') + ']';
  if (value && typeof value === 'object') {
    return '{' + Object.entries(value).map(([k, v]) =>
      JSON.stringify(k) + ': ' + (k === 'token' || skip.includes(k) ? '"<varies>"' : spaced(v, skip))).join(', ') + '}';
  }
  return JSON.stringify(value);
}

const lines = answers().map(({ answer, skip }) => spaced(answer, skip));
writeFileSync(join(HERE, 'recorded.json'), '[\n' + lines.join(',\n') + '\n]\n');
console.log(lines.length + ' answers recorded');
