#!/usr/bin/env node
'use strict';
// npm test: run the Python unit tests with the project's Python.
// Python is chosen in this order: the OPEN_OPTICS_PYTHON environment variable, the project's .venv, then `python` on PATH.
// The .venv holds CPU-only torch and numpy for the ComfyUI node tests; the lens math core does not need them.
const { spawnSync } = require('node:child_process');
const { pythonFor } = require('./py.js');

const root = require('node:path').resolve(__dirname, '..');
const { python, error } = pythonFor(root);
if (error) {
  console.error(error);
  process.exit(2);
}
const r = spawnSync(python, ['-m', 'unittest', 'discover', '-s', 'tests', '-t', '.', ...process.argv.slice(2)], { cwd: root, stdio: 'inherit' });
process.exit(r.status === null ? 1 : r.status);
