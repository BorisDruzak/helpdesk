import type { BadgeProps } from "../../components/ui/badge";

type BadgeTone = NonNullable<BadgeProps["tone"]>;

export const TARGET_LABELS: Record<string, string> = {
  server_builtin: "Серверная проверка",
  server_connector: "API-коннектор",
  observer_query: "Запрос Observer",
  manual: "Ручная проверка",
  endpoint_operation: "Endpoint операция",
};

export const PROVIDER_GROUP_LABELS: Record<string, string> = {
  server_builtin: "Server builtins",
  server_connector: "Server connectors",
  observer_query: "Observer",
  manual: "Manual",
  endpoint_operation: "Endpoint operations",
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
  if (value === "server_connector" || value === "endpoint_operation") {
    return "brand";
  }
  if (value === "server_builtin" || value === "observer_query") {
    return "info";
  }
  return "neutral";
}
