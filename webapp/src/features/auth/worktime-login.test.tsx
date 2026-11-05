import { fireEvent,render,screen,waitFor } from "@testing-library/react";
import { MemoryRouter,Route,Routes,useLocation } from "react-router-dom";
import { afterEach,expect,it,vi } from "vitest";
import { WorktimeLink } from "./worktime-link";
import { WorktimeConnectPage } from "./worktime-connect-page";
import { LoginPage } from "./login-page";
import { worktimeAuthorizePath,openWorktimeAuthorization } from "./worktime-navigation";

const fixture=vi.hoisted(()=>({status:"authenticated",session:{user_login:"fixture",actor_role:"user",available_workspaces:["requester"],default_workspace:"requester",worktime_portal_url:"https://endpoint-staging.sosnadmin.local/employee",worktime_handoff_enabled:true}}));
vi.mock('./session-provider',()=>({useSession:()=>({...fixture,login:vi.fn()})}));
vi.mock('./worktime-navigation',async importOriginal=>({...await importOriginal<typeof import('./worktime-navigation')>(),openWorktimeAuthorization:vi.fn()}));
const query=new URLSearchParams({state:'s'.repeat(43),code_challenge:'c'.repeat(43),code_challenge_method:'S256',redirect_uri:'https://endpoint-staging.sosnadmin.local/auth/worktime/helpdesk/callback'}).toString();
afterEach(()=>{vi.clearAllMocks();vi.unstubAllGlobals();fixture.status='authenticated';});

it('opens the fixed consumer handoff entry instead of prompting for a second login',()=>{
  render(<WorktimeLink url={fixture.session.worktime_portal_url} handoffEnabled/>);
  expect(screen.getByRole('link',{name:'Рабочее время'})).toHaveAttribute('href','https://endpoint-staging.sosnadmin.local/auth/worktime/helpdesk/login');
});

it('continues an authenticated closed handoff without any person or role parameter',async()=>{
  render(<MemoryRouter initialEntries={['/app/worktime/connect?'+query]}><WorktimeConnectPage/></MemoryRouter>);
  await waitFor(()=>expect(openWorktimeAuthorization).toHaveBeenCalledWith('/api/web/session/worktime/authorize?'+query));
});

it('sends anonymous users through login with a bounded internal continuation',async()=>{
  fixture.status='anonymous';
  function Probe(){return <p>{useLocation().search}</p>;}
  render(<MemoryRouter initialEntries={['/app/worktime/connect?'+query]}><Routes><Route path='/app/worktime/connect' element={<WorktimeConnectPage/>}/><Route path='/app/login' element={<Probe/>}/></Routes></MemoryRouter>);
  expect(await screen.findByText(/next=/)).toHaveTextContent(encodeURIComponent('/app/worktime/connect?'+query));
  expect(openWorktimeAuthorization).not.toHaveBeenCalled();
});

it('rejects an extra person selector or wrong environment before navigating',()=>{
  expect(worktimeAuthorizePath('?'+query+'&person_id=other',fixture.session.worktime_portal_url)).toBeNull();
  expect(worktimeAuthorizePath('?'+query,'https://endpoint.sosnadmin.local/employee')).toBeNull();
});

it('offers explicit AD login and retains the continuation for its verified callback',async()=>{
  fixture.status='anonymous';
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({status:'success',data:{sso_enabled:true,self_registration_enabled:true}}),{headers:{'Content-Type':'application/json'}})));
  const next='/app/worktime/connect?'+query;
  render(<MemoryRouter initialEntries={['/app/login?next='+encodeURIComponent(next)]}><LoginPage/></MemoryRouter>);
  const link=await screen.findByRole('link',{name:'Войти через AD'});
  expect(link.getAttribute('href')).toBe('/api/web/session/oidc/login?'+new URLSearchParams({next}).toString());
  fireEvent.click(screen.getByLabelText('Логин')); // Local login remains available.
});
