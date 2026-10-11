const labels: Record<string, string> = {
  open: "Открыто", assigned: "Назначено", in_review: "На проверке",
  passed: "Проверка пройдена", failed: "Проверка не пройдена",
  action_required: "Требуются действия", dismissed: "Отклонено",
  in_progress: "В работе", blocked: "Заблокировано", done: "Выполнено",
  critical: "Критический", high: "Высокий", medium: "Средний", low: "Низкий", info: "Информационный",
  low_csat: "Низкая оценка пользователя", reopened: "Повторное открытие",
  sla_breached: "Нарушение SLA", high_priority: "Высокий приоритет",
  missing_evidence: "Недостаточно подтверждений", closure_policy_exception: "Исключение из правил закрытия",
  negative_kb_feedback: "Отрицательная оценка статьи", random_sample: "Выборочная проверка",
  manager_request: "Запрос руководителя", quality_audit: "Аудит качества",
  update_kb_article: "Обновить статью базы знаний", create_kb_article: "Создать статью базы знаний",
  create_known_error: "Зарегистрировать известную ошибку", improve_request_form: "Улучшить форму обращения",
  update_routing_policy: "Обновить правила маршрутизации", adjust_sla_policy: "Скорректировать правила SLA",
  add_diagnostic_playbook: "Добавить сценарий диагностики", train_support: "Обучить поддержку",
  open_problem_candidate: "Предложить регистрацию проблемы", create_change_candidate: "Предложить изменение",
  contact_requester: "Связаться с заявителем", process_review: "Пересмотреть процесс",
  perform_rca: "Проанализировать первопричину", implement_permanent_fix: "Внедрить постоянное решение",
  validate_workaround: "Проверить обходное решение", update_known_error: "Обновить известную ошибку", other: "Другое",
  global: "Все услуги", service: "Услуга", offering: "Вариант услуги", queue: "Очередь",
};

export function qualityLabel(value: string | null | undefined): string {
  return value ? labels[value] ?? "Неизвестно" : "Не указано";
}
