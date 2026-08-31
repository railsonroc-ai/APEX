'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');
const net = require('net');
const http = require('http');
const { builtinModules } = require('module');
const { spawnSync } = require('child_process');

const PROJECT_ROOT = __dirname;
const LOG_DIR = path.join(PROJECT_ROOT, 'logs');
const LOG_FILE = path.join(LOG_DIR, 'apex_diagnostic.log');
const REPORT_FILE = path.join(LOG_DIR, 'apex_diagnostic_report_latest.json');

const JS_EXTENSIONS = new Set(['.js', '.cjs', '.mjs']);
const PY_EXTENSIONS = new Set(['.py']);
const IGNORE_DIRS = new Set([
	'.git',
	'.venv',
	'node_modules',
	'__pycache__',
	'dist',
	'build',
	'logs'
]);

function ensureLogDir() {
	if (!fs.existsSync(LOG_DIR)) {
		fs.mkdirSync(LOG_DIR, { recursive: true });
	}
}

function log(level, message, data = null) {
	try {
		ensureLogDir();
		const entry = {
			timestamp: new Date().toISOString(),
			level,
			message,
			data
		};
		fs.appendFileSync(LOG_FILE, `${JSON.stringify(entry)}\n`, 'utf8');
	} catch (_error) {
		// best-effort logging
	}
}

function saveLatestReport(report) {
	try {
		ensureLogDir();
		fs.writeFileSync(REPORT_FILE, JSON.stringify(report, null, 2), 'utf8');
	} catch (error) {
		log('warning', 'failed to persist diagnostic report', { error: error.message || String(error) });
	}
}

function runCommand(command, args = [], options = {}) {
	return spawnSync(command, args, {
		encoding: 'utf8',
		timeout: 15000,
		...options
	});
}

function commandAvailable(command, args = ['--version']) {
	const result = runCommand(command, args);
	return result && result.status === 0;
}

function detectNodeLauncher() {
	if (commandAvailable('node', ['--version'])) {
		return {
			command: 'node',
			prefix: [],
			mode: 'node'
		};
	}

	if (commandAvailable('npx', ['node', '--version'])) {
		return {
			command: 'npx',
			prefix: ['node'],
			mode: 'npx'
		};
	}

	return null;
}

function runNodeCommand(nodeLauncher, args = [], options = {}) {
	if (!nodeLauncher) {
		return {
			status: null,
			stderr: 'Nenhum launcher Node disponível (node ou npx node).'
		};
	}

	return runCommand(nodeLauncher.command, [...nodeLauncher.prefix, ...args], options);
}

function isFile(filePath) {
	try {
		return fs.statSync(filePath).isFile();
	} catch (_error) {
		return false;
	}
}

function isDirectory(dirPath) {
	try {
		return fs.statSync(dirPath).isDirectory();
	} catch (_error) {
		return false;
	}
}

function safeReadJson(jsonPath) {
	try {
		const raw = fs.readFileSync(jsonPath, 'utf8');
		return JSON.parse(raw);
	} catch (error) {
		return { __error: error.message || String(error) };
	}
}

function scanProjectFiles(rootDir) {
	const allFiles = [];

	function walk(currentDir) {
		let entries = [];
		try {
			entries = fs.readdirSync(currentDir, { withFileTypes: true });
		} catch (error) {
			log('warning', 'failed to read directory during scan', { currentDir, error: error.message || String(error) });
			return;
		}

		for (const entry of entries) {
			const fullPath = path.join(currentDir, entry.name);

			if (entry.isDirectory()) {
				if (IGNORE_DIRS.has(entry.name)) {
					continue;
				}
				walk(fullPath);
				continue;
			}

			if (entry.isFile()) {
				allFiles.push(fullPath);
			}
		}
	}

	walk(rootDir);
	return allFiles;
}

function getPythonCommand() {
	const candidates = [
		['python'],
		['py', '-3'],
		['py']
	];

	for (const candidate of candidates) {
		const [cmd, ...prefix] = candidate;
		const result = runCommand(cmd, [...prefix, '--version']);
		if (result.status === 0) {
			return {
				cmd,
				prefix,
				version: (result.stdout || result.stderr || '').trim()
			};
		}
	}

	return null;
}

