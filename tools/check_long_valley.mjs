import assert from 'node:assert/strict';
import { execFileSync, spawn } from 'node:child_process';
import { once } from 'node:events';
import { chmod, cp, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { createServer, request } from 'node:http';
import { createRequire } from 'node:module';
import { networkInterfaces, tmpdir } from 'node:os';
import { basename, dirname, join } from 'node:path';
import { createInterface } from 'node:readline';
import { test } from 'node:test';
import { setTimeout as delay } from 'node:timers/promises';
import { fileURLToPath } from 'node:url';
import { downloadConnection, extractWindowsDownload, retryWindowsDownload } from './tests/windows-download.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const root = new URL('../', import.meta.url);
const python = process.env.PYTHON || 'python3';
const lanAddresses = Object.values(networkInterfaces()).flat()
  .filter(({ family, internal }) => family === 'IPv4' && !internal).map(({ address }) => address);
const lanTest = { timeout: 30000, skip: !lanAddresses.length && 'Needs a connected IPv4 interface' };
const hasNativeShortcut = process.platform === 'darwin' || process.platform === 'win32';
let launcherProfile;
test.before(async () => { launcherProfile = await mkdtemp(join(tmpdir(), 'long-valley-user-')); });
test.after(async () => { if (launcherProfile) await rm(launcherProfile, { recursive: true, force: true }); });

async function openClassroomBrowser(t, child, closed, browser, timeout = 10000) {
  const output = createInterface({ input: child.stdout });
  const setupMessages = [];
  output.on('line', line => {
    if (/^(Setting up SiMetropolis Edu|Downloading )/.test(line)) setupMessages.push(line);
    else output.emit('launch-url', line);
  });
  function nextLaunchUrl() {
    return Promise.race([
      once(output, 'launch-url', { signal: AbortSignal.timeout(timeout) }).then(([line]) => {
        if (line.startsWith('SiMetropolis Edu could not open.')) throw new Error(line);
        return new URL(line);
      }),
      closed.then(([code]) => { throw new Error(`Classroom exited with code ${code} before reporting its URL`); }),
    ]);
  }
  const launchUrl = await nextLaunchUrl();
  if (!browser) {
    browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, timeout: 10000 });
    t.after(() => browser.close());
  }
  return { browser, launchUrl, nextLaunchUrl, setupMessages };
}

async function classroom(t, ...options) {
  const data = await mkdtemp(join(tmpdir(), 'long-valley-test-'));
  t.after(() => rm(data, { recursive: true, force: true }));
  const command = ['-B', '-m', 'classroom', '--data-dir', data];
  function issueCredential() {
    return execFileSync(python, [...command, 'issue-teacher-credential'], {
      cwd: root, encoding: 'utf8',
    }).trim();
  }
  const server = spawn(python, [...command, 'serve', '--host', '127.0.0.1', '--port', '0', ...options], {
    cwd: root, stdio: ['ignore', 'pipe', 'inherit'],
  });
  const closed = once(server, 'close');
  t.after(async () => {
    server.kill();
    await closed;
  });
  const { browser, launchUrl } = await openClassroomBrowser(t, server, closed);
  return { browser, issueCredential, origin: launchUrl.origin };
}

async function prepareShortcut(temporary, env, shortcut) {
  let script;
  if (process.platform === 'win32') {
    script = await extractWindowsDownload(temporary);
    if (shortcut === 'legacy') {
      script = join(dirname(script), 'start-product.cmd');
      await cp(new URL('start-product.cmd', root), script);
    }
  } else {
    const folder = join(temporary, 'SiMetropolis Edu');
    await cp(new URL('classroom/', root), join(folder, 'classroom'), {
      recursive: true,
      filter: (path) => !['.data', '.DS_Store', '__pycache__'].includes(basename(path)),
    });
    script = join(folder, 'Open SiMetropolis Edu.command');
    await cp(new URL('Open SiMetropolis Edu.command', root), script);
  }
  const packageRoot = dirname(script);
  const setup = { cwd: packageRoot, env };
  execFileSync(python, ['-I', '-m', 'venv', '.venv'], setup);
  const interpreter = process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python';
  const requirements = fileURLToPath(new URL('classroom/requirements.txt', root));
  execFileSync(join(packageRoot, '.venv', interpreter),
    ['-I', '-m', 'pip', '--disable-pip-version-check', 'install', '-r', requirements], setup);
  return script;
}

async function launchClassroom(t, {
  shortcut = false, windowsScript, browser, delayedProfile = false, env = {}, retryDownload = false,
  networkAddress, settingsPlatform = '', durationSeconds = 2700,
} = {}) {
  const temporary = await mkdtemp(join(tmpdir(), 'long-valley-launch-'));
  const launches = [];
  let readOnlyClassroom;
  async function stop({ launcher, closed }) {
    if (launcher.pid && launcher.exitCode === null && launcher.signalCode === null) {
      if ((shortcut || windowsScript) && process.platform === 'win32') {
        const kill = spawn('taskkill.exe', ['/pid', String(launcher.pid), '/t', '/f'], { stdio: 'ignore' });
        await once(kill, 'close');
      } else {
        launcher.kill();
      }
    }
    await closed.catch(() => {});
  }
  t.after(async () => {
    await Promise.all(launches.map(stop));
    if (readOnlyClassroom) await chmod(readOnlyClassroom, 0o755);
    await rm(temporary, { recursive: true, force: true });
  });
  const browserCommand = join(temporary, 'open-browser.mjs');
  // A foreground opener waits for the page before returning control to the launcher.
  await writeFile(browserCommand, `
const url = new URL(process.argv[2]);
try {
  const response = await fetch(url, { signal: AbortSignal.timeout(5000) });
  if (!response.ok) throw new Error('HTTP ' + response.status);
  console.log(url.href);
} catch (error) {
  // Fail the fixture's URL check without invoking a fallback desktop browser.
  console.log('Classroom did not answer the foreground browser: ' + error.message);
}
`);
  const browserOverride = [process.execPath, browserCommand].map((path) => `"${path.replaceAll('\\', '/')}"`);
  const options = {
    cwd: root, stdio: ['ignore', 'pipe', 'inherit'],
    env: { ...process.env, XDG_STATE_HOME: launcherProfile, LOCALAPPDATA: launcherProfile, ...env,
      TMPDIR: temporary, TEMP: temporary, BROWSER: `${browserOverride.join(' ')} %s` },
  };
  let command = python;
  const launchArgs = ['--data-dir', join(temporary, 'data'), 'launch'];
  let args = ['-B', '-m', 'classroom', ...launchArgs];
  const networkFile = join(temporary, 'network-address');
  const settingsFile = join(temporary, 'opened-settings');
  const setNetworkAddress = address => writeFile(networkFile, address);
  if (windowsScript || shortcut) {
    options.env.PYTHONPATH = '';
    options.cwd = temporary;
    const script = windowsScript || await prepareShortcut(temporary, options.env, shortcut);
    if (process.platform === 'darwin') {
      readOnlyClassroom = join(dirname(script), 'classroom');
      await chmod(readOnlyClassroom, 0o555);
    }
    if (process.platform === 'win32') {
      command = 'cmd.exe';
      args = ['/d', '/s', '/c', `""${script}""`];
      options.windowsVerbatimArguments = true;
    } else {
      command = script;
      args = [];
    }
  } else if (networkAddress !== undefined) {
    await setNetworkAddress(networkAddress);
    args = ['-B', '-c', `
from contextlib import ExitStack
from pathlib import Path
import subprocess
import sys
from time import monotonic, sleep
from types import SimpleNamespace
from unittest.mock import patch
from classroom.__main__ import main

network_address, opened_settings, settings_platform, duration_seconds = sys.argv[1:5]
del sys.argv[1:5]

def discover(port):
    # A held OS query tests whether the teacher page waits for adapter discovery.
    deadline = monotonic() + 8
    while (address := Path(network_address).read_text().strip()) == 'checking' and monotonic() < deadline:
        sleep(.05)
    return f'http://{address}:{port}' if address and address != 'checking' else None

def open_settings(target):
    Path(opened_settings).write_text(target)

def run_command(args, **kwargs):
    assert args[0] == '/usr/bin/open'
    open_settings(args[1])
    return subprocess.CompletedProcess(args, 0)

with ExitStack() as fixtures:
    fixtures.enter_context(patch('classroom.network.local_join_origin', new=discover))
    fixtures.enter_context(patch('classroom.__main__.DEFAULT_CLASS_DURATION_SECONDS', int(duration_seconds)))
    if settings_platform:
        fixtures.enter_context(patch('classroom.network.sys', new=SimpleNamespace(platform=settings_platform)))
        fixtures.enter_context(patch('platform.mac_ver', return_value=('26.0', ('', '', ''), '')))
        fixtures.enter_context(patch('os.startfile', new=open_settings, create=True))
        fixtures.enter_context(patch('subprocess.run', new=run_command))
    main()
`, networkFile, settingsFile, settingsPlatform, String(durationSeconds), ...launchArgs];
  } else if (delayedProfile) {
    args = ['-B', '-c', `
from unittest.mock import patch
from classroom.__main__ import main

# Issue the first ticket at time zero; the profile opens 121 seconds later.
clock = iter([0])
with patch('classroom.server.monotonic', new=lambda: next(clock, 121)):
    main()
`, ...launchArgs];
  }
  if (windowsScript) options.stdio[2] = 'pipe';
  async function start() {
    const launcher = spawn(command, args, options);
    const closed = once(launcher, 'close');
    const processToStop = { launcher, closed };
    launches.push(processToStop);
    let progress = '';
    if (windowsScript) launcher.stderr.on('data', chunk => { progress += chunk; });
    const retry = new AbortController();
    try {
      const [opened] = await Promise.all([
        openClassroomBrowser(t, launcher, closed, browser, retryDownload ? 180000 : 10000),
        retryDownload && retryWindowsDownload(launcher.pid, retry.signal),
      ]);
      browser = opened.browser;
      return {
        ...opened, closed, stop: () => stop(processToStop), progress, setNetworkAddress,
        openedSettings: () => readFile(settingsFile, 'utf8'),
      };
    } finally {
      retry.abort();
    }
  }
  return { ...await start(), relaunch: start };
}

async function openClass(page, origin, credential, language = 'English') {
  await prepareClass(page, origin, credential, language);
  await page.getByRole('button', { name: /Start class|開始課堂/ }).click();
}

async function prepareClass(page, origin, credential, language) {
  await page.goto(`${origin}/teacher`);
  if (language === '繁體中文') {
    await page.getByRole('link', { name: '繁體中文' }).click();
  }
  await page.getByLabel(/Teacher credential|教師憑證/).fill(credential);
  await page.getByRole('button', { name: /Sign in|登入/ }).click();
  await page.getByLabel(/Starting language|起始語言/).selectOption({ label: language });
}

async function participant(browser) {
  const context = await browser.newContext();
  context.setDefaultTimeout(5000);
  return context.newPage();
}

async function openProjection(teacher) {
  const link = teacher.getByRole('link', { name: /project join information|投影加入資訊/i });
  const projectUrl = new URL(await link.getAttribute('href'), teacher.url()).href;
  const [projector] = await Promise.all([
    teacher.waitForEvent('popup'),
    link.click(),
  ]);
  await projector.waitForURL(projectUrl);
  projector.setDefaultTimeout(5000);
  return projector;
}

async function readQr(projector) {
  const image = projector.getByRole('img', { name: /Join QR code|加入課堂的二維碼/ });
  assert.equal(await image.count(), 1, 'The projection must show a join QR code');
  const { pixels, width, height } = await image.evaluate(async (element) => {
    await element.decode();
    const { naturalWidth: width, naturalHeight: height } = element;
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext('2d');
    context.drawImage(element, 0, 0);
    return { pixels: Array.from(context.getImageData(0, 0, width, height).data), width, height };
  });
  const decode = require(process.env.JSQR_PATH || 'jsqr');
  const result = decode(Uint8ClampedArray.from(pixels), width, height);
  assert.ok(result, 'The projected QR image must be scannable');
  return result.data;
}

async function startConnectedClass(teacher, launchUrl, language) {
  await teacher.goto(launchUrl.href);
  await teacher.waitForURL(`${launchUrl.origin}/teacher`);
  await teacher.reload();
  const start = teacher.getByRole('button', { name: 'Start class' });
  await start.waitFor();
  assert.equal(await teacher.getByRole('timer').count(), 0);
  assert.equal(await teacher.getByRole('link', { name: 'Project join information' }).count(), 0);
  assert.equal(await teacher.getByRole('alert').count(), 0);
  await teacher.getByLabel('Starting language').selectOption({ label: language });
  const started = performance.now();
  await start.click();
  const timer = teacher.getByRole('timer', { name: /Time remaining|剩餘時間/ });
  const [minutes, seconds] = (await timer.textContent()).split(':').map(Number);
  const remaining = (minutes * 60 + seconds) * 1000;
  assert.ok(remaining <= 45 * 60000 && remaining >= 45 * 60000 - (performance.now() - started),
    'The default deadline should be 45 minutes from Start class');
  assert.equal(await teacher.getByRole('alert').count(), 0);
  assert.equal(await teacher.getByRole('button', { name: /Open network settings|開啟網絡設定/ }).count(), 0);
}

