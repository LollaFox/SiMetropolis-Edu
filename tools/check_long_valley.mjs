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

async function startInvestigation(t) {
  const { browser, issueCredential, origin } = await classroom(t);
  const teacher = await participant(browser);
  await openClass(teacher, origin, issueCredential());
  const projector = await openProjection(teacher);
  const joinUrl = await projector.getByRole('link', { name: /\/join\// }).getAttribute('href');

  async function groupAt(site) {
    const group = await participant(browser);
    await group.goto(joinUrl);
    await group.getByRole('button', { name: `Choose Site ${site}` }).click();
    await group.getByRole('heading', { name: `Site ${site}:`, exact: false }).waitFor();
    return group;
  }

  return { groupAt, joinUrl, teacher };
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
  await groupA.route('**/classes/*/status', route => route.abort());
  await groupA.getByLabel('Crossing type').selectOption('tunnel');
  await groupA.getByRole('button', { name: 'Save for swap' }).click();
  await groupA.getByText('Crossing saved for Pass the City.', { exact: true }).waitFor();
  await groupA.getByLabel('Crossing type').selectOption('elevated');
  await teacher.getByRole('button', { name: 'Pass the City' }).click();
  await groupA.getByRole('button', { name: '繁體中文' }).click();
  await groupA.getByRole('heading', { name: '場地 B：河畔濕地' }).waitFor();
  assert.equal(await groupA.getByLabel('鐵路形式').inputValue(), 'tunnel');
  await groupA.unroute('**/classes/*/status');
  await groupB.getByRole('heading', { name: 'Site A: Central wetland' }).waitFor();

  await teacher.getByRole('button', { name: 'End class' }).click();
  await Promise.all([
    groupA.getByRole('heading', { name: '這個課堂已結束' }).waitFor(),
    groupB.getByRole('heading', { name: 'This class is closed' }).waitFor(),
  ]);
});
