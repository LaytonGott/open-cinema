#!/usr/bin/env node
'use strict';
// node scripts/run-app.js [options]: run the director web app (`python -m app`) with the project's Python (see py.js).
const { spawnSync } = require('node:child_process');
const path = require('node:path');
const { pythonFor } = require('./py.js');

const root = path.resolve(__dirname, '..');
const { python, error } = pythonFor(root);
if (error) {
  console.error(error);
  process.exit(2);
}
const r = spawnSync(python, ['-m', 'app', ...process.argv.slice(2)], { cwd: root, stdio: 'inherit' });
process.exit(r.status === null ? 1 : r.status);
