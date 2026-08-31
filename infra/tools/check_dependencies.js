'use strict';

const fs = require('fs/promises');
const path = require('path');
const net = require('net');
const { exec } = require('child_process');
const { promisify } = require('util');

const execAsync = promisify(exec);

const DEFAULT_CONFIG = {
  workspaceRoot: process.cwd(),
  logDir: 'logs',
  logFile: 'check_dependencies.jsonl',
  ports: [5000, 3000],
  commands: {
    node: 'node --version',
    npm: 'npm --version',
    python: 'python --version',
    pip: 'pip --version'
  }
};

function normalizeError(error) {
  return {
    message: error?.message || String(error),
    code: error?.code || null
  };
}

class DependencyChecker {
  constructor(config = {}) {
    this.config = {
      ...DEFAULT_CONFIG,
      ...config,
      ports: Array.isArray(config.ports) ? config.ports : DEFAULT_CONFIG.ports,
      commands: {
        ...DEFAULT_CONFIG.commands,
        ...(config.commands || {})
      }
    };

    this.logPath = path.resolve(this.config.workspaceRoot, this.config.logDir, this.config.logFile);
  }

  async log(level, event, data = null) {
    const line = {
      timestamp: new Date().toISOString(),
      level,
      event,
      data
    };

    try {
      await fs.mkdir(path.dirname(this.logPath), { recursive: true });
      await fs.appendFile(this.logPath, `${JSON.stringify(line)}\n`, 'utf-8');
    } catch (_error) {
      // best-effort logging
    }
  }

  async checkCommand(name, command) {
    const startedAt = Date.now();

    try {
      const { stdout, stderr } = await execAsync(command, {
        cwd: this.config.workspaceRoot,
        windowsHide: true,
        timeout: 15000
      });

      const output = String(stdout || stderr || '').trim();
      const result = {
        ok: true,
        name,
        command,
        output,
        durationMs: Date.now() - startedAt
      };

      await this.log('info', 'command_check_success', result);
      return result;
    } catch (error) {
      const result = {
        ok: false,
        name,
        command,
        output: null,
        error: normalizeError(error),
        durationMs: Date.now() - startedAt
      };

      await this.log('warning', 'command_check_failed', result);
      return result;
    }
  }

  async isPortFree(port) {
    const startedAt = Date.now();

    return new Promise((resolve) => {
      const server = net.createServer();

      server.once('error', async (error) => {
        const result = {
          ok: false,
          port,
          free: false,
          error: normalizeError(error),
          durationMs: Date.now() - startedAt
        };

        await this.log('warning', 'port_check_in_use', result);
        resolve(result);
      });

      server.once('listening', async () => {
        server.close(async () => {
          const result = {
            ok: true,
            port,
            free: true,
            error: null,
            durationMs: Date.now() - startedAt
          };

          await this.log('info', 'port_check_free', result);
          resolve(result);
        });
      });

      server.listen(port, '127.0.0.1');
    });
  }

  async run() {
    await this.log('info', 'dependency_check_started', {
      workspaceRoot: this.config.workspaceRoot
    });

    const commandChecks = [];
    for (const [name, command] of Object.entries(this.config.commands)) {
      commandChecks.push(await this.checkCommand(name, command));
    }

    const portChecks = [];
    for (const port of this.config.ports) {
      portChecks.push(await this.isPortFree(Number(port)));
    }

    const allCommandsOk = commandChecks.every((item) => item.ok);
    const allPortsFree = portChecks.every((item) => item.free);

    const report = {
      ok: allCommandsOk && allPortsFree,
      timestamp: new Date().toISOString(),
      summary: {
        commandsOk: allCommandsOk,
        portsOk: allPortsFree,
        totalCommands: commandChecks.length,
        totalPorts: portChecks.length
      },
      checks: {
        commands: commandChecks,
        ports: portChecks
      }
    };

    await this.log(report.ok ? 'info' : 'warning', 'dependency_check_finished', report.summary);
    return report;
  }
}

async function checkDependencies(config = {}) {
  const checker = new DependencyChecker(config);
  return checker.run();
}

if (require.main === module) {
  checkDependencies()
    .then((report) => {
      // eslint-disable-next-line no-console
      console.log(JSON.stringify(report, null, 2));
      process.exit(report.ok ? 0 : 1);
    })
    .catch((error) => {
      // eslint-disable-next-line no-console
      console.error(JSON.stringify({ ok: false, error: normalizeError(error) }, null, 2));
      process.exit(1);
    });
}

module.exports = {
  DependencyChecker,
  checkDependencies,
  DEFAULT_CONFIG
};
