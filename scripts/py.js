'use strict';
// Which Python the project uses: OPEN_OPTICS_PYTHON (must exist if set), then <root>/.venv, then `python` on PATH.
const fs = require('node:fs');
const path = require('node:path');

function pythonFor(root, env = process.env) {
  if (env.OPEN_OPTICS_PYTHON) {
    if (!fs.existsSync(env.OPEN_OPTICS_PYTHON)) return { error: `OPEN_OPTICS_PYTHON points to a file that does not exist: ${env.OPEN_OPTICS_PYTHON}` };
    return { python: env.OPEN_OPTICS_PYTHON };
  }
  for (const rel of [path.join('.venv', 'Scripts', 'python.exe'), path.join('.venv', 'bin', 'python')]) {
    const p = path.join(root, rel);
    if (fs.existsSync(p)) return { python: p };
  }
  return { python: 'python' };
}

module.exports = { pythonFor };
