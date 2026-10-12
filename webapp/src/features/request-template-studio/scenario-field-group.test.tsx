import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { ScenarioFieldGroup } from "./scenario-field-group";
import type { ScenarioField } from "./scenario-contract";

it("assigns and renames a section using titles while preserving stable group keys", () => {
  function Harness() {
    const [fields, setFields] = useState<ScenarioField[]>([{ key: "one", label: "Первый", type: "text" }, { key: "two", label: "Второй", type: "text", group: "existing", group_title: "Устройство" }]);
    return <><ScenarioFieldGroup field={fields[0]} fields={fields} disabled={false} onChange={setFields} /><output>{fields.map(item => `${item.group}:${item.group_title}`).join(";")}</output></>;
  }
  render(<Harness />);
  fireEvent.change(screen.getByLabelText("Раздел"), { target: { value: "existing" } });
  fireEvent.change(screen.getByLabelText("Название раздела"), { target: { value: "Параметры устройства" } });
  expect(screen.getByRole("status")).toHaveTextContent("existing:Параметры устройства;existing:Параметры устройства");
  fireEvent.change(screen.getByLabelText("Новый раздел"), { target: { value: "Влияние" } });
  fireEvent.click(screen.getByRole("button", { name: "Создать раздел для вопроса" }));
  expect(screen.getByLabelText("Название раздела")).toHaveValue("Влияние");
  expect(screen.getByRole("status")).toHaveTextContent("existing:Параметры устройства");
});
