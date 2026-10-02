import * as Sentry from '@sentry/react';
import { useEffect } from 'react';
import type { RootOptions } from 'react-dom/client';
import { createBrowserRouter, createRoutesFromChildren, matchRoutes, useLocation, useNavigationType, type RouteObject } from 'react-router-dom';
import { createBrowserEventSanitizer } from './privacy';
import { resolveRouteTemplate } from './routes';
import type { BrowserSentryConfig } from './runtime-config';

const escapeRegex = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

export function buildTracePropagationTargets(origin: string, dsn: string): RegExp[] {
  const url = new URL(dsn);
  const parts = url.pathname.split('/');
  const project = parts.pop()!;
  const prefix = parts.join('/');
  const ingestion = `${url.origin}${prefix}/api/${project}/`;
  // Absolute matching only: the SDK resolves URLs before testing these targets.
  return [new RegExp(`^(?!${escapeRegex(ingestion)}(?:envelope|store|security)(?:/|[?#]|$))${escapeRegex(origin)}/api/`)];
}

export function buildBrowserSentryOptions(config: BrowserSentryConfig, routes: RouteObject[], origin: string): Sentry.BrowserOptions & { sendDefaultPii: false } {
  const targets = buildTracePropagationTargets(origin, config.dsn);
  return {
    dsn: config.dsn, environment: config.environment, release: config.release,
    defaultIntegrations: false, sendDefaultPii: false,
    dataCollection: { userInfo: false, cookies: false, httpHeaders: false, httpBodies: [], urlQueryParams: false, stackFrameVariables: false, frameContextLines: 0 },
    maxBreadcrumbs: 0, sendClientReports: false, debug: false,
    transportOptions: { fetchOptions: { credentials: 'omit', referrerPolicy: 'no-referrer' } },
    traceLifecycle: 'static', tracesSampleRate: config.tracesSampleRate,
    tracePropagationTargets: targets, propagateTraceparent: false,
    beforeSendLog: () => null, beforeSendMetric: () => null,
    profileSessionSampleRate: 0,
    ...createBrowserEventSanitizer(config, routes, origin),
    integrations: [
      Sentry.globalHandlersIntegration({ onerror: true, onunhandledrejection: true }),
      Sentry.reactRouterBrowserTracingIntegration({
        useEffect, useLocation, useNavigationType, createRoutesFromChildren, matchRoutes,
        beforeStartSpan: options => ({ ...options, name: resolveRouteTemplate(routes, window.location.pathname) }),
        shouldCreateSpanForRequest: value => {
          try { return targets.some(target => target.test(new URL(value, origin).toString())); }
          catch { return false; }
        },
        enableLongTask: false, enableLongAnimationFrame: false, enableInp: false,
        enableHTTPTimings: false, instrumentBfcacheRestore: false,
        linkPreviousTrace: 'off', ignoreResourceSpans: ['resource.script', 'resource.css', 'resource.img', 'resource.other'],
      }),
      // v11 BrowserTracing auto-registers WebVitals unless this name exists.
      // A deliberately inert integration prevents all its collectors from starting.
      { name: 'WebVitals' },
    ],
  };
}

interface BrowserObservability {
  createRouter: typeof createBrowserRouter;
  rootOptions: RootOptions;
}
let attempted = false;
let runtime: BrowserObservability | null = null;

export function initializeBrowserSentry(config: BrowserSentryConfig | null, routes: RouteObject[], origin: string): BrowserObservability | null {
  if (!config) return null;
  if (attempted) return runtime;
  attempted = true;
  try {
    Sentry.init(buildBrowserSentryOptions(config, routes, origin));
    const handler = Sentry.reactErrorHandler();
    const safeHandler: typeof handler = (error, info) => { try { handler(error, info); } catch { /* observability is optional */ } };
    runtime = { createRouter: Sentry.wrapCreateBrowserRouter(createBrowserRouter),
      rootOptions: { onCaughtError: safeHandler, onUncaughtError: safeHandler, onRecoverableError: safeHandler } };
  } catch { /* no config values or SDK errors are logged */ }
  return runtime;
}
