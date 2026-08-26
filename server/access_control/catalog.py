from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class PermissionDefinition:
    code: str
    label: str
    description: str
    group: str
    group_label: str
    risk: str = "normal"


ROLE_LABELS: dict[str, str] = {
    "admin": "Администратор",
    "support": "Поддержка",
    "auditor": "Аудитор",
    "user": "Пользователь",
    "agent": "Агент",
    "system": "Система",
}

PERMISSION_CATALOG: tuple[PermissionDefinition, ...] = (
    PermissionDefinition(
        "workspace.admin.view",
        "Видеть admin workspace",
        "Доступ к административной рабочей области /app/admin.",
        "workspaces",
        "Рабочие области",
    ),
    PermissionDefinition(
        "workspace.support.view",
        "Видеть support workspace",
        "Доступ к операторской рабочей области поддержки.",
        "workspaces",
        "Рабочие области",
    ),
    PermissionDefinition(
        "workspace.requester.view",
        "Requester workspace",
        "Authenticated requester workspace /app/requester.",
        "workspaces",
        "Workspaces",
    ),
    PermissionDefinition(
        "requester.ticket.view",
        "View own requester tickets",
        "Read requester-safe tickets owned by the authenticated web user.",
        "requester",
        "Requester workspace",
    ),
    PermissionDefinition(
        "requester.ticket.create",
        "Create requester tickets",
        "Create tickets for devices owned by the authenticated web user.",
        "requester",
        "Requester workspace",
    ),
    PermissionDefinition(
        "requester.ticket.comment",
        "Comment on own requester tickets",
        "Send requester-visible messages on owned tickets.",
        "requester",
        "Requester workspace",
    ),
    PermissionDefinition(
        "requester.ticket.close",
        "Close own requester tickets",
        "Confirm closure for owned requester tickets.",
        "requester",
        "Requester workspace",
    ),
    PermissionDefinition(
        "requester.ticket.reopen",
        "Reopen own requester tickets",
        "Request reopen for owned requester tickets.",
        "requester",
        "Requester workspace",
    ),
    PermissionDefinition(
        "requester.ticket.feedback",
        "Leave requester feedback",
        "Submit requester feedback for owned tickets.",
        "requester",
        "Requester workspace",
    ),
    PermissionDefinition(
        "requester.ticket.attachment.upload",
        "Upload requester attachments",
        "Upload attachments for owned requester tickets.",
        "requester",
        "Requester workspace",
    ),
    PermissionDefinition(
        "requester.ticket.attachment.download",
        "Download requester attachments",
        "Download requester-visible attachments for owned tickets.",
        "requester",
        "Requester workspace",
    ),
    PermissionDefinition(
        "requester.device.view",
        "View own devices",
        "Read devices actively bound to the authenticated requester identity.",
        "requester",
        "Requester workspace",
    ),
    PermissionDefinition(
        "requester.profile.view",
        "View requester profile",
        "Read the registry person profile resolved for the authenticated web user.",
        "requester",
        "Requester workspace",
    ),
    PermissionDefinition(
        "requester.consent.decide",
        "Decide requester consent",
        "Approve or deny requester-owned consent prompts.",
        "requester",
        "Requester workspace",
    ),
    PermissionDefinition(
        "admin.access.view",
        "Открывать Access Control",
        "Просмотр панели пользователей, ролей, прав и effective access.",
        "admin",
        "Администрирование",
    ),
    PermissionDefinition(
        "admin.inventory.view",
        "Смотреть inventory",
        "Просмотр устройств, токенов и состояния агентов.",
        "admin",
        "Администрирование",
    ),
    PermissionDefinition(
        "admin.inventory.manage_tokens",
        "Управлять токенами устройств",
        "Отзыв и просмотр agent tokens.",
        "admin",
        "Администрирование",
        risk="high",
    ),
    PermissionDefinition(
        "admin.registry.view",
        "Смотреть реестры",
        "Просмотр людей, локаций, сервисов и активов.",
        "admin",
        "Администрирование",
    ),
    PermissionDefinition(
        "admin.modules.view",
        "Смотреть модули",
        "Просмотр реестра модулей и статуса rollout.",
        "modules",
        "Модули и инструменты",
    ),
    PermissionDefinition(
        "admin.modules.author",
        "Публиковать модули",
        "Создание, проверка и публикация новых версий модулей.",
        "modules",
        "Модули и инструменты",
        risk="high",
    ),
    PermissionDefinition(
        "modules.audit",
        "Аудит Endpoint Recipe модулей",
        "Просмотр metadata и audit Endpoint Recipe модулей без authoring или execution.",
        "modules",
        "Модули и инструменты",
    ),
    PermissionDefinition(
        "admin.playbooks.view",
        "Смотреть плейбуки",
        "Просмотр конструктора диагностических плейбуков.",
        "automation",
        "Автоматизация",
    ),
    PermissionDefinition(
        "admin.playbooks.publish",
        "Публиковать плейбуки",
        "Сохранение и публикация диагностических playbook-сценариев.",
        "automation",
        "Автоматизация",
        risk="high",
    ),
    PermissionDefinition(
        "admin.forms.view",
        "Смотреть конструктор форм",
        "Просмотр каталога request forms и route preview.",
        "automation",
        "Автоматизация",
    ),
    PermissionDefinition(
        "admin.forms.publish",
        "Публиковать формы",
        "Сохранение каталога форм заявок и playbook triggers.",
        "automation",
        "Автоматизация",
        risk="high",
    ),
    PermissionDefinition(
        "settings.view",
        "Смотреть настройки",
        "Просмотр очередей, SLA, routing и ticket lifecycle.",
        "settings",
        "Настройки",
    ),
    PermissionDefinition(
        "settings.manage_queues",
        "Управлять очередями",
        "Изменение очередей и участников очередей.",
        "settings",
        "Настройки",
        risk="high",
    ),
    PermissionDefinition(
        "settings.manage_routing",
        "Управлять routing",
        "Изменение routing rules, SLA, календарей и resolution codes.",
        "settings",
        "Настройки",
        risk="high",
    ),
    PermissionDefinition(
        "ticket.queue.view",
        "Видеть очередь тикетов",
        "Просмотр доступной оператору очереди заявок.",
        "tickets",
        "Тикеты",
    ),
    PermissionDefinition(
        "ticket.detail.view",
        "Открывать тикет",
        "Просмотр карточки тикета, timeline и формы заявки.",
        "tickets",
        "Тикеты",
    ),
    PermissionDefinition(
        "ticket.status.change",
        "Менять статус тикета",
        "Запуск разрешённых FSM-переходов статуса.",
        "tickets",
        "Тикеты",
    ),
    PermissionDefinition(
        "ticket.queue.change",
        "Переключать очередь",
        "Ручной перевод тикета между доступными очередями.",
        "tickets",
        "Тикеты",
        risk="high",
    ),
    PermissionDefinition(
        "ticket.assign",
        "Назначать исполнителя",
        "Назначение support/admin исполнителей внутри правил очереди.",
        "tickets",
        "Тикеты",
    ),
    PermissionDefinition(
        "ticket.comment.public",
        "Писать публичные комментарии",
        "Ответы, которые видит requester.",
        "tickets",
        "Тикеты",
    ),
    PermissionDefinition(
        "ticket.comment.internal",
        "Писать внутренние заметки",
        "Комментарии только для support/admin.",
        "tickets",
        "Тикеты",
    ),
    PermissionDefinition(
        "ticket.passport.manage",
        "Вести паспорт решения",
        "Создание evidence, action log и official resolution dossier.",
        "tickets",
        "Тикеты",
    ),
    PermissionDefinition(
        "diagnostics.create_manual_evidence",
        "Добавлять ручные диагностические факты",
        "Создание manual diagnostic evidence без автоматического изменения статуса тикета.",
        "tickets",
        "Тикеты",
    ),
    PermissionDefinition(
        "ticket.playbook.run",
        "Запускать плейбуки из тикета",
        "Запуск опубликованных диагностических playbooks против устройства тикета.",
        "automation",
        "Автоматизация",
        risk="high",
    ),
    PermissionDefinition(
        "ticket.tool.run",
        "Запускать инструменты из тикета",
        "Запуск module/tool команд из support-карточки.",
        "modules",
        "Модули и инструменты",
        risk="high",
    ),
    PermissionDefinition(
        "remote_assist.request",
        "Запрашивать удалённую помощь",
        "Создание view-only Remote Assist сессии из тикета с обязательным согласием пользователя.",
        "remote_assist",
        "Удалённая помощь",
        risk="high",
    ),
    PermissionDefinition(
        "remote_assist.view",
        "Открывать удалённую помощь",
        "Просмотр статуса и подключение к разрешённой Remote Assist сессии.",
        "remote_assist",
        "Удалённая помощь",
        risk="high",
    ),
    PermissionDefinition(
        "remote_assist.control",
        "Управлять мышью и клавиатурой",
        "Запрос interactive-control Remote Assist сессии после явного согласия пользователя.",
        "remote_assist",
        "Удалённая помощь",
        risk="high",
    ),
    PermissionDefinition(
        "remote_assist.file_transfer",
        "Передавать файлы",
        "Запрос передачи файлов внутри Remote Assist сессии с отдельным согласием.",
        "remote_assist",
        "Удалённая помощь",
        risk="high",
    ),
    PermissionDefinition(
        "remote_assist.clipboard",
        "Работать с clipboard",
        "Запрос чтения или записи буфера обмена внутри Remote Assist сессии с отдельным согласием.",
        "remote_assist",
        "Удалённая помощь",
        risk="high",
    ),
    PermissionDefinition(
        "remote_assist.elevated",
        "Запрашивать elevated/admin mode",
        "Запрос видимой elevated/admin Remote Assist сессии без обхода системного подтверждения.",
        "remote_assist",
        "Удалённая помощь",
        risk="high",
    ),
    PermissionDefinition(
        "remote_assist.unattended",
        "Запрашивать managed unattended access",
        "Запрос policy-backed unattended access только для явно enrolled устройств.",
        "remote_assist",
        "Удалённая помощь",
        risk="high",
    ),
    PermissionDefinition(
        "module.tool.run.low_risk",
        "Запускать low-risk tools",
        "Запуск безопасных диагностических команд.",
        "modules",
        "Модули и инструменты",
    ),
    PermissionDefinition(
        "module.tool.run.high_risk",
        "Запускать high-risk tools",
        "Запуск команд с повышенным риском, где требуется server policy/consent.",
        "modules",
        "Модули и инструменты",
        risk="high",
    ),
    PermissionDefinition(
        "observer.trace.view",
        "Смотреть observer traces",
        "Просмотр trace detail, signatures и degradation groups.",
        "observer",
        "Observer",
    ),
    PermissionDefinition(
        "monitoring.zabbix.view",
        "View Zabbix diagnostics",
        "Run read-only Zabbix monitoring lookups from diagnostic capabilities.",
        "monitoring",
        "Monitoring",
    ),
    PermissionDefinition(
        "admin.observer.view",
        "Открывать admin observer",
        "Доступ к /app/admin/observer.",
        "observer",
        "Observer",
    ),
    PermissionDefinition(
        "control.server.view",
        "Смотреть runtime сервера",
        "Просмотр health/status/logs control-plane.",
        "runtime",
        "Runtime",
    ),
    PermissionDefinition(
        "control.server.action",
        "Управлять runtime сервера",
        "Start/stop/restart/smoke действия control-plane.",
        "runtime",
        "Runtime",
        risk="high",
    ),
)