function checkPortOccupied(port) {
	return new Promise((resolve) => {
		const server = net.createServer();
		server.unref();

		server.once('error', (error) => {
			if (error && error.code === 'EADDRINUSE') {
				resolve(true);
			} else {
				resolve(false);
			}
		});

		server.once('listening', () => {
			server.close(() => resolve(false));
		});

		server.listen(port, '127.0.0.1');
	});
}

function httpProbe(url, timeoutMs = 2500) {
	return new Promise((resolve) => {
		const req = http.get(url, { timeout: timeoutMs }, (res) => {
			const statusCode = res.statusCode || 0;
			res.resume();
			resolve({ ok: statusCode > 0 && statusCode < 500, statusCode });
		});

		req.on('timeout', () => {
			req.destroy(new Error('timeout'));
		});

		req.on('error', (error) => {
			resolve({ ok: false, error: error.message || String(error) });
		});
	});
}

function resolveRelativeImport(baseFile, spec) {
	const absoluteBase = path.resolve(path.dirname(baseFile), spec);
	const candidates = [
		absoluteBase,
		`${absoluteBase}.js`,
		`${absoluteBase}.cjs`,
		`${absoluteBase}.mjs`,
		`${absoluteBase}.json`,
		path.join(absoluteBase, 'index.js'),
		path.join(absoluteBase, 'index.cjs'),
		path.join(absoluteBase, 'index.mjs')
	];

	return candidates.some((filePath) => isFile(filePath));
}

function parseJsImports(content) {
	const imports = [];

	const requireRegex = /require\s*\(\s*['"]([^'"]+)['"]\s*\)/g;
	const fromImportRegex = /import\s+[^'"\n]+\s+from\s+['"]([^'"]+)['"]/g;
	const bareImportRegex = /import\s*\(\s*['"]([^'"]+)['"]\s*\)/g;
	const sideEffectImportRegex = /import\s+['"]([^'"]+)['"]/g;

	for (const regex of [requireRegex, fromImportRegex, bareImportRegex, sideEffectImportRegex]) {
		let match;
		while ((match = regex.exec(content)) !== null) {
			imports.push(match[1]);
		}
	}

	return imports;
}

function parsePythonImports(content) {
	const modules = new Set();
	const lines = content.split(/\r?\n/);

	for (const line of lines) {
		const trimmed = line.trim();
		if (!trimmed || trimmed.startsWith('#')) {
			continue;
		}

		let match = trimmed.match(/^import\s+(.+)$/);
		if (match) {
			const chunks = match[1].split(',');
			for (const chunk of chunks) {
				const first = chunk.trim().split(/\s+/)[0].split('.')[0];
				if (first) {
					modules.add(first);
				}
			}
			continue;
		}

		match = trimmed.match(/^from\s+([a-zA-Z0-9_\.]+)\s+import\s+/);
		if (match) {
			const first = match[1].split('.')[0];
			if (first && !first.startsWith('.')) {
				modules.add(first);
			}
		}
	}

	return Array.from(modules);
}

function topLevelPackageName(moduleName) {
	if (!moduleName) {
		return '';
	}
	if (moduleName.startsWith('@')) {
		const parts = moduleName.split('/');
		return `${parts[0] || ''}/${parts[1] || ''}`;
	}
	return moduleName.split('/')[0];
}

