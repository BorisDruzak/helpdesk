import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { CatalogCategories } from "./catalog-categories";

afterEach(cleanup);
it("keeps compatibility forms in a collapsed section without hiding the published service", () => {
  const select = vi.fn();
  render(<CatalogCategories categories={[
    {key:"print",title:"Принтеры и МФУ",offeringFullCode:"it.print",items:[]},
    {key:"legacy",title:"Печать / принтер",supplemental:true,items:[]},
  ]} onSelect={vi.fn()} onCategorySelect={select} />);
  expect(screen.getByRole("button",{name:"Принтеры и МФУ"})).toBeVisible();
  expect(screen.getByText("Печать / принтер")).not.toBeVisible();
  fireEvent.click(screen.getByText("Дополнительные формы (1)"));
  fireEvent.click(screen.getByRole("button",{name:"Печать / принтер"}));
  expect(select).toHaveBeenCalledWith("legacy");
});