ROLE_DEFAULTS: dict[str, frozenset[str]] = {
    "admin": frozenset(permission.code for permission in PERMISSION_CATALOG),
    "support": frozenset(
        {
            "workspace.support.view",
            "settings.view",
            "ticket.queue.view",
            "ticket.detail.view",
            "ticket.status.change",
            "ticket.queue.change",
            "ticket.assign",
            "ticket.comment.public",
            "ticket.comment.internal",
            "ticket.passport.manage",
            "diagnostics.create_manual_evidence",
            "ticket.playbook.run",
            "ticket.tool.run",
            "remote_assist.request",
            "remote_assist.view",
            "remote_assist.control",
            "remote_assist.file_transfer",
            "remote_assist.clipboard",
            "remote_assist.elevated",
            "module.tool.run.low_risk",
            "module.tool.run.high_risk",
            "monitoring.zabbix.view",
            "observer.trace.view",
            "control.server.view",
        }
    ),
    "auditor": frozenset(
        {
            "settings.view",
            "ticket.queue.view",
            "ticket.detail.view",
            "observer.trace.view",
            "control.server.view",
            "modules.audit",
        }
    ),
    "user": frozenset(
        {
            "workspace.requester.view",
            "requester.ticket.view",
            "requester.ticket.create",
            "requester.ticket.comment",
            "requester.ticket.close",
            "requester.ticket.reopen",
            "requester.ticket.feedback",
            "requester.ticket.attachment.upload",
            "requester.ticket.attachment.download",
            "requester.device.view",
            "requester.profile.view",
            "requester.consent.decide",
            "ticket.detail.view",
            "ticket.comment.public",
        }
    ),
    "agent": frozenset(),
    "system": frozenset(),
}

