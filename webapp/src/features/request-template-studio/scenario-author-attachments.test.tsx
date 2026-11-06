import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ScenarioAuthorAttachmentProvider, ScenarioAuthorAttachments } from "./scenario-author-attachments";
import type { ScenarioDraftDefinition } from "./scenario-contract";
vi.mock("./scenario-api", () => ({ uploadScenarioAttachment: vi.fn() }));
const assets = ["a", "b"].map(asset_id => ({ asset_id, name: `${asset_id}.png`, mime_type: "image/png", url: `/api/web/request-scenario-assets/${asset_id}/download`, size_bytes: 1 }));
const doc = { type: "doc", content: [{ type: "paragraph", content: [{type: "text", text: "keep"}] }, {type: "image", attrs: {asset_id: "a"}}, {type: "image", attrs: {asset_id: "b"}}] };
it.each(["instruction", "field"])("removes only the selected image and attachment from %s", async kind => {
 const block = kind === "instruction" ? {id:"q",kind:"instruction",title:"Q",content:{body:"keep",attachments:assets,rich_document:doc}} : {id:"q",kind:"form_page",title:"Q",fields:[{key:"f",type:"text",label:"F",help_attachments:assets,help_document:doc}]};
 const definition = {scenario_key:"x",title:"X",blocks:[block]} as unknown as ScenarioDraftDefinition;
 const onChange=vi.fn();
 render(<ScenarioAuthorAttachmentProvider id="s" definition={definition} onChange={onChange}><ScenarioAuthorAttachments blockId="q" fieldKey={kind === "field" ? "f" : undefined} attachments={assets}/></ScenarioAuthorAttachmentProvider>);
 fireEvent.click(screen.getByRole("button",{name:"Убрать вложение a.png"}));
 await waitFor(() => expect(screen.queryByText("Сохраняем вложения…")).not.toBeInTheDocument());
 const changed=onChange.mock.lastCall![0].blocks[0]; const target=kind === "field" ? changed.fields[0] : changed.content;
 expect(target[kind === "field" ? "help_attachments" : "attachments"]).toEqual([assets[1]]);
 expect(target[kind === "field" ? "help_document" : "rich_document"].content).toEqual([doc.content[0],doc.content[2]]);
});



it("ignores an upload completing after changing scenario scope", async () => {
 const { uploadScenarioAttachment } = await import("./scenario-api");
 let resolve!: (value: typeof assets[number]) => void;
 vi.mocked(uploadScenarioAttachment).mockImplementationOnce(() => new Promise(done => { resolve = done; }));
 const definition = {scenario_key:"x",title:"X",blocks:[{id:"q",kind:"instruction",title:"Q",content:{body:"keep",attachments:[]}}]} as unknown as ScenarioDraftDefinition;
 const oldChange=vi.fn(), newChange=vi.fn();
 const view=render(<ScenarioAuthorAttachmentProvider id="old" definition={definition} onChange={oldChange}><ScenarioAuthorAttachments blockId="q" attachments={[]}/></ScenarioAuthorAttachmentProvider>);
 fireEvent.change(screen.getByLabelText("Прикрепить скриншоты или файлы"), {target:{files:[new File(["a"],"a.png",{type:"image/png"})]}});
 view.rerender(<ScenarioAuthorAttachmentProvider id="new" definition={definition} onChange={newChange}><ScenarioAuthorAttachments blockId="q" attachments={[]}/></ScenarioAuthorAttachmentProvider>);
 resolve(assets[0]); await waitFor(() => expect(screen.queryByText("Сохраняем вложения…")).not.toBeInTheDocument());
 expect(oldChange).not.toHaveBeenCalled(); expect(newChange).not.toHaveBeenCalled();
});
