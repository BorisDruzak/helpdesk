import { cleanup,fireEvent,render,screen } from '@testing-library/react';
import { afterEach,expect,it,vi } from 'vitest';
import { CatalogFunnel,useCatalogEvent } from './catalog-funnel';
import { StrictMode } from 'react';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
function Child(){const record=useCatalogEvent();return <button onClick={()=>record('submitted')}>Done</button>;}
it('tracks one flow across child remounts and never reports successful submission as abandonment',async()=>{
 const fetchMock=vi.fn().mockResolvedValue({ok:true});vi.stubGlobal('fetch',fetchMock);
 const view=render(<CatalogFunnel><Child key="a"/></CatalogFunnel>);
 view.rerender(<CatalogFunnel><Child key="b"/></CatalogFunnel>);
 fireEvent.click(screen.getByText('Done'));view.unmount();
 const events=fetchMock.mock.calls.map(([,init])=>JSON.parse(init.body));
 expect(events.map(e=>e.event)).toEqual(['opened','submitted']);
 expect(new Set(events.map(e=>e.flow_id)).size).toBe(1);
 expect(Object.keys(events[0]).sort()).toEqual(['elapsed_ms','event','flow_id','rank','result_count','sequence']);
});
it('reports abandonment once even if pagehide is followed by unmount',()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true}));
 const view=render(<CatalogFunnel><Child/></CatalogFunnel>);
 window.dispatchEvent(new Event('pagehide'));view.unmount();
 expect(vi.mocked(fetch).mock.calls.map(([,init])=>JSON.parse(String(init?.body)).event)).toEqual(['opened','abandoned']);
});
it('does not turn StrictMode effect replay into a false abandonment',async()=>{
 const fetchMock=vi.fn().mockResolvedValue({ok:true});vi.stubGlobal('fetch',fetchMock);
 const view=render(<StrictMode><CatalogFunnel><Child/></CatalogFunnel></StrictMode>);
 await new Promise(resolve=>setTimeout(resolve,5));
 fireEvent.click(screen.getByText('Done'));view.unmount();
 expect(fetchMock.mock.calls.map(([,init])=>JSON.parse(init.body).event)).toEqual(['opened','submitted']);
});
