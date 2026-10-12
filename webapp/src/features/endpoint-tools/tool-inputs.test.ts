import { describe,expect,it } from "vitest";

describe("published Endpoint input controls",()=>{
  it("rejects invalid intersections and preserves exact integer bounds",async()=>{
    const module=await import("./tool-inputs").catch(()=>null);
    expect(module).not.toBeNull();
    const valid={name:"count",value_type:"integer" as const,minimum:1,maximum:5,enum_values:null};
    expect(module!.validControls([valid])).toBe(true);
    expect(module!.validControls([{...valid,minimum:6}])).toBe(false);
    expect(module!.validateInputs([valid],{count:6})).not.toBeNull();
    expect(module!.validateInputs([valid],{count:2})).toBeNull();
  });
  it("does not coerce integer inputs or accept URL network targets",async()=>{
    const module=await import("./tool-inputs").catch(()=>null);
    expect(module).not.toBeNull();
    expect(module!.validateInputs([{name:"count",value_type:"integer",minimum:1,maximum:5,enum_values:null}],{count:"2"})).not.toBeNull();
    expect(module!.validateInputs([{name:"target",value_type:"string",minimum:null,maximum:null,enum_values:null}],{target:"https://example.test/private"})).not.toBeNull();
  });
});
