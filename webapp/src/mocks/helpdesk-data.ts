export type BadgeTone = "brand" | "danger" | "info" | "neutral" | "success" | "warning";

export type TicketStatus =
  | "new"
  | "in_progress"
  | "waiting_on_user"
  | "resolved";

export type TicketPriority = "low" | "medium" | "high";

export type TicketMessage = {
  id: string;
  author: string;
  body: string;
  role: "agent" | "client" | "system";
  timestamp: string;
};

export type TicketAttachment = {
  id: string;
  name: string;
  size: string;
};

export type TicketHistoryItem = {
  id: string;
  label: string;
  detail: string;
  timestamp: string;
};

export type TicketRecord = {
  id: string;
  code: string;
  title: string;
  category: string;
  requesterName: string;
  requesterEmail: string;
  requesterPhone: string;
  assigneeName: string;
  browser: string;
  os: string;
  ipAddress: string;
  createdAt: string;
  updatedAt: string;
  responseSla: string;
  resolutionSla: string;
  channel: string;
  mine: boolean;
  unreadCount: number;
  priority: TicketPriority;
  status: TicketStatus;
  tags: string[];
  summary: string;
  messages: TicketMessage[];
  attachments: TicketAttachment[];
  history: TicketHistoryItem[];
};

export type DeviceRecord = {
  id: string;
  hostname: string;
  platform: string;
  version: string;
  target: string;
  owner: string;
  location: string;
  lastSeen: string;
  status: "online" | "offline" | "attention";
  rolloutStatus: string;
  observerHealth: string;
  notes: string;
};

export type ModuleRecord = {
  name: string;
  summary: string;
  preferredVersion: string;
  latestVersion: string;
  statusLabel: string;
  statusTone: BadgeTone;
  maintainer: string;
  updatedAt: string;
};

export type ObserverTrace = {
  id: string;
  title: string;
  device: string;
  status: string;
  statusTone: BadgeTone;
  duration: string;
  timestamp: string;
  summary: string;
};

export type KnowledgeArticle = {
  id: string;
  title: string;
  category: string;
  views: string;
  helpful: string;
  updatedAt: string;
  summary: string;
};

export type ReportMetric = {
  label: string;
  value: string;
  delta: string;
  tone: BadgeTone;
};

export const ticketStatusMeta: Record<
  TicketStatus,
  { label: string; tone: BadgeTone }
> = {
  new: { label: "Новый", tone: "info" },
  in_progress: { label: "В работе", tone: "success" },
  waiting_on_user: { label: "Ожидает ответа", tone: "warning" },
  resolved: { label: "Решен", tone: "brand" }
};

export const ticketPriorityMeta: Record<
  TicketPriority,
  { label: string; tone: BadgeTone }
> = {
  low: { label: "Низкий", tone: "success" },
  medium: { label: "Средний", tone: "warning" },
  high: { label: "Высокий", tone: "danger" }
};

