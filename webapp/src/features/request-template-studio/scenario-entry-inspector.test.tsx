import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { ScenarioEntryInspector } from "./scenario-entry-inspector";
import type { ScenarioDraftDefinition } from "./scenario-contract";

it("retains a trailing newline while entering multiple search phrases", () => {
  let saved: string[] | undefined;
  function Editor() {
    const [definition, setDefinition] = useState<ScenarioDraftDefinition>({ scenario_key: "s", title: "S", service_code: "it", offering_full_code: "it.print", process_binding: { request_template_key: "t" }, entry_points: [{ key: "jam", title: "Jam", target_block_id: "block" }] });
    return <ScenarioEntryInspector definition={definition} blockId="block" catalog={{ categories: [], services: [], offerings: [], scenarios: [], total: 0, offset: 0, limit: 100 }} disabled={false} onChange={next => { saved = next.entry_points?.[0].synonyms; setDefinition(next); }} />;
  }
  render(<Editor />);
  fireEvent.click(screen.getByText("Поиск в каталоге"));
  const input = screen.getByLabelText("Дополнительные поисковые выражения");
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value: "замятие\n" } });
  expect(input).toHaveValue("замятие\n");
  fireEvent.change(input, { target: { value: "замятие\nбумага застряла" } });
  expect(saved).toEqual(["замятие", "бумага застряла"]);
});
