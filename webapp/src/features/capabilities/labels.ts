import type { BadgeProps } from "../../components/ui/badge";

type BadgeTone = NonNullable<BadgeProps["tone"]>;

export const TARGET_LABELS: Record<string, string> = {
  agent_builtin: "Встроено в агент",
  agent_managed_module: "Модуль агента",
  agent_recipe: "Agent Recipe",
  server_builtin: "Серверная проверка",
  server_connector: "API-коннектор",
  observer_query: "Запрос Observer",
  remote_assist: "Удаленная помощь",
  manual: "Ручная проверка",
  hybrid: "Hybrid",
};

export const PROVIDER_GROUP_LABELS: Record<string, string> = {
  agent_builtin: "Agent builtins",
  agent_managed_module: "Agent managed modules",
  agent_recipe: "Agent Recipe Runner",
  server_builtin: "Server builtins",
  server_connector: "Server connectors",
  observer_query: "Observer",
  remote_assist: "Remote Assist",
  manual: "Manual",
  hybrid: "Hybrid",
};

export function label(value: string | null | undefined): string {
  if (!value) {
    return "Не задано";
  }
  return TARGET_LABELS[value] ?? value;
}

export function readinessTone(value: string | null | undefined): BadgeTone {
  if (value === "available") {
    return "success";
  }
  if (
    [
      "install_required",
      "installing",
      "runner_not_installed",
      "runner_install_required",
      "runner_installing",
      "runner_outdated",
      "consent_required",
      "credentials_missing",
      "mapping_missing",
    ].includes(value ?? "")
  ) {
    return "warning";
  }
  if (
    [
      "permission_denied",
      "disabled_by_policy",
      "unsupported_platform",
      "agent_offline",
      "primitive_not_supported",
      "recipe_not_published",
      "unavailable",
    ].includes(value ?? "")
  ) {
    return "danger";
  }
  return "neutral";
}

export function riskTone(value: string | null | undefined): BadgeTone {
  if (["high", "critical", "dangerous"].includes(value ?? "")) {
    return "danger";
  }
  if (value === "medium") {
    return "warning";
  }
  if (value === "low") {
    return "success";
  }
  return "neutral";
}

export function targetTone(value: string | null | undefined): BadgeTone {
  if (value === "server_connector" || value === "agent_recipe") {
    return "brand";
  }
  if (value === "server_builtin" || value === "observer_query") {
    return "info";
  }
  if (value === "remote_assist") {
    return "warning";
  }
  return "neutral";
}
