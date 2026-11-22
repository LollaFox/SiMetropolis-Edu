import assert from 'node:assert/strict';
import { execFileSync, spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdtemp, rm } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createInterface } from 'node:readline';
import { test } from 'node:test';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const root = new URL('../', import.meta.url);
const python = process.env.PYTHON || 'python3';

async function classroom(t, ...options) {
  const data = await mkdtemp(join(tmpdir(), 'long-valley-test-'));
  t.after(() => rm(data, { recursive: true, force: true }));
  const command = ['-B', '-m', 'classroom', '--data-dir', data];
  function issueCredential() {
    return execFileSync(python, [...command, 'issue-teacher-credential'], {
      cwd: root, encoding: 'utf8',
    }).trim();
  }
  const server = spawn(python, [...command, 'serve', '--port', '0', ...options], {
    cwd: root, stdio: ['ignore', 'pipe', 'inherit'],
  });
  const closed = once(server, 'close');
  t.after(async () => {
    server.kill();
    await closed;
  });
  const output = createInterface({ input: server.stdout });
  const origin = await Promise.race([
    once(output, 'line').then(([line]) => new URL(line).origin),
    closed.then(([code]) => { throw new Error(`Classroom exited with code ${code}`); }),
  ]);
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, timeout: 10000 });
  t.after(() => browser.close());
  return { browser, issueCredential, origin };
}

async function openClass(page, origin, credential, language = 'English') {
  await page.goto(`${origin}/teacher`);
  if (language === '繁體中文') {
    await page.getByRole('link', { name: '繁體中文' }).click();
  }
  await page.getByLabel(/Teacher credential|教師憑證/).fill(credential);
  await page.getByRole('button', { name: /Sign in|登入/ }).click();
  await page.getByLabel(/Starting language|起始語言/).selectOption({ label: language });
  await page.getByRole('button', { name: /Start class|開始課堂/ }).click();
}

async function participant(browser) {
  const page = await browser.newPage();
  page.setDefaultTimeout(5000);
  return page;
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
