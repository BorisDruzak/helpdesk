export const diagnosticFailureLabels = {
  unavailable: "Недоступно",
  denied: "Согласие не получено",
  timeout: "Истёк срок ожидания",
  capability_absent: "Возможность проверки отсутствует",
} as const;
export type DiagnosticFailureStatus = keyof typeof diagnosticFailureLabels;
