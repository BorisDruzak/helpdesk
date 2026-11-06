import { afterEach, expect, it, vi } from 'vitest';
import { simulateScenario, ScenarioApiError } from './scenario-api';
afterEach(()=>vi.unstubAllGlobals());
it('keeps strict simulation default and explicitly requests author preview',async()=>{
 const fetcher=vi.fn(async(_url:unknown,_init?:RequestInit)=>new Response(JSON.stringify({status:'success',data:{}}),{headers:{'content-type':'application/json'}}));vi.stubGlobal('fetch',fetcher);
 await simulateScenario('s',1);await simulateScenario('s',1,[],undefined,undefined,undefined,true);
 expect(JSON.parse(String(fetcher.mock.calls[0][1]?.body))).not.toHaveProperty('author_preview');
 expect(JSON.parse(String(fetcher.mock.calls[1][1]?.body))).toHaveProperty('author_preview',true);
});
it('retains bounded field errors from the authenticated simulation response',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({status:'error',error_code:'INVALID_ANSWERS',errors:{name:'Field is required',bad:{raw:'not a string'},large:'x'.repeat(2000)}}),{status:400,headers:{'content-type':'application/json'}})));
 try{await simulateScenario('s',1);throw new Error('Expected rejection');}catch(error){expect(error).toBeInstanceOf(ScenarioApiError);const failure=error as ScenarioApiError;expect(failure.errors.name).toBe('Field is required');expect(failure.errors.bad).toBeUndefined();expect(failure.errors.large).toHaveLength(1000);}
});