export const tickets: TicketRecord[] = [
  {
    id: "tk-2024-0421",
    code: "TK-2024-0421",
    title: "Не работает вход в личный кабинет",
    category: "Техническая поддержка",
    requesterName: "Иван Петров",
    requesterEmail: "ivan.petrov@example.com",
    requesterPhone: "+7 (999) 123-45-67",
    assigneeName: "Алексей П.",
    browser: "Google Chrome 124.0",
    os: "Windows 11",
    ipAddress: "192.168.1.1",
    createdAt: "12 мая 2024, 14:32",
    updatedAt: "12 мая 2024, 14:50",
    responseSla: "15м",
    resolutionSla: "24ч",
    channel: "Портал",
    mine: true,
    unreadCount: 2,
    priority: "medium",
    status: "in_progress",
    tags: ["вход", "пароль", "личный кабинет"],
    summary:
      "Пользователь сообщает об ошибке авторизации. Требуется перепроверить сброс пароля и журнал попыток входа.",
    messages: [
      {
        id: "msg-1",
        author: "Иван Петров",
        body: "Здравствуйте! Не могу войти в личный кабинет. При вводе пароля появляется ошибка «Неверный логин или пароль». Хотя я точно не менял пароль.",
        role: "client",
        timestamp: "12 мая 2024, 14:32"
      },
      {
        id: "msg-2",
        author: "Алексей П.",
        body: "Спасибо за обращение. Давайте попробуем сбросить пароль. Проверьте, пожалуйста, вашу почту: я отправил ссылку для сброса.",
        role: "agent",
        timestamp: "12 мая 2024, 14:45"
      },
      {
        id: "msg-3",
        author: "Иван Петров",
        body: "Спасибо, письмо получил, пароль успешно сбросил. Теперь все работает!",
        role: "client",
        timestamp: "12 мая 2024, 14:48"
      },
      {
        id: "msg-4",
        author: "Алексей П.",
        body: "Отлично. Если возникнут другие вопросы, обращайтесь.",
        role: "agent",
        timestamp: "12 мая 2024, 14:50"
      }
    ],
    attachments: [
      { id: "file-1", name: "screenshot-login-error.png", size: "1.8 MB" },
      { id: "file-2", name: "auth-log-export.txt", size: "36 KB" }
    ],
    history: [
      {
        id: "hist-1",
        label: "Создан тикет",
        detail: "Заявка поступила через портал самообслуживания.",
        timestamp: "12 мая 2024, 14:32"
      },
      {
        id: "hist-2",
        label: "Назначен агент",
        detail: "Тикет автоматически назначен на линию ServiceDesk L1.",
        timestamp: "12 мая 2024, 14:40"
      }
    ]
  },
  {
    id: "tk-2024-0420",
    code: "TK-2024-0420",
    title: "Ошибка при сбросе пароля",
    category: "Учетные записи",
    requesterName: "Мария Смирнова",
    requesterEmail: "maria.smirnova@example.com",
    requesterPhone: "+7 (982) 001-11-21",
    assigneeName: "Алексей П.",
    browser: "Яндекс Браузер 24.4",
    os: "Windows 10",
    ipAddress: "10.0.5.40",
    createdAt: "12 мая 2024, 14:11",
    updatedAt: "12 мая 2024, 14:32",
    responseSla: "15м",
    resolutionSla: "24ч",
    channel: "Почта",
    mine: true,
    unreadCount: 1,
    priority: "high",
    status: "waiting_on_user",
    tags: ["аккаунт", "сброс пароля"],
    summary: "Пользователь не получает письмо для сброса пароля. Нужна проверка SMTP и очереди уведомлений.",
    messages: [
      {
        id: "msg-5",
        author: "Мария Смирнова",
        body: "Ссылка для сброса пароля не приходит уже 20 минут.",
        role: "client",
        timestamp: "12 мая 2024, 14:11"
      },
      {
        id: "msg-6",
        author: "Алексей П.",
        body: "Перепроверил почтовый шлюз. Отправка восстановлена, жду подтверждения от пользователя.",
        role: "agent",
        timestamp: "12 мая 2024, 14:32"
      }
    ],
    attachments: [],
    history: [
      {
        id: "hist-3",
        label: "Изменен статус",
        detail: "Тикет переведен в ожидание ответа пользователя.",
        timestamp: "12 мая 2024, 14:32"
      }
    ]
  },
  {
    id: "tk-2024-0419",
    code: "TK-2024-0419",
    title: "Не приходит письмо с подтверждением",
    category: "Почта",
    requesterName: "ООО «Агро-Сервис»",
    requesterEmail: "support@agro-service.ru",
    requesterPhone: "+7 (343) 800-01-11",
    assigneeName: "Екатерина Л.",
    browser: "Mozilla Firefox 126",
    os: "macOS Sonoma",
    ipAddress: "172.16.4.30",
    createdAt: "12 мая 2024, 13:55",
    updatedAt: "12 мая 2024, 14:10",
    responseSla: "30м",
    resolutionSla: "48ч",
    channel: "Портал",
    mine: false,
    unreadCount: 0,
    priority: "low",
    status: "new",
    tags: ["email", "подтверждение"],
    summary: "Подозрение на задержку в очереди отправки или блокировку домена на стороне получателя.",
    messages: [],
    attachments: [],
    history: [
      {
        id: "hist-4",
        label: "Создан тикет",
        detail: "Новый тикет ожидает назначения.",
        timestamp: "12 мая 2024, 13:55"
      }
    ]
  },
  {
    id: "tk-2024-0418",
    code: "TK-2024-0418",
    title: "Вопрос по настройке уведомлений",
    category: "Настройки профиля",
    requesterName: "Андрей Волков",
    requesterEmail: "andrey.volkov@example.com",
    requesterPhone: "+7 (912) 555-31-40",
    assigneeName: "Екатерина Л.",
    browser: "Google Chrome 123.0",
    os: "Windows 11",
    ipAddress: "10.5.0.12",
    createdAt: "12 мая 2024, 13:18",
    updatedAt: "12 мая 2024, 13:55",
    responseSla: "1ч",
    resolutionSla: "48ч",
    channel: "Чат",
    mine: false,
    unreadCount: 0,
    priority: "medium",
    status: "in_progress",
    tags: ["уведомления"],
    summary: "Нужно настроить персональные email-уведомления по срокам ответа и эскалациям.",
    messages: [],
    attachments: [],
    history: []
  },
  {
    id: "tk-2024-0417",
    code: "TK-2024-0417",
    title: "Не отображаются данные в отчете",
    category: "Отчеты",
    requesterName: "Екатерина Лебедева",
    requesterEmail: "e.lebedeva@example.com",
    requesterPhone: "+7 (912) 676-33-90",
    assigneeName: "Олег К.",
    browser: "Edge 124.0",
    os: "Windows 11",
    ipAddress: "192.168.30.2",
    createdAt: "12 мая 2024, 12:50",
    updatedAt: "12 мая 2024, 13:20",
    responseSla: "15м",
    resolutionSla: "24ч",
    channel: "Портал",
    mine: false,
    unreadCount: 0,
    priority: "high",
    status: "waiting_on_user",
    tags: ["отчеты", "дашборд"],
    summary: "Похоже на задержку синхронизации данных после обновления ETL-пакета.",
    messages: [],
    attachments: [],
    history: []
  },
  {
    id: "tk-2024-0416",
    code: "TK-2024-0416",
    title: "Интеграция с 1С",
    category: "Интеграции",
    requesterName: "ООО «Ромашка»",
    requesterEmail: "it@romashka.example",
    requesterPhone: "+7 (343) 550-20-20",
    assigneeName: "Олег К.",
    browser: "Google Chrome 122.0",
    os: "ALT Linux",
    ipAddress: "10.10.1.24",
    createdAt: "12 мая 2024, 12:02",
    updatedAt: "12 мая 2024, 12:45",
    responseSla: "1ч",
    resolutionSla: "72ч",
    channel: "Почта",
    mine: false,
    unreadCount: 0,
    priority: "medium",
    status: "resolved",
    tags: ["1с", "api"],
    summary: "Проблема с access token решена. Интеграция подтверждена заказчиком.",
    messages: [],
    attachments: [],
    history: []
  }
];

