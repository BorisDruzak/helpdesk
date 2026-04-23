import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TicketRequestFormCard } from "./detail-page";

describe("TicketRequestFormCard", () => {
  it("renders structured request form data", () => {
    render(
      <TicketRequestFormCard
        requestForm={{
          request_kind: "printer",
          form_key: "printer",
          form_title: "Печать / принтер",
          rows: [
            { key: "room", label: "Кабинет", value: "214" },
            { key: "printer_model", label: "Модель", value: "HP LaserJet Pro M404" },
            { key: "printer_number", label: "Номер принтера", value: "PRN-214-01" },
          ],
        }}
      />,
    );

    expect(screen.getByText("Данные формы")).toBeInTheDocument();
    expect(screen.getByText("Печать / принтер")).toBeInTheDocument();
    expect(screen.getByText("request_kind")).toBeInTheDocument();
    expect(screen.getAllByText("printer").length).toBeGreaterThan(0);
    expect(screen.getByText("HP LaserJet Pro M404")).toBeInTheDocument();
    expect(screen.getByText("PRN-214-01")).toBeInTheDocument();
  });
});