async function runDiagnostics(options = {}) {
	const startedAt = new Date();
	const full = Boolean(options.full);
	const nodeLauncher = detectNodeLauncher();

	const report = {
		ok: true,
		errors: [],
		warnings: [],
		suggestions: [],
		environmentInfo: {
			projectRoot: PROJECT_ROOT,
			timestamp: startedAt.toISOString(),
			os: `${os.platform()} ${os.release()}`,
			arch: os.arch(),
			nodeVersion: process.version,
			nodeLauncher: nodeLauncher ? nodeLauncher.mode : 'unavailable',
			pythonVersion: null,
			electronVersion: null,
			scan: {
				full,
				mode: full ? 'full' : 'quick'
			}
		}
	};

	const addError = (message) => {
		if (!report.errors.includes(message)) {
			report.errors.push(message);
			report.ok = false;
		}
	};

	const addWarning = (message) => {
		if (!report.warnings.includes(message)) {
			report.warnings.push(message);
		}
	};

	const addSuggestion = (message) => {
		if (!report.suggestions.includes(message)) {
			report.suggestions.push(message);
		}
	};

	if (!nodeLauncher) {
		addError('Node.js indisponível no PATH e fallback `npx node` também falhou.');
		addSuggestion('Instale Node.js ou execute o diagnóstico com `npx node apex_diagnostic.js --full`.');
	}

	log('info', 'diagnostics started', { full });

	const packageJsonPath = path.join(PROJECT_ROOT, 'package.json');
	const packageJson = safeReadJson(packageJsonPath);
	const packageJsonAvailable = !packageJson.__error;

	if (!packageJsonAvailable) {
		addError(`package.json inválido ou não encontrado: ${packageJson.__error}`);
	}

	const dependencies = packageJsonAvailable ? packageJson.dependencies || {} : {};
	const devDependencies = packageJsonAvailable ? packageJson.devDependencies || {} : {};
	const allNodeDeps = new Set([
		...Object.keys(dependencies),
		...Object.keys(devDependencies)
	]);

	const pythonCmd = getPythonCommand();
	if (pythonCmd) {
		report.environmentInfo.pythonVersion = pythonCmd.version;
	} else {
		addError('Python não encontrado no ambiente (python/py).');
		addSuggestion('Instale Python 3 e garanta que o comando `python` ou `py` esteja disponível no PATH.');
	}

	const electronDepVersion = dependencies.electron || devDependencies.electron || null;
	report.environmentInfo.electronVersion = electronDepVersion;
	if (!electronDepVersion) {
		addError('Dependência `electron` ausente em package.json.');
	}

	const requiredDeps = ['electron', 'electron-builder'];
	for (const dep of requiredDeps) {
		if (!allNodeDeps.has(dep)) {
			addError(`Dependência obrigatória ausente em package.json: ${dep}`);
		}

		const depPath = path.join(PROJECT_ROOT, 'node_modules', dep);
		if (!isDirectory(depPath)) {
			addWarning(`Dependência Node não instalada em node_modules: ${dep}`);
			addSuggestion('Execute `npm install` para instalar dependências locais.');
		}
	}

	const essentialFiles = [
		'package.json',
		'electron_main.js',
		'app.py',
		'apex_server.py',
		'local_agent_server.js',
		'config.json'
	];

	for (const relativePath of essentialFiles) {
		const absolutePath = path.join(PROJECT_ROOT, relativePath);
		if (!isFile(absolutePath)) {
			addError(`Arquivo essencial ausente: ${relativePath}`);
		}
	}

	const scannedFiles = scanProjectFiles(PROJECT_ROOT);
	const jsFiles = scannedFiles.filter((filePath) => JS_EXTENSIONS.has(path.extname(filePath).toLowerCase()));
	const pyFiles = scannedFiles.filter((filePath) => PY_EXTENSIONS.has(path.extname(filePath).toLowerCase()));
	report.environmentInfo.scan.totalFiles = scannedFiles.length;
	report.environmentInfo.scan.jsFiles = jsFiles.length;
	report.environmentInfo.scan.pyFiles = pyFiles.length;

	const nodeBuiltins = new Set([...builtinModules, ...builtinModules.map((item) => `node:${item}`)]);
	const unresolvedJsImports = [];

	for (const jsFile of jsFiles) {
		const syntaxCheck = runNodeCommand(nodeLauncher, ['--check', jsFile]);
		if (syntaxCheck.status !== 0) {
			addError(`Erro de sintaxe JS em ${path.relative(PROJECT_ROOT, jsFile)}: ${(syntaxCheck.stderr || '').trim() || 'invalid syntax'}`);
		}

		let content = '';
		try {
			content = fs.readFileSync(jsFile, 'utf8');
		} catch (error) {
			addWarning(`Não foi possível ler ${path.relative(PROJECT_ROOT, jsFile)}: ${error.message || String(error)}`);
			continue;
		}

		const imports = parseJsImports(content);
		for (const importSpec of imports) {
			if (importSpec.startsWith('.') || importSpec.startsWith('/')) {
				const ok = resolveRelativeImport(jsFile, importSpec);
				if (!ok) {
					unresolvedJsImports.push(`${path.relative(PROJECT_ROOT, jsFile)} -> ${importSpec}`);
				}
				continue;
			}

			if (nodeBuiltins.has(importSpec)) {
				continue;
			}

			const packageName = topLevelPackageName(importSpec);
			if (!allNodeDeps.has(packageName)) {
				unresolvedJsImports.push(`${path.relative(PROJECT_ROOT, jsFile)} -> ${importSpec}`);
				continue;
			}

			const installedDepPath = path.join(PROJECT_ROOT, 'node_modules', packageName);
			if (!isDirectory(installedDepPath)) {
				unresolvedJsImports.push(`${path.relative(PROJECT_ROOT, jsFile)} -> ${importSpec} (não instalado)`);
			}
		}
	}

	if (unresolvedJsImports.length > 0) {
		addError(`Imports JS quebrados ou módulos ausentes detectados (${unresolvedJsImports.length}).`);
		for (const item of unresolvedJsImports.slice(0, 20)) {
			addWarning(`JS import problem: ${item}`);
		}
		if (unresolvedJsImports.length > 20) {
			addWarning(`... e mais ${unresolvedJsImports.length - 20} problemas de import JS.`);
		}
	}

	const pythonModules = new Set();
	for (const pyFile of pyFiles) {
		if (pythonCmd) {
			const compileCheck = runCommand(pythonCmd.cmd, [...pythonCmd.prefix, '-m', 'py_compile', pyFile]);
			if (compileCheck.status !== 0) {
				addError(`Erro de sintaxe Python em ${path.relative(PROJECT_ROOT, pyFile)}: ${(compileCheck.stderr || '').trim() || 'invalid syntax'}`);
			}
		}

		let content = '';
		try {
			content = fs.readFileSync(pyFile, 'utf8');
		} catch (error) {
			addWarning(`Não foi possível ler ${path.relative(PROJECT_ROOT, pyFile)}: ${error.message || String(error)}`);
			continue;
		}

		const imports = parsePythonImports(content);
		for (const moduleName of imports) {
			pythonModules.add(moduleName);
		}
	}

	if (pythonCmd && pythonModules.size > 0) {
		const localModuleNames = new Set();
		for (const pyFile of pyFiles) {
			const relative = path.relative(PROJECT_ROOT, pyFile);
			const parsed = path.parse(relative);
			if (!parsed.dir) {
				localModuleNames.add(parsed.name);
			}
			const dirModuleInit = path.join(PROJECT_ROOT, parsed.dir, '__init__.py');
			if (isFile(dirModuleInit) && parsed.dir) {
				const top = parsed.dir.split(path.sep)[0];
				if (top) {
					localModuleNames.add(top);
				}
			}
		}

		const unresolvedPyModules = [];
		for (const moduleName of pythonModules) {
			if (localModuleNames.has(moduleName)) {
				continue;
			}

			const findSpecCode = [
				'import importlib.util, sys',
				'name = sys.argv[1]',
				'spec = importlib.util.find_spec(name)',
				'sys.exit(0 if spec is not None else 2)'
			].join('; ');

			const findSpec = runCommand(
				pythonCmd.cmd,
				[...pythonCmd.prefix, '-c', findSpecCode, moduleName],
				{ cwd: PROJECT_ROOT }
			);

			if (findSpec.status !== 0) {
				unresolvedPyModules.push(moduleName);
			}
		}

		if (unresolvedPyModules.length > 0) {
			addError(`Módulos Python ausentes/imports quebrados detectados (${unresolvedPyModules.length}).`);
			for (const moduleName of unresolvedPyModules.slice(0, 20)) {
				addWarning(`Python import problem: ${moduleName}`);
			}
			if (unresolvedPyModules.length > 20) {
				addWarning(`... e mais ${unresolvedPyModules.length - 20} problemas de import Python.`);
			}
			addSuggestion('Instale dependências Python com `pip install -r requirements.txt`.');
		}
	}

	const portsToCheck = [5000, 3000, 5173, 8080];
	report.environmentInfo.ports = {};
	for (const port of portsToCheck) {
		const occupied = await checkPortOccupied(port);
		report.environmentInfo.ports[port] = occupied ? 'occupied' : 'free';
		if (occupied) {
			addWarning(`Porta ${port} está ocupada.`);
		}
	}

	const flaskBackendFile = isFile(path.join(PROJECT_ROOT, 'app.py')) || isFile(path.join(PROJECT_ROOT, 'apex_server.py'));
	if (!flaskBackendFile) {
		addError('Backend Flask não encontrado (app.py/apex_server.py).');
	}

	const localAgentFile = isFile(path.join(PROJECT_ROOT, 'local_agent_server.js'));
	if (!localAgentFile) {
		addError('Agente local não encontrado (local_agent_server.js).');
	}

	const backendProbe = await httpProbe('http://127.0.0.1:5000/health');
	if (backendProbe.ok) {
		report.environmentInfo.backendFlask = { running: true, endpoint: '/health', statusCode: backendProbe.statusCode };
	} else {
		const fallbackProbe = await httpProbe('http://127.0.0.1:5000/');
		if (fallbackProbe.ok) {
			report.environmentInfo.backendFlask = { running: true, endpoint: '/', statusCode: fallbackProbe.statusCode };
		} else {
			report.environmentInfo.backendFlask = { running: false };
			addWarning('Backend Flask não respondeu em http://127.0.0.1:5000.');
		}
	}

	const localAgentProbe = await httpProbe('http://127.0.0.1:7070/health');
	if (localAgentProbe.ok) {
		report.environmentInfo.localAgent = { running: true, endpoint: '/health', statusCode: localAgentProbe.statusCode };
	} else {
		const fallbackProbe = await httpProbe('http://127.0.0.1:7070/');
		if (fallbackProbe.ok) {
			report.environmentInfo.localAgent = { running: true, endpoint: '/', statusCode: fallbackProbe.statusCode };
		} else {
			report.environmentInfo.localAgent = { running: false };
			addWarning('Agente local não respondeu em http://127.0.0.1:7070.');
		}
	}

	if (packageJsonAvailable) {
		const main = packageJson.main;
		const scripts = packageJson.scripts || {};
		const build = packageJson.build || {};

		if (!main) {
			addError('Configuração Electron ausente: campo `main` em package.json.');
		} else if (!isFile(path.join(PROJECT_ROOT, main))) {
			addError(`Arquivo main do Electron não encontrado: ${main}`);
		}

		if (!scripts.start || !String(scripts.start).includes('electron')) {
			addWarning('Script `start` não parece iniciar Electron.');
			addSuggestion('Defina `scripts.start` como `electron .` em package.json.');
		}

		if (!build.win) {
			addWarning('Configuração build.win ausente no electron-builder.');
		}

		if (!build.productName) {
			addWarning('build.productName ausente no package.json.');
		}

		if (!build.publish) {
			addSuggestion('Auto-update opcional: adicione `build.publish` no package.json quando houver servidor de updates.');
		}
	}

	if (!full) {
		addSuggestion('Use `npx node apex_diagnostic.js --full` ou `npm run diagnostic` para varredura completa explícita.');
	}

	report.environmentInfo.durationMs = Date.now() - startedAt.getTime();
	report.environmentInfo.reportFile = REPORT_FILE;
	saveLatestReport(report);

	log('info', 'diagnostics finished', {
		ok: report.ok,
		errors: report.errors.length,
		warnings: report.warnings.length,
		suggestions: report.suggestions.length,
		durationMs: report.environmentInfo.durationMs
	});

	return report;
}

