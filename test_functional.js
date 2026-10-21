const fs = require('fs');
const path = require('path');
const cp = require('child_process');
const crypto = require('crypto');
const assert = require('assert');

const appRoot = '/usr/share/buddycn/resources/app';
const nm = path.join(appRoot, 'node_modules');

async function main() {
  const spdlog = require(path.join(nm, '@vscode/spdlog'));
  const logFile = '/tmp/cb-spdlog-test.log';
  if (fs.existsSync(logFile)) fs.unlinkSync(logFile);
  const logger = await spdlog.createAsyncRotatingLogger('test_logger', logFile, 1024 * 1024, 3);
  logger.info('spdlog write check');
  logger.flush();
  logger.drop();
  await new Promise(r => setTimeout(r, 200));
  const logContent = fs.readFileSync(logFile, 'utf8');
  assert(logContent.includes('spdlog write check'));
  console.log('spdlog:', logContent.trim());

  const pty = require(path.join(nm, 'node-pty'));
  const ptyOutput = await new Promise((resolve, reject) => {
    const term = pty.spawn('/bin/sh', ['-c', 'echo "PTY_OK_$(uname -s)_$(uname -m)"'], {
      name: 'xterm-color',
      cols: 80,
      rows: 24,
      cwd: '/tmp',
      env: process.env
    });
    let out = '';
    const timer = setTimeout(() => reject(new Error('pty timeout')), 5000);
    term.onData(data => {
      out += data;
      if (out.includes('PTY_OK_')) {
        clearTimeout(timer);
        resolve(out.trim());
      }
    });
  });
  console.log('node-pty:', ptyOutput);

  const watcher = require(path.join(nm, '@parcel/watcher'));
  const watchDir = '/tmp/cb-watch-' + process.pid;
  fs.mkdirSync(watchDir, { recursive: true });
  const watchEvent = await new Promise(async (resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('watcher timeout')), 5000);
    const sub = await watcher.subscribe(watchDir, (err, events) => {
      if (err) return reject(err);
      if (events && events.length > 0) {
        clearTimeout(timer);
        sub.unsubscribe().then(() => resolve(events[0]));
      }
    });
    setTimeout(() => {
      fs.writeFileSync(path.join(watchDir, 'probe.txt'), '1');
    }, 150);
  });
  fs.rmSync(watchDir, { recursive: true, force: true });
  console.log('parcel-watcher:', watchEvent.type, watchEvent.path);

  const sqlite3 = require(path.join(nm, '@vscode/sqlite3'));
  const dbRow = await new Promise((resolve, reject) => {
    const db = new sqlite3.Database(':memory:', err => {
      if (err) return reject(err);
      db.serialize(() => {
        db.run('CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value BLOB)');
        db.run('INSERT INTO ItemTable VALUES (?, ?)', ['codebuddy.state', 'ready']);
        db.get('SELECT key, value FROM ItemTable WHERE key = ?', ['codebuddy.state'], (err2, row) => {
          if (err2) return reject(err2);
          db.close(() => resolve(row));
        });
      });
    });
  });
  assert.strictEqual(dbRow.value, 'ready');
  console.log('sqlite3:', JSON.stringify(dbRow));

  require(path.join(nm, 'kerberos'));
  require(path.join(nm, 'native-is-elevated'))();
  require(path.join(nm, '@vscode/deviceid'));
  require(path.join(nm, 'windows-foreground-love'));
  require(path.join(nm, 'native-keymap')).getCurrentKeyboardLayout();
  require(path.join(nm, 'native-watchdog'));

  const rgBin = path.join(nm, '@vscode/ripgrep/bin/rg');
  const rgOut = cp.execFileSync(rgBin, ['--version'], { encoding: 'utf8' }).split('\n')[0];
  const trashBin = path.join(appRoot, 'extensions/genie/out/vendor/genie-trash/linux-x64');
  const trashOut = cp.execFileSync(trashBin, ['--version'], { encoding: 'utf8' }).trim();
  console.log('binaries:', rgOut, '/', trashOut);

  fs.readdirSync(path.join(appRoot, 'node_modules.asar'));
  const geniePkg = JSON.parse(fs.readFileSync(path.join(appRoot, 'extensions/genie/package.json'), 'utf8'));
  const genieMainStat = fs.statSync(path.join(appRoot, 'extensions/genie', geniePkg.main));
  assert(genieMainStat.size > 1000000);
  console.log('genie:', geniePkg.name, geniePkg.version, genieMainStat.size);

  const product = JSON.parse(fs.readFileSync(path.join(appRoot, 'product.json'), 'utf8'));
  for (const [relPath, expectedHash] of Object.entries(product.checksums)) {
    const fullPath = path.join(appRoot, 'out', relPath);
    const content = fs.readFileSync(fullPath);
    const actualHash = crypto.createHash('sha256').update(content).digest('base64').replace(/=+$/, '');
    assert.strictEqual(actualHash, expectedHash, `Checksum mismatch: ${relPath}`);
  }
  console.log('checksums_ok:', Object.keys(product.checksums).length);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
