/**
 * Stage 10.4: Chat-first страница тикета.
 * Один таймлайн (чат + события), WS /ws_ui, slash-команды, public/internal.
 */
(function () {
    const AUTH_TOKEN_KEY = 'admin_auth_token';
    const POLL_FALLBACK_MS = 25000;
    const STATUS_LABELS = {
        new: 'Новая', triaged: 'В очереди у оператора', in_progress: 'В работе',
        waiting_on_user: 'Ожидание ответа пользователя', waiting_on_vendor: 'Ожидание внешней стороны',
        resolved: 'Решена', closed: 'Закрыта'
    };
    const PRIORITY_LABELS = { P0: 'Критический', P1: 'Высокий', P2: 'Средний', P3: 'Низкий' };
    const STATUS_OPTIONS = [
        { value: 'new', label: 'Новая' },
        { value: 'triaged', label: 'В очереди у оператора' },
        { value: 'in_progress', label: 'В работе' },
        { value: 'waiting_on_user', label: 'Ожидание ответа пользователя' },
        { value: 'waiting_on_vendor', label: 'Ожидание внешней стороны' },
        { value: 'resolved', label: 'Решена' }
    ];
    const HIDDEN_TIMELINE_EVENT_TYPES = new Set([
        'job_started',
        'job_running',
        'job_succeeded',
        'chat_session',
        'chat_ended',
        'event_delivered',
        'tool_response',
        'routing_applied',
        'initial_message_sent_to_agent',
        'initial_message_pending_delivery',
        'initial_message_send_failed',
        'no_active_job',
        'message_read'
    ]);
    /** Сопоставление module → сценарий для панели «Инструменты ПК» */
    const TOOL_SCENARIOS = {
        'Диагностика': ['os_check', 'system', 'diagnostic'],
        'Сеть': ['ping_check', 'network', 'ping'],
        'Логи': ['logs', 'log'],
        'Доступ/сеанс': ['session', 'access', 'remote'],
        'Сервисные': ['service', 'install', 'maintenance'],
        'С установкой': []  // инструменты с сервера (модуль установится при запуске)
    };
    let ticketId = null;
    let meta = {}; // snapshot metadata
    let events = []; // { id, event_type, ts, payload }
    let lastEventId = 0;
    let seenEventIds = new Set();
    let ws = null;
    let pollTimer = null;
    let wsLive = false;
    let toolsList = [];
    let actorRole = ''; // admin | support | auditor — из snapshot или по умолчанию
    let usersCache = [];
    let queuesCache = [];
    let devicesCache = [];
    let pendingAttachments = [];

    function getToken() {
        const t = localStorage.getItem(AUTH_TOKEN_KEY);
        return (t && typeof t === 'string') ? t.trim() : '';
    }
    function authHeaders(json) {
        const h = {};
        const token = getToken();
        if (token) h['Authorization'] = 'Bearer ' + token;
        if (json) h['Content-Type'] = 'application/json';
        return h;
    }
    function el(id) { return document.getElementById(id); }

    function statusLabel(s) { return s ? (STATUS_LABELS[s] || s) : '—'; }
    function priorityLabel(p) { return p ? ((PRIORITY_LABELS[p] || p) + ' (' + p + ')') : '—'; }
    function boolLabel(v) { return v ? 'Да' : 'Нет'; }
    function formatTime(ts) {
        if (!ts) return '';
        try { return new Date(ts).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' }); } catch { return String(ts); }
    }
    function formatSla(iso) {
        if (!iso) return '—';
        try { return new Date(iso).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }); } catch { return iso; }
    }
    function escapeHtml(str) {
        if (!str) return '';
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    /** Определяет тип медиа по mime/kind для артефакта (image или video). */
    function artifactMediaType(art) {
        const mime = (art.mime_type || art.mime || '').toLowerCase();
        const kind = (art.kind || '').toLowerCase();
        if (mime.startsWith('video/') || kind === 'screen_recording') return 'video';
        if (mime.startsWith('image/') || kind === 'screenshot') return 'image';
        return 'file';
    }

    /** Строит HTML блок .ti-artifacts для списка артефактов (placeholder — медиа подгружается в loadArtifactMedia). */
    function buildArtifactsHtml(artifacts) {
        if (!Array.isArray(artifacts) || artifacts.length === 0) return '';
        const items = artifacts.map(art => {
            const aid = art.artifact_id || art.id || '';
            const label = art.name || art.filename || art.original_name || (art.kind === 'screen_recording' ? 'Запись экрана' : 'Скриншот');
            const mediaType = artifactMediaType(art);
            return `<div class="ti-artifact" data-artifact-id="${escapeHtml(String(aid))}" data-media-type="${escapeHtml(mediaType)}">
  <span class="artifact-loading">Загрузка…</span>
  <span class="artifact-label">${escapeHtml(label)}</span>
</div>`;
        });
        return `<div class="ti-artifacts">${items.join('')}</div>`;
    }

    /** Загружает медиа артефактов в контейнере: fetch с токеном → blob URL → img/video. */
    function loadArtifactMedia(container) {
        if (!container || !ticketId) return;
        const token = getToken();
        container.querySelectorAll('.ti-artifact[data-artifact-id]').forEach(async (wrap) => {
            const artifactId = wrap.getAttribute('data-artifact-id');
            const mediaType = wrap.getAttribute('data-media-type') || 'image';
            if (!artifactId) return;
            const url = '/api/artifacts/' + encodeURIComponent(artifactId) + '/download?ticket_id=' + encodeURIComponent(ticketId);
            const headers = authHeaders();
            try {
                const r = await fetch(url, { headers });
                if (!r.ok) {
                    const errEl = wrap.querySelector('.artifact-loading');
                    if (errEl) { errEl.textContent = 'Ошибка загрузки'; errEl.classList.add('artifact-error'); }
                    return;
                }
                const blob = await r.blob();
                const objectUrl = URL.createObjectURL(blob);
                const loadingEl = wrap.querySelector('.artifact-loading');
                if (loadingEl) loadingEl.remove();
                if (mediaType === 'video') {
                    const video = document.createElement('video');
                    video.className = 'artifact-media';
                    video.controls = true;
                    video.src = objectUrl;
                    wrap.insertBefore(video, wrap.querySelector('.artifact-label') || wrap.firstChild);
                } else if (mediaType === 'file') {
                    const link = document.createElement('a');
                    link.className = 'artifact-download';
                    link.href = objectUrl;
                    link.download = wrap.querySelector('.artifact-label')?.textContent || 'attachment';
                    link.textContent = 'Скачать файл';
                    link.target = '_blank';
                    wrap.insertBefore(link, wrap.querySelector('.artifact-label') || wrap.firstChild);
                } else {
                    const img = document.createElement('img');
                    img.className = 'artifact-media';
                    img.alt = wrap.querySelector('.artifact-label')?.textContent || 'Скриншот';
                    img.src = objectUrl;
                    wrap.insertBefore(img, wrap.querySelector('.artifact-label') || wrap.firstChild);
                }
            } catch (e) {
                const errEl = wrap.querySelector('.artifact-loading');
                if (errEl) { errEl.textContent = 'Ошибка: ' + (e.message || 'загрузка'); errEl.classList.add('artifact-error'); }
            }
        });
    }

    function setTopbar(m) {
        meta = m || meta;
        const code = meta.ticket_code || meta.ticket_id || '—';
        const status = statusLabel(meta.status);
        const queue = meta.queue_code || meta.queue_id || '—';
        const assignee = meta.assignee_id || 'Не назначен';
        const priority = priorityLabel(meta.priority_class || meta.priority);
        const fr = meta.first_response_due_at ? formatSla(meta.first_response_due_at) : '—';
        const res = meta.resolution_due_at ? formatSla(meta.resolution_due_at) : '—';
        el('tbCode').textContent = code;
        el('tbStatus').textContent = status;
        el('tbStatus').className = 'tb-status';
        el('tbQueue').textContent = queue;
        el('tbAssignee').textContent = assignee;
        el('tbPriority').textContent = priority;
        el('tbSlaFr').textContent = fr;
        el('tbSlaRes').textContent = res;
        el('tbSlaFr').classList.toggle('breach', false);
        el('tbSlaRes').classList.toggle('breach', false);
        const liveEl = el('tbLive');
        if (liveEl) {
            liveEl.textContent = wsLive ? '● Онлайн' : '○ Обновление по опросу';
            liveEl.className = wsLive ? 'tb-live' : 'tb-degraded';
        }
    }

    function hasBoundDevice() {
        return Boolean(meta.device_id) && !Boolean(meta.public_ticket_unbound);
    }

    function findDevice(deviceId) {
        if (!deviceId) return null;
        return (devicesCache || []).find((device) => device.device_id === deviceId) || null;
    }

    function deviceLabel(deviceId) {
        if (!deviceId) return 'Не привязан';
        const device = findDevice(deviceId);
        if (!device) return deviceId;
        const host = device.hostname || device.device_id || 'device';
        return device.online ? `${host} (online)` : `${host} (offline)`;
    }

    function refreshDeviceActionControls() {
        const quickScreenshotBtn = el('quickScreenshotBtn');
        const quickRecordBtn = el('quickRecordBtn');
        const readOnly = !canPerformActions();
        const available = hasBoundDevice();
        if (quickScreenshotBtn) quickScreenshotBtn.disabled = readOnly || !available;
        if (quickRecordBtn) quickRecordBtn.disabled = readOnly || !available;
    }

    function setSegmentedValue(containerId, value) {
        const container = el(containerId);
        if (!container) return;
        const normalized = String(value);
        container.dataset.value = normalized;
        container.querySelectorAll('button[data-value]').forEach((btn) => {
            btn.classList.toggle('active', btn.dataset.value === normalized);
        });
    }

    function getSegmentedValue(containerId) {
        const container = el(containerId);
        if (!container) return 'false';
        return container.dataset.value === 'true' ? 'true' : 'false';
    }

    function isSidebarEditing() {
        const active = document.activeElement;
        return !!(active && active.closest && active.closest('.sidebar-editable'));
    }

    function syncActionStateMarker() {
        const markerEl = el('sideActionState');
        if (!markerEl) return;
        const isWaiting = meta.status === 'waiting_on_user' || meta.status === 'waiting_on_vendor';
        if (meta.requires_operator_action) {
            markerEl.textContent = 'Требует действия оператора';
            markerEl.className = 'ticket-state-marker needs-action';
            markerEl.classList.remove('hidden');
            return;
        }
        if (isWaiting) {
            markerEl.textContent = 'Ожидание ответа';
            markerEl.className = 'ticket-state-marker waiting';
            markerEl.classList.remove('hidden');
            return;
        }
        markerEl.className = 'ticket-state-marker hidden';
        markerEl.textContent = '';
    }

    function syncSidebarForm(force) {
        if (!force && isSidebarEditing()) return;
        const profile = meta.requester_profile || {};
        if (el('sideRequesterName')) el('sideRequesterName').textContent = meta.requester_display_name || '—';
        if (el('sideRequesterDisplayNameInput')) el('sideRequesterDisplayNameInput').value = meta.requester_display_name || '';
        if (el('sideRequesterFullNameInput')) el('sideRequesterFullNameInput').value = profile.full_name || '';
        if (el('sideRequesterBuildingInput')) el('sideRequesterBuildingInput').value = profile.building || '';
        if (el('sideRequesterRoomInput')) el('sideRequesterRoomInput').value = profile.room || '';
        if (el('sideRequesterPhoneInput')) el('sideRequesterPhoneInput').value = profile.phone || '';
        if (el('sideStatusText')) el('sideStatusText').textContent = statusLabel(meta.status);
        if (el('sideDescriptionText')) el('sideDescriptionText').textContent = meta.description || '—';
        if (el('sideStatusSelect')) el('sideStatusSelect').value = meta.status || 'new';
        if (el('sidePrioritySummary')) el('sidePrioritySummary').textContent = priorityLabel(meta.priority_class || meta.priority);
        if (el('sideUrgencyReasonInput')) el('sideUrgencyReasonInput').value = meta.urgency_reason || '';
        if (el('sideImportanceReasonInput')) el('sideImportanceReasonInput').value = meta.importance_reason || '';
        setSegmentedValue('sideUrgencyToggle', Boolean(meta.urgency) ? 'true' : 'false');
        setSegmentedValue('sideImportanceToggle', Boolean(meta.importance) ? 'true' : 'false');
        if (el('sideAssigneeText')) el('sideAssigneeText').textContent = meta.assignee_id || 'Не назначен';
        if (el('sideAssigneeSelect')) el('sideAssigneeSelect').value = meta.assignee_id || '';
        if (el('sideQueueText')) el('sideQueueText').textContent = meta.queue_code || meta.queue_id || '—';
        if (el('sideQueueSelect')) el('sideQueueSelect').value = meta.queue_id != null ? String(meta.queue_id) : '';
        if (el('sideDeviceText')) el('sideDeviceText').textContent = hasBoundDevice() ? deviceLabel(meta.device_id) : 'Не привязан';
        if (el('sideDeviceState')) {
            let stateText = 'Ожидает привязки';
            if (hasBoundDevice()) {
                const device = findDevice(meta.device_id);
                stateText = device && device.online ? 'Агент подключён' : 'Привязан, агент офлайн';
            } else if (meta.public_ticket_unbound) {
                stateText = 'Веб-тикет без агента';
            }
            el('sideDeviceState').textContent = stateText;
        }
        if (el('sideDeviceSelect')) {
            el('sideDeviceSelect').value = hasBoundDevice() ? (meta.device_id || '') : '';
        }
        const queueSection = el('sideQueueSection');
        if (queueSection) queueSection.classList.toggle('hidden', queuesCache.length <= 1);
        syncActionStateMarker();
        refreshDeviceActionControls();
    }

    function renderSidebar(force) {
        syncSidebarForm(force === true);
        refreshCloseControls();
    }

    function renderHistory(items) {
        const container = el('ticketHistory');
        if (!container) return;
        const history = Array.isArray(items) ? items : [];
        if (!history.length) {
            container.innerHTML = '<div class="empty">Нет изменений.</div>';
            return;
        }
        container.innerHTML = history.map((item) => {
            const payload = item.payload || {};
            const titleMap = {
                status_changed: 'Изменение статуса',
                priority_changed: 'Изменение приоритета',
                assignee_changed: 'Изменение исполнителя',
                queue_changed: 'Изменение очереди',
                requester_profile_changed: 'Изменение профиля инициатора',
                device_changed: 'Привязка к агенту'
            };
            const title = titleMap[item.event_type] || item.event_type;
            let before = payload.old_value;
            let after = payload.new_value;
            if (item.event_type === 'device_changed') {
                before = payload.previous_device_id || before;
                after = payload.device_id || after;
            }
            const metaLine = [payload.actor_id || 'system', formatTime(item.ts)].filter(Boolean).join(' • ');
            const details = [
                before ? `Было: ${formatChangeValue(item.event_type, before)}` : '',
                after ? `Стало: ${formatChangeValue(item.event_type, after)}` : '',
                payload.reason ? `Причина: ${payload.reason}` : '',
                payload.comment ? `Комментарий: ${payload.comment}` : ''
            ].filter(Boolean).join('\n');
            return `<div class="history-item"><div class="history-title">${escapeHtml(title)}</div><div class="history-meta">${escapeHtml(metaLine)}</div><div class="history-details">${escapeHtml(details || 'Без деталей')}</div></div>`;
        }).join('');
    }

    function formatChangeValue(type, value) {
        if (value == null || value === '') return '—';
        if (type === 'status_changed') return statusLabel(value);
        if (type === 'priority_changed') return priorityLabel(value);
        if (type === 'device_changed') return deviceLabel(String(value));
        if (typeof value === 'object') return JSON.stringify(value);
        return String(value);
    }

    function renderChangeEventCard(type, ts, payload) {
        const titleMap = {
            status_changed: 'Изменён статус',
            priority_changed: 'Изменён приоритет',
            assignee_changed: 'Изменён исполнитель',
            queue_changed: 'Изменена очередь',
            requester_profile_changed: 'Обновлён профиль инициатора',
            device_changed: 'Привязан агент'
        };
        let before = payload.old_value;
        let after = payload.new_value;
        if (type === 'status_changed') {
            before = payload.old_value || payload.from_status || payload.previous_status;
            after = payload.new_value || payload.to_status || payload.status;
        } else if (type === 'priority_changed') {
            before = payload.old_priority_class || payload.old_value || payload.old_priority;
            after = payload.new_priority_class || payload.new_value || payload.new_priority || payload.priority;
        } else if (type === 'assignee_changed') {
            before = payload.previous_assignee_id || payload.old_value;
            after = payload.assignee_id || payload.new_value;
        } else if (type === 'queue_changed') {
            before = payload.previous_queue_id || payload.old_value;
            after = payload.queue_code || payload.queue_id || payload.new_value;
        } else if (type === 'requester_profile_changed') {
            before = payload.old_value;
            after = payload.new_value || payload.requester_profile;
        } else if (type === 'device_changed') {
            before = payload.previous_device_id || payload.old_value;
            after = payload.device_id || payload.new_value;
        }
        const lines = [
            `Было: ${formatChangeValue(type, before)}`,
            `Стало: ${formatChangeValue(type, after)}`,
            payload.reason ? `Причина: ${payload.reason}` : '',
            payload.comment ? `Комментарий: ${payload.comment}` : '',
        ].filter(Boolean);
        const metaLine = [payload.actor_id || payload.actor_role || 'system', formatTime(ts)].filter(Boolean).join(' • ');
        return `<div class="timeline-item system" data-event-id="${escapeHtml(String(payload.event_id || ''))}">
  <div class="ti-avatar">!</div>
  <div class="ti-body">
    <div class="ti-bubble success">
      <div class="ti-system-card">
        <div class="ti-system-title">${escapeHtml(titleMap[type] || type)}</div>
        <div class="ti-system-meta">${escapeHtml(metaLine)}</div>
        <div class="ti-system-detail">${escapeHtml(lines.join('\n') || 'Без деталей')}</div>
      </div>
    </div>
    <div class="ti-time">${escapeHtml(formatTime(ts))}</div>
  </div>
</div>`;
    }

    function renderMessageReadEventCard(ts, payload) {
        const count = Number(payload.messages_read_count || 1);
        const title = count > 1 ? 'Сообщения прочитаны' : 'Сообщение прочитано';
        const actor = payload.actor_id || payload.actor_role || 'system';
        const lines = [
            payload.last_read_message_id ? `Сообщение: ${payload.last_read_message_id}` : '',
            payload.message_preview ? `Текст: ${payload.message_preview}` : '',
        ].filter(Boolean);
        const metaLine = [actor, formatTime(ts)].filter(Boolean).join(' • ');
        return `<div class="timeline-item system" data-event-id="${escapeHtml(String(payload.event_id || ''))}">
  <div class="ti-avatar">✓</div>
  <div class="ti-body">
    <div class="ti-bubble success">
      <div class="ti-system-card">
        <div class="ti-system-title">${escapeHtml(title)}</div>
        <div class="ti-system-meta">${escapeHtml(metaLine)}</div>
        <div class="ti-system-detail">${escapeHtml(lines.join('\n') || 'Без деталей')}</div>
      </div>
    </div>
    <div class="ti-time">${escapeHtml(formatTime(ts))}</div>
  </div>
</div>`;
    }

    function eventToItem(ev) {
        const id = ev.id || ev.event_id;
        const type = ev.event_type || ev.type || 'unknown';
        const ts = ev.ts || ev.created_at;
        const payload = ev.payload || ev;
        if (HIDDEN_TIMELINE_EVENT_TYPES.has(type)) {
            return null;
        }
        if (type === 'chat_message') {
            const fromRole = payload.from_role || payload.from || payload.sender_role || 'unknown';
            const text = payload.text || '';
            const vis = payload.visibility || 'public';
            const isRequester = fromRole === 'user' || fromRole === 'agent';
            const isStaff = fromRole === 'support' || fromRole === 'admin';
            const senderResolved = isRequester
                ? (meta.requester_display_name || 'Пользователь')
                : (payload.actor_id || payload.sender_display_name || meta.assignee_id || (fromRole === 'support' ? 'Поддержка' : fromRole === 'admin' ? 'Админ' : 'Агент'));
            const avatar = isRequester ? 'U' : (fromRole === 'support' ? 'S' : fromRole === 'admin' ? 'A' : '?');
            const internalBadge = vis === 'internal' ? '<span class="ti-badge-internal">Внутр.</span>' : '';
            const attachments = payload.attachments || [];
            const attachmentRefs = payload.attachment_refs || [];
            const artifactList = attachments.length ? attachments : attachmentRefs.map(ref => (typeof ref === 'string' ? { artifact_id: ref } : ref));
            const attachmentsHtml = artifactList.length ? buildArtifactsHtml(artifactList) : '';
            return {
                id,
                type: 'chat',
                html: `<div class="timeline-item ${isRequester ? 'from-user' : ''} ${isStaff ? 'from-staff' : ''}" data-event-id="${escapeHtml(String(id))}">
  <div class="ti-avatar">${escapeHtml(avatar)}</div>
  <div class="ti-body">
    <div class="ti-meta">${internalBadge} <span class="ti-sender">${escapeHtml(senderResolved)}</span></div>
    <div class="ti-bubble">${escapeHtml(text)}</div>
    ${attachmentsHtml}
    <div class="ti-time">${escapeHtml(formatTime(ts))}</div>
  </div>
</div>`
            };
        }
        if (type === 'tool_call_started') {
            const tool = payload.tool_name || payload.tool || '—';
            return { id, type: 'system', html: `<div class="timeline-item system" data-event-id="${escapeHtml(String(id))}">
  <div class="ti-avatar">⚙</div>
  <div class="ti-body">
    <div class="ti-bubble">Запуск: ${escapeHtml(tool)}</div>
    <div class="ti-time">${escapeHtml(formatTime(ts))}</div>
  </div>
</div>` };
        }
        if (type === 'tool_call_result') {
            const status = payload.status || 'unknown';
            const summary = payload.summary != null ? String(payload.summary) : (payload.error || '');
            const cls = status === 'success' ? 'success' : 'error';
            let resultPreview = '';
            if (payload.result && typeof payload.result === 'object') resultPreview = JSON.stringify(payload.result).slice(0, 300);
            else if (payload.observations) resultPreview = JSON.stringify(payload.observations).slice(0, 300);
            const artifactsHtml = buildArtifactsHtml(payload.artifacts || []);
            return { id, type: 'system', html: `<div class="timeline-item system" data-event-id="${escapeHtml(String(id))}">
  <div class="ti-avatar">✓</div>
  <div class="ti-body">
    <div class="ti-bubble ${cls}">Результат: ${escapeHtml(summary)}</div>
    ${resultPreview ? `<div class="ti-tool-result">${escapeHtml(resultPreview)}</div>` : ''}
    ${artifactsHtml}
    <div class="ti-time">${escapeHtml(formatTime(ts))}</div>
  </div>
</div>` };
        }
        if (type === 'system_message_local') {
            const cls = payload.status === 'error' ? 'error' : 'success';
            return { id, type: 'system', html: `<div class="timeline-item system">
  <div class="ti-avatar">!</div>
  <div class="ti-body">
    <div class="ti-bubble ${cls}">${escapeHtml(payload.text || '')}</div>
    <div class="ti-time">${escapeHtml(formatTime(ts))}</div>
  </div>
</div>` };
        }
        if (type === 'message_read') {
            return { id, type: 'system', html: renderMessageReadEventCard(ts, { ...payload, event_id: id }) };
        }
        if (type === 'status_changed' || type === 'queue_changed' || type === 'assignee_changed' || type === 'priority_changed' || type === 'requester_profile_changed' || type === 'device_changed') {
            return { id, type: 'system', html: renderChangeEventCard(type, ts, { ...payload, event_id: id }) };
        }
        return { id, type: 'system', html: `<div class="timeline-item system" data-event-id="${escapeHtml(String(id))}">
  <div class="ti-avatar">•</div>
  <div class="ti-bubble">${escapeHtml(type)}</div>
  <div class="ti-time">${escapeHtml(formatTime(ts))}</div>
</div>` };
    }

    function getTimelineScrollState(container) {
        if (!container) return { shouldStick: true, distanceFromBottom: 0 };
        const distanceFromBottom = Math.max(container.scrollHeight - container.scrollTop - container.clientHeight, 0);
        return {
            shouldStick: distanceFromBottom < 80,
            distanceFromBottom
        };
    }

    function restoreTimelineScroll(container, state, forceStick) {
        if (!container) return;
        if (forceStick || !state || state.shouldStick) {
            container.scrollTop = container.scrollHeight;
            return;
        }
        container.scrollTop = Math.max(container.scrollHeight - container.clientHeight - state.distanceFromBottom, 0);
    }

    function appendEvent(ev, options) {
        const opts = options || {};
        const id = ev.id || ev.event_id;
        if (id != null && seenEventIds.has(id)) return;
        if (id != null) seenEventIds.add(id);
        events.push(ev);
        const item = eventToItem(ev);
        if (!item) return;
        const timelineEl = el('timeline');
        const scrollState = getTimelineScrollState(timelineEl);
        const wrap = document.createElement('div');
        wrap.innerHTML = item.html;
        const node = wrap.firstElementChild;
        if (node) {
            const emptyState = timelineEl.querySelector('.empty');
            if (emptyState) emptyState.remove();
            timelineEl.appendChild(node);
            loadArtifactMedia(node);
        }
        if (ev.event_type === 'chat_message' && (ev.payload || {}).visibility !== 'internal') {
            const p = ev.payload || {};
            if (p.status) meta.status = p.status;
        }
        if (ev.event_type === 'status_changed' && ev.payload) meta.status = ev.payload.to_status || ev.payload.new_value || meta.status;
        if (ev.event_type === 'queue_changed' && ev.payload) {
            meta.queue_code = ev.payload.queue_code || ev.payload.queue_id || meta.queue_code;
            meta.queue_id = ev.payload.queue_id || meta.queue_id;
        }
        if (ev.event_type === 'assignee_changed' && ev.payload) meta.assignee_id = ev.payload.assignee_id;
        if (ev.event_type === 'priority_changed' && ev.payload) {
            meta.priority = ev.payload.new_priority != null ? ev.payload.new_priority : ev.payload.priority;
            meta.priority_class = ev.payload.new_priority_class || meta.priority_class;
            if (Object.prototype.hasOwnProperty.call(ev.payload, 'new_urgency')) meta.urgency = ev.payload.new_urgency;
            if (Object.prototype.hasOwnProperty.call(ev.payload, 'new_importance')) meta.importance = ev.payload.new_importance;
            if (ev.payload.urgency_reason) meta.urgency_reason = ev.payload.urgency_reason;
            if (ev.payload.importance_reason) meta.importance_reason = ev.payload.importance_reason;
        }
        if (ev.event_type === 'device_changed' && ev.payload) {
            meta.device_id = ev.payload.device_id || meta.device_id;
            meta.public_ticket_unbound = false;
        }
        if (ev.event_type === 'requester_profile_changed' && ev.payload) {
            meta.requester_profile = ev.payload.requester_profile || meta.requester_profile;
            meta.requester_display_name = ev.payload.requester_display_name || meta.requester_display_name;
        }
        meta.requires_operator_action = meta.status === 'new' || meta.status === 'triaged' || meta.status === 'in_progress';
        setTopbar(meta);
        renderSidebar(opts.forceSidebarSync === true);
        renderHistory(events.filter((item) => ['status_changed', 'priority_changed', 'assignee_changed', 'queue_changed', 'requester_profile_changed', 'device_changed'].includes(item.event_type)));
        restoreTimelineScroll(timelineEl, scrollState, opts.forceScroll === true || opts.forceStick === true || (ev.event_type === 'chat_message' && (ev.payload || {}).from === 'user'));
    }

    function renderTimeline(evs, options) {
        const container = el('timeline');
        const opts = options || {};
        const scrollState = getTimelineScrollState(container);
        container.innerHTML = '';
        seenEventIds = new Set();
        (evs || []).forEach(ev => {
            const id = ev.id || ev.event_id;
            if (id != null) seenEventIds.add(id);
            const item = eventToItem(ev);
            if (!item) return;
            const wrap = document.createElement('div');
            wrap.innerHTML = item.html;
            const node = wrap.firstElementChild;
            if (node) container.appendChild(node);
        });
        if (container.children.length === 0) container.innerHTML = '<div class="empty">Нет сообщений.</div>';
        loadArtifactMedia(container);
        restoreTimelineScroll(container, scrollState, opts.forceScroll !== false);
    }

    function showSystemMessage(text, isError) {
        const html = `<div class="timeline-item system">
  <div class="ti-avatar">!</div>
  <div class="ti-bubble ${isError ? 'error' : 'success'}">${escapeHtml(text)}</div>
  <div class="ti-time">${formatTime(new Date().toISOString())}</div>
</div>`;
        const wrap = document.createElement('div');
        wrap.innerHTML = html;
        appendEvent({
            id: null,
            event_type: 'system_message_local',
            ts: new Date().toISOString(),
            payload: { text, status: isError ? 'error' : 'success' }
        }, { forceScroll: true, forceSidebarSync: false });
    }

    function kindFromFile(file) {
        const mime = (file && file.type ? String(file.type) : '').toLowerCase();
        if (mime.startsWith('image/')) return 'screenshot';
        if (mime.startsWith('video/')) return 'screen_recording';
        return 'file';
    }

    async function uploadAttachment(file) {
        if (!file) return null;
        const form = new FormData();
        form.append('file', file, file.name || 'attachment.bin');
        form.append('ticket_id', ticketId);
        form.append('kind', kindFromFile(file));
        const r = await fetch('/api/upload', {
            method: 'POST',
            headers: authHeaders(),
            body: form
        });
        const d = await r.json().catch(() => ({}));
        if (!r.ok || d.status === 'error') {
            throw new Error(d.error || ('Ошибка загрузки файла: HTTP ' + r.status));
        }
        return {
            artifact_id: d.artifact_id,
            name: file.name || d.filename || 'attachment',
            kind: d.kind || kindFromFile(file),
            mime_type: d.mime_type || file.type || '',
            size: d.size || file.size || 0
        };
    }

    function renderPendingAttachments() {
        const wrap = el('pendingAttachments');
        if (!wrap) return;
        if (!pendingAttachments.length) {
            wrap.classList.add('hidden');
            wrap.innerHTML = '';
            return;
        }
        wrap.classList.remove('hidden');
        wrap.innerHTML = pendingAttachments.map((item, idx) => {
            const title = item.name || item.artifact_id || 'attachment';
            const kind = item.kind || 'file';
            const sizeKb = item.size ? Math.max(1, Math.round(item.size / 1024)) : 0;
            return `<div class="pending-attachment">
  <span class="pending-attachment-name">${escapeHtml(title)}</span>
  <span class="pending-attachment-meta">${escapeHtml(kind)}${sizeKb ? ' • ' + sizeKb + ' KB' : ''}</span>
  <button class="pending-attachment-remove" data-attachment-index="${idx}" type="button">Удалить</button>
</div>`;
        }).join('');
        wrap.querySelectorAll('.pending-attachment-remove').forEach((btn) => {
            btn.addEventListener('click', () => {
                const idx = Number(btn.getAttribute('data-attachment-index'));
                if (!Number.isFinite(idx)) return;
                pendingAttachments.splice(idx, 1);
                renderPendingAttachments();
            });
        });
    }

    async function loadSnapshot() {
        const ctrl = new AbortController();
        const t = setTimeout(() => ctrl.abort(), 15000);
        const r = await fetch('/api/tickets/' + ticketId + '/snapshot', { headers: authHeaders(), signal: ctrl.signal }).finally(() => clearTimeout(t));
        if (!r.ok) {
            if (r.status === 401) throw new Error('Требуется авторизация. Войдите через /admin.');
            if (r.status === 404) throw new Error('Тикет не найден.');
            throw new Error(r.statusText || 'Ошибка загрузки');
        }
        const data = await r.json().catch(() => ({}));
        if (data.error) throw new Error(data.error);
        const evs = data.events || [];
        events = evs.slice();
        lastEventId = data.last_event_id || 0;
        evs.forEach(e => { if (e.id != null) seenEventIds.add(e.id); });
        meta = {
            ticket_id: data.ticket_id,
            ticket_code: data.ticket_code,
            device_id: data.device_id,
            title: data.title,
            description: data.description,
            status: data.status,
            queue_id: data.queue_id,
            queue_code: data.queue_code,
            assignee_id: data.assignee_id,
            priority: data.priority,
            priority_class: data.priority_class,
            urgency: data.urgency,
            importance: data.importance,
            urgency_reason: data.urgency_reason,
            importance_reason: data.importance_reason,
            requester_profile: data.requester_profile || {},
            requester_display_name: data.requester_display_name,
            requires_operator_action: data.requires_operator_action,
            resolution_confirmation_pending: !!data.resolution_confirmation_pending,
            public_ticket_unbound: !!data.public_ticket_unbound,
            first_response_due_at: data.first_response_due_at,
            resolution_due_at: data.resolution_due_at,
        };
        actorRole = data.actor_role || '';
        setTopbar(meta);
        renderSidebar(!isSidebarEditing());
        renderHistory(data.history || []);
        renderTimeline(evs, { forceScroll: false });
        return data;
    }

    function connectWs() {
        if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = proto + '//' + location.host + '/ws_ui';
        try { ws = new WebSocket(url); } catch (e) { wsLive = false; setTopbar(); return; }
        ws.onopen = () => {
            const token = getToken();
            if (!token) { ws.close(); return; }
            ws.send(JSON.stringify({ type: 'ui_hello', token }));
        };
        ws.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                if (data.type === 'ui_hello_ack') {
                    wsLive = true;
                    setTopbar();
                    ws.send(JSON.stringify({ type: 'subscribe_ticket', ticket_id: ticketId, since_event_id: lastEventId }));
                    return;
                }
                if (data.type === 'subscribe_ack' && data.ticket_id === ticketId) {
                    if (data.last_event_id != null) lastEventId = data.last_event_id;
                    return;
                }
                if (data.type === 'ticket_event_committed' && data.ticket_id === ticketId) {
                    lastEventId = Math.max(lastEventId, data.event_id || 0);
                    appendEvent({
                        id: data.event_id,
                        event_type: data.event_type,
                        ts: data.ts,
                        payload: data.payload || {}
                    }, { forceSidebarSync: false });
                    return;
                }
                if (data.type === 'catchup_done' && data.scope === 'ticket' && data.id === ticketId && data.last_event_id != null) {
                    lastEventId = data.last_event_id;
                }
            } catch (err) { console.warn('ws parse', err); }
        };
        ws.onclose = () => { ws = null; wsLive = false; setTopbar(); };
        ws.onerror = () => { wsLive = false; setTopbar(); };
    }

    function startPollFallback() {
        if (pollTimer) return;
        pollTimer = setInterval(async () => {
            if (ws && ws.readyState === WebSocket.OPEN) return;
            try {
                const data = await loadSnapshot();
                lastEventId = data.last_event_id || lastEventId;
            } catch (e) { console.warn('poll snapshot', e); }
        }, POLL_FALLBACK_MS);
    }

    async function sendMessage(text, visibility, attachmentRefs) {
        const messageId = 'msg_' + Date.now() + '_' + Math.random().toString(36).slice(2, 9);
        const refs = Array.isArray(attachmentRefs) ? attachmentRefs.filter(Boolean) : [];
        const r = await fetch('/api/tickets/' + ticketId + '/message', {
            method: 'POST',
            headers: authHeaders(true),
            body: JSON.stringify({
                message_id: messageId,
                text: (text || '').trim(),
                visibility: visibility || 'public',
                attachment_refs: refs
            })
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) {
            showSystemMessage(data.details?.text || data.error || 'Ошибка отправки', true);
            return false;
        }
        if (data.status === 'error') {
            showSystemMessage(data.error || 'Ошибка отправки', true);
            return false;
        }
        // Не добавляем оптимистичное сообщение: ждём ticket_event_committed по WS или обновление по polling.
        if (data.event_id != null) {
            lastEventId = Math.max(lastEventId, data.event_id);
        }
        return true;
    }

    async function runQuickTool(toolName, params, successMessage) {
        if (!canPerformActions()) {
            showSystemMessage('Недостаточно прав для запуска инструмента', true);
            return;
        }
        if (!hasBoundDevice()) {
            showSystemMessage('Нет привязки тикета к устройству', true);
            return;
        }
        const payload = {
            device_id: meta.device_id,
            ticket_id: ticketId,
            tool_name: toolName
        };
        if (params && typeof params === 'object') payload.params = params;
        const r = await fetch('/api/tools/run', {
            method: 'POST',
            headers: authHeaders(true),
            body: JSON.stringify(payload)
        });
        const d = await r.json().catch(() => ({}));
        if (!r.ok || d.status === 'error') {
            showSystemMessage(d.error || 'Ошибка запуска инструмента', true);
            return;
        }
        showSystemMessage(successMessage || ('Инструмент запущен: ' + toolName), false);
        setTimeout(() => loadSnapshot(), 1800);
    }

    function openInlinePanel(title, bodyHtml, onApply, onOpen) {
        const panel = el('inlinePanel');
        const titleEl = el('inlinePanelTitle');
        const bodyEl = el('inlinePanelBody');
        const errEl = el('inlinePanelError');
        const applyBtn = el('inlinePanelApply');
        const cancelBtn = el('inlinePanelCancel');
        if (!panel || !titleEl || !bodyEl) return;
        titleEl.textContent = title;
        bodyEl.innerHTML = bodyHtml;
        if (errEl) errEl.textContent = '';
        if (typeof onOpen === 'function') onOpen(bodyEl);
        panel.classList.remove('hidden');
        panel.classList.add('open');
        const close = () => {
            panel.classList.remove('open');
            panel.classList.add('hidden');
        };
        cancelBtn.onclick = close;
        applyBtn.onclick = async () => {
            if (errEl) errEl.textContent = '';
            try {
                await onApply(bodyEl, errEl);
                close();
            } catch (e) {
                if (errEl) errEl.textContent = e.message || String(e);
            }
        };
    }
    function closeInlinePanel() {
        const panel = el('inlinePanel');
        if (panel) {
            panel.classList.remove('open');
            panel.classList.add('hidden');
        }
    }

    async function ensureUsersLoaded() {
        if (usersCache.length) return usersCache;
        const r = await fetch('/api/admin/users', { headers: authHeaders() });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.error || 'Не удалось загрузить список исполнителей');
        usersCache = (d.users || d || []).filter((u) => u.is_active !== false && ['support', 'admin'].includes(u.actor_role));
        return usersCache;
    }

    async function ensureQueuesLoaded() {
        if (queuesCache.length) return queuesCache;
        const r = await fetch('/api/admin/tickets/queues', { headers: authHeaders() });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.error || 'Не удалось загрузить очереди');
        queuesCache = d.queues || d || [];
        return queuesCache;
    }

    async function ensureDevicesLoaded() {
        if (devicesCache.length) return devicesCache;
        const r = await fetch('/api/devices', { headers: authHeaders() });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.error || 'Не удалось загрузить список агентов');
        devicesCache = d.devices || d || [];
        return devicesCache;
    }

    function populateStatusSelect() {
        const select = el('sideStatusSelect');
        if (!select || select.options.length) return;
        select.innerHTML = STATUS_OPTIONS.map((option) => `<option value="${escapeHtml(option.value)}">${escapeHtml(option.label)}</option>`).join('');
    }

    function populateAssigneeSelect() {
        const select = el('sideAssigneeSelect');
        if (!select) return;
        const current = meta.assignee_id || '';
        const options = ['<option value="">Не назначен</option>'].concat(
            usersCache.map((user) => `<option value="${escapeHtml(user.user_login || user.login || '')}">${escapeHtml(user.user_login || user.login || '')}</option>`)
        );
        select.innerHTML = options.join('');
        select.value = current;
    }

    function populateQueueSelect() {
        const select = el('sideQueueSelect');
        if (!select) return;
        const options = queuesCache.map((queue) => `<option value="${escapeHtml(String(queue.id))}">${escapeHtml(queue.code || queue.name || String(queue.id))}</option>`);
        select.innerHTML = options.join('');
        if (meta.queue_id != null) select.value = String(meta.queue_id);
        const queueSection = el('sideQueueSection');
        if (queueSection) queueSection.classList.toggle('hidden', queuesCache.length <= 1);
    }

    function populateDeviceSelect() {
        const select = el('sideDeviceSelect');
        if (!select) return;
        const sortedDevices = (devicesCache || []).slice().sort((left, right) => {
            const onlineDelta = Number(Boolean(right.online)) - Number(Boolean(left.online));
            if (onlineDelta !== 0) return onlineDelta;
            return String(left.hostname || left.device_id || '').localeCompare(String(right.hostname || right.device_id || ''), 'ru');
        });
        const currentDeviceId = hasBoundDevice() ? (meta.device_id || '') : '';
        const options = ['<option value="">-- Выберите агент --</option>'];
        if (currentDeviceId && !sortedDevices.some((device) => device.device_id === currentDeviceId)) {
            options.push(`<option value="${escapeHtml(currentDeviceId)}">${escapeHtml(deviceLabel(currentDeviceId))}</option>`);
        }
        sortedDevices.forEach((device) => {
            options.push(`<option value="${escapeHtml(device.device_id)}">${escapeHtml(deviceLabel(device.device_id))}</option>`);
        });
        select.innerHTML = options.join('');
        select.value = currentDeviceId;
    }

    async function refreshSidebarOptions() {
        if (!canPerformActions()) return;
        try {
            await Promise.all([ensureUsersLoaded(), ensureQueuesLoaded(), ensureDevicesLoaded()]);
            populateAssigneeSelect();
            populateQueueSelect();
            populateDeviceSelect();
            syncSidebarForm(false);
        } catch (err) {
            console.warn('sidebar options', err);
        }
    }

    async function applyRequesterProfile() {
        const payload = {
            user_display_name: el('sideRequesterDisplayNameInput')?.value?.trim() || '',
            requester_profile: {
                full_name: el('sideRequesterFullNameInput')?.value?.trim() || '',
                building: el('sideRequesterBuildingInput')?.value?.trim() || '',
                room: el('sideRequesterRoomInput')?.value?.trim() || '',
                phone: el('sideRequesterPhoneInput')?.value?.trim() || ''
            }
        };
        const r = await fetch('/api/tickets/' + ticketId + '/requester_profile', { method: 'POST', headers: authHeaders(true), body: JSON.stringify(payload) });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.error || 'Ошибка обновления профиля');
        const updatedTicket = d.ticket || {};
        meta.requester_profile = updatedTicket.requester_profile || payload.requester_profile;
        meta.requester_display_name =
            updatedTicket.requester_display_name
            || payload.requester_profile.full_name
            || payload.user_display_name
            || meta.requester_display_name;
        renderSidebar(true);
    }

    async function applyStatus() {
        const toStatus = el('sideStatusSelect')?.value;
        const r = await fetch('/api/tickets/' + ticketId + '/status', { method: 'POST', headers: authHeaders(true), body: JSON.stringify({ to_status: toStatus }) });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.details?.to_status || d.error || 'Ошибка смены статуса');
    }

    async function applyPriority() {
        const urgencyReason = el('sideUrgencyReasonInput')?.value?.trim() || '';
        const importanceReason = el('sideImportanceReasonInput')?.value?.trim() || '';
        if (!urgencyReason || !importanceReason) throw new Error('Заполните оба обоснования');
        const payload = {
            urgency: getSegmentedValue('sideUrgencyToggle') === 'true',
            importance: getSegmentedValue('sideImportanceToggle') === 'true',
            urgency_reason: urgencyReason,
            importance_reason: importanceReason
        };
        const r = await fetch('/api/tickets/' + ticketId + '/priority', { method: 'POST', headers: authHeaders(true), body: JSON.stringify(payload) });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.details?.priority || d.error || 'Ошибка смены приоритета');
    }

    async function applyAssignee() {
        const assigneeId = el('sideAssigneeSelect')?.value || null;
        const r = await fetch('/api/tickets/' + ticketId + '/assign', { method: 'POST', headers: authHeaders(true), body: JSON.stringify({ assignee_id: assigneeId }) });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.message || d.error || 'Ошибка назначения');
    }

    async function applyAutoAssign() {
        const r = await fetch('/api/tickets/' + ticketId + '/assign', { method: 'POST', headers: authHeaders(true), body: JSON.stringify({ auto_assign: true, reason: 'auto_balance' }) });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.message || d.error || 'Ошибка автоназначения');
    }

    async function applyQueue() {
        const queueId = parseInt(el('sideQueueSelect')?.value || '', 10);
        if (!Number.isFinite(queueId)) throw new Error('Выберите очередь');
        const r = await fetch('/api/tickets/' + ticketId + '/queue', { method: 'POST', headers: authHeaders(true), body: JSON.stringify({ queue_id: queueId, reason: 'manual' }) });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.details?.queue_id || d.error || 'Ошибка смены очереди');
    }

    async function applyDeviceBinding(deviceIdOverride, reasonOverride) {
        const deviceId = (deviceIdOverride || el('sideDeviceSelect')?.value || '').trim();
        const reason = (reasonOverride || el('sideDeviceReasonInput')?.value || '').trim() || 'manual_bind';
        if (!deviceId) throw new Error('Выберите агент');
        const r = await fetch('/api/tickets/' + ticketId + '/device', {
            method: 'POST',
            headers: authHeaders(true),
            body: JSON.stringify({ device_id: deviceId, reason })
        });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.details?.device_id || d.error || 'Ошибка привязки к агенту');
        const updatedTicket = d.ticket || {};
        meta.device_id = updatedTicket.device_id || deviceId;
        meta.public_ticket_unbound = Boolean(updatedTicket.public_ticket_unbound);
        setTopbar(meta);
        renderSidebar(true);
        showSystemMessage('Тикет привязан к агенту');
        await loadSnapshot();
    }

    async function closeTicket() {
        const r = await fetch('/api/tickets/' + ticketId + '/close', { method: 'POST', headers: authHeaders(true), body: JSON.stringify({ reason: 'requester_confirmed_resolution' }) });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.error || 'Ошибка закрытия');
        meta.status = 'closed';
        meta.resolution_confirmation_pending = false;
        setTopbar(meta);
        renderSidebar();
        loadSnapshot();
    }

    function canPerformActions() {
        return actorRole === 'admin' || actorRole === 'support';
    }

    function canConfirmResolution() {
        return actorRole === 'user' && meta.status === 'resolved' && !!meta.resolution_confirmation_pending;
    }

    function refreshCloseControls() {
        const closeWrap = el('sideActions');
        const closeBtn = el('sideCloseBtn');
        const closeMenuItem = document.querySelector('.menu-item[data-cmd="/close"]');
        const allowConfirm = canConfirmResolution();
        if (closeBtn) {
            closeBtn.textContent = 'Подтвердить решение';
            closeBtn.disabled = !allowConfirm;
        }
        if (closeWrap) {
            closeWrap.classList.toggle('hidden', !allowConfirm);
        }
        if (closeMenuItem) {
            closeMenuItem.classList.toggle('hidden', !allowConfirm);
            closeMenuItem.disabled = !allowConfirm;
        }
    }

    async function runCommand(cmd) {
        if (cmd === '/status') {
            const statusOpts = [
                { v: 'new', l: 'Новая' }, { v: 'triaged', l: 'В очереди у оператора' }, { v: 'in_progress', l: 'В работе' },
                { v: 'waiting_on_user', l: 'Ожидание ответа пользователя' }, { v: 'waiting_on_vendor', l: 'Ожидание внешней стороны' },
                { v: 'resolved', l: 'Решена' }
            ];
            openInlinePanel('Сменить статус',
                `<div class="form-group"><label>Новый статус</label><select id="cmdStatusSelect">${statusOpts.map(o => `<option value="${escapeHtml(o.v)}">${escapeHtml(o.l)}</option>`).join('')}</select></div>`,
                async (body) => {
                    const to = body.querySelector('#cmdStatusSelect').value;
                    const r = await fetch('/api/tickets/' + ticketId + '/status', { method: 'POST', headers: authHeaders(true), body: JSON.stringify({ to_status: to }) });
                    const d = await r.json().catch(() => ({}));
                    if (!r.ok) throw new Error(d.details?.to_status || d.error || 'Ошибка смены статуса');
                    if (d.status === 'error') throw new Error(d.error);
                });
            return;
        }
        if (cmd === '/assign_auto') {
            const r = await fetch('/api/tickets/' + ticketId + '/assign', { method: 'POST', headers: authHeaders(true), body: JSON.stringify({ auto_assign: true, reason: 'auto_balance' }) });
            const d = await r.json().catch(() => ({}));
            if (!r.ok) { showSystemMessage(d.message || d.error || 'Ошибка автоназначения', true); return; }
            meta.assignee_id = d.assignee_id || meta.assignee_id;
            setTopbar(meta);
            renderSidebar();
            return;
        }
        if (cmd === '/assign') {
            const r = await fetch('/api/admin/users', { headers: authHeaders() });
            const d = await r.json().catch(() => ({}));
            const users = (d.users || d || []).filter(u => u.is_active !== false && ['support', 'admin'].includes(u.actor_role));
            const opts = '<option value="">— Снять назначение —</option>' + users.map(u => `<option value="${escapeHtml(u.user_login || u.login || '')}">${escapeHtml(u.user_login || u.login || '')}</option>`).join('');
            openInlinePanel('Назначить исполнителя',
                `<div class="form-group"><label>Исполнитель</label><select id="cmdAssignSelect">${opts}</select></div>`,
                async (body) => {
                    const assigneeId = body.querySelector('#cmdAssignSelect').value || null;
                    const r = await fetch('/api/tickets/' + ticketId + '/assign', { method: 'POST', headers: authHeaders(true), body: JSON.stringify({ assignee_id: assigneeId }) });
                    const d = await r.json().catch(() => ({}));
                    if (!r.ok) throw new Error(d.error || 'Ошибка назначения');
                    meta.assignee_id = assigneeId || 'Не назначен';
                    setTopbar(meta);
                });
            return;
        }
        if (cmd === '/requester') {
            const profile = meta.requester_profile || {};
            openInlinePanel('Профиль инициатора',
                `<div class="form-group"><label>Отображаемое имя</label><input type="text" id="cmdRequesterDisplayName" value="${escapeHtml(meta.requester_display_name || '')}"/></div>
                 <div class="form-group"><label>ФИО</label><input type="text" id="cmdRequesterFullName" value="${escapeHtml(profile.full_name || '')}"/></div>
                 <div class="form-group"><label>Корпус</label><input type="text" id="cmdRequesterBuilding" value="${escapeHtml(profile.building || '')}"/></div>
                 <div class="form-group"><label>Кабинет</label><input type="text" id="cmdRequesterRoom" value="${escapeHtml(profile.room || '')}"/></div>
                 <div class="form-group"><label>Телефон</label><input type="text" id="cmdRequesterPhone" value="${escapeHtml(profile.phone || '')}"/></div>`,
                async (body) => {
                    const payload = {
                        user_display_name: body.querySelector('#cmdRequesterDisplayName').value || '',
                        requester_profile: {
                            full_name: body.querySelector('#cmdRequesterFullName').value || '',
                            building: body.querySelector('#cmdRequesterBuilding').value || '',
                            room: body.querySelector('#cmdRequesterRoom').value || '',
                            phone: body.querySelector('#cmdRequesterPhone').value || '',
                        }
                    };
                    const r = await fetch('/api/tickets/' + ticketId + '/requester_profile', { method: 'POST', headers: authHeaders(true), body: JSON.stringify(payload) });
                    const d = await r.json().catch(() => ({}));
                    if (!r.ok) throw new Error(d.error || 'Ошибка обновления профиля');
                    const updatedTicket = d.ticket || {};
                    meta.requester_profile = updatedTicket.requester_profile || payload.requester_profile;
                    meta.requester_display_name =
                        updatedTicket.requester_display_name
                        || payload.requester_profile.full_name
                        || payload.user_display_name
                        || meta.requester_display_name;
                    renderSidebar(true);
                });
            return;
        }
        if (cmd === '/queue') {
            const r = await fetch('/api/admin/tickets/queues', { headers: authHeaders() });
            const d = await r.json().catch(() => ({}));
            const queues = d.queues || d || [];
            const opts = queues.map(q => `<option value="${q.id}">${escapeHtml(q.name || q.code)}</option>`).join('');
            openInlinePanel('Сменить очередь',
                `<div class="form-group"><label>Очередь</label><select id="cmdQueueSelect">${opts}</select></div>
                 <div class="form-group"><label>Причина</label><input type="text" id="cmdQueueReason" value="manual" placeholder="причина"/></div>`,
                async (body) => {
                    const queueId = parseInt(body.querySelector('#cmdQueueSelect').value, 10);
                    const reason = body.querySelector('#cmdQueueReason').value || 'manual';
                    const r = await fetch('/api/tickets/' + ticketId + '/queue', { method: 'POST', headers: authHeaders(true), body: JSON.stringify({ queue_id: queueId, reason }) });
                    const d = await r.json().catch(() => ({}));
                    if (!r.ok) throw new Error(d.details?.queue_id || d.error || 'Ошибка смены очереди');
                    const snap = await loadSnapshot();
                    setTopbar(snap);
                });
            return;
        }
        if (cmd === '/device') {
            await ensureDevicesLoaded();
            const sortedDevices = (devicesCache || []).slice().sort((left, right) => {
                const onlineDelta = Number(Boolean(right.online)) - Number(Boolean(left.online));
                if (onlineDelta !== 0) return onlineDelta;
                return String(left.hostname || left.device_id || '').localeCompare(String(right.hostname || right.device_id || ''), 'ru');
            });
            const options = ['<option value="">-- Выберите агент --</option>'].concat(
                sortedDevices.map((device) => `<option value="${escapeHtml(device.device_id)}"${hasBoundDevice() && meta.device_id === device.device_id ? ' selected' : ''}>${escapeHtml(deviceLabel(device.device_id))}</option>`)
            ).join('');
            openInlinePanel('Привязать к агенту',
                `<div class="form-group"><label>Агент</label><select id="cmdDeviceSelect">${options}</select></div>
                 <div class="form-group"><label>Причина</label><input type="text" id="cmdDeviceReason" value="manual_bind" placeholder="manual_bind"/></div>`,
                async (body) => {
                    const deviceId = body.querySelector('#cmdDeviceSelect').value || '';
                    const reason = body.querySelector('#cmdDeviceReason').value || 'manual_bind';
                    await applyDeviceBinding(deviceId, reason);
                });
            return;
        }
        if (cmd === '/priority') {
            openInlinePanel('Изменить приоритет',
                `<div class="form-group"><label>Срочность</label><select id="cmdPriorityUrgency"><option value="true"${meta.urgency ? ' selected' : ''}>Срочно</option><option value="false"${!meta.urgency ? ' selected' : ''}>Несрочно</option></select></div>
                 <div class="form-group"><label>Обоснование срочности</label><input type="text" id="cmdPriorityUrgencyReason" value="${escapeHtml(meta.urgency_reason || '')}" placeholder="обязательно"/></div>
                 <div class="form-group"><label>Важность</label><select id="cmdPriorityImportance"><option value="true"${meta.importance ? ' selected' : ''}>Важно</option><option value="false"${!meta.importance ? ' selected' : ''}>Неважно</option></select></div>
                 <div class="form-group"><label>Обоснование важности</label><input type="text" id="cmdPriorityImportanceReason" value="${escapeHtml(meta.importance_reason || '')}" placeholder="обязательно"/></div>`,
                async (body) => {
                    const urgency = body.querySelector('#cmdPriorityUrgency').value === 'true';
                    const urgencyReason = body.querySelector('#cmdPriorityUrgencyReason').value || '';
                    const importance = body.querySelector('#cmdPriorityImportance').value === 'true';
                    const importanceReason = body.querySelector('#cmdPriorityImportanceReason').value || '';
                    const r = await fetch('/api/tickets/' + ticketId + '/priority', { method: 'POST', headers: authHeaders(true), body: JSON.stringify({ urgency, urgency_reason: urgencyReason, importance, importance_reason: importanceReason }) });
                    const d = await r.json().catch(() => ({}));
                    if (!r.ok) throw new Error(d.error || 'Ошибка смены приоритета');
                    meta.priority = d.priority;
                    meta.priority_class = d.priority_class;
                    meta.urgency = d.urgency;
                    meta.importance = d.importance;
                    meta.urgency_reason = urgencyReason;
                    meta.importance_reason = importanceReason;
                    setTopbar(meta);
                    renderSidebar();
                });
            return;
        }
        if (cmd === '/reroute') {
            const r = await fetch('/api/tickets/' + ticketId + '/reroute', { method: 'POST', headers: authHeaders(true), body: JSON.stringify({}) });
            const d = await r.json().catch(() => ({}));
            if (!r.ok) { showSystemMessage(d.error || 'Ошибка reroute', true); return; }
            showSystemMessage('Очередь пересчитана по правилам');
            loadSnapshot();
            return;
        }
        if (cmd === '/close') {
            openInlinePanel('Подтвердить решение',
                `<div class="form-group"><p>Подтвердите, что проблема действительно решена и тикет можно закрыть.</p></div>`,
                async (body) => {
                    const r = await fetch('/api/tickets/' + ticketId + '/close', { method: 'POST', headers: authHeaders(true), body: JSON.stringify({ reason: 'requester_confirmed_resolution' }) });
                    const d = await r.json().catch(() => ({}));
                    if (!r.ok) throw new Error(d.message || d.error || 'Ошибка подтверждения');
                    meta.status = 'closed';
                    meta.resolution_confirmation_pending = false;
                    setTopbar(meta);
                    renderSidebar();
                    loadSnapshot();
                });
            return;
        }
        if (cmd === '/worklog') {
            openInlinePanel('Трудозатраты',
                `<div class="form-group"><label>Минуты</label><input type="number" id="cmdWorklogMin" value="15" min="1" max="1440"/></div>
                 <div class="form-group"><label>Комментарий</label><input type="text" id="cmdWorklogNote" placeholder="необязательно"/></div>`,
                async (body) => {
                    const spent = parseInt(body.querySelector('#cmdWorklogMin').value, 10) || 15;
                    const note = body.querySelector('#cmdWorklogNote').value?.trim() || null;
                    const r = await fetch('/api/tickets/' + ticketId + '/worklogs', { method: 'POST', headers: authHeaders(true), body: JSON.stringify({ spent_minutes: spent, note }) });
                    const d = await r.json().catch(() => ({}));
                    if (!r.ok) throw new Error(d.details?.spent_minutes || d.error || 'Ошибка добавления трудозатрат');
                    showSystemMessage('Трудозатраты добавлены: ' + spent + ' мин');
                });
            return;
        }
        if (cmd === '/tool' || cmd === '/module') {
            if (!hasBoundDevice()) { showSystemMessage('Нет привязки к устройству', true); return; }
            const r = await fetch('/api/tools?device_id=' + encodeURIComponent(meta.device_id), { headers: authHeaders() });
            const d = await r.json().catch(() => ({}));
            if (!r.ok) {
                const msg = (d.error_code === 'AUTH_REQUIRED' || r.status === 401)
                    ? 'Требуется авторизация. Откройте админ-панель (/admin), войдите и снова откройте тикет.'
                    : (d.error || 'Ошибка загрузки списка инструментов');
                showSystemMessage(msg, true);
                return;
            }
            const agentTools = d.tools || [];
            // Множество имён установленных инструментов для дедупликации
            const installedToolNames = new Set(agentTools.map(t => t.tool || t.name));
            // Инструменты с сервера: только те, которых нет на агенте
            const serverOnlyTools = (d.tools_from_server || [])
                .filter(t => !installedToolNames.has(t.tool || t.name))
                .map(t => ({ ...t, _needsInstall: true }));
            toolsList = agentTools.concat(serverOnlyTools);
            if (toolsList.length === 0) { showSystemMessage('Нет доступных инструментов', true); return; }
            function scenarioForTool(t) {
                const mod = (t.module || t.tool || t.name || '').toLowerCase();
                for (const [scenario, modules] of Object.entries(TOOL_SCENARIOS)) {
                    if (scenario === 'С установкой') continue;
                    if (modules.some(m => mod.includes(m))) return scenario;
                }
                return 'Прочее';
            }
            const byScenario = {};
            toolsList.forEach(t => {
                const sc = scenarioForTool(t);
                if (!byScenario[sc]) byScenario[sc] = [];
                byScenario[sc].push(t);
            });
            const scenarioOrder = ['Диагностика', 'Сеть', 'Логи', 'Доступ/сеанс', 'Сервисные', 'Прочее'];
            let scenarioOpts = scenarioOrder.filter(sc => (byScenario[sc] || []).length > 0).map(sc => {
                const hasInstall = (byScenario[sc] || []).some(t => t._needsInstall);
                const label = sc + (hasInstall ? ' ⬇' : '');
                return `<option value="${escapeHtml(sc)}">${escapeHtml(label)}</option>`;
            }).join('');
            if (!scenarioOpts) scenarioOpts = '<option value="Прочее">Прочее</option>';
            let toolOpts = '';
            const installLabel = ' (с установкой)';
            function buildToolOpts(scenario) {
                const list = byScenario[scenario] || [];
                // Установленные первыми, потом требующие установки
                const installed = list.filter(t => !t._needsInstall);
                const needsInstall = list.filter(t => t._needsInstall);
                const buildOpts = (tools) => tools.map(t => {
                    const name = t.tool || t.name || '—';
                    const suffix = t._needsInstall ? installLabel : '';
                    const presets = (t.spec && t.spec.presets) || [];
                    let opts = presets.length ? presets.map(p => `<option value="${escapeHtml(name)}:${escapeHtml(p.id)}">${escapeHtml(name)} — ${escapeHtml(p.name || p.id)}${suffix}</option>`) : [];
                    opts.push(`<option value="${escapeHtml(name)}:">${escapeHtml(name)} (по умолчанию)${suffix}</option>`);
                    return opts.join('');
                }).join('');
                let result = buildOpts(installed);
                if (needsInstall.length > 0) {
                    if (installed.length > 0) result += `<option disabled>─── с установкой ───</option>`;
                    result += buildOpts(needsInstall);
                }
                return result;
            }
            function normalizeSchema(raw) {
                if (!raw) return [];
                if (Array.isArray(raw)) return raw;
                // объект вида {name: {...}} → массив
                if (typeof raw === 'object') return Object.values(raw);
                return [];
            }
            function buildParamsForm(tool) {
                const schema = normalizeSchema(tool && tool.spec && tool.spec.params_schema);
                if (schema.length === 0) return '';
                const fields = schema.map(p => {
                    const id = 'param_' + (p.name || '').replace(/\W/g, '_');
                    const req = p.required ? ' <span class="required">*</span>' : '';
                    const def = p.default != null ? String(p.default) : '';
                    return `<div class="form-group"><label for="${id}">${escapeHtml(p.name || '')}${req}</label><input type="text" id="${id}" name="${escapeHtml(p.name)}" placeholder="${escapeHtml(def)}" value="${escapeHtml(def)}"/></div>`;
                }).join('');
                return `<div id="toolParamsBlock" class="tool-params-block">${fields}</div>`;
            }
            const firstScenario = scenarioOrder.find(sc => (byScenario[sc] || []).length > 0) || 'Прочее';
            toolOpts = buildToolOpts(firstScenario);
            const firstTool = (byScenario[firstScenario] || [])[0];
            const initialParamsHtml = buildParamsForm(firstTool);
            const bodyHtml = `
                <div class="form-group"><label>Сценарий</label><select id="cmdToolScenario">${scenarioOpts}</select></div>
                <div class="form-group"><label>Инструмент / пресет</label><select id="cmdToolSelect">${toolOpts}</select></div>
                ${initialParamsHtml}
                <div id="toolRiskConfirm" class="form-group"><label class="risk-label"><input type="checkbox" id="cmdToolConfirm"/> Подтверждаю запуск рискованного действия</label></div>
            `;
            openInlinePanel('Инструменты ПК', bodyHtml, async (body, errEl) => {
                const val = body.querySelector('#cmdToolSelect').value;
                const [toolName, presetId] = val.includes(':') ? val.split(':', 2) : [val, null];
                const tool = toolsList.find(t => (t.tool || t.name) === toolName);
                if (tool && tool._needsInstall) {
                    showSystemMessage('Установка модуля ' + toolName.split('.')[0] + '...', false);
                }
                const riskLevel = tool && tool.spec && tool.spec.risk_level ? String(tool.spec.risk_level) : '';
                const requiresConsent = !!(tool && tool.metadata && tool.metadata.requires_consent);
                const isRisky = requiresConsent || riskLevel === 'system_write' || riskLevel === 'code_exec';
                const confirmEl = body.querySelector('#cmdToolConfirm');
                if (isRisky && (!confirmEl || !confirmEl.checked)) {
                    const riskBlock = body.querySelector('#toolRiskConfirm');
                    if (riskBlock) {
                        riskBlock.classList.remove('hidden');
                        if (errEl) errEl.textContent = 'Подтвердите запуск рискованного действия.';
                    }
                    throw new Error('Подтвердите запуск рискованного действия.');
                }
                const payload = { device_id: meta.device_id, ticket_id: ticketId, tool_name: toolName };
                if (presetId) {
                    payload.preset_id = presetId;
                } else {
                    payload.params = {};
                    const paramsBlock = body.querySelector('#toolParamsBlock');
                    const schemaForSubmit = normalizeSchema(tool && tool.spec && tool.spec.params_schema);
                    if (paramsBlock && schemaForSubmit.length > 0) {
                        schemaForSubmit.forEach(p => {
                            const paramName = p.name;
                            if (!paramName) return;
                            const input = body.querySelector('[name="' + paramName + '"]') || body.querySelector('#param_' + (paramName || '').replace(/\W/g, '_'));
                            if (input && input.value !== undefined && input.value !== '') payload.params[paramName] = input.value;
                        });
                    }
                }
                const r = await fetch('/api/tools/run', { method: 'POST', headers: authHeaders(true), body: JSON.stringify(payload) });
                const resp = await r.json().catch(() => ({}));
                if (!r.ok) throw new Error(resp.error || resp.details?.tool_name || 'Ошибка запуска');
                if (resp.status === 'error') throw new Error(resp.error);
                if (resp.status === 'waiting_consent' && resp.operation_id) {
                    showSystemMessage('Ожидает согласования (операция ' + resp.operation_id + ')');
                } else {
                    const installNote = tool && tool._needsInstall ? ' (установка + запуск)' : '';
                    showSystemMessage('Инструмент запущен: ' + toolName + installNote);
                }
                setTimeout(() => loadSnapshot(), 2000);
            }, (body) => {
                const scenarioSelect = body.querySelector('#cmdToolScenario');
                const toolSelect = body.querySelector('#cmdToolSelect');
                const paramsContainer = body.querySelector('#toolParamsBlock');
                function updateParamsForm(tool) {
                    if (!paramsContainer) return;
                    const schema = normalizeSchema(tool && tool.spec && tool.spec.params_schema);
                    if (schema.length === 0) {
                        paramsContainer.innerHTML = '';
                        paramsContainer.style.display = 'none';
                        return;
                    }
                    paramsContainer.style.display = '';
                    const fields = schema.map(p => {
                        const id = 'param_' + (p.name || '').replace(/\W/g, '_');
                        const req = p.required ? ' <span class="required">*</span>' : '';
                        const def = p.default != null ? String(p.default) : '';
                        return `<div class="form-group"><label for="${id}">${escapeHtml(p.name || '')}${req}</label><input type="text" id="${id}" name="${escapeHtml(p.name)}" placeholder="${escapeHtml(def)}" value="${escapeHtml(def)}"/></div>`;
                    }).join('');
                    paramsContainer.innerHTML = fields;
                }
                function onToolChange() {
                    const name = (toolSelect && toolSelect.value && toolSelect.value.split(':')[0]) || '';
                    const tool = toolsList.find(t => (t.tool || t.name) === name) || null;
                    updateParamsForm(tool);
                }
                if (scenarioSelect && toolSelect) {
                    scenarioSelect.onchange = () => {
                        toolSelect.innerHTML = buildToolOpts(scenarioSelect.value);
                        onToolChange();
                    };
                    toolSelect.onchange = onToolChange;
                }
            });
            return;
        }
    }

    function init() {
        const pathMatch = window.location.pathname.match(/\/ticket\/([^/]+)/);
        ticketId = pathMatch ? pathMatch[1] : (new URLSearchParams(window.location.search).get('ticket_id'));
        populateStatusSelect();
        document.querySelectorAll('.segmented-control').forEach((container) => {
            container.querySelectorAll('button[data-value]').forEach((btn) => {
                btn.addEventListener('click', () => setSegmentedValue(container.id, btn.dataset.value || 'false'));
            });
            setSegmentedValue(container.id, container.dataset.value || 'false');
        });
        if (!ticketId) {
            el('ticketError').textContent = 'Не указан ID тикета. Используйте /ticket/{id} или ?ticket_id=...';
            el('ticketError').classList.remove('hidden');
            return;
        }
        el('ticketLoading').classList.remove('hidden');
        el('ticketError').classList.add('hidden');
        loadSnapshot()
            .then(() => {
                el('ticketLoading').classList.add('hidden');
                el('ticketApp').classList.remove('hidden');
                el('topbar').classList.remove('hidden');
                el('ticketMain').classList.remove('hidden');
                el('timeline').classList.remove('hidden');
                const menuBtn = el('composerMenuBtn');
                const menuDropdown = el('composerMenuDropdown');
                const readOnly = !canPerformActions();
                if (menuBtn) {
                    menuBtn.disabled = readOnly;
                    menuBtn.onclick = (e) => {
                        e.stopPropagation();
                        if (readOnly) return;
                        menuDropdown.classList.toggle('open');
                        menuDropdown.classList.toggle('hidden', !menuDropdown.classList.contains('open'));
                    };
                }
                if (menuDropdown) {
                    menuDropdown.addEventListener('click', (e) => e.stopPropagation());
                    menuDropdown.querySelectorAll('.menu-item').forEach(btn => {
                        btn.disabled = readOnly;
                        btn.onclick = (e) => {
                            e.preventDefault();
                            const cmd = btn.getAttribute('data-cmd');
                            if (cmd) runCommand(cmd);
                            menuDropdown.classList.remove('open');
                            menuDropdown.classList.add('hidden');
                        };
                    });
                }
                document.addEventListener('click', () => {
                    if (menuDropdown && menuDropdown.classList.contains('open')) {
                        menuDropdown.classList.remove('open');
                        menuDropdown.classList.add('hidden');
                    }
                });
                el('composer').classList.remove('hidden');
                document.querySelectorAll('.sidebar-editable input, .sidebar-editable select, .sidebar-editable button').forEach((control) => {
                    if (!canPerformActions()) control.setAttribute('disabled', 'disabled');
                    else control.removeAttribute('disabled');
                });
                refreshDeviceActionControls();
                refreshCloseControls();
                refreshSidebarOptions();
                if (canPerformActions()) {
                    el('sideRequesterApplyBtn')?.addEventListener('click', async () => {
                        try { await applyRequesterProfile(); } catch (err) { showSystemMessage(err.message || String(err), true); }
                    });
                    el('sideStatusApplyBtn')?.addEventListener('click', async () => {
                        try { await applyStatus(); } catch (err) { showSystemMessage(err.message || String(err), true); }
                    });
                    el('sidePriorityApplyBtn')?.addEventListener('click', async () => {
                        try { await applyPriority(); } catch (err) { showSystemMessage(err.message || String(err), true); }
                    });
                    el('sideAssigneeApplyBtn')?.addEventListener('click', async () => {
                        try { await applyAssignee(); } catch (err) { showSystemMessage(err.message || String(err), true); }
                    });
                    el('sideAutoAssignBtn')?.addEventListener('click', async () => {
                        try { await applyAutoAssign(); } catch (err) { showSystemMessage(err.message || String(err), true); }
                    });
                    el('sideQueueApplyBtn')?.addEventListener('click', async () => {
                        try { await applyQueue(); } catch (err) { showSystemMessage(err.message || String(err), true); }
                    });
                    el('sideDeviceApplyBtn')?.addEventListener('click', async () => {
                        try { await applyDeviceBinding(); } catch (err) { showSystemMessage(err.message || String(err), true); }
                    });
                }
                el('sideCloseBtn')?.addEventListener('click', async () => {
                    try { await closeTicket(); } catch (err) { showSystemMessage(err.message || String(err), true); }
                });
                connectWs();
                startPollFallback();
            })
            .catch(err => {
                el('ticketLoading').classList.add('hidden');
                el('ticketError').textContent = err.message || 'Ошибка загрузки';
                el('ticketError').classList.remove('hidden');
            });

        const textarea = el('messageInput');
        const sendBtn = el('sendButton');
        const internalCheck = el('internalToggle');

        async function doSend() {
            const text = (textarea && textarea.value || '').trim();
            const attachmentRefs = pendingAttachments.map((item) => item.artifact_id).filter(Boolean);
            if (!text && attachmentRefs.length === 0) return;
            const visibility = (internalCheck && internalCheck.checked) ? 'internal' : 'public';
            const ok = await sendMessage(text, visibility, attachmentRefs);
            if (!ok) return;
            if (textarea) textarea.value = '';
            pendingAttachments = [];
            renderPendingAttachments();
        }

        if (sendBtn) sendBtn.addEventListener('click', () => { void doSend(); });
        if (textarea) {
            textarea.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void doSend(); }
            });
            textarea.addEventListener('focus', () => {
                const timelineEl = el('timeline');
                if (timelineEl && getTimelineScrollState(timelineEl).shouldStick) timelineEl.scrollTop = timelineEl.scrollHeight;
            });
        }
        const attachBtn = el('attachButton');
        const attachInput = el('attachFileInput');
        if (attachBtn && attachInput) {
            attachBtn.addEventListener('click', () => attachInput.click());
            attachInput.addEventListener('change', async () => {
                const files = attachInput.files ? Array.from(attachInput.files) : [];
                if (!files.length) return;
                for (const file of files) {
                    try {
                        const artifact = await uploadAttachment(file);
                        if (artifact && artifact.artifact_id) {
                            pendingAttachments.push(artifact);
                        }
                    } catch (err) {
                        showSystemMessage(err.message || String(err), true);
                    }
                }
                renderPendingAttachments();
                attachInput.value = '';
            });
        }

        const quickScreenshotBtn = el('quickScreenshotBtn');
        if (quickScreenshotBtn) {
            quickScreenshotBtn.addEventListener('click', () => {
                void runQuickTool('screen.collect', {}, 'Запрос на скриншот отправлен');
            });
        }
        const quickRecordBtn = el('quickRecordBtn');
        if (quickRecordBtn) {
            quickRecordBtn.addEventListener('click', () => {
                void runQuickTool('screen.record', { duration_sec: 15 }, 'Запрос на запись видео отправлен');
            });
        }
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();

