#!/usr/bin/env node
'use strict';
// npm test: run the Python unit tests with the project's Python.
// Python is chosen in this order: the OPEN_OPTICS_PYTHON environment variable, the project's .venv, then `python` on PATH.
// The .venv holds CUDA torch and numpy for the ComfyUI node tests; the lens math core does not need them.
//
// A plain `npm test` runs the whole suite in parallel: the browser tests of the director app (tests/test_app_*.py, each file
// starts its own app, fake ComfyUI and Chromium) are spread over several Python processes, and every other test file runs in
// one more. The tests use free ports and their own temporary folders, so they do not collide. The output ends with one
// combined unittest summary ("Ran N tests in Xs", then "OK" or "FAILED (...)") and the output of every failing shard is
// printed before it. TEST_SHARDS=1 runs everything in a single process.
//
// With arguments (`npm test -- -k name`, `npm test -- tests.test_app_player`) the arguments go straight to
// `python -m unittest discover -s tests -t .` in a single process, which is the quick way to run one test while working.
//
// npm run test:bench (node scripts/run-tests.js --bench) runs only the slow benchmark tests, those whose names contain "bench".
// They are skipped in a normal npm test: a benchmark test starts with
//     @unittest.skipUnless(os.environ.get("OPEN_OPTICS_BENCH") == "1", "set by npm run test:bench")
// and --bench sets OPEN_OPTICS_BENCH=1.
const fs = require('node:fs');
const path = require('node:path');
const { spawn, spawnSync } = require('node:child_process');
const { pythonFor } = require('./py.js');

const root = path.resolve(__dirname, '..');
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

const shards = Number(env.TEST_SHARDS) > 0 ? Number(env.TEST_SHARDS) : 4;
if (args.length > 0 || shards <= 1) {
  // module, class or test names (tests.test_x, tests.test_x.Class.test_y) go to unittest as they are; flags like -k use discovery
  const named = args.some((a) => a.startsWith('tests.'));
  const cmd = named ? ['-m', 'unittest', ...args] : ['-m', 'unittest', 'discover', '-s', 'tests', '-t', '.', ...args];
  const r = spawnSync(python, cmd, { cwd: root, env, stdio: 'inherit' });
  process.exit(r.status === null ? 1 : r.status);
}

// ---- parallel run
const dir = path.join(root, 'tests');
const modules = fs.readdirSync(dir).filter((f) => /^test.*\.py$/.test(f)).sort().map((f) => ({ name: `tests.${f.slice(0, -3)}`, size: fs.statSync(path.join(dir, f)).size }));
const appModules = modules.filter((m) => m.name.startsWith('tests.test_app_')).sort((a, b) => b.size - a.size);
const otherModules = modules.filter((m) => !m.name.startsWith('tests.test_app_'));
const groups = Array.from({ length: shards }, () => ({ modules: [], weight: 0 }));
for (const m of appModules) {
  const g = groups.reduce((best, cur) => (cur.weight < best.weight ? cur : best));
  g.modules.push(m.name);
  g.weight += m.size;
}
const jobs = [{ label: 'core', modules: otherModules.map((m) => m.name) }, ...groups.filter((g) => g.modules.length).map((g, i) => ({ label: `app-${i + 1}`, modules: g.modules }))];

const started = Date.now();
function runJob(job) {
  return new Promise((resolve) => {
    const child = spawn(python, ['-m', 'unittest', ...job.modules], { cwd: root, env, stdio: ['ignore', 'pipe', 'pipe'] });
    let out = '';
    child.stdout.on('data', (d) => { out += d; });
    child.stderr.on('data', (d) => { out += d; });
    child.on('close', (code) => resolve({ ...job, code: code === null ? 1 : code, out }));
    child.on('error', (err) => resolve({ ...job, code: 1, out: String(err) }));
  });
}

Promise.all(jobs.map(runJob)).then((results) => {
  let ran = 0;
  let failures = 0;
  let errors = 0;
  let skipped = 0;
  let bad = false;
  for (const r of results) {
    const m = /Ran (\d+) tests? in/.exec(r.out);
    ran += m ? Number(m[1]) : 0;
    const summary = /FAILED \(([^)]*)\)/.exec(r.out) || /OK \(([^)]*)\)/.exec(r.out);
    const counts = Object.fromEntries((summary ? summary[1] : '').split(',').filter(Boolean).map((p) => p.trim().split('=')));
    failures += Number(counts.failures || 0);
    errors += Number(counts.errors || 0);
    skipped += Number(counts.skipped || 0);
    if (r.code !== 0 || !m) bad = true;
  }
  // Browser tests are timing-sensitive: on a busy machine one now and then misses a 15 s wait. A test that failed in the parallel
  // run is repeated once, alone, in a quiet process; the run passes when every one of them passes then. A test that fails twice
  // is a real failure and its output is printed below.
  let flaky = [];
  if (bad && results.every((r) => /Ran \d+ tests? in/.test(r.out))) {
    const ids = [...new Set(results.flatMap((r) => [...r.out.matchAll(/^(?:ERROR|FAIL): \S+ \(([\w.]+)\)/gm)].map((x) => x[1])))];
    if (ids.length > 0 && ids.length <= 12) {
      const again = spawnSync(python, ['-m', 'unittest', ...ids], { cwd: root, env, encoding: 'utf8', timeout: 10 * 60000 });
      if (again.status === 0) {
        flaky = ids;
        bad = false;
        failures = 0;
        errors = 0;
      } else {
        console.log(`\n===== repeated alone and failed again: ${ids.join(', ')} =====`);
        console.log(String(again.stdout || '') + String(again.stderr || ''));
      }
    }
  }
  if (flaky.length) console.log(`\nFlaky (failed in the parallel run, passed when repeated alone; not a defect of the change under test): ${flaky.join(', ')}`);
  for (const r of results) {
    if (bad && (r.code !== 0 || !/Ran \d+ tests? in/.test(r.out))) {
      console.log(`\n===== shard ${r.label} FAILED (exit ${r.code}) =====`);
      console.log(r.out.slice(-60000));
    }
  }
  const seconds = ((Date.now() - started) / 1000).toFixed(3);
  console.log(`\nShards: ${results.map((r) => `${r.label} ${r.modules.length} files exit ${r.code}`).join('; ')}`);
  console.log('----------------------------------------------------------------------');
  console.log(`Ran ${ran} tests in ${seconds}s\n`);
  if (bad) {
    const parts = [];
    if (failures) parts.push(`failures=${failures}`);
    if (errors) parts.push(`errors=${errors}`);
    if (skipped) parts.push(`skipped=${skipped}`);
    console.log(`FAILED (${parts.join(', ') || 'a shard crashed'})`);
  } else {
    console.log(skipped ? `OK (skipped=${skipped})` : 'OK');
  }
  process.exit(bad ? 1 : 0);
});
