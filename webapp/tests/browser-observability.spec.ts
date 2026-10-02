import { expect, test, type Page } from 'playwright/test';

async function anonymousSession(page: Page) {
  await page.route('**/api/web/session/me', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'success', data: null }) }));
}

test('disabled runtime preserves clean login UI and immutable assets', async ({ page }, testInfo) => {
  await anonymousSession(page);
  const errors: string[] = [], failed: string[] = [], ingestion: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('requestfailed', request => failed.push(request.url()));
  page.on('request', request => { if (request.url().includes('/envelope/')) ingestion.push(request.url()); });
  await page.goto('/app/login');
  await expect(page.getByRole('heading', { name: 'Добро пожаловать' })).toBeVisible();
  expect(await page.locator('#helpdesk-runtime-config').textContent()).toBe('{"sentry":null}');
  for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
    await page.setViewportSize({ width, height });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`disabled-login-${width}.png`), fullPage: true });
  }
  expect(errors).toEqual([]);
  expect(failed).toEqual([]);
  expect(ingestion).toEqual([]);
});

test('real SDK sanitizes global errors and restricts fetch/XHR propagation', async ({ page, baseURL }) => {
  await anonymousSession(page);
  await page.route('**/api/web/session/capabilities', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'success', data: { self_registration_enabled: true } }) }));
  const origin = baseURL!;
  const marker = 'PRIVATE_TICKET_EMAIL_AUTH_QUERY_FRAGMENT';
  await page.context().addCookies([{ name: 'privacy_test', value: marker, url: origin }]);
  const events: string[] = [];
  const headers: Record<string, Record<string, string>> = {};
  await page.route('**/app/login*', async route => {
    if (route.request().resourceType() !== 'document') return route.continue();
    const response = await route.fetch();
    const config = JSON.stringify({ sentry: { dsn: `${origin.replace('://', '://public_test_key@')}/1`, environment: 'staging', release: 'a'.repeat(40), tracesSampleRate: 1 } });
    const body = (await response.text()).replace(/(<script type="application\/json" id="helpdesk-runtime-config">).*?(<\/script>)/, `$1${config}$2`);
    await route.fulfill({ response, body });
  });
  await page.route('**/api/1/envelope/**', async route => {
    events.push(route.request().postData() ?? '');
    headers.ingestion = await route.request().allHeaders();
    await route.fulfill({ status: 200, body: '{}' });
  });
  for (const path of ['**/api/web/privacy-check/**', '**/api/web/xhr-check/**', 'https://external.example.invalid/api/check']) {
    await page.route(path, async route => {
      headers[new URL(route.request().url()).pathname] = await route.request().allHeaders();
      await route.fulfill({ status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: '{}' });
    });
  }
  await page.goto('/app/login?token=' + marker + '#' + marker);
  await expect(page.getByRole('heading', { name: 'Добро пожаловать' })).toBeVisible();
  await page.evaluate(async privateMarker => {
    await fetch('/api/web/privacy-check/12345?token=' + privateMarker, { headers: { Authorization: privateMarker } });
    await new Promise<void>(resolve => {
      const xhr = new XMLHttpRequest();
      xhr.open('GET', '/api/web/xhr-check/12345?token=' + privateMarker);
      xhr.onloadend = () => resolve();
      xhr.send();
    });
    await fetch('https://external.example.invalid/api/check');
    setTimeout(() => { throw new TypeError(privateMarker); }, 0);
    void Promise.reject(new Error(privateMarker));
  }, marker);
  await expect.poll(() => events.filter(body => body.includes('"type":"event"')).length).toBeGreaterThanOrEqual(2);
  await expect.poll(() => events.some(body => body.includes('"type":"transaction"'))).toBe(true);
  expect(headers['/api/web/privacy-check/12345']['sentry-trace']).toBeTruthy();
  expect(headers['/api/web/privacy-check/12345'].cookie).toContain('privacy_test=');
  expect(headers['/api/web/xhr-check/12345']['sentry-trace']).toBeTruthy();
  expect(headers['/api/check']['sentry-trace']).toBeUndefined();
  expect(headers['/api/check'].baggage).toBeUndefined();
  expect(headers.ingestion['sentry-trace']).toBeUndefined();
  expect(headers.ingestion.baggage).toBeUndefined();
  expect(headers.ingestion.cookie).toBeUndefined();
  expect(headers.ingestion.referer).toBeUndefined();
  expect(events.join('\n')).not.toContain(marker);
  expect(events.join('\n')).not.toContain('12345');
  expect(events.join('\n')).toContain('/app/login');
  expect(events.join('\n')).not.toMatch(/"type":"(?:session|sessions|log|metric|replay_event|attachment)"/);
  // Transport outage after successful startup must not affect ordinary navigation.
  await page.unroute('**/api/1/envelope/**');
  await page.route('**/api/1/envelope/**', route => route.abort('failed'));
  await page.evaluate(() => { setTimeout(() => { throw new Error('simulated offline'); }, 0); });
  await page.getByRole('link', { name: 'Создать аккаунт', exact: true }).click();
  await expect(page).toHaveURL(/\/app\/register/);
});
