export interface BrowserSentryConfig {
  dsn: string;
  environment: string;
  release?: string;
  tracesSampleRate: number;
}

export function validBrowserDsn(dsn: unknown, production: boolean): dsn is string {
  if (typeof dsn !== 'string' || dsn.length > 2048 || /[\s\\<>"\x00-\x1f\x7f?#]/.test(dsn)) return false;
  if (!/^https?:\/\/[A-Za-z0-9_]+@(?:[A-Za-z0-9.-]+|\[[a-fA-F0-9:.]+\])(?::[0-9]+)?\//.test(dsn)) return false;
  try {
    const url = new URL(dsn);
    return (url.protocol === 'https:' || (!production && url.protocol === 'http:'))
      && !!url.hostname && url.port !== '0' && /^[A-Za-z0-9_]+$/.test(url.username)
      && !url.password && /^(?:\/[A-Za-z0-9_-]+)*\/[0-9]+$/.test(url.pathname);
  } catch { return false; }
}

export function readBrowserSentryConfig(document: Document): BrowserSentryConfig | null {
  try {
    const element = document.getElementById('helpdesk-runtime-config');
    if (!element || element.getAttribute('type') !== 'application/json') return null;
    const text = element.textContent ?? '';
    if (text.length > 4096) return null;
    const value = JSON.parse(text)?.sentry;
    if (!value || typeof value !== 'object' || typeof value.environment !== 'string'
      || !/^[A-Za-z0-9_.-]{1,64}$/.test(value.environment)
      || !validBrowserDsn(value.dsn, value.environment === 'production' || value.environment === 'prod')) return null;
    const raw = value.tracesSampleRate;
    const rate = typeof raw === 'number' && Number.isFinite(raw) && raw >= 0 && raw <= 1 ? raw : .05;
    const config: BrowserSentryConfig = { dsn: value.dsn, environment: value.environment, tracesSampleRate: rate };
    if (typeof value.release === 'string' && /^[a-fA-F0-9]{40}$/.test(value.release)) config.release = value.release.toLowerCase();
    return config;
  } catch { return null; }
}
