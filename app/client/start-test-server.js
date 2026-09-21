// Cross-platform script to seed the test database and start the Flask server
import { execFileSync, spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const serverDir = path.resolve(__dirname, '..', 'server');
const testDbPath = process.env.DATABASE_PATH || path.join(serverDir, 'e2e_test_dogshelter.db');
const python = process.env.PYTHON || (process.platform === 'win32' ? 'py' : 'python3');
const env = { ...process.env, DATABASE_PATH: testDbPath };

// Seed the test database
try {
  execFileSync(python, ['utils/seed_test_database.py'], {
    cwd: serverDir,
    env,
    stdio: 'inherit',
  });
} catch (error) {
  console.error('Failed to seed the test database:', error.message);
  if (error.signal) {
    process.kill(process.pid, error.signal);
  } else {
    process.exit(error.status ?? 1);
  }
}

// Avoid app.py's debug reloader so the launcher owns the only server process.
const server = spawn(python, [
  '-m', 'flask', '--app', 'app', 'run', '--port', '5100', '--no-reload', '--no-debugger',
], {
  cwd: serverDir,
  env,
  stdio: 'inherit',
});

const forwardSignal = (signal) => server.kill(signal);
process.on('SIGINT', forwardSignal);
process.on('SIGTERM', forwardSignal);

server.once('error', (error) => {
  console.error('Failed to start the test server:', error.message);
  process.exitCode = 1;
});

server.once('close', (code, signal) => {
  process.off('SIGINT', forwardSignal);
  process.off('SIGTERM', forwardSignal);
  if (signal) {
    process.kill(process.pid, signal);
  } else {
    process.exitCode = process.exitCode ?? code ?? 1;
  }
});
