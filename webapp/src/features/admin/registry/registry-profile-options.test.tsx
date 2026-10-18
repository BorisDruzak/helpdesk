import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, it } from "vitest";
import { ProfileSelectOptions } from "./registry-profile-options";

it("edits labels and stable values, adds and removes list options", () => {
  function Harness() {
    const [options, setOptions] = useState<Array<string | { value: string; label: string }>>(["old"]);
    return <><ProfileSelectOptions options={options} onChange={setOptions} /><output>{JSON.stringify(options)}</output></>;
  }
  render(<Harness />);
  fireEvent.change(screen.getByLabelText("Название варианта 1"), { target: { value: "Первый" } });
  fireEvent.change(screen.getByLabelText("Значение варианта 1"), { target: { value: "first" } });
  expect(JSON.parse(screen.getByRole("status").textContent!)).toEqual([{ value: "first", label: "Первый" }]);
  fireEvent.click(screen.getByRole("button", { name: "Добавить вариант" }));
  expect(screen.getByLabelText("Название варианта 2")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Удалить вариант 1" }));
  expect(screen.queryByDisplayValue("Первый")).not.toBeInTheDocument();
  expect(screen.getByText(/используется в профилях/)).toBeInTheDocument();
});
