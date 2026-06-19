import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  ActionCard,
  ContentSection,
  EmptyState,
  ErrorState,
  LoadingState,
  PageActions,
  PageHeader,
  PageShell,
  PageSkeleton,
  StatCard,
  StatusBadge,
} from "./page-components";

describe("ui-page components", () => {
  it("renders a labeled responsive page shell with header actions", () => {
    render(
      <PageShell ariaLabelledBy="requester-dashboard-title">
        <PageHeader
          actions={<PageActions label="Действия страницы"><button type="button">Создать</button></PageActions>}
          description="Устройства и обращения"
          eyebrow="Кабинет заявителя"
          id="requester-dashboard-title"
          title="Главная"
        />
        <ContentSection description="Сводка по заявкам" title="Обращения">
          <p>Контент</p>
        </ContentSection>
      </PageShell>,
    );

    expect(screen.getByRole("main")).toHaveAttribute("aria-labelledby", "requester-dashboard-title");
    expect(screen.getByRole("heading", { level: 1, name: "Главная" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Обращения" })).toBeInTheDocument();
    expect(screen.getByLabelText("Действия страницы")).toContainElement(screen.getByRole("button", { name: "Создать" }));
  });

  it("renders semantic loading, empty, skeleton and error states", () => {
    const retry = vi.fn();
    const { rerender } = render(<LoadingState label="Загружаем обращения" />);
    expect(screen.getByRole("status")).toHaveTextContent("Загружаем обращения");

    rerender(<PageSkeleton sections={2} title="Подготавливаем кабинет" />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByText("Подготавливаем кабинет")).toBeInTheDocument();

    rerender(<EmptyState action={<button type="button">Создать</button>} description="Пока нет заявок" title="Нет обращений" />);
    expect(screen.getByRole("heading", { name: "Нет обращений" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Создать" })).toBeInTheDocument();

    rerender(<ErrorState message="Не удалось загрузить" onRetry={retry} retryLabel="Повторить" title="Ошибка" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Не удалось загрузить");
    screen.getByRole("button", { name: "Повторить" }).click();
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("renders action, stat and status primitives without requester-specific classes", () => {
    render(
      <div>
        <ActionCard action={<button type="button">Открыть</button>} description="Продолжить настройку" title="Профиль" />
        <StatCard helper="За сегодня" label="Открытые" status={<StatusBadge status="open" />} value="3" />
        <StatusBadge status="resolved" />
      </div>,
    );

    expect(screen.getByRole("article", { name: "Профиль" })).toBeInTheDocument();
    expect(screen.getByText("Открытые")).toBeInTheDocument();
    expect(screen.getByText("Открыта")).toBeInTheDocument();
    expect(screen.getByText("Решена")).toBeInTheDocument();
  });
});