export const ticketById = new Map(tickets.map((ticket) => [ticket.id, ticket]));

export const reportMetrics: ReportMetric[] = [
  { label: "Всего тикетов", value: "128", delta: "+12%", tone: "success" },
  { label: "В работе", value: "45", delta: "+8%", tone: "success" },
  { label: "Решено", value: "78", delta: "+15%", tone: "brand" },
  { label: "Средний ответ", value: "12м 24с", delta: "-10%", tone: "brand" }
];

export const reportTrend = [
  { day: "12 мая", requests: 8, waiting: 6, resolved: 3 },
  { day: "13 мая", requests: 14, waiting: 7, resolved: 5 },
  { day: "14 мая", requests: 11, waiting: 10, resolved: 6 },
  { day: "15 мая", requests: 17, waiting: 12, resolved: 8 },
  { day: "16 мая", requests: 15, waiting: 10, resolved: 7 },
  { day: "17 мая", requests: 20, waiting: 14, resolved: 9 }
];

export const reportChannels = [
  { label: "Портал", value: 62, tone: "brand" as const },
  { label: "Почта", value: 24, tone: "success" as const },
  { label: "Телефон", value: 10, tone: "warning" as const },
  { label: "Чат", value: 4, tone: "info" as const }
];

export const knowledgeCategories = [
  { label: "Все статьи", count: 128 },
  { label: "Начало работы", count: 24 },
  { label: "Аккаунт и доступ", count: 32 },
  { label: "Настройки", count: 18 },
  { label: "Интеграции", count: 15 },
  { label: "Частые вопросы", count: 25 },
  { label: "Устранение неполадок", count: 14 }
];

export const knowledgeArticles: KnowledgeArticle[] = [
  {
    id: "kb-1",
    title: "Как восстановить пароль",
    category: "Аккаунт и доступ",
    views: "1.2K",
    helpful: "98",
    updatedAt: "04.05.2024",
    summary: "Пошаговая инструкция по сбросу пароля для личного кабинета."
  },
  {
    id: "kb-2",
    title: "Как добавить нового сотрудника",
    category: "Начало работы",
    views: "980",
    helpful: "76",
    updatedAt: "05.05.2024",
    summary: "Создание учетной записи, назначение ролей и первичная настройка."
  },
  {
    id: "kb-3",
    title: "Настройка уведомлений",
    category: "Настройки",
    views: "870",
    helpful: "64",
    updatedAt: "06.05.2024",
    summary: "Как выбрать каналы и правила уведомлений для операторов и руководителей."
  },
  {
    id: "kb-4",
    title: "Интеграция с 1С",
    category: "Интеграции",
    views: "650",
    helpful: "51",
    updatedAt: "03.05.2024",
    summary: "Подключение и проверка обмена данными между HelpDesk и 1С."
  }
];

export const settingsTabs = [
  "Общие",
  "Почта",
  "Уведомления",
  "Сроки ответа",
  "Поля тикетов",
  "Интеграции",
  "Безопасность"
];

