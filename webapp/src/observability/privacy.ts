import type { Event, EventHint, BrowserOptions } from '@sentry/react';
import type { RouteObject } from 'react-router-dom';
import type { BrowserSentryConfig } from './runtime-config';
import { resolveRouteTemplate } from './routes';
type TransactionEvent = Parameters<NonNullable<BrowserOptions['beforeSendTransaction']>>[0];

const hex = (value: unknown, length: number): string | undefined =>
  typeof value === 'string' && new RegExp(`^[a-f0-9]{${length}}$`, 'i').test(value) ? value.toLowerCase() : undefined;
const number = (value: unknown): number | undefined => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : undefined;
const operations = new Set(['pageload', 'navigation', 'http.client', 'resource.script', 'resource.css', 'resource.img', 'ui.react', 'ui.long-task']);
const errorTypes = new Set(['Error', 'TypeError', 'ReferenceError', 'RangeError', 'SyntaxError', 'URIError', 'EvalError', 'AggregateError', 'DOMException']);
const statuses = new Set(['ok', 'unknown_error', 'internal_error', 'cancelled', 'deadline_exceeded', 'not_found', 'permission_denied', 'unauthenticated', 'unavailable']);

function safeFilename(value: unknown, origin: string): string | undefined {
  if (typeof value !== 'string') return undefined;
  try {
    const url = new URL(value, origin);
    // Only compiled app assets; no document paths, third-party URLs or source contents.
    if (url.origin === origin && /^\/assets\/[A-Za-z0-9_-]+-[A-Za-z0-9_-]{5,}\.js$/.test(url.pathname)) return url.pathname;
  } catch { /* no arbitrary frame content */ }
  return undefined;
}

function safeFunction(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  return /^[A-Za-z_$][A-Za-z0-9_$]{0,2}$/.test(value) || ['render', 'dispatch', 'anonymous', '<anonymous>'].includes(value) ? value : undefined;
}

function traceProjection(trace: Record<string, unknown>) {
  const trace_id = hex(trace.trace_id, 32), span_id = hex(trace.span_id, 16);
  if (!trace_id || !span_id) return undefined;
  return {
    trace_id, span_id,
    ...(hex(trace.parent_span_id, 16) ? { parent_span_id: hex(trace.parent_span_id, 16) } : {}),
    ...(typeof trace.op === 'string' && operations.has(trace.op) ? { op: trace.op } : {}),
    ...(typeof trace.status === 'string' && statuses.has(trace.status) ? { status: trace.status } : {}),
  };
}

export function createBrowserEventSanitizer(config: BrowserSentryConfig, routes: RouteObject[], origin: string) {
  function project(event: Event, hint: EventHint): Event {
    // The SDK adds attachments to envelopes after these hooks.
    hint.attachments = [];
    const result: Event = { platform: 'javascript', environment: config.environment,
      transaction: resolveRouteTemplate(routes, event.transaction || window.location.pathname) };
    if (config.release) result.release = config.release;
    if (hex(event.event_id, 32)) result.event_id = hex(event.event_id, 32);
    if (number(event.timestamp) !== undefined) result.timestamp = number(event.timestamp);
    if (event.level && ['fatal', 'error', 'warning', 'info', 'debug'].includes(event.level)) result.level = event.level;
    const trace = event.contexts?.trace;
    if (trace && typeof trace === 'object') {
      const safe = traceProjection(trace);
      if (safe) result.contexts = { trace: safe };
    }
    if (event.exception?.values?.length) result.exception = { values: event.exception.values.slice(0, 5).map(exception => ({
      type: errorTypes.has(exception.type ?? '') ? exception.type : 'Error',
      value: '[message omitted]',
      stacktrace: { frames: (exception.stacktrace?.frames ?? []).slice(-50).flatMap(frame => {
        const filename = safeFilename(frame.filename, origin);
        if (!filename) return [];
        return [{ filename,
          ...(safeFunction(frame.function) ? { function: safeFunction(frame.function) } : {}),
          ...(number(frame.lineno) !== undefined ? { lineno: number(frame.lineno) } : {}),
          ...(number(frame.colno) !== undefined ? { colno: number(frame.colno) } : {}) }];
      }) },
    })) };
    return result;
  }
  return {
    beforeSend: (event: Event, hint: EventHint) => ({ ...project(event, hint), type: undefined }),
    beforeSendTransaction(event: TransactionEvent, hint: EventHint): TransactionEvent {
      const result: TransactionEvent = { ...project(event, hint), type: 'transaction',
        start_timestamp: number(event.start_timestamp) ?? 0,
        transaction_info: { source: 'route' }, spans: [] };
      result.spans = (event.spans ?? []).slice(0, 100).flatMap(span => {
        const trace = traceProjection(span as unknown as Record<string, unknown>);
        const start = number(span.start_timestamp), end = number(span.timestamp);
        return trace && start !== undefined && end !== undefined ? [{ ...trace, status: trace.status ?? 'unknown_error', start_timestamp: start, timestamp: end, data: {} }] : [];
      });
      return result;
    },
  };
}
