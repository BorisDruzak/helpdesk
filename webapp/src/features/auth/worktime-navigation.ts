const callbacks=new Map([
  ["https://endpoint.sosnadmin.local/employee","https://endpoint.sosnadmin.local/auth/worktime/helpdesk/callback"],
  ["https://endpoint-staging.sosnadmin.local/employee","https://endpoint-staging.sosnadmin.local/auth/worktime/helpdesk/callback"],
]);

export function worktimeAuthorizePath(search:string,portal?:string | null):string | null {
  const params=new URLSearchParams(search);
  const keys=['state','code_challenge','code_challenge_method','redirect_uri'];
  if([...params.keys()].length!==4 || keys.some(key=>params.getAll(key).length!==1))return null;
  if(!/^[A-Za-z0-9_-]{43,128}$/.test(params.get('state') ?? '') || !/^[A-Za-z0-9_-]{43}$/.test(params.get('code_challenge') ?? '') || params.get('code_challenge_method')!=='S256')return null;
  const callback=params.get('redirect_uri');
  if(portal ? callbacks.get(portal)!==callback : ![...callbacks.values()].includes(callback ?? ''))return null;
  return '/api/web/session/worktime/authorize?'+params.toString();
}

export function safeWorktimeContinuation(value:string | null):boolean {
  if(!value?.startsWith('/app/worktime/connect?') || value.length>1800 || value.includes('#'))return false;
  return worktimeAuthorizePath(value.slice(value.indexOf('?')))!==null;
}

export function openWorktimeAuthorization(path:string){window.location.assign(path);}
