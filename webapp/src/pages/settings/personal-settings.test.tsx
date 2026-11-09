import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, expect, it, vi} from 'vitest';
import {SettingsPage} from './index';
import {jsonResponse} from './settings-test-fixtures';

vi.mock('../../features/auth/session-provider',()=>({useSession:()=>({session:{user_login:'operator',actor_role:'support',permissions:['workspace.support.view'],available_workspaces:['support']}})}));
vi.mock('../../features/notifications/browser-push-control',()=>({BrowserPushControl:()=> <p>Состояние браузера</p>}));
afterEach(()=>vi.unstubAllGlobals());
function renderPersonal(failRead=false) {
 const fetcher=vi.fn(async(input:RequestInfo|URL,init?:RequestInit)=>{
  if(String(input)!=='/api/web/notifications/preferences')throw new Error('Personal page requested service configuration');
  if(failRead)return new Response('',{status:503});
  return jsonResponse({status:'ok',preferences:{mute_internal:false,muted_event_types:[],suppress_self:true}});
 });
 vi.stubGlobal('fetch',fetcher);
 render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><SettingsPage/></QueryClientProvider>);
 return fetcher;
}
it('allows support to change own notifications without service management rights',async()=>{
 const fetcher=renderPersonal();
 const field=await screen.findByRole('checkbox',{name:/Новые сообщения/});
 expect(field).toBeEnabled();fireEvent.click(field);
 await waitFor(()=>expect(fetcher.mock.calls.some(([,init])=>init?.method==='POST')).toBe(true));
 expect(screen.queryByRole('button',{name:'Сроки'})).not.toBeInTheDocument();
 expect(screen.queryByRole('link',{name:'Настройки службы'})).not.toBeInTheDocument();
});
it('does not show guessed enabled preferences when the read failed',async()=>{
 renderPersonal(true);
 expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось загрузить');
 expect(screen.queryByRole('checkbox',{name:/Новые сообщения/})).not.toBeInTheDocument();
});