test('a connected English class projects a LAN link that a group can use', lanTest, async (t) => {
  const { browser, launchUrl } = await launchClassroom(t, { shortcut: hasNativeShortcut });
  const teacher = await participant(browser);
  await startConnectedClass(teacher, launchUrl, 'English');
  const projector = await openProjection(teacher);
  const bookmark = await teacher.request.get(projector.url() + '/');
  assert.equal(bookmark.status(), 200);
  const joinUrl = await projector.getByRole('link', { name: /\/join\// }).getAttribute('href');
  assert.ok(lanAddresses.includes(new URL(joinUrl).hostname), 'The projection must use a LAN address');
  const group = await participant(browser);
  await group.goto(joinUrl);
  await group.getByRole('button', { name: 'Choose Site A' }).click();
  await group.getByRole('heading', { name: 'Site A: Central wetland' }).waitFor();
});

test('a connected Traditional Chinese class admits groups by QR and short code and keeps the projection private', lanTest, async (t) => {
  const { browser, launchUrl } = await launchClassroom(t);
  const teacher = await participant(browser);
  await startConnectedClass(teacher, launchUrl, '繁體中文');

  const projector = await openProjection(teacher);
  const joinUrl = await readQr(projector);
  const lanOrigin = new URL(joinUrl).origin;
  assert.ok(lanAddresses.includes(new URL(joinUrl).hostname), 'The QR must use a LAN address');
  assert.equal(joinUrl, await projector.getByRole('link', { name: /\/join\// }).getAttribute('href'));
  assert.ok(!joinUrl.includes(launchUrl.hash.slice(1)), 'The QR must contain only the student URL');
  const groupA = await participant(browser);
  await groupA.goto(joinUrl);
  await groupA.getByRole('button', { name: '選擇場地 A' }).click();
  await groupA.getByRole('heading', { name: '場地 A：中央濕地' }).waitFor();

  const code = await projector.locator('code').innerText();
  const entry = await projector.getByRole('link', { name: `${lanOrigin}/join`, exact: true }).getAttribute('href');
  const groupB = await participant(browser);
  await groupB.goto(entry);
  await groupB.getByLabel('課堂代碼').fill(code);
  await groupB.getByRole('button', { name: '尋找課堂' }).click();
  assert.equal(groupB.url(), joinUrl);
  assert.ok(await groupB.getByRole('button', { name: '選擇場地 A' }).isDisabled());
  await groupB.getByRole('button', { name: '選擇場地 B' }).click();
  await groupB.getByRole('heading', { name: '場地 B：河畔濕地' }).waitFor();

  const teacherPage = await groupB.goto(`${lanOrigin}/teacher?lang=zh-Hant`);
  if (teacherPage.ok()) await groupB.getByRole('button', { name: '登入' }).waitFor();
  else assert.ok([403, 404].includes(teacherPage.status()));
  assert.equal(await groupB.getByRole('button', { name: /開始課堂|結束課堂|交換場地/ }).count(), 0);
  const projectionPath = new URL(projector.url()).pathname;
  for (const path of [projectionPath, `${projectionPath}/qr.png`]) {
    assert.equal((await groupB.request.get(lanOrigin + path)).status(), 403);
  }
});

test('the teacher countdown starts on click and keeps its original deadline after reload', { timeout: 30000 }, async (t) => {
  const { browser, issueCredential, origin } = await classroom(t, '--duration-seconds', '7');
  const teacher = await participant(browser);
  await prepareClass(teacher, origin, issueCredential(), '繁體中文');
  const timer = teacher.getByRole('timer', { name: '剩餘時間' });
  const project = teacher.getByRole('link', { name: '投影加入資訊' });
  assert.equal(await timer.count(), 0);
  const [started] = await Promise.all([
    teacher.waitForRequest(request => new URL(request.url()).pathname === '/teacher/start')
      .then(() => performance.now()),
    teacher.getByRole('button', { name: '開始課堂' }).click(),
  ]);
  assert.equal(await timer.textContent(), '00:07');
  const projectionPath = await project.getAttribute('href');
  await teacher.waitForFunction(() => document.querySelector('[role="timer"]').textContent === '00:05');
  await teacher.reload();
  assert.match(await timer.textContent(), /^00:0[345]$/);
  assert.equal(await project.getAttribute('href'), projectionPath);
  const statusUrl = new URL(projectionPath + '/status', origin).href;
  await delay(Math.max(0, started + 6750 - performance.now()));
  assert.equal((await teacher.request.get(statusUrl)).status(), 204, 'The original deadline is still ahead');
  await delay(Math.max(0, started + 7500 - performance.now()));
  assert.equal((await teacher.request.get(statusUrl)).status(), 410, 'Reload must not extend the original deadline');
  await teacher.getByRole('button', { name: '開始課堂' }).waitFor({ timeout: 2500 });
});

test('the prepared launcher opens lesson preparation with only a loopback connection', { timeout: 30000 }, async (t) => {
  const { browser, launchUrl } = await launchClassroom(t);
  assert.equal(launchUrl.hostname, '127.0.0.1');
  const teacher = await participant(browser);
  await teacher.route('**/*', (route) => new URL(route.request().url()).origin === launchUrl.origin
    ? route.continue() : route.abort());
  await teacher.goto(launchUrl.href);
  await teacher.waitForURL(`${launchUrl.origin}/teacher`);
  await teacher.getByRole('heading', { name: 'Open a Long Valley class' }).waitFor();
  const language = teacher.getByLabel('Starting language');
  assert.equal(await language.inputValue(), 'en');
  await language.selectOption({ label: '繁體中文' });
  assert.equal(await language.inputValue(), 'zh-Hant');
  assert.equal(await teacher.getByRole('link', { name: 'Project join information' }).count(), 0);
  await teacher.getByRole('button', { name: 'Start class' }).click();
  await teacher.getByRole('heading', { name: '課堂已開啟' }).waitFor();
});

test('the teacher can start a Traditional Chinese class while the network is unavailable', { timeout: 30000 }, async (t) => {
  const { browser, launchUrl, setNetworkAddress } = await launchClassroom(t, { networkAddress: 'checking' });
  const teacher = await participant(browser);
  await teacher.goto(launchUrl.href);
  await teacher.getByLabel('Starting language').selectOption({ label: '繁體中文' });
  await teacher.getByRole('button', { name: 'Start class' }).click();
  const timer = teacher.getByRole('timer', { name: '剩餘時間' });
  assert.match(await timer.textContent(), /^(45:00|44:59)$/);
  assert.equal(await teacher.getByRole('button', { name: '開啟網絡設定' }).count(), 0);
  await setNetworkAddress('');
  await teacher.getByText('無法連接課堂網絡。Edu 正在自動重試。').waitFor();
  if (hasNativeShortcut) await teacher.getByRole('button', { name: '開啟網絡設定' }).waitFor();
  assert.equal(await teacher.getByRole('link', { name: '投影加入資訊' }).count(), 0);
  await teacher.waitForFunction(() => /^44:5[0-8]$/.test(document.querySelector('[role="timer"]').textContent));
  await setNetworkAddress('192.0.2.10');
  await teacher.getByRole('link', { name: '投影加入資訊' }).waitFor({ timeout: 12000 });
  assert.equal(await teacher.getByText('無法連接課堂網絡。Edu 正在自動重試。').isVisible(), false);
});

for (const [platform, target] of [
  ['darwin', 'x-apple.systempreferences:com.apple.Network-Settings.extension'],
  ['win32', 'ms-settings:network-status'],
]) {
  test(`the local teacher can open ${platform === 'darwin' ? 'Mac' : 'Windows'} network settings during an outage`,
    { timeout: 30000 }, async (t) => {
      const { browser, launchUrl, openedSettings } = await launchClassroom(t, {
        networkAddress: '', settingsPlatform: platform,
      });
      const teacher = await participant(browser);
      await teacher.goto(launchUrl.href);
      await teacher.getByRole('button', { name: 'Start class' }).click();
      const settings = teacher.getByRole('button', { name: 'Open network settings' });
      const originalLoad = await teacher.evaluate(() => performance.timeOrigin);
      const [response] = await Promise.all([
        teacher.waitForResponse(result => result.request().method() === 'POST'),
        settings.click(),
      ]);
      assert.equal(response.status(), 204);
      assert.equal(await openedSettings(), target);
      assert.equal(await teacher.evaluate(() => performance.timeOrigin), originalLoad);
      await teacher.getByRole('timer').waitFor();

      const group = await participant(browser);
      const rejected = await group.request.post(response.url(), {
        headers: { Origin: launchUrl.origin, 'Content-Type': 'application/x-www-form-urlencoded' },
        data: response.request().postData(),
      });
      assert.equal(rejected.status(), 403);
    });
}

test('a running class withdraws stale join information and projects the new address after reconnecting', lanTest, async (t) => {
  const { browser, launchUrl, setNetworkAddress } = await launchClassroom(t, { networkAddress: '192.0.2.10' });
  const teacher = await participant(browser);
  await startConnectedClass(teacher, launchUrl, 'English');
  const projector = await openProjection(teacher);
  const original = new URL(await readQr(projector));
  const code = await projector.locator('code').innerText();
  const projectLink = teacher.getByRole('link', { name: 'Project join information' });
  const outage = teacher.getByText('The classroom network is unavailable. Edu is retrying automatically.');
  assert.equal(original.hostname, '192.0.2.10');
  assert.equal(await outage.isVisible(), false);
  const started = performance.now();

  await setNetworkAddress('');
  await outage.waitFor({ timeout: 12000 });
  await projectLink.waitFor({ state: 'hidden' });
  await projector.getByRole('img', { name: 'Join QR code' }).waitFor({ state: 'hidden', timeout: 12000 });
  assert.equal(await projector.getByRole('link', { name: original.href }).isVisible(), false);
  assert.equal(await projector.locator('code').isVisible(), false);
  const pages = [teacher, projector];
  const originalLoads = await Promise.all(pages.map(page => page.evaluate(() => performance.timeOrigin)));

  await setNetworkAddress(lanAddresses[0]);
  await projectLink.waitFor({ timeout: 12000 });
  await outage.waitFor({ state: 'hidden' });
  const restoredLink = projector.getByRole('link', { name: new RegExp(`/join/${code}\\?lang=en$`) });
  await restoredLink.waitFor({ timeout: 12000 });
  const restored = new URL(await restoredLink.getAttribute('href'));
  assert.equal(restored.hostname, lanAddresses[0]);
  assert.equal(restored.pathname, original.pathname);
  assert.equal(await readQr(projector), restored.href);
  assert.deepEqual(await Promise.all(pages.map(page => page.evaluate(() => performance.timeOrigin))), originalLoads);
  const [minutes, seconds] = (await teacher.getByRole('timer').textContent()).split(':').map(Number);
  assert.ok((45 * 60 - minutes * 60 - seconds) * 1000 >= performance.now() - started - 1000,
    'The original countdown should continue during the interruption');

  const group = await participant(browser);
  await group.goto(restored.href);
  await group.getByRole('button', { name: 'Choose Site A' }).click();
  await group.getByRole('heading', { name: 'Site A: Central wetland' }).waitFor();
});

test('both joined groups recover their work through the new QR after a host address change', lanTest, async t => {
  const { browser, launchUrl, setNetworkAddress } = await launchClassroom(t, { networkAddress: '127.0.0.1' });
  const teacher = await participant(browser);
  await startConnectedClass(teacher, launchUrl, 'English');
  const projector = await openProjection(teacher);
  const original = new URL(await readQr(projector));
  const students = [
    { page: await participant(browser), site: 'A', alignment: 'north', partner: 'Site B: Riverside wetland' },
    { page: await participant(browser), site: 'B', alignment: 'south', partner: '場地 A：中央濕地' },
  ];
  for (const { page, site, alignment } of students) {
    await page.goto(original.href);
    await page.getByRole('button', { name: `Choose Site ${site}` }).click();
    await page.getByLabel('Railway alignment').selectOption(alignment);
    await page.getByRole('button', { name: 'Save for swap' }).click();
    await page.getByText('Crossing saved for Pass the City.').waitFor();
  }
  await students[1].page.getByRole('button', { name: '繁體中文' }).click();

  await setNetworkAddress('');
  await projector.getByRole('img', { name: 'Join QR code' }).waitFor({ state: 'hidden', timeout: 12000 });
  await teacher.getByRole('button', { name: 'Pass the City' }).click();
  await setNetworkAddress(lanAddresses[0]);
  await projector.getByRole('img', { name: 'Join QR code' }).waitFor({ timeout: 12000 });
  const restored = new URL(await readQr(projector));
  assert.notEqual(restored.hostname, original.hostname);
  assert.equal(restored.pathname + restored.search, original.pathname + original.search);

  for (const { page, site, alignment, partner } of students) {
    // Open the projected address with this group's original browser, whose cookie is on the old host.
    await page.goto(restored.href);
    assert.equal(await page.getByRole('button', { name: /Choose Site [AB]/, disabled: true }).count(), 2);
    await teacher.getByText('Help a group rejoin', { exact: true }).click();
    await teacher.getByLabel('Group’s starting site').selectOption(site);
    await teacher.getByRole('button', { name: 'Get group rejoin code' }).click();
    const rejoinCode = await teacher.locator('code').innerText();
    await page.getByLabel('Group rejoin code', { exact: true }).fill(rejoinCode);
    await page.getByRole('button', { name: 'Rejoin my group' }).click();
    await page.getByRole('heading', { name: partner }).waitFor();
    assert.equal(await page.getByLabel(/Railway alignment|鐵路走線/).inputValue(), alignment);
    await page.reload();
    await page.getByRole('heading', { name: partner }).waitFor();
    await teacher.getByRole('link', { name: 'Back to teacher view' }).click();
  }
  await teacher.getByRole('button', { name: 'End class' }).click();
  await students[1].page.goto(restored.href);
  await students[1].page.getByRole('heading', { name: '這個課堂已結束' }).waitFor();
});

test('a returning group can retry a one-use code while the other starting site is still free', { timeout: 30000 }, async t => {
  const { groupAt, teacher, projector, joinUrl } = await startInvestigation(t, '繁體中文');
  const group = await groupAt('A');
  await teacher.getByText('協助小組重新加入', { exact: true }).click();
  await teacher.getByLabel('小組的起始場地').selectOption('A');
  await teacher.getByRole('button', { name: '取得小組重入碼' }).click();
  const originalCode = await teacher.locator('code').innerText();
  await teacher.reload();
  assert.equal(await teacher.locator('code').innerText(), originalCode);

  await group.context().clearCookies();
  await group.goto(joinUrl);
  assert.ok(await group.getByRole('button', { name: '選擇場地 B' }).isEnabled());
  assert.ok(!(await group.content()).includes(originalCode));
  assert.ok(!(await projector.content()).includes(originalCode));
  const input = group.getByLabel('小組重入碼', { exact: true });
  const rejoin = group.getByRole('button', { name: '返回我的小組' });
  await input.fill(originalCode.toLowerCase().replaceAll('-', ''));
  await rejoin.click();
  await group.getByRole('heading', { name: '場地 A：中央濕地' }).waitFor();

  // A second loss of browser storage needs the group's new code from the private teacher tab.
  await group.context().clearCookies();
  await group.goto(joinUrl);
  await input.fill(originalCode);
  await rejoin.click();
  await group.getByRole('alert').getByText('請向老師核對小組重入碼，然後再試一次。').waitFor();
  assert.ok(await group.getByRole('button', { name: '選擇場地 B' }).isEnabled());
  await teacher.reload();
  const nextCode = await teacher.locator('code').innerText();
  assert.notEqual(nextCode, originalCode);
  await input.fill(nextCode);
  await rejoin.click();
  await group.getByRole('heading', { name: '場地 A：中央濕地' }).waitFor();
});

test('the projection retries a failed QR when the same address returns', { timeout: 30000 }, async (t) => {
  const address = '192.0.2.10';
  const { browser, launchUrl, setNetworkAddress } = await launchClassroom(t, { networkAddress: address });
  const teacher = await participant(browser);
  await startConnectedClass(teacher, launchUrl, 'English');
  const context = teacher.context();
  const outage = teacher.getByText('The classroom network is unavailable. Edu is retrying automatically.');
  // Deliver the first image request to the server after adapter discovery has detected the loss.
  await context.route('**/qr.png?*', async route => {
    await setNetworkAddress('');
    await outage.waitFor({ timeout: 12000 });
    await route.continue();
  }, { times: 1 });
  const [projector, failedQr] = await Promise.all([
    teacher.waitForEvent('popup'),
    context.waitForEvent('response', {
      predicate: response => new URL(response.url()).pathname.endsWith('/qr.png'), timeout: 12000,
    }),
    teacher.getByRole('link', { name: 'Project join information' }).click(),
  ]);
  assert.equal(failedQr.status(), 503);
  await projector.locator('[data-network-notice]').waitFor({ timeout: 12000 });
  const originalLoad = await projector.evaluate(() => performance.timeOrigin);
  await setNetworkAddress(address);
  const joinLink = projector.locator('[data-join-link]');
  await joinLink.waitFor({ timeout: 12000 });
  await projector.waitForFunction(() => document.querySelector('[data-join-qr]').naturalWidth > 0,
    undefined, { timeout: 5000 });
  assert.equal(await readQr(projector), await joinLink.getAttribute('href'));
  assert.equal(await projector.evaluate(() => performance.timeOrigin), originalLoad);
});

for (const [previousAddress, newAddress] of [['192.0.2.10', ''], ['', '192.0.2.10']]) {
  test(`a new ${newAddress ? 'connected' : 'offline'} class checks the current adapter on its first poll`, async t => {
    const { browser, launchUrl, setNetworkAddress } = await launchClassroom(t, { networkAddress: previousAddress });
    const teacher = await participant(browser);
    await teacher.goto(launchUrl.href);
    const start = teacher.getByRole('button', { name: 'Start class' });
    const project = teacher.getByRole('link', { name: 'Project join information' });
    const outage = teacher.getByText('The classroom network is unavailable. Edu is retrying automatically.');
    await start.click();
    await (previousAddress ? project : outage).waitFor();
    await teacher.getByRole('button', { name: 'End class' }).click();
    await setNetworkAddress(newAddress);
    const [firstPoll] = await Promise.all([
      teacher.waitForResponse(response => response.url().endsWith('/status?network=1')),
      start.click(),
    ]);
    assert.equal(firstPoll.status(), 204);
    const joinUrl = await firstPoll.headerValue('x-join-url');
    assert.equal(joinUrl ? new URL(joinUrl).hostname : '', newAddress);
    await (newAddress ? project : outage).waitFor();
    assert.equal(await (newAddress ? outage : project).isVisible(), false);
  });
}

test('a class that expires during an outage stays closed after the network returns', lanTest, async (t) => {
  const lanAddress = lanAddresses[0];
  const { browser, launchUrl, setNetworkAddress } = await launchClassroom(t, {
    networkAddress: lanAddress, durationSeconds: 12,
  });
  const teacher = await participant(browser);
  await teacher.goto(launchUrl.href);
  await teacher.getByRole('button', { name: 'Start class' }).click();
  const projector = await openProjection(teacher);
  const joinUrl = await readQr(projector);

  await setNetworkAddress('');
  await teacher.getByText('The classroom network is unavailable. Edu is retrying automatically.')
    .waitFor({ timeout: 10000 });
  await Promise.all([
    teacher.getByRole('heading', { name: 'Open a Long Valley class' }).waitFor({ timeout: 12000 }),
    projector.getByRole('heading', { name: 'This class is closed' }).waitFor({ timeout: 12000 }),
  ]);

  await setNetworkAddress(lanAddress);
  const group = await participant(browser);
  assert.equal((await group.goto(joinUrl)).status(), 410);
  await group.getByRole('heading', { name: 'This class is closed' }).waitFor();
  assert.equal(await teacher.getByRole('link', { name: 'Project join information' }).count(), 0);
});

test('Open SiMetropolis Edu runs from a prepared folder with spaces', {
  skip: !hasNativeShortcut,
  timeout: 30000,
}, async (t) => {
  const { browser, launchUrl } = await launchClassroom(t, { shortcut: true });
  const teacher = await participant(browser);
  await teacher.goto(launchUrl.href);
  await teacher.getByRole('button', { name: 'Start class' }).waitFor();
});

test('the legacy Windows shortcut opens private lesson preparation', {
  skip: process.platform !== 'win32',
  timeout: 30000,
}, async (t) => {
  const { browser, launchUrl } = await launchClassroom(t, { shortcut: 'legacy' });
  const teacher = await participant(browser);
  await teacher.goto(launchUrl.href);
  await teacher.getByRole('heading', { name: 'Open a Long Valley class' }).waitFor();
});

test('the Windows download retries interrupted setup and reopens lesson preparation offline', {
  skip: process.platform !== 'win32'
    || (process.env.WINDOWS_DOWNLOAD_TEST !== '1' && 'Set WINDOWS_DOWNLOAD_TEST=1 for live first-use setup'),
  timeout: 240000,
}, async (t) => {
  const temporary = await mkdtemp(join(tmpdir(), 'long-valley-windows-'));
  try {
    const windowsScript = await extractWindowsDownload(temporary, process.env.WINDOWS_DOWNLOAD_ZIP);
    const connection = await downloadConnection(t);
    const first = await launchClassroom(t, { windowsScript, env: connection.env, retryDownload: true });
    assert.ok(connection.interrupted, 'A required download was interrupted after receiving bytes');
    assert.match(first.progress, /#+|\d+(\.\d+)?%/, 'The launcher displayed download progress');
    const teacher = await participant(first.browser);
    await teacher.goto(first.launchUrl.href);
    await teacher.waitForURL(`${first.launchUrl.origin}/teacher`);
    await teacher.getByRole('button', { name: 'Start class' }).waitFor();
    await first.stop();

    connection.offline = true;
    const offline = await launchClassroom(t, { windowsScript, env: connection.env, browser: first.browser });
    assert.equal(connection.offlineAttempts, 0, 'The installed launcher should open without requesting components');
    assert.deepEqual(offline.setupMessages, []);
    const returning = await participant(offline.browser);
    await returning.route('**/*', route => new URL(route.request().url()).origin === offline.launchUrl.origin
      ? route.continue() : route.abort());
    await returning.goto(offline.launchUrl.href);
    await returning.waitForURL(`${offline.launchUrl.origin}/teacher`);
    await returning.getByRole('heading', { name: 'Open a Long Valley class' }).waitFor();
  } finally {
    // Registered after the launcher hooks so even a failed launch releases its runtime first.
    t.after(() => rm(temporary, { recursive: true, force: true }));
  }
});

test('a slow browser profile selection renews its link after another launch', { timeout: 30000 }, async (t) => {
  const { browser, launchUrl, nextLaunchUrl, relaunch } = await launchClassroom(t, { delayedProfile: true });
  const later = await relaunch();
  const teacher = await participant(browser);
  await teacher.goto(later.launchUrl.href);
  await teacher.getByRole('button', { name: 'Start class' }).click();
  const code = await teacher.getByRole('button', { name: 'End class' }).getAttribute('value');
  const delayedTab = await participant(browser);
  const [renewedUrl] = await Promise.all([nextLaunchUrl(), delayedTab.goto(launchUrl.href)]);
  await delayedTab.getByText('Your sign-in link expired. Continue in the new teacher tab.').waitFor();
  await delayedTab.goto(`${launchUrl.origin}/teacher`);
  await delayedTab.getByLabel('Teacher credential').waitFor();
  await delayedTab.goto(launchUrl.href);
  await delayedTab.getByRole('alert').getByText('Open SiMetropolis Edu again to reach the teacher view.').waitFor();

  assert.equal(renewedUrl.origin, launchUrl.origin);
  assert.ok(renewedUrl.hash && renewedUrl.hash !== launchUrl.hash, 'The launcher must issue a fresh ticket');
  const newTab = await participant(browser);
  await newTab.goto(renewedUrl.href);
  assert.equal(await newTab.getByRole('button', { name: 'End class' }).getAttribute('value'), code);
});

test('a group browser cannot reuse the launcher sign-in or open the teacher projection', { timeout: 30000 }, async (t) => {
  const { browser, launchUrl } = await launchClassroom(t);
  const teacher = await participant(browser);
  const group = await participant(browser);
  const teacherView = `${launchUrl.origin}/teacher`;

  await group.goto(teacherView);
  await group.getByLabel('Teacher credential').waitFor();
  assert.equal(await group.getByRole('button', { name: 'Start class' }).count(), 0);

  await teacher.goto(launchUrl.href);
  await teacher.waitForURL(teacherView);
  await teacher.getByRole('button', { name: 'Start class' }).click();
  await teacher.getByRole('heading', { name: 'Your class is open' }).waitFor();

  await group.goto(launchUrl.href);
  await group.getByRole('alert').getByText('Open SiMetropolis Edu again to reach the teacher view.').waitFor();
  assert.equal(new URL(group.url()).hash, '');
  const code = await teacher.getByRole('button', { name: 'End class' }).getAttribute('value');
  for (const path of [`/teacher/project/${code}`, `/teacher/project/${code}/qr.png`]) {
    assert.equal((await group.request.get(launchUrl.origin + path)).status(), 403);
  }
  const project = teacher.getByRole('link', { name: 'Project join information' });
  if (await project.count()) {
    const projector = await openProjection(teacher);
    const joinUrl = await projector.getByRole('link', { name: /\/join\// }).getAttribute('href');
    const address = new URL(joinUrl);
    assert.ok(lanAddresses.includes(address.hostname));
    assert.equal(joinUrl, `${address.origin}/join/${code}?lang=en`);
    assert.equal(await readQr(projector), joinUrl);
    assert.ok(!(await projector.content()).includes(launchUrl.hash.slice(1)), 'Projection exposed the sign-in ticket');
    await group.goto(joinUrl);
    await group.getByRole('heading', { name: 'Choose your starting site' }).waitFor();
  }
});

test('a second installation preserves the first teacher session in the same browser', { timeout: 30000 }, async (t) => {
  const options = { shortcut: hasNativeShortcut };
  const first = await launchClassroom(t, options);
  const teacher = await participant(first.browser);
  await teacher.goto(first.launchUrl.href);
  await teacher.getByRole('button', { name: 'Start class' }).click();
  const endClass = teacher.getByRole('button', { name: 'End class' });
  const originalClass = await endClass.getAttribute('value');

  const second = await launchClassroom(t, { ...options, browser: first.browser });
  if (await teacher.getByRole('link', { name: 'Project join information' }).count()) {
    const projector = await openProjection(teacher);
    const joinUrl = await projector.getByRole('link', { name: /\/join\// }).getAttribute('href');
    const studentEntry = new URL(second.launchUrl);
    studentEntry.hostname = new URL(joinUrl).hostname;
    const group = await participant(first.browser);
    const response = await group.goto(studentEntry.href);
    if (response.ok()) await group.getByRole('alert').waitFor();
    else assert.ok([403, 404].includes(response.status()));
    assert.equal(await group.getByRole('button', { name: 'Start class' }).count(), 0);
  }
  const secondTab = await teacher.context().newPage();
  await secondTab.goto(second.launchUrl.href);
  const signOut = secondTab.getByRole('button', { name: 'Sign out' });
  await signOut.waitFor();
  await teacher.reload();
  assert.equal(await endClass.getAttribute('value'), originalClass);

  await signOut.click();
  await secondTab.getByLabel('Teacher credential').waitFor();
  await teacher.reload();
  assert.equal(await endClass.getAttribute('value'), originalClass);
  await teacher.getByRole('button', { name: 'End class' }).click();
  await teacher.getByRole('button', { name: 'Start class' }).waitFor();
});

test('reopening the launcher returns to the live lesson and the group keeps its crossing', lanTest, async (t) => {
  const { browser, launchUrl, relaunch } = await launchClassroom(t, { shortcut: hasNativeShortcut });
  const teacher = await participant(browser);
  await startConnectedClass(teacher, launchUrl, 'English');
  const projector = await openProjection(teacher);
  const code = await projector.locator('code').innerText();
  const joinUrl = await projector.getByRole('link', { name: /\/join\// }).getAttribute('href');
  const group = await participant(browser);
  await group.goto(joinUrl);
  await group.getByRole('button', { name: 'Choose Site A' }).click();
  await group.getByLabel('Crossing type').selectOption('tunnel');
  await group.getByRole('button', { name: 'Test crossing' }).click();
  const tunnel = group.getByRole('list', { name: 'Map key' }).getByText('Tunnel entrances', { exact: true });
  await tunnel.waitFor();

  async function displayedDeadline(page) {
    const readAt = performance.now();
    const [minutes, seconds] = (await page.getByRole('timer').innerText()).split(':').map(Number);
    return readAt + (minutes * 60 + seconds) * 1000;
  }

  // Let the countdown leave its starting value so a reset would be observable.
  await teacher.waitForFunction(() => document.querySelector('[role="timer"]').textContent < '44:58');
  const deadline = await displayedDeadline(teacher);
  const teacherContext = teacher.context();
  await projector.close();
  await teacher.close();

  await group.reload();
  await tunnel.waitFor();

  const [first, second] = await Promise.all([relaunch(), relaunch()]);
  // The second tab uses a fresh browser profile with no existing teacher cookie.
  for (const [reopened, newTeacher] of [
    [first, await teacherContext.newPage()], [second, await participant(browser)],
  ]) {
    assert.equal(reopened.launchUrl.origin, launchUrl.origin, 'The launcher should reuse the running classroom');
    assert.equal((await reopened.closed)[0], 0, 'An attaching launcher should exit after opening its tab');
    await newTeacher.goto(reopened.launchUrl.href);
    await newTeacher.getByRole('heading', { name: 'Your class is open' }).waitFor();
    assert.ok(Math.abs((await displayedDeadline(newTeacher)) - deadline) < 1500,
      'Reopening should preserve the original deadline within the timer display’s one-second resolution');
    const newProjection = await openProjection(newTeacher);
    assert.equal(await newProjection.locator('code').innerText(), code);
    assert.equal(await newProjection.getByRole('link', { name: /\/join\// }).getAttribute('href'), joinUrl);
  }

  await group.reload();
  await group.getByRole('heading', { name: 'Site A: Central wetland' }).waitFor();
  await group.getByRole('button', { name: 'Replay crossing' }).click();
  await tunnel.waitFor();
});

test('only the class owner can open the projection and load its QR image', { timeout: 30000 }, async (t) => {
  const { browser, issueCredential, origin } = await classroom(t);
  const credential = issueCredential();
  const teacher = await participant(browser);
  await openClass(teacher, origin, credential);

  const projector = await openProjection(teacher);
  await projector.getByRole('heading', { name: 'Join the Long Valley class' }).waitFor();
  const joinUrl = await projector.getByRole('link', { name: /\/join\// }).getAttribute('href');
  assert.equal(new URL(joinUrl).origin, origin);
  assert.equal(await readQr(projector), joinUrl);
  const code = await projector.locator('code').innerText();
  assert.match(code, /^[A-Z2-9]{6,8}$/);
  assert.equal(await projector.getByRole('button', { name: 'End class' }).count(), 0);
  assert.ok(!(await projector.content()).includes(credential));
  assert.ok(!projector.url().includes(credential));

  const imagePath = await projector.getByRole('img', { name: 'Join QR code' }).getAttribute('src');
  const legacyProjection = new URL(`/project/${code}`, origin).href;
  const protectedUrls = new Set([
    projector.url(), new URL(imagePath, projector.url()).href,
    legacyProjection, `${legacyProjection}/qr.png`,
  ]);
  const visitor = await participant(browser);
  await visitor.goto(origin);
  const group = await participant(browser);
  await group.goto(joinUrl);
  await group.getByRole('button', { name: 'Choose Site A' }).click();
  await group.getByRole('heading', { name: 'Site A: Central wetland' }).waitFor();
  const otherTeacher = await participant(browser);
  await openClass(otherTeacher, origin, issueCredential());
  await otherTeacher.getByRole('heading', { name: 'Your class is open' }).waitFor();
  for (const [role, page] of [['visitor', visitor], ['group', group], ['other teacher', otherTeacher]]) {
    for (const url of protectedUrls) {
      const status = await page.evaluate(async (url) => (await fetch(url)).status, url);
      assert.ok([401, 403, 404].includes(status), `${role} received HTTP ${status} for ${new URL(url).pathname}`);
    }
  }
});

test('the join link, scanned QR, and short code reach the paired sites before the teacher ends class', { timeout: 30000 }, async (t) => {
  const { browser, issueCredential, origin } = await classroom(t);
  const credential = issueCredential();
  const teacher = await participant(browser);
  const groupA = await participant(browser);
  const groupB = await participant(browser);
  await openClass(teacher, origin, credential, '繁體中文');
  const projector = await openProjection(teacher);
  const joinUrl = await projector.getByRole('link', { name: /\/join\// }).getAttribute('href');
  const code = await projector.locator('code').innerText();

  await groupA.goto(joinUrl);
  await groupA.getByRole('button', { name: '選擇場地 A' }).click();
  await groupA.getByRole('heading', { name: '你會怎樣讓鐵路穿越塱原？' }).waitFor();
  await groupA.getByRole('heading', { name: '場地 A：中央濕地' }).waitFor();
  assert.equal(await groupA.locator('html').getAttribute('lang'), 'zh-Hant');
  const scannedUrl = await readQr(projector);
  assert.equal(scannedUrl, joinUrl);
  await groupA.goto(scannedUrl);
  await groupA.getByRole('heading', { name: '場地 A：中央濕地' }).waitFor();

  await groupB.goto(`${origin}/join`);
  await groupB.getByLabel('Join code').fill(code.toLowerCase());
  await groupB.getByRole('button', { name: 'Find class' }).click();
  assert.equal(groupB.url(), joinUrl);
  assert.ok(await groupB.getByRole('button', { name: '選擇場地 A' }).isDisabled());
  await groupB.getByRole('button', { name: '選擇場地 B' }).click();
  await groupB.getByRole('heading', { name: '場地 B：河畔濕地' }).waitFor();

  await groupB.getByRole('button', { name: 'English' }).click();
  await groupB.getByRole('heading', { name: 'How would you get a railway across Long Valley?' }).waitFor();
  await groupB.getByText('Imagined Long Valley setting', { exact: true }).waitFor();
  assert.equal(groupB.url(), joinUrl);
  await groupB.reload();
  await groupB.getByRole('heading', { name: 'Site B: Riverside wetland' }).waitFor();
  assert.equal(await groupB.locator('html').getAttribute('lang'), 'en');
  await groupA.reload();
  await groupA.getByRole('heading', { name: '場地 A：中央濕地' }).waitFor();

  await groupB.goto(`${origin}/teacher`);
  assert.equal(await groupB.getByRole('button', { name: /Start class|End class/ }).count(), 0);
  const forbidden = await groupB.evaluate(async (joinCode) => {
    const statuses = [];
    for (const action of ['start', 'end']) {
      const response = await fetch(`/teacher/${action}`, {
        method: 'POST', body: new URLSearchParams({ code: joinCode, language: 'en' }),
      });
      statuses.push(response.status);
    }
    return statuses;
  }, code);
  assert.deepEqual(forbidden, [403, 403]);
  await groupB.goto(joinUrl);

  await teacher.getByRole('button', { name: '結束課堂' }).click();
  await Promise.all([
    projector.getByRole('heading', { name: '這個課堂已結束' }).waitFor({ timeout: 8000 }),
    groupA.getByRole('heading', { name: '這個課堂已結束' }).waitFor({ timeout: 8000 }),
    groupB.getByRole('heading', { name: 'This class is closed' }).waitFor({ timeout: 8000 }),
  ]);

  await teacher.getByRole('button', { name: '登出' }).click();
  await openClass(teacher, origin, credential);
  const freshProjector = await openProjection(teacher);
  const freshLink = await freshProjector.getByRole('link', { name: /\/join\// }).getAttribute('href');
  assert.notEqual(freshLink, joinUrl);
  assert.notEqual(await freshProjector.locator('code').innerText(), code);
  const oldQrResponse = await groupA.goto(scannedUrl);
  assert.equal(oldQrResponse.status(), 410);
  await groupB.goto(`${origin}/join`);
  await groupB.getByLabel('Join code').fill(code);
  await groupB.getByRole('button', { name: 'Find class' }).click();
  await groupB.getByRole('heading', { name: 'This class is closed' }).waitFor();
  await groupA.goto(freshLink);
  assert.ok(await groupA.getByRole('button', { name: 'Choose Site A' }).isEnabled());
  assert.ok(await groupA.getByRole('button', { name: 'Choose Site B' }).isEnabled());
});

test('reopening the link or scanning the QR of a closed Traditional Chinese class shows its closing message in Chinese', { timeout: 30000 }, async (t) => {
  const { browser, issueCredential, origin } = await classroom(t);
  const teacher = await participant(browser);
  await openClass(teacher, origin, issueCredential(), '繁體中文');
  const projector = await openProjection(teacher);
  const joinUrl = await projector.getByRole('link', { name: /\/join\// }).getAttribute('href');
  const scannedUrl = await readQr(projector);
  await teacher.getByRole('button', { name: '結束課堂' }).click();
  for (const url of [joinUrl, scannedUrl]) {
    const group = await participant(browser);
    const response = await group.goto(url);
    assert.equal(response.status(), 410);
    await group.getByRole('heading', { name: '這個課堂已結束' }).waitFor();
    assert.equal(await group.locator('html').getAttribute('lang'), 'zh-Hant');
  }

  const legacyLink = new URL(joinUrl);
  legacyLink.search = '';
  const returningGroup = await participant(browser);
  assert.equal((await returningGroup.goto(legacyLink.href)).status(), 410);
  await returningGroup.getByRole('link', { name: '繁體中文' }).click();
  await returningGroup.getByRole('heading', { name: '這個課堂已結束' }).waitFor();
  assert.equal(new URL(returningGroup.url()).pathname, legacyLink.pathname);
});

test('an expired Traditional Chinese class closes for joined groups and rejects its link and short code', { timeout: 30000 }, async (t) => {
  const { browser, issueCredential, origin } = await classroom(t, '--duration-seconds', '4');
  const teacher = await participant(browser);
  const group = await participant(browser);
  await openClass(teacher, origin, issueCredential(), '繁體中文');
  const projector = await openProjection(teacher);
  const joinUrl = await projector.getByRole('link', { name: /\/join\// }).getAttribute('href');
  const code = await projector.locator('code').innerText();
  await group.goto(joinUrl);
  await group.getByRole('button', { name: '選擇場地 A' }).click();
  await group.getByRole('heading', { name: '場地 A：中央濕地' }).waitFor();

  await Promise.all([
    group.getByRole('heading', { name: '這個課堂已結束' }).waitFor({ timeout: 10000 }),
    projector.getByRole('heading', { name: '這個課堂已結束' }).waitFor({ timeout: 10000 }),
    teacher.getByRole('button', { name: '開始課堂' }).waitFor({ timeout: 10000 }),
  ]);
  const returning = await participant(browser);
  assert.equal((await returning.goto(joinUrl)).status(), 410);
  await returning.getByRole('heading', { name: '這個課堂已結束' }).waitFor();
  assert.equal(await returning.locator('html').getAttribute('lang'), 'zh-Hant');
  await group.goto(`${origin}/join`);
  await group.getByLabel('Join code').fill(code);
  await group.getByRole('button', { name: 'Find class' }).click();
  await group.getByRole('heading', { name: 'This class is closed' }).waitFor();
});

async function startInvestigation(t, language = 'English', ...options) {
  const { browser, issueCredential, origin } = await classroom(t, ...options);
  const teacher = await participant(browser);
  await openClass(teacher, origin, issueCredential(), language);
  const projector = await openProjection(teacher);
  const joinUrl = await projector.getByRole('link', { name: /\/join\// }).getAttribute('href');

  async function groupAt(site, url = joinUrl) {
    const group = await participant(browser);
    await group.goto(url);
    await group.getByRole('button', { name: new RegExp(`^(?:Choose Site|選擇場地) ${site}$`) }).click();
    await group.getByRole('heading', { name: new RegExp(`^(?:Site|場地) ${site}[:：]`) }).waitFor();
    return group;
  }

  return { teacher, projector, groupAt, joinUrl, origin, issueCredential };
}

test('both groups can draw a different alignment between the same two stations', { timeout: 30000 }, async (t) => {
  const { groupAt } = await startInvestigation(t);
  for (const site of ['A', 'B']) {
    const group = await groupAt(site);
    const alignment = group.getByLabel('Railway alignment');
    const map = group.getByRole('group', { name: 'Spring site map' });
    assert.equal(await alignment.inputValue(), 'central');
    const centralMap = await map.screenshot();

    await alignment.selectOption({ label: 'Northern crossing' });
    await group.getByRole('button', { name: 'Test crossing' }).click();
    await map.getByText('West station', { exact: true }).waitFor();
    await map.getByText('East station', { exact: true }).waitFor();
    assert.equal(await alignment.inputValue(), 'north');
    assert.ok(!centralMap.equals(await map.screenshot()), 'The chosen crossing must change the drawn map');
  }
});

test('a tunnel shows tunnel entrances where an elevated crossing would show bridge supports', { timeout: 30000 }, async (t) => {
  const { groupAt } = await startInvestigation(t);
  const group = await groupAt('A');
  const map = group.getByRole('group', { name: 'Spring site map' });
  const key = group.getByRole('list', { name: 'Map key' });
  await key.getByText('Bridge supports', { exact: true }).waitFor();
  const supports = map.locator('rect.map-supports:visible');
  const entrances = map.locator('rect.map-entrances:visible');
  assert.equal(await supports.count(), 5);
  assert.equal(await entrances.count(), 0);

  await group.getByLabel('Crossing type').selectOption({ label: 'Tunnel' });
  await group.getByRole('button', { name: 'Test crossing' }).click();
  await key.getByText('Tunnel entrances', { exact: true }).waitFor();
  assert.equal(await key.getByText('Bridge supports', { exact: true }).count(), 0);
  assert.equal(await supports.count(), 0);
  assert.equal(await entrances.count(), 2);
});

test('each striped map location opens its own evidence by pointer or keyboard', { timeout: 30000 }, async (t) => {
  const { groupAt } = await startInvestigation(t);
  const group = await groupAt('A');
  await group.setViewportSize({ width: 320, height: 800 });
  await group.getByRole('combobox', { name: 'Construction access route', exact: true }).selectOption({ label: 'Valley approach' });
  await group.getByRole('button', { name: 'Test crossing' }).click();

  for (const labels of [
    { map: 'Spring site map', access: 'Inspect overlap for Construction access route',
      supports: 'Inspect overlap for Bridge supports', accessEvidence: 'Construction access route overlaps modelled nesting habitat.',
      supportEvidence: 'Bridge supports overlap modelled nesting habitat.' },
    { map: '春季場地地圖', access: '查看施工通道的重疊範圍', supports: '查看橋墩的重疊範圍',
      accessEvidence: '施工通道與模型中的築巢生境重疊。', supportEvidence: '橋墩與模型中的築巢生境重疊。' },
  ]) {
    if (labels.map === '春季場地地圖') await group.getByRole('button', { name: '繁體中文' }).click();
    const map = group.getByRole('group', { name: labels.map });
    const access = map.getByRole('link', { name: labels.access });
    const supports = map.getByRole('link', { name: labels.supports });
    assert.equal(await map.getByRole('link').count(), 2);
    assert.equal(await access.getAttribute('href'), '#evidence-access');

    // At this width the left edge of the access stripe is near the bridge support.
    await access.scrollIntoViewIfNeeded();
    const stripe = await access.boundingBox();
    await group.mouse.click(stripe.x + stripe.width * 0.05, stripe.y + stripe.height / 2);
    const selected = group.locator('li:target:focus');
    await selected.filter({ hasText: labels.accessEvidence }).waitFor();

    await access.focus();
    await group.keyboard.press('Tab');
    assert.ok(await supports.evaluate(link => link === document.activeElement));
    await group.keyboard.press('Enter');
    await selected.filter({ hasText: labels.supportEvidence }).waitFor();
  }
});

test('the same access route can overlap nesting habitat at one site and clear it at the other', { timeout: 30000 }, async (t) => {
  const { groupAt } = await startInvestigation(t);
  const groupA = await groupAt('A');
  const groupB = await groupAt('B');
  for (const group of [groupA, groupB]) {
    await group.getByLabel('Crossing type').selectOption({ label: 'Tunnel' });
    await group.getByRole('combobox', { name: 'Construction access route', exact: true }).selectOption({ label: 'Valley approach' });
    await group.getByRole('button', { name: 'Test crossing' }).click();
  }

  const finding = groupA.getByText('Possible disturbance', { exact: true });
  await finding.click();
  await groupA.getByText('Construction access route overlaps modelled nesting habitat.', { exact: true }).waitFor();
  await groupA.getByRole('list', { name: 'Map key' }).getByText('Footprint overlap', { exact: true }).waitFor();
  const overlapMap = await groupA.getByRole('group', { name: 'Spring site map' }).screenshot();
  await groupB.getByText('No modelled overlap', { exact: true }).waitFor();

  await groupA.getByRole('combobox', { name: 'Construction access route', exact: true }).selectOption({ label: 'East approach' });
  await groupA.getByRole('button', { name: 'Test crossing' }).click();
  await groupA.getByText('No modelled overlap', { exact: true }).waitFor();
  assert.equal(await finding.count(), 0);
  assert.equal(await groupA.getByText('Footprint overlap', { exact: true }).count(), 0);
  assert.ok(!overlapMap.equals(await groupA.getByRole('group', { name: 'Spring site map' }).screenshot()));
  assert.equal(await groupB.getByRole('combobox', { name: 'Construction access route', exact: true }).inputValue(), 'valley');
});

test('the spring baseline hides the works while keeping the site, habitat, and proposal', { timeout: 30000 }, async (t) => {
  const { groupAt } = await startInvestigation(t);
  const group = await groupAt('A');
  const map = group.getByRole('group', { name: 'Spring site map' });
  const key = group.getByRole('list', { name: 'Map key' });
  await group.getByLabel('Crossing type').selectOption({ label: 'Tunnel' });
  await group.getByRole('combobox', { name: 'Construction access route', exact: true }).selectOption({ label: 'Valley approach' });
  await group.getByRole('button', { name: 'Test crossing' }).click();
  await group.getByText('Possible disturbance', { exact: true }).waitFor();
  const proposedMap = await map.screenshot();

  await group.getByRole('button', { name: 'Without proposed works' }).click();
  await group.getByText('Spring baseline', { exact: true }).waitFor();
  assert.ok(await group.evaluate(() => window.scrollY > 0), 'The form should open at the comparison');
  await key.getByText('Modelled nesting habitat', { exact: true }).waitFor();
  await group.getByRole('heading', { name: 'Site A: Central wetland' }).waitFor();
  assert.equal(await key.getByText('Tunnel entrances', { exact: true }).count(), 0);
  await map.getByText('Wetland', { exact: true }).waitFor();
  assert.equal(await group.getByText('Possible disturbance', { exact: true }).count(), 0);
  assert.ok(!proposedMap.equals(await map.screenshot()));

  await group.getByRole('button', { name: 'With proposed works' }).click();
  await group.getByText('Possible disturbance', { exact: true }).click();
  await group.getByText('Construction access route overlaps modelled nesting habitat.', { exact: true }).waitFor();
  await key.getByText('Tunnel entrances', { exact: true }).waitFor();
});

async function testNorthernTunnelAtSiteB(groupAt) {
  const group = await groupAt('B');
  await group.getByLabel('Railway alignment').selectOption({ label: 'Northern crossing' });
  await group.getByLabel('Crossing type').selectOption({ label: 'Tunnel' });
  await group.getByRole('combobox', { name: 'Construction access route', exact: true }).selectOption({ label: 'Valley approach' });
  await group.getByRole('button', { name: 'Test crossing' }).click();
  return group;
}

test('replaying the last proposal from the baseline reproduces its visible evidence', { timeout: 30000 }, async (t) => {
  const { groupAt } = await startInvestigation(t);
  const group = await testNorthernTunnelAtSiteB(groupAt);
  const finding = group.getByText('Possible disturbance', { exact: true });
  const evidence = group.getByText('Construction access route overlaps modelled nesting habitat.', { exact: true });
  await finding.click();
  await evidence.waitFor();

  await group.getByRole('button', { name: 'Without proposed works' }).click();
  await group.getByText('Spring baseline', { exact: true }).waitFor();
  await group.getByRole('button', { name: 'Replay crossing' }).click();
  await group.getByRole('status').getByText('Crossing replayed.').waitFor();
  await finding.click();
  await evidence.waitFor();
});

test('reset restores the opening design at the group’s assigned site', { timeout: 30000 }, async (t) => {
  const { groupAt } = await startInvestigation(t);
  const group = await testNorthernTunnelAtSiteB(groupAt);
  await group.getByLabel('Railway alignment').selectOption({ label: 'Southern crossing' });
  await group.getByRole('button', { name: 'Without proposed works' }).click();
  assert.equal(await group.getByLabel('Railway alignment').inputValue(), 'south');
  await group.getByRole('button', { name: 'Reset crossing' }).click();
  await group.getByRole('heading', { name: 'Site B: Riverside wetland' }).waitFor();
  await group.getByText('No modelled overlap', { exact: true }).waitFor();
  assert.equal(await group.getByLabel('Railway alignment').inputValue(), 'central');
  assert.equal(await group.getByLabel('Crossing type').inputValue(), 'elevated');
  assert.equal(await group.getByRole('combobox', { name: 'Construction access route', exact: true }).inputValue(), 'east');
});

test('switching language preserves the untested draft, baseline and last tested crossing', { timeout: 30000 }, async (t) => {
  const { groupAt } = await startInvestigation(t);
  const group = await testNorthernTunnelAtSiteB(groupAt);
  await group.getByRole('button', { name: 'Without proposed works' }).click();
  await group.getByLabel('Railway alignment').selectOption({ label: 'Southern crossing' });
  await group.getByLabel('Crossing type').selectOption({ label: 'Elevated railway' });
  await group.getByRole('combobox', { name: 'Construction access route', exact: true }).selectOption({ label: 'East approach' });
  await group.getByRole('button', { name: '繁體中文' }).click();

  await group.getByRole('heading', { name: '場地 B：河畔濕地' }).waitFor();
  assert.equal(await group.locator('html').getAttribute('lang'), 'zh-Hant');
  assert.equal(await group.getByLabel('鐵路走線').inputValue(), 'south');
  assert.equal(await group.getByLabel('鐵路形式').inputValue(), 'elevated');
  assert.equal(await group.getByRole('combobox', { name: '施工通道', exact: true }).inputValue(), 'east');
  await group.getByText('春季基準', { exact: true }).waitFor();
  await group.getByRole('group', { name: '春季場地地圖' }).getByText('西面車站', { exact: true }).waitFor();

  await group.getByRole('button', { name: '重播走線測試' }).click();
  await group.getByText('可能造成滋擾', { exact: true }).click();
  await group.getByText('施工通道與模型中的築巢生境重疊。', { exact: true }).waitFor();
  await group.getByText('春季模型如何判斷？', { exact: true }).click();
  await group.getByRole('link', { name: '塱原自然生態公園四季指南' }).waitFor();
  await group.getByRole('button', { name: 'English' }).click();
  await group.getByText('Possible disturbance', { exact: true }).waitFor();
  assert.equal(await group.getByLabel('Railway alignment').inputValue(), 'south');
  assert.equal(await group.getByLabel('Crossing type').inputValue(), 'elevated');
  assert.equal(await group.getByRole('combobox', { name: 'Construction access route', exact: true }).inputValue(), 'east');
  await group.getByRole('button', { name: 'Test crossing' }).click();
  await group.getByText('No modelled overlap', { exact: true }).waitFor();
  await group.getByRole('list', { name: 'Map key' }).getByText('Bridge supports', { exact: true }).waitFor();
});

function rectangleGeometry(rectangles) {
  return rectangles.evaluateAll(elements => elements.map(rect => {
    const { x, y, width, height } = rect.getBBox();
    return { x, y, width, height };
  }));
}

for (const labels of [
  {
    language: 'English', gallery: 'Shared comparisons', empty: 'No group has shared a comparison yet.',
    choose: 'Choose Site', siteA: 'Site A: Central wetland', siteB: 'Site B: Riverside wetland',
    share: 'Share comparison', shared: 'Comparison shared with your teacher.',
    proposed: 'With proposed works', baseline: 'Without proposed works', context: 'Spring · Construction',
    design: 'Central crossing · Tunnel · Valley approach', replayed: 'Crossing replayed.',
    evidence: 'Construction access route overlaps modelled nesting habitat.',
    inspectAccess: 'Inspect overlap for Construction access route', back: 'Back to shared comparisons',
  },
  {
    language: '繁體中文', gallery: '已分享的比較結果', empty: '暫時沒有小組分享比較結果。',
    choose: '選擇場地', siteA: '場地 A：中央濕地', siteB: '場地 B：河畔濕地',
    share: '分享比較結果', shared: '已與老師分享比較結果。',
    proposed: '有擬議工程', baseline: '無擬議工程', context: '春季 · 施工階段',
    design: '中央走線 · 隧道 · 谷中通道', replayed: '已重播走線測試。',
    evidence: '施工通道與模型中的築巢生境重疊。',
    inspectAccess: '查看施工通道的重疊範圍', back: '返回已分享的比較結果',
  },
]) {
  test(`the teacher can project the original shared comparison in ${labels.language}`, { timeout: 30000 }, async (t) => {
    const { browser, issueCredential, origin } = await classroom(t);
    const [teacher, groupA, groupB, otherTeacher] = await Promise.all(
      Array.from({ length: 4 }, () => participant(browser)),
    );
    await openClass(teacher, origin, issueCredential(), labels.language);
    const projector = await openProjection(teacher);
    const joinUrl = await projector.getByRole('link', { name: /\/join\// }).getAttribute('href');
    await projector.getByRole('link', { name: labels.gallery }).click();
    await projector.getByText(labels.empty).waitFor();
    const galleryUrl = projector.url();
    const choices = projector.getByRole('list', { name: labels.gallery });
    const feedUrl = await choices.getAttribute('data-comparison-feed');

    await groupA.goto(joinUrl);
    await groupA.getByRole('button', { name: `${labels.choose} A` }).click();
    const alignment = groupA.getByLabel(/Railway alignment|鐵路走線/);
    const testCrossing = groupA.getByRole('button', { name: /Test crossing|測試走線/ });
    await groupA.getByLabel(/Crossing type|鐵路形式/).selectOption('tunnel');
    await groupA.getByRole('combobox', { name: /Construction access route|施工通道/ }).selectOption('valley');
    await testCrossing.click();
    const access = groupA.locator('.site-map rect.map-access');
    const originalAccess = await rectangleGeometry(access);
    assert.equal(originalAccess.length, 3);
    await groupA.getByRole('button', { name: labels.baseline }).click();
    await alignment.selectOption('south');
    await groupA.getByRole('button', { name: labels.share }).click();
    await groupA.getByRole('status').getByText(labels.shared).waitFor();
    assert.equal(await groupA.getByRole('button', { name: labels.baseline }).getAttribute('aria-pressed'), 'true');
    assert.equal(await alignment.inputValue(), 'south');

    const shared = choices.getByRole('link', { name: new RegExp(labels.siteA) });
    await shared.getByText(labels.design, { exact: true }).waitFor();
    assert.equal(projector.url(), galleryUrl);
    assert.equal(await projector.getByRole('heading', { name: labels.baseline }).count(), 0);

    await testCrossing.click();
    assert.notDeepEqual(await rectangleGeometry(access), originalAccess);
    await groupA.getByRole('button', { name: /Replay crossing|重播走線測試/ }).click();
    await groupA.getByRole('status').getByText(labels.replayed).waitFor();
    await groupA.getByRole('button', { name: /Reset crossing|重設走線/ }).click();
    assert.equal(await alignment.inputValue(), 'central');

    await shared.click();
    await projector.getByRole('heading', { name: labels.siteA, exact: true }).waitFor();
    await projector.getByText(labels.context, { exact: true }).waitFor();
    await projector.getByText(labels.design, { exact: true }).waitFor();
    const proposed = projector.getByRole('region', { name: labels.proposed });
    const baseline = projector.getByRole('region', { name: labels.baseline });
    await proposed.getByText(labels.evidence, { exact: true }).waitFor();
    assert.equal(await baseline.locator('.map-railway').count(), 0);
    assert.equal(await proposed.locator('.map-entrances:visible').count(), 2);
    assert.deepEqual(await rectangleGeometry(proposed.locator('.map-access')), originalAccess);
    await proposed.getByRole('link', { name: labels.inspectAccess }).click();
    await proposed.locator('li:target:focus').filter({ hasText: labels.evidence }).waitFor();
    const selectedUrl = projector.url();

    await groupB.goto(joinUrl);
    await groupB.getByRole('button', { name: `${labels.choose} B` }).click();
    await groupB.getByRole('button', { name: labels.share }).click();
    await groupB.getByRole('status').getByText(labels.shared).waitFor();
    await projector.reload();
    await proposed.getByText(labels.evidence, { exact: true }).waitFor();
    assert.equal(projector.url(), selectedUrl);
    await projector.getByRole('link', { name: labels.back }).click();
    await choices.getByRole('link', { name: new RegExp(labels.siteB) }).click();
    await projector.getByRole('heading', { name: labels.siteB, exact: true }).waitFor();

    await openClass(otherTeacher, origin, issueCredential(), labels.language);
    const otherProjector = await openProjection(otherTeacher);
    await otherProjector.getByRole('link', { name: labels.gallery }).click();
    await otherProjector.getByText(labels.empty).waitFor();
    for (const page of [groupA, otherProjector]) {
      for (const url of [galleryUrl, feedUrl, selectedUrl]) {
        assert.equal(await page.evaluate(async (path) => (await fetch(path)).status, url), 403);
      }
    }
  });
}

async function projectSiteAComparison(projector) {
  await projector.getByRole('link', { name: /Shared comparisons|已分享的比較結果/ }).click();
  const galleryUrl = projector.url();
  await projector.getByRole('link', { name: /Site A:|場地 A：/ }).click();
  await projector.getByRole('heading', { name: /Site A:|場地 A：/ }).waitFor();
  return galleryUrl;
}

test('sharing from an older group tab captures its displayed crossing and preserves the newer draft', { timeout: 30000 }, async (t) => {
  const { groupAt, projector } = await startInvestigation(t);
  const older = await groupAt('A');
  await older.getByLabel('Construction access route', { exact: true }).selectOption('valley');
  await older.getByRole('button', { name: 'Test crossing' }).click();
  await older.getByRole('list', { name: 'Map key' }).getByText('Bridge supports').waitFor();
  await older.getByLabel('Railway alignment').selectOption('north');

  const newer = await older.context().newPage();
  await newer.goto(older.url());
  await newer.getByLabel('Crossing type').selectOption('tunnel');
  await newer.getByRole('button', { name: 'Test crossing' }).click();
  await newer.getByRole('list', { name: 'Map key' }).getByText('Tunnel entrances').waitFor();
  await newer.getByLabel('Railway alignment').selectOption('south');
  await newer.getByRole('button', { name: 'Without proposed works' }).click();

  await older.getByRole('button', { name: 'Share comparison' }).click();
  await older.getByRole('status').getByText('Comparison shared with your teacher.').waitFor();
  await projectSiteAComparison(projector);
  await projector.getByText('Central crossing · Elevated railway · Valley approach', { exact: true }).waitFor();
  const proposed = projector.getByRole('region', { name: 'With proposed works' });
  assert.equal(await proposed.locator('.map-supports:visible').count(), 5);
  await newer.reload();
  assert.equal(await newer.getByLabel('Railway alignment').inputValue(), 'south');
  assert.equal(await newer.getByLabel('Crossing type').inputValue(), 'tunnel');
});

test('signing out clears the open comparison and gallery before the projector is reused', { timeout: 30000 }, async (t) => {
  const { teacher, projector, groupAt, origin, issueCredential } = await startInvestigation(t);
  const group = await groupAt('A');
  await group.getByRole('button', { name: 'Share comparison' }).click();
  const galleryUrl = await projectSiteAComparison(projector);
  const gallery = await teacher.context().newPage();
  await gallery.goto(galleryUrl);
  const listed = gallery.getByRole('link', { name: /Site A: Central wetland/ });
  const projected = projector.getByRole('heading', { name: 'Site A: Central wetland' });
  await listed.waitFor();
  await projected.waitFor();

  await teacher.getByRole('button', { name: 'Sign out' }).click();
  await Promise.all([listed, projected].map(content => content.waitFor({ state: 'hidden', timeout: 8000 })));
  await group.reload();
  await group.getByRole('button', { name: 'Share comparison' }).waitFor();
  await openClass(teacher, origin, issueCredential());
  assert.equal(await gallery.getByText('Site A: Central wetland', { exact: true }).count(), 0);
  assert.equal(await projector.getByRole('group', { name: 'Spring site map' }).count(), 0);
});

test('reopening the gallery and selected comparison of a closed Traditional Chinese class shows Chinese', { timeout: 30000 }, async (t) => {
  const { teacher, projector, groupAt } = await startInvestigation(t, '繁體中文');
  const group = await groupAt('A');
  await group.getByRole('button', { name: '分享比較結果' }).click();
  const galleryUrl = await projectSiteAComparison(projector);
  const comparisonUrl = projector.url();
  await teacher.getByRole('button', { name: '結束課堂' }).click();

  const returning = await teacher.context().newPage();
  for (const url of [galleryUrl, comparisonUrl]) {
    const response = await returning.goto(url);
    assert.equal(response.status(), 410);
    assert.equal(await returning.locator('html').getAttribute('lang'), 'zh-Hant');
    await returning.getByRole('heading', { name: '這個課堂已結束' }).waitFor();
  }
});

const swapNotification = '**/join/*/status?wait=swap';

async function delayClassroomRequest(t, origin, shouldHold) {
  let arrived, release;
  const reached = new Promise(resolve => { arrived = resolve; });
  const gate = new Promise(resolve => { release = resolve; });
  // Delay at the server so Chromium can still run the document awaiting navigation.
  const proxy = createServer(async (incoming, outgoing) => {
    const { pathname, search } = new URL(incoming.url, origin);
    const target = new URL(origin);
    target.pathname = pathname;
    target.search = search;
    if (shouldHold(incoming.method, target)) {
      arrived(target);
      await gate;
    }
    if (outgoing.destroyed) return;
    const headers = { ...incoming.headers, host: target.host };
    if (headers.origin === proxyOrigin) headers.origin = origin;
    const forwarded = request(target, { method: incoming.method, headers }, response => {
      outgoing.writeHead(response.statusCode, response.headers);
      response.pipe(outgoing);
    });
    forwarded.on('error', () => outgoing.destroy());
    outgoing.on('close', () => forwarded.destroy());
    incoming.pipe(forwarded);
  });
  proxy.listen(0, '127.0.0.1');
  await once(proxy, 'listening');
  const proxyOrigin = `http://127.0.0.1:${proxy.address().port}`;
  t.after(() => {
    release();
    proxy.close();
    proxy.closeAllConnections();
  });
  const url = address => new URL(address.replace(origin, proxyOrigin)).href;
  return { url, reached, release };
}

async function holdRequest(page, url) {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route(url, async route => {
    await gate;
    await route.continue();
  }, { times: 1 });
  return release;
}

async function watchOpeningNotice(page) {
  // Report from the original document while the replacement response is still held.
  const prefix = 'Opening notice state ';
  await page.evaluate(prefix => {
    const notice = document.querySelector('[data-site-check]');
    const observer = new MutationObserver(() => {
      if (notice.hidden || notice.textContent !== notice.dataset.siteOpening) return;
      observer.disconnect();
      requestAnimationFrame(() => requestAnimationFrame(report));
    });
    function report() {
      const site = document.querySelector('[data-group-site]');
      const isVisible = element => element.getClientRects().length > 0;
      console.debug(prefix + JSON.stringify({
        site: site.dataset.groupSite,
        text: document.body.innerText,
        map: isVisible(site.querySelector('.site-map')),
        controls: Array.from(site.querySelectorAll('button, select, a')).some(isVisible),
        focusInSite: site.contains(document.activeElement),
      }));
    }
    observer.observe(notice, { attributes: true, childList: true });
  }, prefix);
  return () => page.waitForEvent('console', event => event.text().startsWith(prefix))
    .then(event => JSON.parse(event.text().slice(prefix.length)));
}

test('the outstanding swap notification hides the old map while the partner site loads', { timeout: 30000 }, async (t) => {
  const { groupAt, teacher, joinUrl, origin } = await startInvestigation(t);
  const assignment = `${new URL(joinUrl).pathname}/status?wait=swap`;
  assert.equal((await teacher.request.get(new URL(assignment, joinUrl).href, { timeout: 3000 })).status(), 403);
  const navigation = await delayClassroomRequest(t, origin, (method, url) =>
    method === 'GET' && url.pathname === new URL(joinUrl).pathname && url.searchParams.get('notice') === 'swapped');
  const groupA = await groupAt('A', navigation.url(joinUrl));
  const groupB = await groupAt('B');
  await groupB.getByLabel('Railway alignment').selectOption('north');
  await groupB.getByRole('button', { name: 'Test crossing' }).click();
  await groupA.getByRole('button', { name: '繁體中文' }).click();
  await groupA.getByLabel('鐵路形式').selectOption('tunnel');

  // Only the first watch can deliver the swap. A later polling cycle cannot satisfy this test.
  let watches = 0;
  await groupA.route(swapNotification, route => {
    if (++watches === 1) return route.continue();
  });
  await Promise.all([
    groupA.waitForRequest(swapNotification),
    groupA.getByRole('button', { name: '儲存走線以交換場地' }).click(),
  ]);
  await groupA.getByLabel('鐵路形式').focus();

  const openingNotice = await watchOpeningNotice(groupA);
  try {
    const [state, destination] = await Promise.all([
      openingNotice(),
      navigation.reached,
      teacher.getByRole('button', { name: 'Pass the City' }).click(),
    ]);
    assert.equal(state.site, 'A', 'The original document should still be on screen');
    assert.doesNotMatch(state.text, /場地 A：中央濕地/);
    assert.match(state.text, /正在開啟對方的場地⋯/);
    assert.equal(state.map, false);
    assert.equal(state.controls, false);
    assert.equal(state.focusInSite, false);
    assert.equal(destination.searchParams.get('lang'), 'zh-Hant');
    await groupB.getByRole('heading', { name: 'Site A: Central wetland' }).waitFor();
    assert.equal(await groupB.getByLabel('Railway alignment').inputValue(), 'north');
  } finally {
    navigation.release();
  }
  await groupA.getByRole('heading', { name: '場地 B：河畔濕地' }).waitFor();
  assert.equal(await groupA.getByLabel('鐵路形式').inputValue(), 'tunnel');
  assert.ok(await groupA.locator('.site-map').isVisible());
  const current = await groupA.request.get(new URL(assignment, joinUrl).href, { timeout: 3000 });
  assert.equal(current.status(), 204);
  assert.equal(current.headers()['x-current-site'], 'B');
});

test('an offline group hides its map, preserves an unchanged draft, and catches up to a swap', { timeout: 30000 }, async (t) => {
  const { groupAt, teacher } = await startInvestigation(t);
  const group = await groupAt('A');
  await groupAt('B');
  const checking = group.getByText('Checking your current site…', { exact: true });
  const original = group.getByRole('heading', { name: 'Site A: Central wetland' });
  const alignment = group.getByLabel('Railway alignment');
  const assignment = '**/join/*/status';
  await alignment.selectOption('north');

  await group.context().setOffline(true);
  await checking.waitFor();
  const releaseUnchanged = await holdRequest(group, assignment);
  try {
    await Promise.all([group.waitForRequest(assignment), group.context().setOffline(false)]);
    await checking.waitFor();
    assert.ok(!(await group.locator('.site-map').isVisible()));
    assert.ok(!(await alignment.isVisible()));
  } finally {
    releaseUnchanged();
  }
  await original.waitFor();
  assert.equal(await alignment.inputValue(), 'north');

  await group.context().setOffline(true);
  await checking.waitFor();
  await teacher.getByRole('button', { name: 'Pass the City' }).click();
  const releaseSwapped = await holdRequest(group, assignment);
  try {
    await Promise.all([group.waitForRequest(assignment), group.context().setOffline(false)]);
    await checking.waitFor();
    assert.ok(!(await original.isVisible()));
    assert.ok(!(await group.locator('.site-map').isVisible()));
  } finally {
    releaseSwapped();
  }
  await group.getByRole('heading', { name: 'Site B: Riverside wetland' }).waitFor();
  assert.equal(await alignment.inputValue(), 'central');
});

test('reconnecting after class ends shows the group’s chosen closing language', { timeout: 30000 }, async (t) => {
  const { groupAt, teacher } = await startInvestigation(t);
  const group = await groupAt('A');
  await groupAt('B');
  await group.getByRole('button', { name: '繁體中文' }).click();
  await group.getByRole('heading', { name: '場地 A：中央濕地' }).waitFor();
  await group.context().setOffline(true);
  const checking = group.getByText('正在確認你們的場地⋯', { exact: true });
  await checking.waitFor();
  await teacher.getByRole('button', { name: 'End class' }).click();

  const assignment = '**/join/*/status';
  const releaseCheck = await holdRequest(group, assignment);
  try {
    await Promise.all([group.waitForRequest(assignment), group.context().setOffline(false)]);
    await checking.waitFor();
    assert.ok(!(await group.locator('.site-map').isVisible()));
  } finally {
    releaseCheck();
  }
  await group.getByRole('heading', { name: '這個課堂已結束' }).waitFor();
  assert.equal(await group.locator('html').getAttribute('lang'), 'zh-Hant');
});

test('returning to a starting site with browser Back keeps the map hidden until revalidation', { timeout: 30000 }, async (t) => {
  const { groupAt, origin } = await startInvestigation(t);
  const group = await groupAt('A');
  const alignment = group.getByLabel('Railway alignment');
  await alignment.selectOption('north');
  await group.goto(origin);
  const assignment = '**/join/*/status';
  const releaseCheck = await holdRequest(group, assignment);
  try {
    await Promise.all([group.waitForRequest(assignment), group.goBack({ waitUntil: 'domcontentloaded' })]);
    await group.getByText('Checking your current site…', { exact: true }).waitFor();
    assert.ok(!(await group.locator('.site-map').isVisible()));
    assert.ok(!(await alignment.isVisible()));
  } finally {
    releaseCheck();
  }
  await group.getByRole('heading', { name: 'Site A: Central wetland' }).waitFor();
  assert.equal(await alignment.inputValue(), 'north');
});

test('browser Back after a swap restores the carried crossing in the map and controls', { timeout: 30000 }, async (t) => {
  const { groupAt, teacher, origin, joinUrl } = await startInvestigation(t);
  const saved = await groupAt('A');
  const tested = await groupAt('B');
  const railway = page => page.locator('.site-map .map-railway')
    .evaluateAll(lines => lines.map(line => line.getAttribute('points')));
  await saved.getByRole('button', { name: '繁體中文' }).click();
  await saved.getByRole('button', { name: '儲存走線以交換場地' }).click();
  await saved.getByRole('list', { name: '圖例' }).getByText('橋墩', { exact: true }).waitFor();
  const savedRailway = await railway(saved);
  await saved.getByLabel('鐵路走線').selectOption('north');
  await saved.getByLabel('鐵路形式').selectOption('tunnel');
  await tested.getByLabel('Railway alignment').selectOption('north');
  await tested.getByLabel('Crossing type').selectOption('tunnel');
  await tested.getByRole('button', { name: 'Test crossing' }).click();
  await tested.getByRole('list', { name: 'Map key' }).getByText('Tunnel entrances', { exact: true }).waitFor();
  const testedRailway = await railway(tested);
  await tested.getByLabel('Railway alignment').selectOption('south');
  await tested.getByLabel('Crossing type').selectOption('elevated');
  const joinPath = new URL(joinUrl).pathname;
  await saved.route(url => url.pathname === joinPath, route => route.continue());
  await Promise.all([saved.goto(origin), tested.goto(origin)]);
  await teacher.getByRole('button', { name: 'Pass the City' }).click();

  for (const [group, heading, alignment, crossing, mapKey, work, testButton, carriedRailway] of [
    [saved, '場地 B：河畔濕地', 'central', 'elevated', '圖例', '橋墩', '測試走線', savedRailway],
    [tested, 'Site A: Central wetland', 'north', 'tunnel', 'Map key', 'Tunnel entrances', 'Test crossing', testedRailway],
  ]) {
    const assertCrossing = async page => {
      await page.getByRole('heading', { name: heading }).waitFor();
      await page.getByRole('list', { name: mapKey }).getByText(work, { exact: true }).waitFor();
      assert.equal(await page.getByLabel(/Railway alignment|鐵路走線/).inputValue(), alignment);
      assert.equal(await page.getByLabel(/Crossing type|鐵路形式/).inputValue(), crossing);
      assert.deepEqual(await railway(page), carriedRailway);
    };
    await group.goBack({ waitUntil: 'commit' });
    await assertCrossing(group);
    await group.getByRole('button', { name: testButton }).click();
    const reopened = await group.context().newPage();
    await reopened.goto(joinUrl);
    await assertCrossing(reopened);
  }
});

test('browser Back while offline restores the same-site draft on reconnect', { timeout: 30000 }, async (t) => {
  const { groupAt, origin, joinUrl } = await startInvestigation(t);
  const group = await groupAt('A');
  await groupAt('B');
  const alignment = group.getByLabel('Railway alignment');
  const crossing = group.getByLabel('Crossing type');
  await alignment.selectOption('north');
  await crossing.selectOption('tunnel');
  const otherTab = await group.context().newPage();
  await otherTab.goto(joinUrl);
  await otherTab.getByRole('heading', { name: 'Site A: Central wetland' }).waitFor();
  assert.equal(await otherTab.getByLabel('Railway alignment').inputValue(), 'central');

  await group.goto(origin);
  await group.context().setOffline(true);
  try {
    await group.goBack({ waitUntil: 'commit' });
    assert.ok(!(await alignment.isVisible()));
  } catch (error) {
    assert.match(error.message, /ERR_INTERNET_DISCONNECTED/);
  } finally {
    await group.context().setOffline(false);
  }

  await group.getByRole('heading', { name: 'Site A: Central wetland' }).waitFor();
  assert.equal(await alignment.inputValue(), 'north');
  assert.equal(await crossing.inputValue(), 'tunnel');
});

test('a slow assignment response finishes revalidation and reveals the crossing controls', { timeout: 30000 }, async (t) => {
  const { groupAt, joinUrl } = await startInvestigation(t, '繁體中文');
  const group = await groupAt('A');
  await groupAt('B');
  const alignment = group.getByLabel('鐵路走線');
  await alignment.selectOption('north');
  await group.context().setOffline(true);
  const checking = group.getByText('正在確認你們的場地⋯', { exact: true });
  await checking.waitFor();

  const assignment = '**/join/*/status';
  await group.route(assignment, async route => {
    const response = await route.fetch();
    await delay(5500);
    await route.fulfill({ response }).catch(() => {});
  });
  await Promise.all([group.waitForRequest(assignment), group.context().setOffline(false)]);
  assert.ok(await checking.isVisible());
  assert.ok(!(await group.locator('.site-map').isVisible()));
  assert.ok(!(await alignment.isVisible()));
  await group.getByRole('heading', { name: '場地 A：中央濕地' }).waitFor({ timeout: 12000 });
  assert.equal(await alignment.inputValue(), 'north');
  await group.getByRole('button', { name: '測試走線' }).click();
  const reopened = await group.context().newPage();
  await reopened.goto(joinUrl);
  await reopened.getByRole('heading', { name: '場地 A：中央濕地' }).waitFor();
  assert.equal(await reopened.getByLabel('鐵路走線').inputValue(), 'north');
});

test('an interrupted status script download recovers the partner site on reconnect', { timeout: 30000 }, async (t) => {
  const { groupAt, teacher } = await startInvestigation(t);
  const group = await groupAt('A');
  const partner = await groupAt('B');
  await group.getByLabel('Crossing type').selectOption('tunnel');
  await group.getByRole('button', { name: 'Save for swap' }).click();
  await group.getByRole('status').getByText('Crossing saved for Pass the City.').waitFor();

  let interrupted;
  const disconnected = new Promise(resolve => { interrupted = resolve; });
  await group.route('**/class-status.js', async route => {
    await group.context().setOffline(true);
    await route.abort('internetdisconnected');
    interrupted();
  }, { times: 1 });
  await group.reload({ waitUntil: 'commit' });
  await disconnected;
  await group.getByText('Checking your current site…', { exact: true }).waitFor();
  assert.ok(!(await group.locator('.site-map').isVisible()));
  assert.ok(!(await group.getByLabel('Crossing type').isVisible()));
  await teacher.getByRole('button', { name: 'Pass the City' }).click();
  await partner.getByRole('heading', { name: 'Site A: Central wetland' }).waitFor();

  await group.context().setOffline(false);
  await group.getByRole('heading', { name: 'Site B: Riverside wetland' }).waitFor();
  assert.equal(await group.getByLabel('Crossing type').inputValue(), 'tunnel');
  await group.getByRole('list', { name: 'Map key' }).getByText('Tunnel entrances', { exact: true }).waitFor();
});

for (const [startingLanguage, chosenLanguage, chosenTag, closeHeading, operation] of [
  ['English', '繁體中文', 'zh-Hant', '這個課堂已結束', 'ends'],
  ['繁體中文', 'English', 'en', 'This class is closed', 'expires'],
]) {
  test(`browser Back after class ${operation} opens a fresh closing page in ${chosenLanguage}`, { timeout: 30000 }, async (t) => {
    const options = operation === 'expires' ? ['--duration-seconds', '6'] : [];
    const { groupAt, teacher, origin, joinUrl } = await startInvestigation(t, startingLanguage, ...options);
    const group = await groupAt('A');
    const partner = await groupAt('B');
    await group.getByRole('button', { name: chosenLanguage }).click();
    await group.getByRole('heading', { name: /^(?:Site|場地) A[:：]/ }).waitFor();
    assert.equal(await group.locator('html').getAttribute('lang'), chosenTag);

    // Route the history request to bypass Chromium's HTTP cache.
    await group.route(`${new URL(joinUrl).origin}${new URL(joinUrl).pathname}*`, route => route.continue());
    await group.goto(origin);
    if (operation === 'ends') await teacher.getByRole('button', { name: 'End class' }).click();
    await partner.getByRole('heading', { name: /This class is closed|這個課堂已結束/ }).waitFor({ timeout: 9000 });

    const response = await group.goBack({ waitUntil: 'domcontentloaded' });
    assert.equal(response?.status(), 410);
    await group.getByRole('heading', { name: closeHeading }).waitFor();
    assert.equal(await group.locator('html').getAttribute('lang'), chosenTag);
  });
}

test('Pass the City applies each saved crossing at the partner site', { timeout: 30000 }, async (t) => {
  const { groupAt, joinUrl, teacher } = await startInvestigation(t);
  const groupA = await groupAt('A');
  const passTheCity = teacher.getByRole('button', { name: 'Pass the City' });
  await passTheCity.click();
  await teacher.getByRole('alert').getByText('Both groups need to join before you can swap sites.').waitFor();
  const groupB = await groupAt('B');

  const timing = groupA.getByLabel('Construction season', { exact: true });
  const hasTiming = await timing.count() > 0;
  if (hasTiming) {
    await timing.selectOption('summer');
    await groupA.getByRole('button', { name: 'Summer', exact: true }).click();
  }
  await groupA.getByLabel('Crossing type').selectOption('tunnel');
  await groupA.getByLabel('Construction access route', { exact: true }).selectOption('valley');
  await groupA.getByRole('button', { name: 'Save for swap' }).click();
  await groupA.getByRole('status').getByText('Crossing saved for Pass the City.').waitFor();
  await groupA.getByText('Possible disturbance', { exact: true }).waitFor();

  await groupB.getByLabel('Railway alignment').selectOption('north');
  await groupB.getByRole('button', { name: 'Save for swap' }).click();
  await groupB.getByRole('status').getByText('Crossing saved for Pass the City.').waitFor();
  await groupB.getByText('Possible disturbance', { exact: true }).waitFor();

  await groupA.getByLabel('Railway alignment').selectOption('south');
  await groupA.getByLabel('Crossing type').selectOption('elevated');
  if (hasTiming) await timing.selectOption('winter');
  await groupA.getByRole('button', { name: 'Test crossing' }).click();
  await groupA.getByRole('list', { name: 'Map key' }).getByText('Elevated railway', { exact: true }).waitFor();
  await groupA.getByRole('button', { name: 'Without proposed works' }).click();
  const join = new URL(joinUrl);
  const code = join.pathname.split('/').pop();
  const passRequest = { form: { code }, headers: { Origin: join.origin }, maxRedirects: 0 };
  const forbidden = await groupB.request.post(`${join.origin}/teacher/pass-the-city`, passRequest);
  assert.equal(forbidden.status(), 403);

  await passTheCity.click();
  await teacher.getByRole('status').getByText('Both groups have moved to their partner sites.').waitFor();
  await Promise.all([
    groupA.getByRole('heading', { name: 'Site B: Riverside wetland' }).waitFor(),
    groupB.getByRole('heading', { name: 'Site A: Central wetland' }).waitFor(),
  ]);
  for (const [group, alignment, crossing, access, work, season] of [
    [groupA, 'central', 'tunnel', 'valley', 'Tunnel entrances', 'summer'],
    [groupB, 'north', 'elevated', 'east', 'Bridge supports', 'spring'],
  ]) {
    assert.equal(await group.getByLabel('Railway alignment').inputValue(), alignment);
    assert.equal(await group.getByLabel('Crossing type').inputValue(), crossing);
    assert.equal(await group.getByLabel('Construction access route', { exact: true }).inputValue(), access);
    if (hasTiming) {
      assert.equal(await group.getByLabel('Construction season', { exact: true }).inputValue(), season);
    }
    await group.getByRole('list', { name: 'Map key' }).getByText(work, { exact: true }).waitFor();
    await group.getByText('No modelled overlap', { exact: true }).waitFor();
  }

  const repeated = await teacher.request.post(`${join.origin}/teacher/pass-the-city`, passRequest);
  assert.equal(repeated.status(), 303);
  await groupB.reload();
  await groupB.getByRole('heading', { name: 'Site A: Central wetland' }).waitFor();

  await groupA.getByRole('button', { name: '繁體中文' }).click();
  await groupA.getByRole('heading', { name: '場地 B：河畔濕地' }).waitFor();
  assert.equal(await groupA.getByLabel('鐵路走線', { exact: true }).inputValue(), 'central');
  assert.equal(await groupA.getByLabel('鐵路形式').inputValue(), 'tunnel');
  assert.equal(await groupA.getByLabel('施工通道', { exact: true }).inputValue(), 'valley');
  if (hasTiming) assert.equal(await groupA.getByLabel('施工季節', { exact: true }).inputValue(), 'summer');
  await groupA.getByRole('button', { name: '重播走線測試' }).click();
  await groupA.getByRole('status').getByText('已重播走線測試。').waitFor();
  await groupA.getByText('模型未顯示重疊', { exact: true }).waitFor();
  await groupA.getByLabel('鐵路走線', { exact: true }).selectOption('north');
  await groupA.getByRole('button', { name: '測試走線' }).click();
  await groupA.getByText('可能造成滋擾', { exact: true }).waitFor();
  await groupA.getByRole('button', { name: '重設走線' }).click();
  await groupA.getByRole('heading', { name: '場地 B：河畔濕地' }).waitFor();
  assert.equal(await groupA.getByLabel('鐵路形式').inputValue(), 'elevated');
  await groupA.getByText('模型未顯示重疊', { exact: true }).waitFor();
});

test('an unsaved group can swap without a stale form replacing its last tested crossing', { timeout: 30000 }, async (t) => {
  const { groupAt, joinUrl, teacher } = await startInvestigation(t);
  const groupA = await groupAt('A');
  const groupB = await groupAt('B');
  await groupA.getByLabel('Crossing type').selectOption('tunnel');
  await groupA.getByRole('button', { name: 'Test crossing' }).click();
  await groupA.getByRole('list', { name: 'Map key' }).getByText('Tunnel entrances', { exact: true }).waitFor();
  await teacher.getByRole('button', { name: 'Pass the City' }).click();

  const join = new URL(joinUrl);
  const stale = await groupA.request.post(`${join.origin}${join.pathname}/design`, {
    form: { site: 'A', alignment: 'south', crossing_type: 'elevated', access: 'valley', save: '1' },
    headers: { Origin: join.origin },
    maxRedirects: 0,
  });
  assert.equal(stale.status(), 303);
  await groupA.getByRole('heading', { name: 'Site B: Riverside wetland' }).waitFor();
  await groupB.getByRole('heading', { name: 'Site A: Central wetland' }).waitFor();
  assert.equal(await groupA.getByLabel('Railway alignment').inputValue(), 'central');
  assert.equal(await groupA.getByLabel('Crossing type').inputValue(), 'tunnel');
  assert.equal(await groupA.getByLabel('Construction access route').inputValue(), 'east');
});

test('a language switch during the swap keeps the saved crossing and both partner screens close with the class', { timeout: 30000 }, async (t) => {
  const { groupAt, teacher } = await startInvestigation(t);
  const groupA = await groupAt('A');
  const groupB = await groupAt('B');

  // Delay the swap notification so the group submits the form it still sees at Site A.
  await groupA.route(swapNotification, () => {});
  await groupA.getByLabel('Crossing type').selectOption('tunnel');
  await groupA.getByRole('button', { name: 'Save for swap' }).click();
  await groupA.getByText('Crossing saved for Pass the City.', { exact: true }).waitFor();
  await groupA.getByLabel('Crossing type').selectOption('elevated');
  await teacher.getByRole('button', { name: 'Pass the City' }).click();
  await groupA.getByRole('button', { name: '繁體中文' }).click();
  await groupA.getByRole('heading', { name: '場地 B：河畔濕地' }).waitFor();
  assert.equal(await groupA.getByLabel('鐵路形式').inputValue(), 'tunnel');
  await groupA.unroute(swapNotification);
  await groupB.getByRole('heading', { name: 'Site A: Central wetland' }).waitFor();

  await teacher.getByRole('button', { name: 'End class' }).click();
  await Promise.all([
    groupA.getByRole('heading', { name: '這個課堂已結束' }).waitFor(),
    groupB.getByRole('heading', { name: 'This class is closed' }).waitFor(),
  ]);
});

test('Pass the City keeps the original Site A comparison on the projector while the group shares Site B', { timeout: 30000 }, async (t) => {
  const { groupAt, teacher, projector } = await startInvestigation(t);
  const group = await groupAt('A');
  const partner = await groupAt('B');
  await group.getByLabel('Crossing type').selectOption('tunnel');
  await group.getByLabel('Construction access route', { exact: true }).selectOption('valley');
  await group.getByRole('button', { name: 'Save for swap' }).click();
  const evidence = 'Construction access route overlaps modelled nesting habitat.';
  await group.getByText('Possible disturbance', { exact: true }).click();
  await group.getByText(evidence, { exact: true }).waitFor();
  const originalAccess = await rectangleGeometry(group.locator('.site-map .map-access'));
  const originalHabitat = await rectangleGeometry(group.locator('.site-map .map-habitat'));
  assert.equal(originalAccess.length, 3);
  assert.equal(originalHabitat.length, 1);
  await group.getByRole('button', { name: 'Share comparison' }).click();
  await projectSiteAComparison(projector);
  const originalUrl = projector.url();
  const proposed = projector.getByRole('region', { name: 'With proposed works' });
  const baseline = projector.getByRole('region', { name: 'Without proposed works' });
  await proposed.getByText(evidence, { exact: true }).waitFor();

  await teacher.getByRole('button', { name: 'Pass the City' }).click();
  await group.getByRole('heading', { name: 'Site B: Riverside wetland' }).waitFor();
  await partner.getByRole('heading', { name: 'Site A: Central wetland' }).waitFor();
  await group.getByText('No modelled overlap', { exact: true }).waitFor();
  await group.getByLabel('Railway alignment').selectOption('south');
  await group.getByLabel('Crossing type').selectOption('elevated');
  await group.getByLabel('Construction access route', { exact: true }).selectOption('east');
  await group.getByRole('button', { name: 'Test crossing' }).click();
  assert.notDeepEqual(await rectangleGeometry(group.locator('.site-map .map-access')), originalAccess);
  const partnerHabitat = await rectangleGeometry(group.locator('.site-map .map-habitat'));
  assert.notDeepEqual(partnerHabitat, originalHabitat);
  await group.getByRole('button', { name: 'Share comparison' }).click();
  await group.getByRole('status').getByText('Comparison shared with your teacher.').waitFor();
  assert.equal(projector.url(), originalUrl);
  await proposed.getByText(evidence, { exact: true }).waitFor();

  await projector.getByRole('link', { name: 'Back to shared comparisons' }).click();
  await projector.getByRole('link', { name: /Site B: Riverside wetland/ }).click();
  await projector.getByRole('heading', { name: 'Site B: Riverside wetland' }).waitFor();
  await proposed.getByText('No modelled overlap', { exact: true }).waitFor();
  assert.deepEqual(await rectangleGeometry(proposed.locator('.map-habitat')), partnerHabitat);
  await projector.getByRole('link', { name: 'Back to shared comparisons' }).click();
  await projector.getByRole('link', { name: /Site A: Central wetland/ }).click();
  assert.equal(projector.url(), originalUrl);
  await projector.getByText('Central crossing · Tunnel · Valley approach', { exact: true }).waitFor();
  await proposed.getByText(evidence, { exact: true }).waitFor();
  assert.deepEqual(await rectangleGeometry(proposed.locator('.map-access')), originalAccess);
  assert.deepEqual(await rectangleGeometry(proposed.locator('.map-habitat')), originalHabitat);
  assert.deepEqual(await rectangleGeometry(baseline.locator('.map-habitat')), originalHabitat);
  assert.equal(await baseline.locator('.map-railway').count(), 0);
});

test('a pre-swap tab can share Site A without restoring its outdated draft at Site B', { timeout: 30000 }, async (t) => {
  const { groupAt, teacher, projector, origin } = await startInvestigation(t);
  const group = await groupAt('A');
  const partner = await groupAt('B');
  await partner.getByRole('button', { name: 'Share comparison' }).click();
  await projector.getByRole('link', { name: 'Shared comparisons' }).click();
  await projector.getByRole('link', { name: /Site B: Riverside wetland/ }).click();
  const selectedBeforeSwap = projector.url();
  await group.getByRole('button', { name: 'Save for swap' }).click();
  await group.getByLabel('Crossing type').selectOption('tunnel');
  await group.getByLabel('Construction access route', { exact: true }).selectOption('valley');
  await group.getByRole('button', { name: 'Test crossing' }).click();

  const share = await delayClassroomRequest(t, origin, (method, url) =>
    method === 'POST' && url.pathname.endsWith('/share'));
  const stale = await group.context().newPage();
  const releaseNotification = await holdRequest(stale, swapNotification);
  await stale.goto(share.url(group.url()));
  await stale.getByRole('heading', { name: 'Site A: Central wetland' }).waitFor();
  await stale.getByLabel('Railway alignment').selectOption('north');
  const openingNotice = await watchOpeningNotice(stale);
  try {
    await Promise.all([
      share.reached,
      stale.getByRole('button', { name: 'Share comparison' }).click({ noWaitAfter: true }),
    ]);
    await teacher.getByRole('button', { name: 'Pass the City' }).click();
    await group.getByRole('heading', { name: 'Site B: Riverside wetland' }).waitFor();
    assert.equal(await group.getByLabel('Crossing type').inputValue(), 'elevated');
    await group.getByLabel('Railway alignment').selectOption('south');
    await group.getByRole('button', { name: 'Without proposed works' }).click();

    const notice = openingNotice();
    const notification = stale.waitForResponse(swapNotification);
    releaseNotification();
    const [state, response] = await Promise.all([notice, notification]);
    assert.equal(response.headers()['x-current-site'], 'B');
    assert.match(state.text, /Opening your partner site…/);
    assert.equal(state.controls, false);
  } finally {
    releaseNotification();
    share.release();
  }

  await stale.getByRole('heading', { name: 'Site B: Riverside wetland' }).waitFor();
  await stale.getByRole('status').getByText('Comparison shared with your teacher.').waitFor();
  assert.equal(await stale.getByLabel('Railway alignment').inputValue(), 'south');
  assert.equal(await stale.getByRole('button', { name: 'Without proposed works' }).getAttribute('aria-pressed'), 'true');
  assert.equal(projector.url(), selectedBeforeSwap);
  await projector.getByRole('heading', { name: 'Site B: Riverside wetland' }).waitFor();
  await projector.getByRole('link', { name: 'Back to shared comparisons' }).click();
  await projector.getByRole('link', { name: /Site A: Central wetland/ }).click();
  const selected = projector.url();
  await projector.getByText('Central crossing · Tunnel · Valley approach', { exact: true }).waitFor();
  await projector.getByRole('region', { name: 'With proposed works' })
    .getByText('Construction access route overlaps modelled nesting habitat.', { exact: true }).waitFor();
  await group.reload();
  await group.getByRole('heading', { name: 'Site B: Riverside wetland' }).waitFor();
  assert.equal(await group.getByLabel('Railway alignment').inputValue(), 'south');
  assert.equal(await group.getByLabel('Crossing type').inputValue(), 'elevated');
  assert.equal(await group.getByRole('button', { name: 'Without proposed works' }).getAttribute('aria-pressed'), 'true');

  await partner.getByRole('button', { name: 'Share comparison' }).click();
  await partner.getByRole('status').getByText('Comparison shared with your teacher.').waitFor();
  assert.equal(projector.url(), selected);
  await projector.getByText('Central crossing · Tunnel · Valley approach', { exact: true }).waitFor();
});

test('a group that stops Share comparison still moves to its partner site', { timeout: 30000 }, async (t) => {
  const { groupAt, teacher, joinUrl, origin } = await startInvestigation(t);
  const share = await delayClassroomRequest(t, origin, (method, url) =>
    method === 'POST' && url.pathname.endsWith('/share'));
  const group = await groupAt('A', share.url(joinUrl));
  const partner = await groupAt('B');
  await group.getByLabel('Crossing type').selectOption('tunnel');
  await group.getByRole('button', { name: 'Save for swap' }).click();
  await group.getByRole('status').getByText('Crossing saved for Pass the City.').waitFor();
  const browserSession = await group.context().newCDPSession(group);
  try {
    await Promise.all([
      share.reached,
      group.getByRole('button', { name: 'Share comparison' }).click({ noWaitAfter: true }),
    ]);
    await browserSession.send('Page.stopLoading');
    await teacher.getByRole('button', { name: 'Pass the City' }).click();
    await partner.getByRole('heading', { name: 'Site A: Central wetland' }).waitFor();
    await group.getByRole('heading', { name: 'Site B: Riverside wetland' }).waitFor();
    assert.equal(await group.getByLabel('Crossing type').inputValue(), 'tunnel');
  } finally {
    share.release();
  }
});
