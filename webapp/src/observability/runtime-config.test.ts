import { describe, expect, it } from 'vitest';
import { readBrowserSentryConfig } from './runtime-config';

const valid = { dsn: 'https://public_test_key@sentry.example.invalid/1', environment: 'production', release: 'a'.repeat(40), tracesSampleRate: .05 };
function read(value: unknown) {
  document.body.innerHTML = '<script type="application/json" id="helpdesk-runtime-config"></script>';
  document.getElementById('helpdesk-runtime-config')!.textContent = JSON.stringify(value);
  return readBrowserSentryConfig(document);
}
describe('public runtime config', () => {
  it('disables missing or malformed JSON', () => {
    document.body.innerHTML = '';
    expect(readBrowserSentryConfig(document)).toBeNull();
    read(null);
    document.getElementById('helpdesk-runtime-config')!.textContent = '{';
    expect(readBrowserSentryConfig(document)).toBeNull();
  });
  it.each([null, {}, { sentry: null }, { sentry: { ...valid, dsn: 'broken' } },
    { sentry: { ...valid, dsn: 'http://key@host/1' } },
    { sentry: { ...valid, dsn: 'https://invalid-key@host/1' } },
    { sentry: { ...valid, dsn: 'HTTPS://key@host/1' } },
    { sentry: { ...valid, dsn: 'https://key:password@host/1' } },
    { sentry: { ...valid, dsn: 'https://key@host/1?token=x' } },
    { sentry: { ...valid, dsn: 'https://key@host/1#' } },
    { sentry: { ...valid, environment: 'content with spaces' } }])('disables invalid config %j', value => expect(read(value)).toBeNull());
  it('projects only public fields', () => expect(read({ sentry: { ...valid, secret: 'PRIVATE' }, extra: 'PRIVATE' })).toEqual(valid));
  it.each(['bad', null, true, -1, 2])('defaults bad rate %j', tracesSampleRate => {
    expect(read({ sentry: { ...valid, tracesSampleRate } })?.tracesSampleRate).toBe(.05);
  });
  it('omits invalid release', () => expect(read({ sentry: { ...valid, release: 'invalid' } })).not.toHaveProperty('release'));
});
