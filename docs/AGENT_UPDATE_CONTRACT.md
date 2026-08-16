# Agent Update Contract

Жёсткие правила для self-update агента и server-side rollout. Этот документ — cross-cutting контракт между `server/` и `pc_agent/`.

## 1. Source of truth

- Серверный `rollout_policy` по `target` — единственный источник истины для рекомендованной версии.
- `target`-ы независимы: `windows_amd64`, `linux_alt_x86_64`, `linux_amd64` ведут собственные цепочки билдов и rollout.
- GUI агента и admin UI не должны самостоятельно решать, какая версия "актуальна"; они только отображают server verdict.

## 2. Build identity

- Build идентифицируется тройкой `(target, channel, version)`.
- Нельзя выпускать новый артефакт под уже использованным `version` как обычный сценарий.
- Если меняется распространяемый агентский бинарь или launcher, обязательно bump `pc_agent/version.py`.
- Минимальный поддерживаемый baseline для рабочего self-update контракта — `3.1.8`. Более старые build-ы нельзя держать в активном rollout и не рекомендуется хранить в рабочем server registry.

## 3. Recommendation semantics

- Если assigned rollout отличается от текущей версии агента, это actionable mismatch в обе стороны:
  - upgrade на более новую rollout-версию;
  - controlled rollback на более старую rollout-версию.
- После успешного startup handshake агент может один раз автоматически запросить текущий recommended build через обычный self-update endpoint. Это не меняет source of truth: сервер всё равно проверяет target/channel/version и разрешает agent-role запрос только для собственного устройства.
- `scheduled` не считается подтверждённым успехом обновления.
- Успешное обновление подтверждается только следующим handshake новой версии (`applied_update_version` + `last_update_operation_id`).
- Launcher-side failure подтверждается следующим handshake с `failed_update_*`.

A stale `pending_update.json` whose version is not newer than the running `AGENT_VERSION` must be archived as `last_stale_pending_update.json`; it must not block a newer recommended build.

Server handshake may also auto-enqueue an `agent_update` for already-installed older agents when the assigned rollout is a newer release, there is no active update operation, and the last failed update is not for the same recommended version. This compatibility path uses reason `agent_handshake_auto_update`; newer agents may still request the same recommended build themselves with reason `agent_startup_auto_update`.

## 4. Auth and command semantics

- `POST /api/devices/{device_id}/agent/update` разрешён:
  - `admin/system` — для допустимого build-а;
  - `agent` — только для собственного `device_id` и только для текущего recommended build-а.
- Сама WS-команда `update` считается server-authorized privileged action.
- Для backward compatibility сервер отправляет `update` с `actor_role=admin`, а исходного инициатора кладёт в `params.requested_by`.
- Старый агент не должен становиться источником истины о версии; он только исполняет уже авторизованную сервером команду.

## 5. Bulk rollout contract

- Канонический порядок: `upload build -> assign rollout (при необходимости) -> canary update -> handshake/diagnostics verify -> bulk rollout`.
- Массовая раскатка с включённым `require_canary_confirmed` не должна запускаться без подтверждённой canary operation на сервере.
- Проверка canary делается сервером, а не по checkbox в UI как единственному источнику истины.

## 6. Build cleanup contract

- Нельзя удалять build, который сейчас назначен как rollout policy для target.
- Cleanup старых версий делать только штатно через:
  - admin UI Agent Updates;
  - `python scripts/drop_agent_build.py ...`
- Для удаления assigned build сначала нужно снять rollout policy, затем удалить build.

## 7. Что обязательно обновлять при изменении контракта

Если меняется update-flow, rollout semantics, auth, handshake confirmation или admin UI Agent Updates:

- код в `server/` и/или `pc_agent/`;
- `server/docs/AGENT_UPDATES_API.md`;
- `pc_agent/docs/SELF_UPDATE.md` или `pc_agent/docs/AGENT_UPDATE_WORKFLOW.md`;
- `server/docs/CODEMAP.md`;
- `pc_agent/docs/CODEMAP.md`;
- skill/playbook для agent updates, если изменился operator workflow.

## 8. Обязательные проверки

- `python scripts/verify_workspace.py`
- релевантные server update-contract pytest
- релевантные `pc_agent/tests` для runtime/self-update/UI bridge
- browser check admin Agent Updates page
- canary update с подтверждением через handshake/diagnostics

## 9. Операционный запрет

- Нельзя считать update-flow исправным только по popup, логу `accepted` или статусу `scheduled`.
- Нельзя держать в active rollout неподтверждённую версию без canary.
- Нельзя публиковать на сервер и на устройства build-ы ниже `3.1.8` как рабочую цепочку обновления.