export const devices: DeviceRecord[] = [
  {
    id: "dev-1",
    hostname: "ADMIN-2",
    platform: "Windows",
    version: "3.1.20",
    target: "windows_amd64",
    owner: "Алексей П.",
    location: "Отдел ИТ",
    lastSeen: "22 апр. 2026, 00:14",
    status: "attention",
    rolloutStatus: "Ждет связи",
    observerHealth: "Есть предупреждения",
    notes: "Свежий update-статус появится после следующего подключения."
  },
  {
    id: "dev-2",
    hostname: "SRV-ROLLOUT-01",
    platform: "Windows Server",
    version: "3.1.21",
    target: "windows_amd64",
    owner: "Команда выпуска",
    location: "ЦОД",
    lastSeen: "22 апр. 2026, 09:12",
    status: "online",
    rolloutStatus: "Актуален",
    observerHealth: "Норма",
    notes: "Канарейка для финальной волны обновления."
  },
  {
    id: "dev-3",
    hostname: "LT-02",
    platform: "ALT Linux",
    version: "3.1.18",
    target: "linux_alt_x86_64",
    owner: "Олег К.",
    location: "Полевая группа",
    lastSeen: "21 апр. 2026, 23:48",
    status: "offline",
    rolloutStatus: "Оффлайн",
    observerHealth: "Нужно проверить",
    notes: "Устройство давно не выходило на связь."
  },
  {
    id: "dev-4",
    hostname: "OPS-WS-14",
    platform: "Windows",
    version: "3.1.20",
    target: "windows_amd64",
    owner: "Мария С.",
    location: "Служба поддержки",
    lastSeen: "22 апр. 2026, 09:54",
    status: "online",
    rolloutStatus: "Готово к обновлению",
    observerHealth: "Норма",
    notes: "Подходит для ручной проверки rollout-пакета."
  }
];

export const moduleRegistry: ModuleRecord[] = [
  {
    name: "devices_inventory",
    summary: "Синхронизация typed inventory и статусов агентов.",
    preferredVersion: "4.2.1",
    latestVersion: "4.2.3",
    statusLabel: "Требует ревью",
    statusTone: "warning",
    maintainer: "infra-platform",
    updatedAt: "22 апр. 2026, 08:30"
  },
  {
    name: "modules_workbench",
    summary: "Пайплайн загрузки и preferred-версий модулей.",
    preferredVersion: "2.8.0",
    latestVersion: "2.8.0",
    statusLabel: "Стабильно",
    statusTone: "success",
    maintainer: "platform-tools",
    updatedAt: "21 апр. 2026, 17:10"
  },
  {
    name: "observer_quick",
    summary: "Быстрый срез по деградациям, сигнатурам и опасным флоу.",
    preferredVersion: "1.9.4",
    latestVersion: "2.0.0-rc1",
    statusLabel: "Есть RC",
    statusTone: "info",
    maintainer: "observability",
    updatedAt: "22 апр. 2026, 06:45"
  }
];

export const observerTraces: ObserverTrace[] = [
  {
    id: "trace-update-1",
    title: "Launcher signature mismatch",
    device: "ADMIN-2",
    status: "Ошибка",
    statusTone: "danger",
    duration: "6.4с",
    timestamp: "22 апр. 2026, 09:24",
    summary: "После старта обновления возникла несогласованность сигнатур пакета."
  },
  {
    id: "trace-policy-9",
    title: "Rollback policy skipped",
    device: "SRV-ROLLOUT-01",
    status: "Предупреждение",
    statusTone: "warning",
    duration: "1.2с",
    timestamp: "22 апр. 2026, 09:06",
    summary: "Сценарий завершился успешно, но без fallback-политики."
  },
  {
    id: "trace-linux-1",
    title: "Linux agent heartbeat",
    device: "LT-02",
    status: "Норма",
    statusTone: "success",
    duration: "0.8с",
    timestamp: "21 апр. 2026, 23:48",
    summary: "Последний heartbeat обработан без деградаций."
  }
];

export function getTicketQueueCounts() {
  return {
    all: tickets.length,
    mine: tickets.filter((ticket) => ticket.mine).length,
    new: tickets.filter((ticket) => ticket.status === "new").length,
    in_progress: tickets.filter((ticket) => ticket.status === "in_progress").length,
    waiting_on_user: tickets.filter((ticket) => ticket.status === "waiting_on_user").length,
    resolved: tickets.filter((ticket) => ticket.status === "resolved").length
  };
}

export function getDeviceById(deviceId: string) {
  return devices.find((device) => device.id === deviceId) ?? devices[0];
}

export function getTicketById(ticketId: string) {
  return ticketById.get(ticketId) ?? tickets[0];
}
