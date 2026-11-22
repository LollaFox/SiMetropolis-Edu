import assert from 'node:assert/strict';
import { execFile, execFileSync } from 'node:child_process';
import { once } from 'node:events';
import { readdir } from 'node:fs/promises';
import { createServer } from 'node:http';
import { connect } from 'node:net';
import { join } from 'node:path';
import { connect as connectTls } from 'node:tls';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

export async function extractWindowsDownload(temporary, zipPath) {
  const build = fileURLToPath(new URL('../build-windows-download.ps1', import.meta.url));
  const powershell = ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass'];
  if (!zipPath) {
    execFileSync('powershell.exe', [...powershell, '-File', build, '-OutputDirectory', temporary]);
    zipPath = join(temporary, 'SiMetropolis-Edu-Windows.zip');
  }
  const folder = join(temporary, 'SiMetropolis Edu');
  execFileSync('powershell.exe', [...powershell, '-Command',
    'Expand-Archive -LiteralPath $env:TEST_ZIP -DestinationPath $env:TEST_FOLDER'], {
    env: { ...process.env, TEST_ZIP: zipPath, TEST_FOLDER: folder },
  });
  const entries = await readdir(folder, { withFileTypes: true });
  const launchers = entries.filter(entry => entry.isFile() && /\.(cmd|bat|exe|lnk|ps1|url)$/i.test(entry.name));
  assert.deepEqual(launchers.map(entry => entry.name), ['Open SiMetropolis Edu.cmd']);
  assert.ok(!entries.some(e => ['runtime', '.venv'].includes(e.name)), 'The download must start fresh');
  return join(folder, 'Open SiMetropolis Edu.cmd');
}

export function retryWindowsDownload(launcherPid, signal) {
  const script = fileURLToPath(new URL('./retry-windows-download.ps1', import.meta.url));
  return promisify(execFile)('powershell.exe', [
    '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', script, '-LauncherPid', String(launcherPid),
  ], { windowsHide: true, timeout: 100000, signal });
}

// Encrypted HTTPS traffic keeps its original host and certificate. Cut the first
// transfer after the TLS handshake, then let the real Retry finish the download.
export async function downloadConnection(t) {
  const configuredProxy = process.env.https_proxy || process.env.HTTPS_PROXY || process.env.ALL_PROXY;
  const proxy = configuredProxy && new URL(configuredProxy);
  if (proxy && !['http:', 'https:'].includes(proxy.protocol)) {
    throw new Error(`The live Windows download test supports HTTP and HTTPS proxies. The configured proxy uses ${proxy.protocol}`);
  }
  const state = { interrupted: false, offline: false, offlineAttempts: 0 };
  const relay = createServer();
  const sockets = new Set();
  relay.on('connect', (req, client, head) => {
    if (state.offline) {
      state.offlineAttempts++;
      client.destroy();
      return;
    }
    if (!['www.python.org:443', 'files.pythonhosted.org:443'].includes(req.url)) {
      client.destroy();
      return;
    }
    const host = req.url.split(':')[0];
    const upstream = proxy?.protocol === 'https:' ? connectTls({
      host: proxy.hostname, port: proxy.port || 443, servername: proxy.hostname,
    }) : connect(proxy ? Number(proxy.port) || 80 : 443, proxy ? proxy.hostname : host);
    sockets.add(client);
    client.on('close', () => { sockets.delete(client); upstream.destroy(); });
    client.on('error', () => upstream.destroy());
    upstream.on('error', () => client.destroy());
    upstream.on('close', () => client.destroy());
    upstream.once(proxy?.protocol === 'https:' ? 'secureConnect' : 'connect', () => {
      if (proxy) {
        const auth = proxy.username || proxy.password ? 'Proxy-Authorization: Basic ' +
          Buffer.from(decodeURIComponent(proxy.username) + ':' + decodeURIComponent(proxy.password)).toString('base64') + '\r\n' : '';
        upstream.write(`CONNECT ${req.url} HTTP/1.1\r\nHost: ${req.url}\r\n${auth}\r\n`);
      } else {
        client.write('HTTP/1.1 200 Connection established\r\n\r\n');
      }
      upstream.write(head);
      client.pipe(upstream);
      let bytes = 0;
      upstream.on('data', chunk => {
        bytes += chunk.length;
        if (!state.interrupted && bytes >= 128 * 1024) {
          state.interrupted = true;
          client.destroy();
        }
      });
      upstream.pipe(client);
    });
  });
  relay.listen(0, '127.0.0.1');
  await once(relay, 'listening');
  t.after(async () => {
    for (const socket of sockets) socket.destroy();
    await new Promise(resolve => relay.close(resolve));
  });
  state.env = { HTTPS_PROXY: `http://127.0.0.1:${relay.address().port}`, NO_PROXY: 'localhost,127.0.0.1,::1' };
  return state;
}