CATALOG_VERSION = "rbac-" + sha256(
    "|".join(permission.code for permission in PERMISSION_CATALOG).encode("utf-8")
).hexdigest()[:12]


def normalize_role(actor_role: str | None) -> str:
    return str(actor_role or "").strip().lower() or "user"


def get_permission_catalog() -> tuple[PermissionDefinition, ...]:
    return PERMISSION_CATALOG


def get_role_permission_codes(actor_role: str | None) -> list[str]:
    role = normalize_role(actor_role)
    return sorted(ROLE_DEFAULTS.get(role, ROLE_DEFAULTS["user"]))


def get_role_label(actor_role: str | None) -> str:
    role = normalize_role(actor_role)
    return ROLE_LABELS.get(role, role)


def get_available_workspaces(actor_role: str | None) -> list[str]:
    permissions = set(get_role_permission_codes(actor_role))
    workspaces: list[str] = []
    if "workspace.admin.view" in permissions:
        workspaces.append("admin")
    if "workspace.support.view" in permissions:
        workspaces.append("support")
    if "workspace.requester.view" in permissions:
        workspaces.append("requester")
    return workspaces


def get_default_workspace(actor_role: str | None) -> str | None:
    workspaces = get_available_workspaces(actor_role)
    return workspaces[0] if workspaces else None
