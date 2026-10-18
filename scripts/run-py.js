#!/usr/bin/env node
'use strict';
// node scripts/run-py.js <script.py> [args]: run one of the repository's Python scripts with the project's Python (see py.js).
// The goal checks in goals.md use it, because the loop's check commands may only be `npm test` or `node <file>`.
const { spawnSync } = require('node:child_process');
const path = require('node:path');
const { pythonFor } = require('./py.js');

const root = path.resolve(__dirname, '..');
const [script, ...args] = process.argv.slice(2);
if (!script) {
  console.error('usage: node scripts/run-py.js <script.py> [args]');
  process.exit(2);
}
const { python, error } = pythonFor(root);
if (error) {
  console.error(error);
  process.exit(2);
}
const r = spawnSync(python, [path.resolve(root, script), ...args], { cwd: root, stdio: 'inherit' });
process.exit(r.status === null ? 1 : r.status);
