export type PanelPreferences={navigationCollapsed:boolean;ticketListCollapsed:boolean};
const key=(account:string,workspace:string)=>`pc-client:workspace-panels:v1:${JSON.stringify([account,workspace])}`;
export function loadPanelPreferences(account:string,workspace:string,defaults:PanelPreferences={navigationCollapsed:false,ticketListCollapsed:false}):PanelPreferences {
  try {
    if(!account || !workspace) return {...defaults};
    const stored=JSON.parse(localStorage.getItem(key(account,workspace))??"null");
    if(stored?.schema_version!==1) return {...defaults};
    return {navigationCollapsed:typeof stored.navigationCollapsed==="boolean"?stored.navigationCollapsed:defaults.navigationCollapsed,
      ticketListCollapsed:typeof stored.ticketListCollapsed==="boolean"?stored.ticketListCollapsed:defaults.ticketListCollapsed};
  } catch {return {...defaults};}
}
export function savePanelPreferences(account:string,workspace:string,preferences:PanelPreferences) {
  try {if(!account || !workspace) return false;localStorage.setItem(key(account,workspace),JSON.stringify({schema_version:1,...preferences}));return true;} catch {return false;}
}
