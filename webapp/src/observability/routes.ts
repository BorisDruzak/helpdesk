import { matchRoutes, type RouteObject } from 'react-router-dom';

export const UNRESOLVED_ROUTE = '[unresolved route]';

export function resolveRouteTemplate(routes: RouteObject[], pathname: string): string {
  try {
    const path = pathname.split(/[?#]/, 1)[0];
    const matches = matchRoutes(routes, path);
    if (!matches?.length) return UNRESOLVED_ROUTE;
    let pattern = '';
    for (const { route } of matches) {
      if (!route.path) continue;
      if (route.path.includes('*')) return UNRESOLVED_ROUTE;
      pattern = route.path.startsWith('/') ? route.path : `${pattern}/${route.path}`;
    }
    return pattern.replace(/\/+$/, '') || '/';
  } catch { return UNRESOLVED_ROUTE; }
}
