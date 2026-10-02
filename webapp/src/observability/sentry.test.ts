import { describe, expect, it, vi } from 'vitest';
import { buildTracePropagationTargets, buildBrowserSentryOptions, initializeBrowserSentry } from './sentry';
import { appRoutes } from '../app/router';

const init = vi.hoisted(() => vi.fn());
vi.mock('@sentry/react', async importOriginal => ({
  ...await importOriginal<object>(), init,
}));
const config = { dsn: 'https://public_test_key@sentry.example.invalid/1', environment: 'production', release: 'a'.repeat(40), tracesSampleRate: .05 };
describe('minimal initialization', () => {
  it('selects minimal safe SDK options', () => {
    const options = buildBrowserSentryOptions(config, appRoutes, 'http://localhost');
    expect(options.defaultIntegrations).toBe(false);
    expect(options.sendDefaultPii).toBe(false);
    expect(options.maxBreadcrumbs).toBe(0);
    expect(options.sendClientReports).toBe(false);
    expect(options.transportOptions?.fetchOptions).toEqual({ credentials: 'omit', referrerPolicy: 'no-referrer' });
    expect(options.traceLifecycle).toBe('static');
    expect(options.tracesSampleRate).toBe(.05);
    expect(options.sampleRate).toBeUndefined();
    expect(options.environment).toBe('production');
    expect(options.release).toBe(config.release);
    expect((options.integrations as { name: string }[]).map(i => i.name)).toEqual(['GlobalHandlers', 'BrowserTracing', 'WebVitals']);
    expect(options.beforeSendLog?.({} as never)).toBeNull();
    expect(options.beforeSendMetric?.({} as never)).toBeNull();
  });
  it('disabled is inert, enabled is initialized once', () => {
    expect(initializeBrowserSentry(null, appRoutes, 'http://localhost')).toBeNull();
    expect(init).not.toHaveBeenCalled();
    const enabled = initializeBrowserSentry(config, appRoutes, 'http://localhost');
    expect(enabled).not.toBeNull();
    expect(initializeBrowserSentry(config, appRoutes, 'http://localhost')).toBe(enabled);
    expect(init).toHaveBeenCalledTimes(1);
  });
  it('SDK initialization failure leaves ordinary router/root available', async () => {
    vi.resetModules();
    init.mockImplementationOnce(() => { throw new Error('private configuration error'); });
    const { initializeBrowserSentry: freshInitialize } = await import('./sentry');
    expect(freshInitialize(config, appRoutes, 'http://localhost')).toBeNull();
    expect(freshInitialize(config, appRoutes, 'http://localhost')).toBeNull();
  });
});
describe('strict propagation target', () => {
  const origin = 'https://helpdesk.example.invalid';
  const targets = buildTracePropagationTargets(origin, `${origin.replace('https://', 'https://public_test_key@')}/1`);
  const allows = (value: string) => targets.some(target => target.test(new URL(value, origin).toString()));
  it.each(['/api/web/me', `${origin}/api/tickets/123?token=private`, '/api/v1/devices'])('allows own API %s', value => expect(allows(value)).toBe(true));
  it.each(['https://other.example.invalid/api/web/me', `${origin}:444/api/web/me`, 'http://helpdesk.example.invalid/api/web/me',
    '/assets/app.js', '/apix/private', '/api/1/envelope/', '/api/1/store/', 'https://sentry.example.invalid/api/1/envelope/',
    'https://helpdesk.example.invalid.evil/api/web/me', '//external.example.invalid/api/web/me'])('rejects %s', value => expect(allows(value)).toBe(false));
});
