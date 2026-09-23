import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { once } from 'node:events';
import { mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const clientDir = path.dirname(fileURLToPath(import.meta.url));
const serverDir = path.resolve(clientDir, '..', 'server');
const options = {
  timeout: 10_000,
  skip: process.platform === 'win32' && 'Fake executables use POSIX shebangs',
};

async function fixture(t, extraEnv = {}) {
  const directory = path.join(clientDir, `.launcher-fixture-${randomUUID()}`);
  await mkdir(directory, { recursive: true });
  const python = path.join(directory, 'python with spaces; exit 99.cjs');
  const log = path.join(directory, 'calls.jsonl');
  t.after(async () => {
    const entries = await readFile(log, 'utf8').catch(() => '');
    for (const entry of entries.trim().split('\n').filter(Boolean).map(JSON.parse)) {
      if (entry.event === 'server') {
        try { process.kill(entry.pid, 'SIGKILL'); } catch (error) {
          if (error.code !== 'ESRCH') throw error;
        }
      }
    }
    await rm(directory, { recursive: true, force: true });
  });
  await writeFile(python, `#!${process.execPath}
const fs = require('node:fs');
const record = (event) => fs.appendFileSync(process.env.LAUNCHER_TEST_LOG,
  JSON.stringify({ event, args: process.argv.slice(2), cwd: process.cwd(),
    database: process.env.DATABASE_PATH, pid: process.pid }) + '\\n');
const seeding = process.argv[2] === 'utils/seed_test_database.py';
record(seeding ? 'seed' : 'server');
if (seeding) {
  if (process.env.LAUNCHER_TEST_REMOVE === '1') fs.unlinkSync(__filename);
  if (process.env.LAUNCHER_TEST_SEED_SIGNAL) process.kill(process.pid, process.env.LAUNCHER_TEST_SEED_SIGNAL);
  process.exit(Number(process.env.LAUNCHER_TEST_SEED_EXIT || 0));
}
if (process.env.LAUNCHER_TEST_SIGNAL) process.kill(process.pid, process.env.LAUNCHER_TEST_SIGNAL);
else if (process.env.LAUNCHER_TEST_WAIT === '1') {
  for (const signal of ['SIGINT', 'SIGTERM']) {
    process.on(signal, () => {
      record(signal);
      process.removeAllListeners(signal);
      process.kill(process.pid, signal);
    });
  }
  setInterval(() => {}, 1000);
  console.log('LAUNCHER_TEST_READY');
} else process.exit(Number(process.env.LAUNCHER_TEST_EXIT || 0));
`, { mode: 0o755 });
  const env = {
    ...process.env,
    PYTHON: python,
    DATABASE_PATH: path.join(directory, 'isolated database.db'),
    LAUNCHER_TEST_LOG: log,
    ...extraEnv,
  };
  if (extraEnv.DATABASE_PATH === undefined && 'DATABASE_PATH' in extraEnv) {
    delete env.DATABASE_PATH;
  }
  return {
    env,
    calls: async () => (await readFile(log, 'utf8')).trim().split('\n').map(JSON.parse),
  };
}

function launch(t, env) {
  const child = spawn(process.execPath, ['start-test-server.js'], {
    cwd: clientDir,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let output = '';
  child.stdout.on('data', (data) => { output += data; });
  child.stderr.on('data', (data) => { output += data; });
  const closed = once(child, 'close');
  t.after(() => {
    if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL');
  });
  return { child, closed, output: () => output };
}

test('uses literal executable paths and the same database for seeding and serving', options, async (t) => {
  const setup = await fixture(t, { LAUNCHER_TEST_EXIT: '23' });
  const running = launch(t, setup.env);
  assert.deepEqual(await running.closed, [23, null], running.output());
  const calls = await setup.calls();
  assert.equal(calls.length, 2);
  assert.deepEqual(calls[0].args, ['utils/seed_test_database.py']);
  assert.deepEqual(calls[1].args, [
    '-m', 'flask', '--app', 'app', 'run', '--port', '5100', '--no-reload', '--no-debugger',
  ]);
  for (const call of calls) {
    assert.equal(call.cwd, serverDir);
    assert.equal(call.database, setup.env.DATABASE_PATH);
  }
});

test('keeps the default database separate from the shelter database', options, async (t) => {
  const setup = await fixture(t, { DATABASE_PATH: undefined });
  const running = launch(t, setup.env);
  assert.deepEqual(await running.closed, [0, null], running.output());
  for (const call of await setup.calls()) {
    assert.equal(call.database, path.join(serverDir, 'e2e_test_dogshelter.db'));
  }
});

test('does not launch Flask after a failed seed', options, async (t) => {
  const setup = await fixture(t, { LAUNCHER_TEST_SEED_EXIT: '17' });
  const running = launch(t, setup.env);
  assert.deepEqual(await running.closed, [17, null], running.output());
  assert.equal((await setup.calls()).length, 1);
  assert.match(running.output(), /Failed to seed the test database/);
});

test('does not launch Flask after a seed terminated by a signal', options, async (t) => {
  const setup = await fixture(t, { LAUNCHER_TEST_SEED_SIGNAL: 'SIGTERM' });
  const running = launch(t, setup.env);
  assert.deepEqual(await running.closed, [null, 'SIGTERM'], running.output());
  assert.equal((await setup.calls()).length, 1);
});

test('reports a missing Python executable', options, async (t) => {
  const setup = await fixture(t);
  const running = launch(t, { ...setup.env, PYTHON: `${setup.env.PYTHON}-missing` });
  assert.deepEqual(await running.closed, [1, null], running.output());
  assert.match(running.output(), /Failed to seed the test database.*ENOENT/);
});

test('reports a spawn failure after successful seeding', options, async (t) => {
  const setup = await fixture(t, { LAUNCHER_TEST_REMOVE: '1' });
  const running = launch(t, setup.env);
  assert.deepEqual(await running.closed, [1, null], running.output());
  assert.equal((await setup.calls()).length, 1);
  assert.match(running.output(), /Failed to start the test server.*ENOENT/);
});

test('preserves a server exit caused by a signal', options, async (t) => {
  const setup = await fixture(t, { LAUNCHER_TEST_SIGNAL: 'SIGTERM' });
  const running = launch(t, setup.env);
  assert.deepEqual(await running.closed, [null, 'SIGTERM'], running.output());
});

for (const signal of ['SIGINT', 'SIGTERM']) {
  test(`forwards ${signal} and leaves no server process behind`, options, async (t) => {
    const setup = await fixture(t, { LAUNCHER_TEST_WAIT: '1' });
    const running = launch(t, setup.env);
    for await (const data of running.child.stdout) {
      if (data.toString().includes('LAUNCHER_TEST_READY')) break;
    }
    running.child.kill(signal);
    assert.deepEqual(await running.closed, [null, signal], running.output());
    const calls = await setup.calls();
    assert.equal(calls.at(-1).event, signal);
    const serverPid = calls.find((call) => call.event === 'server').pid;
    assert.throws(() => process.kill(serverPid, 0), { code: 'ESRCH' });
  });
}