async function runCli() {
	const args = process.argv.slice(2);
	const full = args.includes('--full');
	const nodeLauncher = detectNodeLauncher();
	const modeLabel = full ? 'completo (--full)' : 'rápido (default)';

	console.log(`[APEX Diagnostic] Modo de execução: ${modeLabel}.`);

	if (nodeLauncher && nodeLauncher.mode === 'npx') {
		console.log('[APEX Diagnostic] `node` indisponível no PATH. Usando fallback: `npx node`.');
	} else if (nodeLauncher && nodeLauncher.mode === 'node') {
		console.log('[APEX Diagnostic] Launcher Node detectado: `node`.');
	} else {
		console.error('[APEX Diagnostic] Falha: não foi possível localizar `node` nem `npx node`.');
	}

	const report = await runDiagnostics({ full });
	console.log(JSON.stringify(report, null, 2));
	console.log(`[APEX Diagnostic] Diagnóstico concluído — modo: ${report.environmentInfo.scan.mode}`);

	process.exitCode = report.ok ? 0 : 1;
}

if (require.main === module) {
	runCli().catch((error) => {
		log('error', 'diagnostic cli failed', { error: error.message || String(error) });
		console.error('Diagnostic CLI failed:', error);
		process.exitCode = 1;
	});
}

module.exports = {
	runDiagnostics
};

