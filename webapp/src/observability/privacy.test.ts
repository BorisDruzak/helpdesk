import { describe, expect, it } from 'vitest';
import { appRoutes } from '../app/router';
import { resolveRouteTemplate } from './routes';
import { createBrowserEventSanitizer } from './privacy';
import type { Event, BrowserOptions } from '@sentry/react';
type TransactionEvent = Parameters<NonNullable<BrowserOptions['beforeSendTransaction']>>[0];

const config = { dsn: 'https://public_test_key@sentry.example.invalid/1', environment: 'production', release: 'a'.repeat(40), tracesSampleRate: .05 };
describe('route templates', () => {
  it.each([
    ['/app/tickets/12345', '/app/tickets/:ticketId'],
    ['/app/admin/operations/opaque-secret-id', '/app/admin/operations/:operationId'],
    ['/app/requester/tickets/opaque%20identifier', '/app/requester/tickets/:ticketId'],
    ['/app/requester/unknown/private', '[unresolved route]'],
    ['/unknown/private', '[unresolved route]'],
    ['/app/admin/device?device=private#secret', '/app/admin/device'],
    ['/app/login', '/app/login'],
  ])('%s -> %s', (path, pattern) => expect(resolveRouteTemplate(appRoutes, path)).toBe(pattern));
});
describe('positive event projection', () => {
  it('removes content from every payload channel and attachments', () => {
    const marker = 'PRIVATE_EMAIL_TOKEN_TICKET_CONTENT';
    const hooks = createBrowserEventSanitizer(config, appRoutes, 'http://localhost');
    const event = {
      event_id: 'b'.repeat(32), timestamp: 123, level: 'error', environment: marker,
      release: marker, message: marker, transaction: '/app/tickets/12345?token=' + marker,
      user: { email: marker, id: marker }, request: { url: marker, headers: { Authorization: marker, Cookie: marker }, data: marker },
      extra: { localStorage: marker, form: marker }, tags: { email: marker }, breadcrumbs: [{ message: marker }],
      contexts: { trace: { trace_id: 'c'.repeat(32), span_id: 'd'.repeat(16), op: 'pageload', data: marker }, react: { componentStack: marker } },
      exception: { values: [{ type: 'TypeError', value: marker, stacktrace: { frames: [
        { filename: 'http://private:password@localhost/assets/index-Ab123.js?token=' + marker + '#' + marker, function: 'render', lineno: 10, colno: 2, vars: { secret: marker } },
        { filename: 'https://external/' + marker, function: marker, lineno: 1 },
      ] } }] },
      spans: [{ trace_id: 'c'.repeat(32), span_id: 'e'.repeat(16), start_timestamp: 1, timestamp: 2, op: 'http.client', description: marker, data: { url: marker } }],
    } as unknown as Event;
    const hint = { attachments: [{ filename: marker, data: marker }] };
    const result = hooks.beforeSend(event, hint)!;
    expect(JSON.stringify(result)).not.toContain(marker);
    expect(result.release).toBe(config.release);
    expect(result.transaction).toBe('/app/tickets/:ticketId');
    expect(result.exception?.values?.[0].stacktrace?.frames?.[0]).toEqual({ filename: '/assets/index-Ab123.js', function: 'render', lineno: 10, colno: 2 });
    expect(hint.attachments).toEqual([]);
    const transaction = hooks.beforeSendTransaction({ ...event, type: 'transaction', start_timestamp: 1 } as TransactionEvent, {});
    expect(JSON.stringify(transaction)).not.toContain(marker);
    expect(transaction?.transaction).toBe('/app/tickets/:ticketId');
    expect(transaction?.spans?.[0].description).toBeUndefined();
  });
});
