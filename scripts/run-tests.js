#!/usr/bin/env node
'use strict';
// npm test: run the Python unit tests with the project's Python.
// Python is chosen in this order: the OPEN_OPTICS_PYTHON environment variable, the project's .venv, then `python` on PATH.
// The .venv holds CUDA torch and numpy for the ComfyUI node tests; the lens math core does not need them.
//
// npm run test:bench (node scripts/run-tests.js --bench) runs only the slow benchmark tests, those whose names contain "bench".
// They are skipped in a normal npm test: a benchmark test starts with
//     @unittest.skipUnless(os.environ.get("OPEN_OPTICS_BENCH") == "1", "set by npm run test:bench")
// and --bench sets OPEN_OPTICS_BENCH=1.
const { spawnSync } = require('node:child_process');
const { pythonFor } = require('./py.js');

const root = require('node:path').resolve(__dirname, '..');
const { python, error } = pythonFor(root);
if (error) {
  console.error(error);
  process.exit(2);
}
const args = process.argv.slice(2);
const env = { ...process.env };
const bench = args.indexOf('--bench');
if (bench >= 0) {
  args.splice(bench, 1, '-k', 'bench');
  env.OPEN_OPTICS_BENCH = '1';
}
const r = spawnSync(python, ['-m', 'unittest', 'discover', '-s', 'tests', '-t', '.', ...args], { cwd: root, env, stdio: 'inherit' });
process.exit(r.status === null ? 1 : r.status);
