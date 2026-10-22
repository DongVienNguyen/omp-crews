#!/usr/bin/env node
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { resolveRuntime } from '../runtime-paths.mjs';

try {
  const runtime = resolveRuntime(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'));
  const child = spawn(runtime.python, [path.join(runtime.packageRoot, 'omp_server.py')], {
    shell: false, windowsHide: true, stdio: 'inherit', cwd: runtime.packageRoot,
    env: { ...process.env, CREWS_OMP_HOME: runtime.state, CREWS_OMP_AGENT_DIR: runtime.agentDir,
      PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' },
  });
  const handlers = new Map(['SIGINT', 'SIGTERM'].map(signal => {
    const handler = () => { if (!child.killed) child.kill(signal); };
    process.on(signal, handler);
    return [signal, handler];
  }));
  child.once('error', error => { console.error(`crews-omp: ${error.message}`); process.exitCode = 1; });
  child.once('exit', (code, signal) => {
    for (const [name, handler] of handlers) process.removeListener(name, handler);
    if (signal) { process.kill(process.pid, signal); return; }
    process.exitCode = code ?? 1;
  });
} catch (error) {
  console.error(`crews-omp: ${error.message}`);
  process.exitCode = 1;
}
