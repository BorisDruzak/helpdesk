/**
 * Support workspace: inbox + preview/work/observe + right workbench drawer.
 * Uses existing UI auth token and ticket/tool APIs.
 */
(function () {
    const AUTH_TOKEN_KEY = 'admin_auth_token';
    const USER_LOGIN_KEY = 'admin_user_login';
    const ROLE_KEY = 'admin_actor_role';
    const LAST_TICKET_KEY = 'support_workspace_last_ticket';
    const SIDEBAR_MODE_KEY = 'support_workspace_sidebar_mode';
    const DRAWER_MODE_KEY = 'support_workspace_drawer_mode';
    const LOGIN_SHELL_VERSION = '20260330a';
    const SUPPORT_SHELL_VERSION = '20260401a';
    const POLL_INTERVAL_MS = 8000;
    const CLOSED_TICKET_HIDE_AFTER_MS = 24 * 60 * 60 * 1000;
    const PANEL_MODES = Object.freeze({
        COLLAPSED: 'collapsed',
        HALF: 'half',
        FULL: 'full',
    });
    const ACTIVE_WORK_STATUSES = new Set(['triaged', 'in_progress', 'waiting_on_user', 'waiting_on_vendor', 'resolved']);
    const STATUS_LABELS = {
        new: 'Новая',
        triaged: 'В очереди у оператора',
        in_progress: 'В работе',
        waiting_on_user: 'Ждёт пользователя',
        waiting_on_vendor: 'Ждёт внешнюю сторону',
        resolved: 'Решена',
        closed: 'Закрыта',
    };
    const PRIORITY_LABELS = {
        P0: 'Критический',
        P1: 'Высокий',
        P2: 'Средний',
        P3: 'Низкий',
    };
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
        'message_read',
    ]);
    const TOOL_SCENARIOS = {
        'Диагностика': ['os_check', 'system', 'diagnostic'],
        'Сеть': ['ping_check', 'network', 'ping'],
        'Логи': ['logs', 'log'],
        'Доступ/сеанс': ['session', 'access', 'remote'],
        'Сервисные': ['service', 'install', 'maintenance'],
        'С установкой': [],
        'Прочее': [],
    };
    const state = {
        actorRole: '',
        userLogin: '',
        currentFilter: 'mine',
        ticketQuery: '',
        tickets: [],
        selectedTicketId: '',
        selectedSnapshot: null,
        selectedLifecycle: null,
        detailLoading: false,
        drawerMode: PANEL_MODES.HALF,
        drawerTab: 'context',
        sidebarMode: PANEL_MODES.HALF,
        ticketClickTimer: 0,
        pollTimer: null,
        tools: [],
        toolsDeviceId: '',
        toolSearch: '',
        activeToolScenario: 'all',
        selectedToolKey: '',
        pipeline: [],
        hiddenClosedCount: 0,
    };
    let resolutionCodesCache = [];
    let resolutionDialogResolve = null;
    let resolutionDialogReject = null;

    function byId(id) {
        return document.getElementById(id);
    }

    function normalizePanelMode(value) {
        if (value === PANEL_MODES.COLLAPSED || value === PANEL_MODES.FULL) {
            return value;
        }
        return PANEL_MODES.HALF;
    }

    function getToken() {
        const token = localStorage.getItem(AUTH_TOKEN_KEY);
        return typeof token === 'string' ? token.trim() : '';
    }

    function authHeaders(includeContentType) {
        const headers = {};
        const token = getToken();
        if (token) {
            headers.Authorization = 'Bearer ' + token;
        }
        if (includeContentType) {
            headers['Content-Type'] = 'application/json';
        }
        return headers;
    }

    function resolutionCodeMeaning(code) {
        const map = {
            fixed: 'Проблему исправили',
            workaround: 'Использован обходной путь',
            user_error: 'Ошибка пользователя',
            duplicate: 'Дубликат другой заявки',
            cannot_reproduce: 'Не удалось повторить',
            vendor: 'Передано вендору',
        };
        return map[code] || 'Служебный код закрытия';
    }

    function boolLabel(value) {
        return value ? 'Да' : 'Нет';
    }

    async function ensureResolutionCodesLoaded() {
        if (resolutionCodesCache.length) {
            return resolutionCodesCache;
        }
        const response = await fetch('/api/tickets/resolution_codes', { headers: authHeaders() });
        const data = await responseToJson(response);
        if (!response.ok) {
            throw new Error(data.error || 'Не удалось загрузить коды решения');
        }
        resolutionCodesCache = data.resolution_codes || [];
        return resolutionCodesCache;
    }

    function closeResolutionDialog(error) {
        const dialog = byId('resolutionDialog');
        const errorNode = byId('resolutionDialogError');
        if (dialog) {
            dialog.classList.add('hidden');
            dialog.setAttribute('aria-hidden', 'true');
        }
        if (errorNode) {
            errorNode.textContent = '';
            errorNode.classList.add('hidden');
        }
        const reject = resolutionDialogReject;
        resolutionDialogResolve = null;
        resolutionDialogReject = null;
        if (error && reject) {
            reject(error);
        }
    }

    function openResolutionDialog(codes) {
        const dialog = byId('resolutionDialog');
        const codeSelect = byId('resolutionDialogCode');
        const rootCauseInput = byId('resolutionDialogRootCause');
        const errorNode = byId('resolutionDialogError');
        if (!dialog || !codeSelect || !rootCauseInput || !errorNode) {
            return Promise.reject(new Error('Не удалось открыть форму завершения тикета'));
        }
        codeSelect.innerHTML = '<option value="">Выберите код решения</option>' + codes.map((code) => {
            const codeValue = String(code.code || '').trim();
            const codeLabel = (code.name || codeValue || '') + ' — ' + resolutionCodeMeaning(codeValue);
            return `<option value="${escapeHtml(codeValue)}">${escapeHtml(codeLabel)}</option>`;
        }).join('');
        rootCauseInput.value = '';
        errorNode.textContent = '';
        errorNode.classList.add('hidden');
        dialog.classList.remove('hidden');
        dialog.setAttribute('aria-hidden', 'false');
        window.setTimeout(() => codeSelect.focus(), 0);
        return new Promise((resolve, reject) => {
            resolutionDialogResolve = resolve;
            resolutionDialogReject = reject;
        });
    }

    async function collectResolutionPayload(nextStatus) {
        if (nextStatus !== 'resolved' && nextStatus !== 'closed') {
            return {};
        }
        const codes = await ensureResolutionCodesLoaded();
        if (!codes.length) {
            throw new Error('В справочнике нет активных кодов решения');
        }
        return openResolutionDialog(codes);
    }

    async function responseToJson(response) {
        const text = await response.text();
        if (!text || !text.trim()) {
            return {};
        }
        try {
            return JSON.parse(text);
        } catch (error) {
            const preview = text.slice(0, 120).replace(/\s+/g, ' ');
            throw new Error('Сервер вернул не JSON. ' + preview);
        }
    }

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function parseServerDate(value) {
        if (!value) {
            return null;
        }
        const normalized = String(value)
            .trim()
            .replace(/\.(\d{3})\d+([+-]\d{2}:\d{2}|Z)$/i, '.$1$2');
        const date = new Date(normalized);
        return Number.isNaN(date.getTime()) ? null : date;
    }

    function formatDate(value) {
        const date = parseServerDate(value);
        if (!date) {
            return '—';
        }
        return date.toLocaleString('ru-RU');
    }

    function formatAge(value) {
        const date = parseServerDate(value);
        if (!date) {
            return '—';
        }
        const diffMs = Math.max(0, Date.now() - date.getTime());
        const diffMin = Math.floor(diffMs / 60000);
        if (diffMin < 1) {
            return 'только что';
        }
        if (diffMin < 60) {
            return diffMin + ' мин';
        }
        const diffHours = Math.floor(diffMin / 60);
        if (diffHours < 24) {
            return diffHours + ' ч';
        }
        const diffDays = Math.floor(diffHours / 24);
        return diffDays + ' д';
    }

    function statusLabel(status) {
        return STATUS_LABELS[status] || status || '—';
    }

    function priorityLabel(priorityClass) {
        if (!priorityClass) {
            return '—';
        }
        return (PRIORITY_LABELS[priorityClass] || priorityClass) + ' (' + priorityClass + ')';
    }

    function statusClass(status) {
        if (status === 'in_progress') {
            return 'status-in-progress';
        }
        if (status === 'waiting_on_user' || status === 'waiting_on_vendor') {
            return 'status-waiting';
        }
        if (status === 'resolved' || status === 'closed') {
            return 'status-resolved';
        }
        return 'status-' + String(status || 'new').replace(/_/g, '-');
    }

    function canWrite() {
        return state.actorRole === 'support' || state.actorRole === 'admin';
    }

    function canAccessWorkspace(role) {
        return role === 'support';
    }

    function setSyncState(text) {
        const node = byId('workspaceSyncState');
        if (node) {
            node.textContent = text;
        }
    }

    function setLoginError(text) {
        const node = byId('loginError');
        if (!node) {
            return;
        }
        node.textContent = text || '';
        node.classList.toggle('hidden', !text);
    }

    function showToast(text, isError) {
        const node = byId('toast');
        if (!node) {
            return;
        }
        node.textContent = text;
        node.style.background = isError ? 'rgba(179, 57, 57, 0.94)' : 'rgba(31, 36, 31, 0.92)';
        node.classList.remove('hidden');
        window.clearTimeout(showToast._timer);
        showToast._timer = window.setTimeout(() => node.classList.add('hidden'), 3200);
    }

    function updateAuthBadge() {
        const node = byId('authBadge');
        if (!node) {
            return;
        }
        const role = state.actorRole || '—';
        const user = state.userLogin || '—';
        node.textContent = user + ' • ' + role;
    }

    function updateSwitchRoleLink() {
        const node = byId('switchRoleBtn');
        if (!node) {
            return;
        }
        node.href = '/login?_shell=' + LOGIN_SHELL_VERSION + '&target=admin';
    }

    function applyLayoutClasses() {
        const layout = byId('supportLayout');
        if (!layout) {
            return;
        }
        layout.dataset.sidebarMode = state.sidebarMode;
        layout.dataset.drawerMode = state.drawerMode;
        const sidebarToggleBtn = byId('sidebarToggleBtn');
        if (sidebarToggleBtn) {
            const isCollapsed = state.sidebarMode === PANEL_MODES.COLLAPSED;
            sidebarToggleBtn.textContent = isCollapsed ? '⟩' : '⟨';
            sidebarToggleBtn.title = isCollapsed ? 'Развернуть список тикетов' : 'Полностью свернуть список тикетов';
        }
        const inboxResizeBtn = byId('collapseInboxBtn');
        if (inboxResizeBtn) {
            const isFull = state.sidebarMode === PANEL_MODES.FULL;
            inboxResizeBtn.textContent = isFull ? '⟫' : '⟪';
            inboxResizeBtn.title = isFull ? 'Вернуть стандартную ширину списка тикетов' : 'Развернуть список тикетов на всю ширину';
        }
        const drawerToggleBtn = byId('drawerToggleBtn');
        if (drawerToggleBtn) {
            const isCollapsed = state.drawerMode === PANEL_MODES.COLLAPSED;
            drawerToggleBtn.textContent = isCollapsed ? '⟨' : '⟩';
            drawerToggleBtn.title = isCollapsed ? 'Развернуть панель инструментов' : 'Полностью свернуть панель инструментов';
        }
        const drawerResizeBtn = byId('drawerResizeBtn');
        if (drawerResizeBtn) {
            const isFull = state.drawerMode === PANEL_MODES.FULL;
            drawerResizeBtn.textContent = isFull ? '⟪' : '⟫';
            drawerResizeBtn.title = isFull ? 'Вернуть стандартную ширину панели инструментов' : 'Развернуть панель инструментов на всю ширину';
        }
    }

    function setSidebarMode(mode, options) {
        state.sidebarMode = normalizePanelMode(mode);
        if (!(options && options.persist === false)) {
            sessionStorage.setItem(SIDEBAR_MODE_KEY, state.sidebarMode);
        }
        applyLayoutClasses();
    }

    function setDrawerMode(mode, options) {
        state.drawerMode = normalizePanelMode(mode);
        if (!(options && options.persist === false)) {
            sessionStorage.setItem(DRAWER_MODE_KEY, state.drawerMode);
        }
        applyLayoutClasses();
    }

    function redirectToLogin(message) {
        const params = new URLSearchParams();
        params.set('_shell', LOGIN_SHELL_VERSION);
        params.set('target', 'support');
        if (message) {
            params.set('message', message);
        }
        window.location.href = '/login?' + params.toString();
    }

    function showLoginScreen() {
        redirectToLogin();
    }

    function showWorkspace() {
        byId('loginContainer')?.classList.add('hidden');
        byId('supportApp')?.classList.remove('hidden');
    }

    function clearStoredSession() {
        localStorage.removeItem(AUTH_TOKEN_KEY);
        localStorage.removeItem(USER_LOGIN_KEY);
        localStorage.removeItem(ROLE_KEY);
        sessionStorage.removeItem(LAST_TICKET_KEY);
        sessionStorage.removeItem(SIDEBAR_MODE_KEY);
        sessionStorage.removeItem(DRAWER_MODE_KEY);
    }

    function logout() {
        stopPolling();
        clearStoredSession();
        state.actorRole = '';
        state.userLogin = '';
        state.tickets = [];
        state.selectedTicketId = '';
        state.selectedSnapshot = null;
        state.selectedLifecycle = null;
        state.sidebarMode = PANEL_MODES.HALF;
        state.drawerMode = PANEL_MODES.HALF;
        renderTicketList();
        renderStage();
        renderContextPanel();
        renderToolPanels();
        redirectToLogin();
    }

    function syncSessionFromStorage() {
        state.userLogin = localStorage.getItem(USER_LOGIN_KEY) || '';
        state.actorRole = localStorage.getItem(ROLE_KEY) || '';
        state.selectedTicketId = sessionStorage.getItem(LAST_TICKET_KEY) || '';
        state.sidebarMode = normalizePanelMode(sessionStorage.getItem(SIDEBAR_MODE_KEY));
        state.drawerMode = normalizePanelMode(sessionStorage.getItem(DRAWER_MODE_KEY));
        updateAuthBadge();
    }

    async function handleLoginSubmit(event) {
        event.preventDefault();
        redirectToLogin();
    }

    async function fetchCurrentSession() {
        const token = getToken();
        if (!token) {
            return null;
        }
        const response = await fetch('/api/ui_session', {
            headers: { Authorization: 'Bearer ' + token },
        });
        if (response.status === 401) {
            clearStoredSession();
            return null;
        }
        const data = await responseToJson(response);
        if (!response.ok || data.status !== 'success') {
            clearStoredSession();
            return null;
        }
        return data;
    }

    function startPolling() {
        stopPolling();
        state.pollTimer = window.setInterval(async () => {
            try {
                await loadTickets({ preserveSelection: true, silent: true });
                if (state.selectedTicketId) {
                    await refreshSelectedDetails(true);
                }
            } catch (error) {
                console.warn('support polling', error);
            }
        }, POLL_INTERVAL_MS);
    }

    function stopPolling() {
        if (state.pollTimer) {
            window.clearInterval(state.pollTimer);
            state.pollTimer = null;
        }
    }

    function selectedTicket() {
        return state.tickets.find((ticket) => ticket.ticket_id === state.selectedTicketId) || null;
    }

    function isNeedsAction(ticket) {
        return Boolean(
            ticket
            && (
                ticket.requires_operator_action
                || ticket.status === 'new'
                || ticket.status === 'waiting_on_user'
                || ticket.resolution_confirmation_pending
            )
        );
    }

    function ticketMatchesQuery(ticket, query) {
        if (!query) {
            return true;
        }
        const needle = query.toLowerCase();
        const haystack = [
            ticket.ticket_code,
            ticket.ticket_id,
            ticket.title,
            ticket.description,
            ticket.requester_display_name,
            ticket.requester_id,
            ticket.queue_code,
            ticket.assignee_id,
            ticket.device_id,
        ]
            .filter(Boolean)
            .join(' ')
            .toLowerCase();
        return haystack.includes(needle);
    }

    function ticketPassesFilter(ticket, filterName) {
        if (!ticket) {
            return false;
        }
        if (filterName === 'mine') {
            return ticket.assignee_id === state.userLogin;
        }
        if (filterName === 'unassigned') {
            return !ticket.assignee_id;
        }
        if (filterName === 'actionable') {
            return isNeedsAction(ticket);
        }
        if (filterName === 'waiting') {
            return ticket.status === 'waiting_on_user';
        }
        return true;
    }

    function closeTimestampForWorkspace(ticket) {
        if (!ticket) {
            return null;
        }
        return parseServerDate(ticket.closed_at || ticket.updated_at || ticket.resolved_at);
    }

    function shouldHideClosedTicket(ticket) {
        if (!ticket) {
            return false;
        }
        if (ticket.archived_at) {
            return true;
        }
        if (ticket.status !== 'closed') {
            return false;
        }
        const closedAt = closeTimestampForWorkspace(ticket);
        if (!closedAt) {
            return false;
        }
        return (Date.now() - closedAt.getTime()) >= CLOSED_TICKET_HIDE_AFTER_MS;
    }

    function filteredTickets() {
        return state.tickets.filter((ticket) => ticketPassesFilter(ticket, state.currentFilter) && ticketMatchesQuery(ticket, state.ticketQuery));
    }

    function countForFilter(filterName) {
        return state.tickets.filter((ticket) => ticketPassesFilter(ticket, filterName)).length;
    }

    function canTakeSelf(ticket) {
        return canWrite() && Boolean(ticket) && !ticket.assignee_id && (ticket.status === 'new' || ticket.status === 'triaged');
    }

    function shouldObserveTicket(ticket) {
        return Boolean(ticket && ticket.assignee_id && ticket.assignee_id !== state.userLogin && ACTIVE_WORK_STATUSES.has(ticket.status));
    }

    function shouldWorkTicket(ticket) {
        return Boolean(ticket && ticket.assignee_id === state.userLogin && ticket.status !== 'closed');
    }

    function currentMode() {
        const ticket = selectedTicket();
        if (!ticket) {
            return 'empty';
        }
        if (shouldWorkTicket(ticket) && canWrite()) {
            return 'work';
        }
        if (shouldObserveTicket(ticket)) {
            return 'observe';
        }
        return 'preview';
    }

    function buildTicketMetaLine(ticket) {
        const parts = [
            ticket.requester_display_name || ticket.requester_id || '—',
            statusLabel(ticket.status),
            ticket.assignee_id ? ('Исполнитель: ' + ticket.assignee_id) : 'Без исполнителя',
        ];
        if (ticket.priority_class) {
            parts.push(priorityLabel(ticket.priority_class));
        }
        if (ticket.queue_code) {
            parts.push('Очередь: ' + ticket.queue_code);
        }
        return parts.join(' • ');
    }

    function renderTicketFilterChips() {
        const chips = document.querySelectorAll('#ticketFilterChips .filter-chip');
        chips.forEach((chip) => {
            const filterName = chip.getAttribute('data-filter') || 'all';
            const baseLabel = chip.textContent.replace(/\s+\(\d+\)$/u, '');
            chip.classList.toggle('active', filterName === state.currentFilter);
            chip.textContent = baseLabel + ' (' + countForFilter(filterName) + ')';
        });
    }

    function renderTicketList() {
        renderTicketFilterChips();
        const listNode = byId('ticketList');
        const metaNode = byId('ticketListMeta');
        if (!listNode || !metaNode) {
            return;
        }
        const tickets = filteredTickets();
        const hiddenClosedNote = state.hiddenClosedCount > 0
            ? (' • Закрытые старше 1 дня скрыты: ' + state.hiddenClosedCount)
            : '';
        metaNode.textContent = 'Показано ' + tickets.length + ' из ' + state.tickets.length;
        metaNode.textContent += hiddenClosedNote;
        if (!tickets.length) {
            listNode.innerHTML = '<div class="activity-item">По выбранным фильтрам тикеты не найдены.</div>';
            return;
        }
        listNode.innerHTML = tickets.map((ticket) => {
            const active = ticket.ticket_id === state.selectedTicketId ? ' active' : '';
            const requester = ticket.requester_display_name || ticket.requester_id || '—';
            const expandedDetails = [
                'ID: ' + (ticket.ticket_id || '—'),
                'Устройство: ' + (ticket.device_id || 'Не привязано'),
                'Создан: ' + formatDate(ticket.created_at),
            ];
            const descriptionPreview = String(ticket.description || '').trim();
            const modeBadge = shouldWorkTicket(ticket)
                ? '<span class="mode-badge">Work</span>'
                : (shouldObserveTicket(ticket) ? '<span class="mode-badge mode-badge-observe">Observe</span>' : '<span class="mode-badge">Preview</span>');
            const actionMarker = isNeedsAction(ticket) ? '<span class="chip">Нужно действие</span>' : '';
            const takeSelfButton = canTakeSelf(ticket)
                ? '<button type="button" class="btn btn-secondary ticket-take-btn" data-ticket-action="take" data-ticket-id="' + escapeHtml(ticket.ticket_id) + '">Взять себе</button>'
                : '';
            return `
                <article class="ticket-row${active}" data-ticket-id="${escapeHtml(ticket.ticket_id)}">
                    <div class="ticket-row-head">
                        <div>
                            <div class="ticket-code">${escapeHtml(ticket.ticket_code || ticket.ticket_id)}</div>
                            <div class="ticket-title">${escapeHtml(ticket.title || 'Без названия')}</div>
                        </div>
                        ${modeBadge}
                    </div>
                    <div class="ticket-row-body">
                        <div>${escapeHtml(requester)}</div>
                        <div class="ticket-meta-line">${escapeHtml(buildTicketMetaLine(ticket))}</div>
                        <div class="ticket-row-foot">Обновлён: ${escapeHtml(formatDate(ticket.updated_at || ticket.created_at))} • Возраст: ${escapeHtml(formatAge(ticket.created_at))}</div>
                        <div class="ticket-row-expanded">
                            <div class="ticket-row-expanded-grid">
                                ${expandedDetails.map((item) => '<div class="ticket-row-expanded-item">' + escapeHtml(item) + '</div>').join('')}
                            </div>
                            ${descriptionPreview ? '<div class="ticket-row-description">' + escapeHtml(descriptionPreview) + '</div>' : ''}
                        </div>
                    </div>
                    <div class="ticket-row-actions">
                        <span class="status-chip ${statusClass(ticket.status)}">${escapeHtml(statusLabel(ticket.status))}</span>
                        ${ticket.priority_class ? '<span class="chip">' + escapeHtml(ticket.priority_class) + '</span>' : ''}
                        ${actionMarker}
                        ${takeSelfButton}
                    </div>
                </article>
            `;
        }).join('');
        listNode.querySelectorAll('.ticket-row').forEach((row) => {
            row.addEventListener('click', async (event) => {
                if (event.target instanceof Element && event.target.closest('[data-ticket-action="take"]')) {
                    return;
                }
                const ticketId = row.getAttribute('data-ticket-id') || '';
                if (!ticketId) {
                    return;
                }
                if (state.ticketClickTimer) {
                    window.clearTimeout(state.ticketClickTimer);
                    state.ticketClickTimer = 0;
                }
                if (event.detail > 1) {
                    await selectTicket(ticketId);
                    if (state.sidebarMode === PANEL_MODES.FULL) {
                        setSidebarMode(PANEL_MODES.HALF);
                    }
                    return;
                }
                state.ticketClickTimer = window.setTimeout(() => {
                    state.ticketClickTimer = 0;
                    selectTicket(ticketId).catch((error) => {
                        console.error('Failed to select ticket from inbox click', error);
                    });
                }, 220);
            });
        });
        listNode.querySelectorAll('[data-ticket-action="take"]').forEach((button) => {
            button.addEventListener('click', async (event) => {
                event.stopPropagation();
                const ticketId = button.getAttribute('data-ticket-id') || '';
                await takeTicketSelf(ticketId);
            });
        });
    }

    function renderSelectedMeta(ticket, snapshot) {
        const metaNode = byId('selectedTicketMeta');
        if (!metaNode) {
            return;
        }
        if (!ticket) {
            metaNode.innerHTML = '';
            return;
        }
        const mode = currentMode();
        const items = [
            ['Код', ticket.ticket_code || ticket.ticket_id],
            ['Статус', statusLabel(ticket.status)],
            ['Очередь', ticket.queue_code || snapshot?.queue_code || ticket.queue_id || '—'],
            ['Исполнитель', ticket.assignee_id || 'Не назначен'],
            ['Инициатор', snapshot?.requester_display_name || ticket.requester_display_name || ticket.requester_id || '—'],
            ['Приоритет', ticket.priority_class ? priorityLabel(ticket.priority_class) : '—'],
            ['Режим', mode === 'work' ? 'Работа' : (mode === 'observe' ? 'Наблюдение' : 'Предпросмотр')],
        ];
        metaNode.innerHTML = items.map(([label, value]) => `
            <div class="selected-ticket-meta-item">
                <div class="selected-ticket-meta-label">${escapeHtml(label)}</div>
                <strong class="selected-ticket-meta-value">${escapeHtml(value)}</strong>
            </div>
        `).join('');
    }

    function quickActionButtons(ticket) {
        if (!ticket) {
            return [];
        }
        const actions = [];
        if (canTakeSelf(ticket)) {
            actions.push({ id: 'take_self', label: 'Взять себе', kind: 'secondary' });
        }
        if (shouldWorkTicket(ticket) && canWrite()) {
            if (ticket.status === 'new' || ticket.status === 'triaged' || ticket.status === 'waiting_on_user' || ticket.status === 'waiting_on_vendor') {
                actions.push({ id: 'to_in_progress', label: ticket.status === 'waiting_on_user' ? 'Вернуть в работу' : 'В работу', kind: 'primary' });
            }
            if (ticket.status === 'in_progress') {
                actions.push({ id: 'to_waiting_user', label: 'Ждём пользователя', kind: 'secondary' });
            }
            if (ticket.status === 'in_progress' || ticket.status === 'waiting_on_user' || ticket.status === 'waiting_on_vendor') {
                actions.push({ id: 'to_resolved', label: 'Решено', kind: 'primary' });
            }
        }
        if (canWrite()) {
            actions.push({ id: 'reroute_queue', label: 'Пересчитать очередь', kind: 'secondary' });
        }
        actions.push({ id: 'refresh', label: 'Обновить', kind: 'secondary' });
        if (ticket.device_id) {
            actions.push({ id: 'open_tools', label: 'Инструменты', kind: 'secondary' });
        }
        return actions;
    }

    function renderStageHeader() {
        const ticket = selectedTicket();
        const snapshot = state.selectedSnapshot;
        const titleNode = byId('selectedTicketTitle');
        const actionsNode = byId('stageQuickActions');
        if (!titleNode || !actionsNode) {
            return;
        }
        if (!ticket) {
            titleNode.textContent = 'Тикет не выбран';
            actionsNode.innerHTML = '';
            renderSelectedMeta(null, null);
            return;
        }
        titleNode.textContent = (ticket.ticket_code || ticket.ticket_id) + ' • ' + (ticket.title || 'Без названия');
        renderSelectedMeta(ticket, snapshot);
        const actions = quickActionButtons(ticket);
        actionsNode.innerHTML = actions.length ? `
            <div class="stage-actions-card">
                <div class="stage-actions-title">Управление тикетом</div>
                <div class="stage-actions-grid">
                    ${actions.map((action) => {
                        const btnClass = action.kind === 'primary' ? 'btn btn-primary' : 'btn btn-secondary';
                        return '<button type="button" class="' + btnClass + '" data-quick-action="' + escapeHtml(action.id) + '">' + escapeHtml(action.label) + '</button>';
                    }).join('')}
                </div>
            </div>
        ` : '';
        actionsNode.querySelectorAll('[data-quick-action]').forEach((button) => {
            button.addEventListener('click', async () => {
                await handleQuickAction(button.getAttribute('data-quick-action') || '');
            });
        });
    }

    function historyItemsFromSnapshot(snapshot) {
        const events = Array.isArray(snapshot?.history) ? snapshot.history : [];
        return events.slice(-8).reverse();
    }

    function renderPreviewPane() {
        const ticket = selectedTicket();
        const snapshot = state.selectedSnapshot;
        byId('previewModeBadge').textContent = currentMode() === 'observe' ? 'Observe' : 'Preview';
        byId('previewDescription').textContent = (snapshot?.description || ticket?.description || 'Описание пока не заполнено.');
        const requesterProfile = snapshot?.requester_profile || {};
        const requesterRows = [
            ['Имя', snapshot?.requester_display_name || ticket?.requester_display_name || ticket?.requester_id || '—'],
            ['ФИО', requesterProfile.full_name || '—'],
            ['Телефон', requesterProfile.phone || '—'],
            ['Корпус / кабинет', [requesterProfile.building, requesterProfile.room].filter(Boolean).join(' / ') || '—'],
        ];
        byId('previewRequester').innerHTML = requesterRows.map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd>`).join('');
        const contextRows = [
            ['Устройство', snapshot?.device_id || ticket?.device_id || 'Не привязано'],
            ['Очередь', snapshot?.queue_code || ticket?.queue_code || ticket?.queue_id || '—'],
            ['Создан', formatDate(ticket?.created_at)],
            ['Обновлён', formatDate(ticket?.updated_at)],
            ['Возраст', formatAge(ticket?.created_at)],
            ['Приоритет', ticket?.priority_class ? priorityLabel(ticket.priority_class) : '—'],
        ];
        byId('previewContext').innerHTML = contextRows.map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd>`).join('');
        const historyItems = historyItemsFromSnapshot(snapshot);
        byId('previewHistory').innerHTML = historyItems.length
            ? historyItems.map((item) => `
                <div class="activity-item">
                    <strong>${escapeHtml(item.event_type || 'event')}</strong>
                    <div class="timeline-meta">${escapeHtml(formatDate(item.created_at || item.ts))}</div>
                </div>
            `).join('')
            : '<div class="activity-item">Изменений пока нет.</div>';
    }

    function summarizeLifecycleDetails(details) {
        if (!details || typeof details !== 'object') {
            return '';
        }
        if (details.text) {
            return String(details.text);
        }
        if (details.summary) {
            return String(details.summary);
        }
        if (details.to_status) {
            return 'Новый статус: ' + statusLabel(details.to_status);
        }
        if (details.assignee_id) {
            return 'Исполнитель: ' + details.assignee_id;
        }
        const compact = Object.entries(details)
            .filter(([key]) => !['actor_id', 'actor_role', 'source'].includes(key))
            .slice(0, 4)
            .map(([key, value]) => key + ': ' + (typeof value === 'string' ? value : JSON.stringify(value)))
            .join('\n');
        return compact;
    }

    function renderObservePane() {
        const lifecycle = state.selectedLifecycle;
        const milestonesNode = byId('observeMilestones');
        const slaNode = byId('observeSlaLane');
        const timelineNode = byId('observeTimeline');
        if (!milestonesNode || !slaNode || !timelineNode) {
            return;
        }
        if (!lifecycle) {
            milestonesNode.innerHTML = '<div class="milestone-item">Загрузка lifecycle…</div>';
            slaNode.innerHTML = '';
            timelineNode.innerHTML = '<div class="activity-item">Подгружаем дерево событий…</div>';
            return;
        }
        const milestoneItems = Array.isArray(lifecycle.milestone_rail) ? lifecycle.milestone_rail : [];
        milestonesNode.innerHTML = milestoneItems.length
            ? milestoneItems.map((item) => `
                <div class="milestone-item">
                    <strong>${escapeHtml(item.label || item.key || 'Этап')}</strong>
                    <div>${escapeHtml(item.at ? formatDate(item.at) : 'ещё не достигнут')}</div>
                </div>
            `).join('')
            : '<div class="milestone-item">Нет milestone-данных.</div>';
        const slaItems = Array.isArray(lifecycle.sla_lane) ? lifecycle.sla_lane : [];
        slaNode.innerHTML = slaItems.length
            ? slaItems.map((item) => `
                <div class="sla-item">
                    <strong>${escapeHtml(item.label || item.key || 'SLA')}</strong>
                    <div>${escapeHtml(item.at ? formatDate(item.at) : 'не отмечено')}</div>
                </div>
            `).join('')
            : '';
        const timeline = Array.isArray(lifecycle.timeline) ? lifecycle.timeline : [];
        timelineNode.innerHTML = timeline.length
            ? timeline.map((item) => {
                const links = Array.isArray(item.links) ? item.links : [];
                return `
                    <article class="observe-item">
                        <div class="timeline-card-head">
                            <strong>${escapeHtml(item.icon || '•')} ${escapeHtml(item.title || item.kind || 'Событие')}</strong>
                            <span class="timeline-meta">${escapeHtml(formatDate(item.at))}</span>
                        </div>
                        <div class="timeline-meta">${escapeHtml(item.actor_label || 'Система')}</div>
                        <div class="observe-details">${escapeHtml(summarizeLifecycleDetails(item.details))}</div>
                        ${links.length ? '<div class="observe-links">' + links.map((link) => '<a href="' + escapeHtml(link.href || '#') + '">' + escapeHtml(link.label || link.href || 'ссылка') + '</a>').join(' • ') + '</div>' : ''}
                    </article>
                `;
            }).join('')
            : '<div class="activity-item">Для этого тикета пока нет дерева lifecycle.</div>';
    }

    function displayRole(payload) {
        const role = String(payload?.sender_role || payload?.from || payload?.actor_role || 'system').toLowerCase();
        if (role === 'support' || role === 'admin') {
            return 'support';
        }
        if (role === 'user' || role === 'requester' || role === 'agent' || role === 'device') {
            return 'user';
        }
        return role;
    }

    function eventSummary(eventType, payload) {
        if (eventType === 'status_changed') {
            return 'Статус: ' + statusLabel(payload?.from_status) + ' → ' + statusLabel(payload?.to_status);
        }
        if (eventType === 'assignee_changed') {
            return 'Исполнитель: ' + (payload?.previous_assignee_id || payload?.old_value || '—') + ' → ' + (payload?.assignee_id || payload?.new_value || '—');
        }
        if (eventType === 'queue_changed') {
            return 'Очередь: ' + (payload?.previous_queue_id || payload?.old_value || '—') + ' → ' + (payload?.queue_code || payload?.queue_id || payload?.new_value || '—');
        }
        if (eventType === 'tool_call_started') {
            return 'Запущен инструмент ' + (payload?.tool_name || payload?.tool || '—');
        }
        if (eventType === 'tool_call_result') {
            return payload?.summary || ('Результат инструмента ' + (payload?.tool_name || '—'));
        }
        if (eventType === 'requester_profile_changed') {
            return 'Профиль инициатора обновлён';
        }
        if (eventType === 'device_changed') {
            return 'Изменена привязка к агенту';
        }
        return Object.keys(payload || {}).length ? JSON.stringify(payload, null, 2) : 'Системное событие';
    }

    function ensureEmbeddedTicketFrame(ticketId) {
        const frame = byId('embeddedTicketFrame');
        if (!frame || !ticketId) {
            return;
        }
        const nextSrc = '/ticket.html?ticket_id=' + encodeURIComponent(ticketId) + '&embed=1&_shell=' + SUPPORT_SHELL_VERSION;
        if (frame.dataset.ticketId !== ticketId || frame.getAttribute('src') !== nextSrc) {
            frame.dataset.loadedTicketId = '';
            frame.dataset.ticketId = ticketId;
            setEmbeddedTicketLoading(true, 'Загрузка чата тикета...');
            frame.src = nextSrc;
            return;
        }
        if (frame.dataset.loadedTicketId === ticketId) {
            setEmbeddedTicketLoading(false, '');
        } else {
            setEmbeddedTicketLoading(true, 'Загрузка чата тикета...');
        }
    }

    function setEmbeddedTicketLoading(isLoading, message) {
        const frame = byId('embeddedTicketFrame');
        const placeholder = byId('embeddedTicketPlaceholder');
        const shell = frame ? frame.closest('.embedded-ticket-shell') : null;
        if (shell) {
            shell.classList.toggle('is-loading', !!isLoading);
        }
        if (frame) {
            frame.dataset.loading = isLoading ? '1' : '0';
        }
        if (!placeholder) {
            return;
        }
        placeholder.textContent = message || 'Загрузка чата тикета...';
        placeholder.classList.toggle('hidden', !isLoading);
    }

    function renderWorkPane() {
        const snapshot = state.selectedSnapshot;
        const ticket = selectedTicket();
        const frame = byId('embeddedTicketFrame');
        const placeholder = byId('embeddedTicketPlaceholder');
        if (!frame || !placeholder) {
            return;
        }
        if (!snapshot || !ticket) {
            setEmbeddedTicketLoading(true, 'Загрузка чата тикета...');
            return;
        }
        ensureEmbeddedTicketFrame(ticket.ticket_id);
    }

    function renderStage() {
        const mode = currentMode();
        renderStageHeader();
        byId('stageEmpty')?.classList.toggle('hidden', mode !== 'empty');
        byId('previewPane')?.classList.toggle('hidden', mode !== 'preview');
        byId('workPane')?.classList.toggle('hidden', mode !== 'work');
        byId('observePane')?.classList.toggle('hidden', mode !== 'observe');
        if (mode === 'preview') {
            renderPreviewPane();
        } else if (mode === 'work') {
            renderWorkPane();
        } else if (mode === 'observe') {
            renderObservePane();
        }
    }

    async function fetchJson(url, options) {
        const response = await fetch(url, options);
        const data = await responseToJson(response);
        if (response.status === 401) {
            clearStoredSession();
            redirectToLogin('Сессия поддержки истекла.');
            throw new Error('Сессия истекла. Войдите заново.');
        }
        if (!response.ok || data.status === 'error') {
            throw new Error(data.error || response.statusText || 'Ошибка запроса');
        }
        return data;
    }

    async function loadTickets(options) {
        const opts = options || {};
        setSyncState(opts.silent ? 'Синхронизация…' : 'Обновляем список тикетов…');
        const data = await fetchJson('/api/tickets?limit=200', { headers: authHeaders() });
        const tickets = (data.tickets || [])
            .map((item) => item.ticket || item)
            .sort((left, right) => {
                const a = parseServerDate(right.updated_at || right.created_at);
                const b = parseServerDate(left.updated_at || left.created_at);
                return (a ? a.getTime() : 0) - (b ? b.getTime() : 0);
            });
        const visibleTickets = tickets.filter((ticket) => !shouldHideClosedTicket(ticket));
        state.hiddenClosedCount = Math.max(0, tickets.length - visibleTickets.length);
        state.tickets = visibleTickets;
        if (state.selectedTicketId && !visibleTickets.some((ticket) => ticket.ticket_id === state.selectedTicketId)) {
            state.selectedTicketId = '';
            state.selectedSnapshot = null;
            state.selectedLifecycle = null;
        }
        renderTicketList();
        if (!state.selectedTicketId) {
            const preferred = visibleTickets.find((ticket) => ticket.ticket_id === sessionStorage.getItem(LAST_TICKET_KEY))
                || filteredTickets()[0]
                || visibleTickets[0]
                || null;
            if (preferred) {
                await selectTicket(preferred.ticket_id);
            } else {
                renderStage();
                renderContextPanel();
                renderToolPanels();
            }
        } else if (!opts.skipSelectionRefresh) {
            renderStage();
        }
        setSyncState('Обновлено ' + new Date().toLocaleTimeString('ru-RU'));
    }

    async function selectTicket(ticketId) {
        if (!ticketId) {
            return;
        }
        state.selectedTicketId = ticketId;
        sessionStorage.setItem(LAST_TICKET_KEY, ticketId);
        state.selectedSnapshot = null;
        state.selectedLifecycle = null;
        state.tools = [];
        state.toolsDeviceId = '';
        state.selectedToolKey = '';
        state.detailLoading = true;
        renderTicketList();
        renderStage();
        renderContextPanel();
        renderToolPanels();
        try {
            await refreshSelectedDetails(false);
        } finally {
            state.detailLoading = false;
        }
    }

    async function refreshSelectedDetails(silent) {
        const ticket = selectedTicket();
        if (!ticket) {
            state.selectedSnapshot = null;
            state.selectedLifecycle = null;
            renderStage();
            renderContextPanel();
            renderToolPanels();
            return;
        }
        if (!silent) {
            setSyncState('Загружаем контекст тикета…');
        }
        const snapshotPromise = fetchJson('/api/tickets/' + encodeURIComponent(ticket.ticket_id) + '/snapshot', { headers: authHeaders() });
        const lifecyclePromise = shouldObserveTicket(ticket)
            ? fetchJson('/api/admin/tech/tickets/' + encodeURIComponent(ticket.ticket_id) + '/lifecycle', { headers: authHeaders() })
            : Promise.resolve(null);
        const results = await Promise.all([snapshotPromise, lifecyclePromise]);
        if (ticket.ticket_id !== state.selectedTicketId) {
            return;
        }
        state.selectedSnapshot = results[0];
        state.selectedLifecycle = results[1];
        renderStage();
        renderContextPanel();
        renderToolPanels();
        setSyncState('Контекст обновлён');
    }

    async function takeTicketSelf(ticketId) {
        if (!ticketId || !state.userLogin) {
            return;
        }
        try {
            await fetchJson('/api/tickets/' + encodeURIComponent(ticketId) + '/assign', {
                method: 'POST',
                headers: authHeaders(true),
                body: JSON.stringify({ assignee_id: state.userLogin, take_self: true }),
            });
            showToast('Тикет назначен на вас');
            await loadTickets({ preserveSelection: true });
            if (state.selectedTicketId === ticketId) {
                await refreshSelectedDetails(true);
            }
        } catch (error) {
            showToast(error.message || 'Не удалось взять тикет', true);
        }
    }

    async function applyTicketStatus(nextStatus) {
        const ticket = selectedTicket();
        if (!ticket) {
            return;
        }
        const extraPayload = await collectResolutionPayload(nextStatus);
        await fetchJson('/api/tickets/' + encodeURIComponent(ticket.ticket_id) + '/status', {
            method: 'POST',
            headers: authHeaders(true),
            body: JSON.stringify({ to_status: nextStatus, ...extraPayload }),
        });
        showToast('Статус обновлён');
        await loadTickets({ preserveSelection: true });
        await refreshSelectedDetails(true);
    }

    async function handleQuickAction(actionId) {
        const ticket = selectedTicket();
        if (!ticket) {
            return;
        }
        try {
            if (actionId === 'refresh') {
                await loadTickets({ preserveSelection: true, skipSelectionRefresh: true });
                await refreshSelectedDetails(false);
                return;
            }
            if (actionId === 'open_tools') {
                if (state.drawerMode === PANEL_MODES.COLLAPSED) {
                    setDrawerMode(PANEL_MODES.HALF);
                }
                state.drawerTab = 'tools';
                renderToolPanels();
                return;
            }
            if (actionId === 'take_self') {
                await takeTicketSelf(ticket.ticket_id);
                return;
            }
            if (actionId === 'reroute_queue') {
                await fetchJson('/api/tickets/' + encodeURIComponent(ticket.ticket_id) + '/reroute', {
                    method: 'POST',
                    headers: authHeaders(true),
                    body: JSON.stringify({}),
                });
                showToast('Очередь пересчитана по правилам');
                await loadTickets({ preserveSelection: true });
                await refreshSelectedDetails(true);
                return;
            }
            if (actionId === 'to_in_progress') {
                await applyTicketStatus('in_progress');
                return;
            }
            if (actionId === 'to_waiting_user') {
                await applyTicketStatus('waiting_on_user');
                return;
            }
            if (actionId === 'to_resolved') {
                await applyTicketStatus('resolved');
            }
        } catch (error) {
            if (error && error.message === 'Операция отменена') {
                return;
            }
            showToast(error.message || 'Не удалось выполнить действие', true);
        }
    }

    async function handleComposerSubmit(event) {
        event.preventDefault();
        const ticket = selectedTicket();
        if (!ticket || !shouldWorkTicket(ticket)) {
            showToast('Открыт нерабочий режим тикета. Сначала возьмите тикет на себя.', true);
            return;
        }
        const input = byId('messageInput');
        if (!input) {
            return;
        }
        const text = String(input.value || '').trim();
        if (!text) {
            showToast('Введите сообщение', true);
            return;
        }
        const internal = Boolean(byId('internalToggle')?.checked);
        byId('sendMessageBtn').disabled = true;
        try {
            await fetchJson('/api/tickets/' + encodeURIComponent(ticket.ticket_id) + '/message', {
                method: 'POST',
                headers: authHeaders(true),
                body: JSON.stringify({ text, visibility: internal ? 'internal' : 'public' }),
            });
            input.value = '';
            showToast('Сообщение отправлено');
            await refreshSelectedDetails(true);
            await loadTickets({ preserveSelection: true, skipSelectionRefresh: true });
        } catch (error) {
            showToast(error.message || 'Не удалось отправить сообщение', true);
        } finally {
            byId('sendMessageBtn').disabled = false;
        }
    }

    function renderContextPanel() {
        const panel = byId('contextPanel');
        if (!panel) {
            return;
        }
        const ticket = selectedTicket();
        const snapshot = state.selectedSnapshot;
        if (!ticket) {
            panel.innerHTML = '<div class="support-card drawer-card">Выберите тикет, чтобы увидеть контекст.</div>';
            return;
        }
        const requester = snapshot?.requester_profile || {};
        const queueMembers = Array.isArray(snapshot?.queue_members) ? snapshot.queue_members : [];
        const deviceMetadata = snapshot?.device_metadata || {};
        const ola = snapshot?.ola || null;
        const queueMemberText = queueMembers.length
            ? queueMembers.map((member) => member.role_in_queue ? `${member.actor_id} (${member.role_in_queue})` : member.actor_id).join(', ')
            : 'У очереди пока нет участников';
        const routeFactorItems = [
            ['Заголовок', ticket.title || '—'],
            ['Описание', ticket.description || '—'],
            ['Отображаемое имя', snapshot?.requester_display_name || ticket.requester_display_name || '—'],
            ['ФИО', requester.full_name || '—'],
            ['Корпус', requester.building || '—'],
            ['Кабинет', requester.room || '—'],
            ['Телефон', requester.phone || '—'],
            ['Приоритет', ticket.priority_class ? priorityLabel(ticket.priority_class) : '—'],
            ['Срочность', boolLabel(Boolean(ticket.urgency))],
            ['Важность', boolLabel(Boolean(ticket.importance))],
            ['Публичный тикет', boolLabel(Boolean(snapshot?.is_public_ticket))],
            ['Без привязанного агента', boolLabel(Boolean(snapshot?.public_ticket_unbound))],
            ['Локация устройства', deviceMetadata.location || '—'],
            ['Тип устройства', deviceMetadata.device_type || '—'],
        ];
        const contextRows = [
            ['Код', ticket.ticket_code || ticket.ticket_id],
            ['Режим', currentMode() === 'work' ? 'Работа' : (currentMode() === 'observe' ? 'Наблюдение' : 'Предпросмотр')],
            ['Статус', statusLabel(ticket.status)],
            ['Исполнитель', ticket.assignee_id || 'Не назначен'],
            ['Очередь', snapshot?.queue_code || ticket.queue_code || ticket.queue_id || '—'],
            ['Состав очереди', queueMemberText],
            ['Инициатор', snapshot?.requester_display_name || ticket.requester_display_name || ticket.requester_id || '—'],
            ['Устройство', snapshot?.device_id || ticket.device_id || 'Не привязано'],
            ['Телефон', requester.phone || '—'],
            ['Корпус / кабинет', [requester.building, requester.room].filter(Boolean).join(' / ') || '—'],
            ['SLA FR', snapshot?.first_response_due_at ? formatDate(snapshot.first_response_due_at) : '—'],
            ['SLA Resolution', snapshot?.resolution_due_at ? formatDate(snapshot.resolution_due_at) : '—'],
        ];
        const queuePolicyRows = [
            ['Автоназначение очереди', snapshot?.queue_auto_assign_enabled === false ? 'Выключено' : 'Включено'],
            ['Если правил нет', 'Тикет уходит в базовую очередь ServiceDesk L1'],
            ['Что происходит при смене очереди', 'Исполнитель должен входить в состав новой очереди. Иначе назначение снимается, а дальше срабатывает автоназначение очереди или тикет возвращается в очередь без исполнителя.'],
        ];
        const slaFacts = [
            ['SLA', 'Внешнее обещание пользователю: когда мы должны ответить и когда должны решить тикет.'],
            ['Календарь', 'Определяет, в какие дни и часы считаются SLA и OLA. Обычно это рабочие часы, выходные и праздники.'],
            ['OLA', 'Внутренний норматив очереди: за сколько очередь должна взять тикет и начать обработку.'],
            ['SLA первого ответа', snapshot?.first_response_due_at ? `Срок до ${formatDate(snapshot.first_response_due_at)}` : 'Для этого тикета срок не рассчитан'],
            ['SLA решения', snapshot?.resolution_due_at ? `Срок до ${formatDate(snapshot.resolution_due_at)}` : 'Для этого тикета срок не рассчитан'],
            ['OLA принятия', ola?.ola_ack_due_at ? `Очередь должна взять тикет до ${formatDate(ola.ola_ack_due_at)}` : 'Для этой очереди OLA принятия не задан'],
            ['OLA обработки', ola?.ola_processing_due_at ? `Очередь должна продвинуть тикет до ${formatDate(ola.ola_processing_due_at)}` : 'Для этой очереди OLA обработки не задан'],
        ];
        panel.innerHTML = `
            <article class="support-card drawer-card">
                <div class="card-head">
                    <h3>Текущий контекст</h3>
                </div>
                <dl class="key-value-list">
                    ${contextRows.map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd>`).join('')}
                </dl>
            </article>
            <article class="support-card drawer-card">
                <div class="card-head">
                    <h3>Очередь и назначение</h3>
                </div>
                <dl class="key-value-list">
                    ${queuePolicyRows.map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd>`).join('')}
                </dl>
            </article>
            <article class="support-card drawer-card">
                <div class="card-head">
                    <h3>Что влияет на маршрут</h3>
                </div>
                <p class="drawer-note">Маршрутизация может смотреть на текст заявки, данные инициатора, приоритет, признак публичного тикета и метаданные устройства.</p>
                <div class="support-facts-list">
                    ${routeFactorItems.map(([label, value]) => `
                        <div class="support-fact">
                            <span class="support-fact-label">${escapeHtml(label)}</span>
                            <div class="support-fact-value">${escapeHtml(value)}</div>
                        </div>
                    `).join('')}
                </div>
            </article>
            <article class="support-card drawer-card">
                <div class="card-head">
                    <h3>SLA, календарь и OLA</h3>
                </div>
                <div class="support-facts-list">
                    ${slaFacts.map(([label, value]) => `
                        <div class="support-fact">
                            <span class="support-fact-label">${escapeHtml(label)}</span>
                            <div class="support-fact-value">${escapeHtml(value)}</div>
                        </div>
                    `).join('')}
                </div>
            </article>
        `;
    }

    function scenarioForTool(tool) {
        const source = String(tool.module || tool.name || '').toLowerCase();
        if (tool.needsInstall) {
            return 'С установкой';
        }
        for (const [scenarioName, markers] of Object.entries(TOOL_SCENARIOS)) {
            if (scenarioName === 'С установкой' || scenarioName === 'Прочее') {
                continue;
            }
            if (markers.some((marker) => source.includes(marker))) {
                return scenarioName;
            }
        }
        return 'Прочее';
    }

    function normalizeTool(rawTool, needsInstall) {
        const name = rawTool.tool || rawTool.name || 'unknown.tool';
        const module = rawTool.module || name.split('.')[0] || 'module';
        const paramsSchema = rawTool?.spec?.params_schema || rawTool?.params_schema || [];
        const presets = rawTool?.spec?.presets || rawTool?.presets || [];
        return {
            key: name + ':' + (needsInstall ? 'server' : 'device'),
            name,
            module,
            description: rawTool.description || rawTool?.spec?.description || '',
            paramsSchema,
            presets: Array.isArray(presets) ? presets : [],
            riskLevel: rawTool?.spec?.risk_level || rawTool?.metadata?.risk_level || 'safe_read',
            requiresConsent: Boolean(rawTool?.metadata?.requires_consent),
            needsInstall: Boolean(needsInstall),
            scenario: '',
            raw: rawTool,
        };
    }

    async function ensureToolsLoaded() {
        const ticket = selectedTicket();
        const deviceId = ticket?.device_id || state.selectedSnapshot?.device_id || '';
        if (!deviceId) {
            state.tools = [];
            state.toolsDeviceId = '';
            state.selectedToolKey = '';
            return;
        }
        if (state.toolsDeviceId === deviceId && state.tools.length) {
            return;
        }
        const data = await fetchJson('/api/tools?device_id=' + encodeURIComponent(deviceId), { headers: authHeaders() });
        const deviceTools = (data.tools || []).map((tool) => normalizeTool(tool, false));
        const installedNames = new Set(deviceTools.map((tool) => tool.name));
        const serverTools = (data.tools_from_server || [])
            .filter((tool) => !installedNames.has(tool.tool || tool.name))
            .map((tool) => normalizeTool(tool, true));
        state.tools = deviceTools.concat(serverTools).map((tool) => ({ ...tool, scenario: scenarioForTool(tool) }));
        state.toolsDeviceId = deviceId;
        if (!state.tools.some((tool) => tool.key === state.selectedToolKey)) {
            state.selectedToolKey = state.tools[0]?.key || '';
        }
    }

    function toolMatchesSearch(tool) {
        if (!state.toolSearch) {
            return true;
        }
        const needle = state.toolSearch.toLowerCase();
        const haystack = [tool.name, tool.module, tool.description, tool.scenario].join(' ').toLowerCase();
        return haystack.includes(needle);
    }

    function filteredTools() {
        return state.tools.filter((tool) => {
            const matchesScenario = state.activeToolScenario === 'all' || tool.scenario === state.activeToolScenario;
            return matchesScenario && toolMatchesSearch(tool);
        });
    }

    function selectedTool() {
        return state.tools.find((tool) => tool.key === state.selectedToolKey) || null;
    }

    function normalizeSchema(raw) {
        if (!raw) {
            return [];
        }
        if (Array.isArray(raw)) {
            return raw.map((item) => ({ ...item }));
        }
        if (typeof raw === 'object' && raw.properties) {
            const requiredSet = new Set(Array.isArray(raw.required) ? raw.required : []);
            return Object.entries(raw.properties).map(([name, descriptor]) => ({
                name,
                required: requiredSet.has(name),
                ...descriptor,
            }));
        }
        if (typeof raw === 'object') {
            return Object.entries(raw).map(([name, descriptor]) => ({
                name,
                ...(typeof descriptor === 'object' ? descriptor : { default: descriptor }),
            }));
        }
        return [];
    }

    function fieldIdForTool(tool, fieldName) {
        return 'tool_' + String(tool?.key || 'tool').replace(/\W/g, '_') + '_' + String(fieldName || '').replace(/\W/g, '_');
    }

    function renderToolScenarioChips() {
        const node = byId('toolScenarioChips');
        if (!node) {
            return;
        }
        const scenarioNames = ['all'].concat(
            Array.from(new Set(state.tools.map((tool) => tool.scenario))).sort((left, right) => left.localeCompare(right, 'ru'))
        );
        node.innerHTML = scenarioNames.map((name) => {
            const label = name === 'all' ? 'Все' : name;
            const count = name === 'all' ? state.tools.length : state.tools.filter((tool) => tool.scenario === name).length;
            return `<button type="button" class="filter-chip ${state.activeToolScenario === name ? 'active' : ''}" data-tool-scenario="${escapeHtml(name)}">${escapeHtml(label)} (${count})</button>`;
        }).join('');
        node.querySelectorAll('[data-tool-scenario]').forEach((button) => {
            button.addEventListener('click', () => {
                state.activeToolScenario = button.getAttribute('data-tool-scenario') || 'all';
                renderToolPanels();
            });
        });
    }

    function renderToolList() {
        const node = byId('toolList');
        if (!node) {
            return;
        }
        const ticket = selectedTicket();
        if (!ticket || !(ticket.device_id || state.selectedSnapshot?.device_id)) {
            node.innerHTML = '<div class="activity-item">Для работы с инструментами тикет должен быть привязан к агенту.</div>';
            return;
        }
        const tools = filteredTools();
        if (!tools.length) {
            node.innerHTML = '<div class="activity-item">По текущему фильтру инструменты не найдены.</div>';
            return;
        }
        node.innerHTML = tools.map((tool) => `
            <article class="tool-card ${tool.key === state.selectedToolKey ? 'active' : ''}" data-tool-key="${escapeHtml(tool.key)}">
                <div class="card-head">
                    <h4>${escapeHtml(tool.name)}</h4>
                    <span class="chip">${escapeHtml(tool.scenario)}</span>
                </div>
                <div class="tool-card-meta">${escapeHtml(tool.module)} • ${escapeHtml(tool.needsInstall ? 'с установкой' : 'доступен')}</div>
                <div>${escapeHtml(tool.description || 'Без описания')}</div>
                <div class="timeline-tags">
                    <span class="chip">${escapeHtml(tool.riskLevel)}</span>
                    ${tool.requiresConsent ? '<span class="chip">consent</span>' : ''}
                </div>
            </article>
        `).join('');
        node.querySelectorAll('[data-tool-key]').forEach((card) => {
            card.addEventListener('click', () => {
                state.selectedToolKey = card.getAttribute('data-tool-key') || '';
                renderToolPanels();
            });
        });
    }

    function renderToolInspector() {
        const node = byId('toolInspector');
        if (!node) {
            return;
        }
        const tool = selectedTool();
        if (!tool) {
            node.innerHTML = '<div class="tool-inspector-empty">Выберите инструмент из списка.</div>';
            return;
        }
        const schema = normalizeSchema(tool.paramsSchema);
        const presets = Array.isArray(tool.presets) ? tool.presets : [];
        const presetOptions = presets.length
            ? `
                <div class="tool-field">
                    <label for="toolPresetSelect">Пресет</label>
                    <select id="toolPresetSelect">
                        <option value="">Без пресета</option>
                        ${presets.map((preset) => {
                            const presetId = preset.preset_id || preset.id || preset.key || '';
                            const label = preset.title || preset.name || presetId;
                            return `<option value="${escapeHtml(presetId)}">${escapeHtml(label)}</option>`;
                        }).join('')}
                    </select>
                </div>
            `
            : '';
        const fields = schema.map((field) => {
            const fieldId = fieldIdForTool(tool, field.name);
            const fieldType = String(field.type || '').toLowerCase();
            const label = escapeHtml(field.title || field.label || field.name || 'param');
            const description = field.description ? '<div class="tool-card-meta">' + escapeHtml(field.description) + '</div>' : '';
            const defaultValue = field.default != null ? field.default : '';
            if (fieldType === 'boolean') {
                return `
                    <div class="tool-field">
                        <label for="${fieldId}">${label}</label>
                        <select id="${fieldId}" data-field-name="${escapeHtml(field.name)}" data-field-type="boolean">
                            <option value="true"${defaultValue === true ? ' selected' : ''}>Да</option>
                            <option value="false"${defaultValue === false || defaultValue === '' ? ' selected' : ''}>Нет</option>
                        </select>
                        ${description}
                    </div>
                `;
            }
            if (fieldType === 'object' || fieldType === 'array') {
                return `
                    <div class="tool-field">
                        <label for="${fieldId}">${label}</label>
                        <textarea id="${fieldId}" rows="4" data-field-name="${escapeHtml(field.name)}" data-field-type="${escapeHtml(fieldType)}">${escapeHtml(defaultValue ? JSON.stringify(defaultValue, null, 2) : '')}</textarea>
                        ${description}
                    </div>
                `;
            }
            const inputType = fieldType === 'integer' || fieldType === 'number' ? 'number' : 'text';
            return `
                <div class="tool-field">
                    <label for="${fieldId}">${label}${field.required ? ' *' : ''}</label>
                    <input id="${fieldId}" type="${inputType}" value="${escapeHtml(defaultValue)}" data-field-name="${escapeHtml(field.name)}" data-field-type="${escapeHtml(fieldType || 'string')}">
                    ${description}
                </div>
            `;
        }).join('');
        node.innerHTML = `
            <div class="card-head">
                <div>
                    <h3>${escapeHtml(tool.name)}</h3>
                    <div class="tool-inspector-meta">${escapeHtml(tool.module)} • ${escapeHtml(tool.scenario)} • ${escapeHtml(tool.riskLevel)}</div>
                </div>
                ${tool.needsInstall ? '<span class="chip">модуль установится при запуске</span>' : ''}
            </div>
            <div>${escapeHtml(tool.description || 'Описание не заполнено.')}</div>
            <div class="tool-inspector-form">
                ${presetOptions}
                ${fields || '<div class="tool-card-meta">Для этого инструмента параметры не требуются.</div>'}
            </div>
            <div class="tool-actions">
                <button id="runSelectedToolBtn" class="btn btn-primary" type="button">Запустить</button>
                <button id="addToolToPipelineBtn" class="btn btn-secondary" type="button">В пайплайн</button>
            </div>
        `;
        byId('runSelectedToolBtn')?.addEventListener('click', async () => {
            await runSelectedTool();
        });
        byId('addToolToPipelineBtn')?.addEventListener('click', () => {
            addSelectedToolToPipeline();
        });
    }

    function collectToolPayload(tool) {
        const payload = { params: {} };
        const presetValue = String(byId('toolPresetSelect')?.value || '').trim();
        if (presetValue) {
            payload.preset_id = presetValue;
            return payload;
        }
        const schema = normalizeSchema(tool.paramsSchema);
        schema.forEach((field) => {
            const node = byId(fieldIdForTool(tool, field.name));
            if (!node) {
                return;
            }
            const raw = 'value' in node ? node.value : '';
            if (raw === '' || raw == null) {
                return;
            }
            const fieldType = String(field.type || '').toLowerCase();
            try {
                if (fieldType === 'boolean') {
                    payload.params[field.name] = raw === 'true';
                } else if (fieldType === 'integer') {
                    payload.params[field.name] = parseInt(raw, 10);
                } else if (fieldType === 'number') {
                    payload.params[field.name] = parseFloat(raw);
                } else if (fieldType === 'object' || fieldType === 'array') {
                    payload.params[field.name] = JSON.parse(raw);
                } else {
                    payload.params[field.name] = raw;
                }
            } catch (error) {
                throw new Error('Параметр "' + field.name + '" имеет невалидный JSON.');
            }
        });
        return payload;
    }

    async function runSelectedTool() {
        const ticket = selectedTicket();
        const tool = selectedTool();
        if (!ticket || !tool) {
            return;
        }
        if (!ticket.device_id && !state.selectedSnapshot?.device_id) {
            showToast('Для запуска инструмента нужен привязанный агент.', true);
            return;
        }
        try {
            const payload = collectToolPayload(tool);
            await fetchJson('/api/tools/run', {
                method: 'POST',
                headers: authHeaders(true),
                body: JSON.stringify({
                    device_id: ticket.device_id || state.selectedSnapshot?.device_id,
                    ticket_id: ticket.ticket_id,
                    tool_name: tool.name,
                    preset_id: payload.preset_id,
                    params: payload.preset_id ? undefined : payload.params,
                }),
            });
            showToast('Инструмент поставлен в очередь: ' + tool.name);
            await refreshSelectedDetails(true);
        } catch (error) {
            showToast(error.message || 'Не удалось запустить инструмент', true);
        }
    }

    function addSelectedToolToPipeline() {
        const tool = selectedTool();
        if (!tool) {
            return;
        }
        try {
            const payload = collectToolPayload(tool);
            state.pipeline.push({
                id: 'step_' + Date.now() + '_' + Math.random().toString(36).slice(2, 7),
                tool_name: tool.name,
                scenario: tool.scenario,
                preset_id: payload.preset_id || '',
                params: payload.preset_id ? {} : (payload.params || {}),
            });
            renderPipelinePanel();
            showToast('Шаг добавлен в черновик пайплайна');
        } catch (error) {
            showToast(error.message || 'Не удалось добавить шаг', true);
        }
    }

    function buildPipelineText() {
        if (!state.pipeline.length) {
            return '';
        }
        const lines = ['План действий по тикету:', ''];
        state.pipeline.forEach((step, index) => {
            const suffix = step.preset_id ? ' preset=' + step.preset_id : '';
            lines.push((index + 1) + '. ' + step.tool_name + suffix);
            if (step.params && Object.keys(step.params).length) {
                lines.push('   params: ' + JSON.stringify(step.params, null, 2).replace(/\n/g, ' '));
            }
        });
        return lines.join('\n');
    }

    function renderPipelinePanel() {
        const node = byId('pipelineList');
        if (!node) {
            return;
        }
        if (!state.pipeline.length) {
            node.innerHTML = '<div class="activity-item">Черновик пуст. Добавляйте шаги из вкладки «Инструменты».</div>';
            return;
        }
        node.innerHTML = state.pipeline.map((step, index) => `
            <article class="pipeline-item" data-pipeline-id="${escapeHtml(step.id)}">
                <div class="pipeline-item-head">
                    <div>
                        <div class="pipeline-item-index">Шаг ${index + 1}</div>
                        <strong>${escapeHtml(step.tool_name)}</strong>
                        <div class="tool-card-meta">${escapeHtml(step.scenario)}${step.preset_id ? ' • preset=' + escapeHtml(step.preset_id) : ''}</div>
                    </div>
                    <div class="pipeline-item-actions">
                        <button type="button" class="pipeline-mini-btn" data-pipeline-action="up">↑</button>
                        <button type="button" class="pipeline-mini-btn" data-pipeline-action="down">↓</button>
                        <button type="button" class="pipeline-mini-btn" data-pipeline-action="remove">Удалить</button>
                    </div>
                </div>
                <div class="timeline-body">${escapeHtml(Object.keys(step.params || {}).length ? JSON.stringify(step.params, null, 2) : 'Без параметров')}</div>
            </article>
        `).join('');
        node.querySelectorAll('[data-pipeline-action]').forEach((button) => {
            button.addEventListener('click', () => {
                const container = button.closest('[data-pipeline-id]');
                const stepId = container?.getAttribute('data-pipeline-id') || '';
                const idx = state.pipeline.findIndex((item) => item.id === stepId);
                if (idx === -1) {
                    return;
                }
                const action = button.getAttribute('data-pipeline-action');
                if (action === 'remove') {
                    state.pipeline.splice(idx, 1);
                } else if (action === 'up' && idx > 0) {
                    const temp = state.pipeline[idx - 1];
                    state.pipeline[idx - 1] = state.pipeline[idx];
                    state.pipeline[idx] = temp;
                } else if (action === 'down' && idx < state.pipeline.length - 1) {
                    const temp = state.pipeline[idx + 1];
                    state.pipeline[idx + 1] = state.pipeline[idx];
                    state.pipeline[idx] = temp;
                }
                renderPipelinePanel();
            });
        });
    }

    function insertPipelineIntoEditor() {
        const ticket = selectedTicket();
        if (!ticket || !shouldWorkTicket(ticket)) {
            showToast('Пайплайн можно вставить только в рабочий чат своего тикета.', true);
            return;
        }
        const text = buildPipelineText();
        if (!text) {
            showToast('Черновик пайплайна пуст.', true);
            return;
        }
        const frame = byId('embeddedTicketFrame');
        const api = frame && frame.contentWindow ? frame.contentWindow.ticketEmbedApi : null;
        if (!api || typeof api.insertText !== 'function') {
            showToast('Чат тикета ещё загружается. Попробуйте через секунду.', true);
            return;
        }
        api.insertText(text);
        state.drawerTab = 'pipeline';
        renderToolPanels();
    }

    async function sendPipelineToChat() {
        const ticket = selectedTicket();
        if (!ticket || !shouldWorkTicket(ticket)) {
            showToast('Отправка пайплайна доступна только в рабочем режиме своего тикета.', true);
            return;
        }
        const text = buildPipelineText();
        if (!text) {
            showToast('Черновик пайплайна пуст.', true);
            return;
        }
        try {
            await fetchJson('/api/tickets/' + encodeURIComponent(ticket.ticket_id) + '/message', {
                method: 'POST',
                headers: authHeaders(true),
                body: JSON.stringify({ text, visibility: 'internal' }),
            });
            showToast('Пайплайн отправлен в чат как внутренняя заметка');
            await refreshSelectedDetails(true);
        } catch (error) {
            showToast(error.message || 'Не удалось отправить пайплайн', true);
        }
    }

    async function renderToolPanels() {
        const toolsPanel = byId('drawerTab-tools');
        const pipelinePanel = byId('drawerTab-pipeline');
        const contextPanel = byId('drawerTab-context');
        if (!toolsPanel || !pipelinePanel || !contextPanel) {
            return;
        }
        contextPanel.classList.toggle('hidden', state.drawerTab !== 'context');
        toolsPanel.classList.toggle('hidden', state.drawerTab !== 'tools');
        pipelinePanel.classList.toggle('hidden', state.drawerTab !== 'pipeline');
        document.querySelectorAll('.drawer-tab').forEach((tab) => {
            tab.classList.toggle('active', tab.getAttribute('data-tab') === state.drawerTab);
        });
        if (state.drawerTab === 'tools' || state.drawerTab === 'pipeline') {
            try {
                await ensureToolsLoaded();
            } catch (error) {
                console.warn('ensureToolsLoaded', error);
                showToast(error.message || 'Не удалось загрузить инструменты', true);
            }
        }
        renderToolScenarioChips();
        renderToolList();
        renderToolInspector();
        renderPipelinePanel();
    }

    async function initializeWorkspace() {
        syncSessionFromStorage();
        if (!getToken()) {
            showLoginScreen();
            return;
        }
        const session = await fetchCurrentSession();
        if (!session) {
            showLoginScreen();
            return;
        }
        if (!canAccessWorkspace(session.actor_role)) {
            clearStoredSession();
            redirectToLogin('Для support workspace нужна роль support.');
            return;
        }
        localStorage.setItem(USER_LOGIN_KEY, session.user_login || '');
        localStorage.setItem(ROLE_KEY, session.actor_role || '');
        syncSessionFromStorage();
        showWorkspace();
        updateAuthBadge();
        updateSwitchRoleLink();
        applyLayoutClasses();
        renderTicketList();
        renderStage();
        renderContextPanel();
        await renderToolPanels();
        await loadTickets({ preserveSelection: false });
        startPolling();
    }

    function bindEvents() {
        byId('logoutBtn')?.addEventListener('click', logout);
        byId('refreshWorkspaceBtn')?.addEventListener('click', async () => {
            try {
                await loadTickets({ preserveSelection: true, skipSelectionRefresh: true });
                await refreshSelectedDetails(false);
            } catch (error) {
                showToast(error.message || 'Не удалось обновить workspace', true);
            }
        });
        byId('ticketSearchInput')?.addEventListener('input', () => {
            state.ticketQuery = String(byId('ticketSearchInput')?.value || '').trim();
            renderTicketList();
        });
        document.querySelectorAll('#ticketFilterChips .filter-chip').forEach((button) => {
            button.addEventListener('click', () => {
                state.currentFilter = button.getAttribute('data-filter') || 'all';
                renderTicketList();
            });
        });
        byId('sidebarToggleBtn')?.addEventListener('click', () => {
            setSidebarMode(state.sidebarMode === PANEL_MODES.COLLAPSED ? PANEL_MODES.HALF : PANEL_MODES.COLLAPSED);
        });
        byId('collapseInboxBtn')?.addEventListener('click', () => {
            setSidebarMode(state.sidebarMode === PANEL_MODES.FULL ? PANEL_MODES.HALF : PANEL_MODES.FULL);
        });
        byId('drawerToggleBtn')?.addEventListener('click', () => {
            setDrawerMode(state.drawerMode === PANEL_MODES.COLLAPSED ? PANEL_MODES.HALF : PANEL_MODES.COLLAPSED);
        });
        byId('drawerResizeBtn')?.addEventListener('click', () => {
            setDrawerMode(state.drawerMode === PANEL_MODES.FULL ? PANEL_MODES.HALF : PANEL_MODES.FULL);
        });
        document.querySelectorAll('.drawer-tab').forEach((button) => {
            button.addEventListener('click', async () => {
                state.drawerTab = button.getAttribute('data-tab') || 'context';
                await renderToolPanels();
            });
        });
        byId('toolSearchInput')?.addEventListener('input', async () => {
            state.toolSearch = String(byId('toolSearchInput')?.value || '').trim();
            await renderToolPanels();
        });
        byId('pipelineInsertBtn')?.addEventListener('click', insertPipelineIntoEditor);
        byId('pipelineSendBtn')?.addEventListener('click', async () => {
            await sendPipelineToChat();
        });
        byId('pipelineClearBtn')?.addEventListener('click', () => {
            state.pipeline = [];
            renderPipelinePanel();
        });
        byId('embeddedTicketFrame')?.addEventListener('load', () => {
            const frame = byId('embeddedTicketFrame');
            if (frame) {
                frame.dataset.loadedTicketId = frame.dataset.ticketId || '';
            }
            setEmbeddedTicketLoading(false, '');
        });
        byId('resolutionDialogClose')?.addEventListener('click', () => {
            closeResolutionDialog(new Error('Операция отменена'));
        });
        byId('resolutionDialogCancel')?.addEventListener('click', () => {
            closeResolutionDialog(new Error('Операция отменена'));
        });
        byId('resolutionDialog')?.addEventListener('click', (event) => {
            if (event.target instanceof HTMLElement && event.target.getAttribute('data-dialog-close') === '1') {
                closeResolutionDialog(new Error('Операция отменена'));
            }
        });
        byId('resolutionDialogApply')?.addEventListener('click', () => {
            const resolve = resolutionDialogResolve;
            const reject = resolutionDialogReject;
            const codeValue = String(byId('resolutionDialogCode')?.value || '').trim();
            const rootCause = String(byId('resolutionDialogRootCause')?.value || '').trim();
            const errorNode = byId('resolutionDialogError');
            if (!resolve || !reject || !errorNode) {
                return;
            }
            if (!codeValue) {
                errorNode.textContent = 'Выберите код решения';
                errorNode.classList.remove('hidden');
                return;
            }
            resolutionDialogResolve = null;
            resolutionDialogReject = null;
            byId('resolutionDialog')?.classList.add('hidden');
            byId('resolutionDialog')?.setAttribute('aria-hidden', 'true');
            errorNode.textContent = '';
            errorNode.classList.add('hidden');
            resolve({
                resolution_code: codeValue,
                root_cause: rootCause,
            });
        });
        window.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && resolutionDialogReject) {
                closeResolutionDialog(new Error('Операция отменена'));
            }
        });
        window.addEventListener('resize', applyLayoutClasses);
    }

    async function init() {
        bindEvents();
        syncSessionFromStorage();
        if (getToken()) {
            await initializeWorkspace();
            return;
        }
        showLoginScreen();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            init().catch((error) => {
                console.error('support init', error);
                showToast(error.message || 'Не удалось инициализировать support workspace', true);
            });
        });
    } else {
        init().catch((error) => {
            console.error('support init', error);
            showToast(error.message || 'Не удалось инициализировать support workspace', true);
        });
    }
})();
