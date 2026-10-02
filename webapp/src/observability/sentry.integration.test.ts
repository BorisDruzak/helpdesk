import { afterEach, expect, it } from 'vitest';
import * as Sentry from '@sentry/react';
import { appRoutes } from '../app/router';
import { buildBrowserSentryOptions } from './sentry';
import { Component, createElement, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';

afterEach(async () => { await Sentry.close(500); Sentry.getCurrentScope().clearAttachments(); });

it('actual SDK emits sanitized error/React/transaction envelopes only', async () => {
  const envelopes: unknown[] = [];
  const marker = 'PRIVATE_EMAIL_AUTH_COOKIE_TICKET_TOKEN';
  const config = { dsn: 'https://public_test_key@sentry.example.invalid/1', environment: 'production', release: 'a'.repeat(40), tracesSampleRate: 1 };
  window.history.replaceState(null, '', '/app/tickets/12345?token=' + marker + '#' + marker);
  Sentry.init({ ...buildBrowserSentryOptions(config, appRoutes, window.location.origin),
    transport: () => ({ send: async envelope => { envelopes.push(envelope); return { statusCode: 200 }; }, flush: async () => true }) });
  Sentry.getCurrentScope().setExtra('content', marker);
  Sentry.getCurrentScope().setTag('private', marker);
  Sentry.getCurrentScope().addAttachment({ filename: marker, data: marker });
  Sentry.captureException(new TypeError(marker));
  Sentry.reactErrorHandler()(new Error(marker), { componentStack: marker });
  Sentry.startSpan({ name: '/app/tickets/12345?token=' + marker, op: 'navigation', forceTransaction: true }, span => {
    span.setAttribute('content', marker);
    Sentry.startSpan({ name: marker, op: 'http.client' }, child => child.setAttribute('http.url', marker));
  });
  Sentry.logger.info(marker);
  Sentry.metrics.count(marker);
  await Sentry.flush(500);
  expect(envelopes.length).toBeGreaterThanOrEqual(3);
  const serialized = JSON.stringify(envelopes);
  expect(serialized).not.toContain(marker);
  expect(serialized).not.toContain('12345');
  expect(serialized).toContain('/app/tickets/:ticketId');
  const types = envelopes.flatMap(envelope => (envelope as [unknown, [{ type: string }, unknown][]])[1].map(item => item[0].type));
  expect(types).toContain('event');
  expect(types).toContain('transaction');
  expect(types.every(type => type === 'event' || type === 'transaction')).toBe(true);
  expect(Sentry.getClient()?.getOptions().traceLifecycle).toBe('static');
  window.history.replaceState(null, '', '/');
});

it('unavailable transport cannot interrupt capture or React callback', async () => {
  Sentry.init({ ...buildBrowserSentryOptions({ dsn: 'https://public_test_key@sentry.example.invalid/1', environment: 'production', tracesSampleRate: 0 }, appRoutes, window.location.origin),
    transport: () => ({ send: async () => { throw new Error('simulated offline'); }, flush: async () => true }) });
  expect(() => Sentry.captureException(new Error('private'))).not.toThrow();
  expect(() => Sentry.reactErrorHandler()(new Error('private'), { componentStack: 'private' })).not.toThrow();
  await Sentry.flush(500);
});

it('React 19 root captures a real render failure without component content', async () => {
  const envelopes: unknown[] = [];
  const marker = 'PRIVATE_REACT_COMPONENT_CONTENT';
  Sentry.init({ ...buildBrowserSentryOptions({ dsn: 'https://public_test_key@sentry.example.invalid/1', environment: 'production', tracesSampleRate: 0 }, appRoutes, window.location.origin),
    transport: () => ({ send: async envelope => { envelopes.push(envelope); return { statusCode: 200 }; }, flush: async () => true }) });
  class Boundary extends Component<{ children: ReactNode }, { failed: boolean }> {
    state = { failed: false };
    static getDerivedStateFromError() { return { failed: true }; }
    render() { return this.state.failed ? 'Recovered' : this.props.children; }
  }
  function Broken(): never { throw new TypeError(marker); }
  const node = document.createElement('div');
  document.body.append(node);
  const root = createRoot(node, { onCaughtError: Sentry.reactErrorHandler(), onUncaughtError: Sentry.reactErrorHandler(), onRecoverableError: Sentry.reactErrorHandler() });
  root.render(createElement(Boundary, { children: createElement(Broken) }));
  await expect.poll(() => node.textContent).toBe('Recovered');
  await Sentry.flush(500);
  expect(JSON.stringify(envelopes)).toContain('TypeError');
  expect(JSON.stringify(envelopes)).not.toContain(marker);
  root.unmount();
  node.remove();
});
