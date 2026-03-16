/**
 * Public queue page (link-based mode):
 * - /queue/common
 * - /queue/test
 * - /queue?queue=<alias|queue_code> (fallback)
 */
(function () {
    const POLL_INTERVAL_MS = 15000;
    const DEFAULT_QUEUE_ALIAS = 'common';
    const PUBLIC_QUEUE_ALIAS_TO_CODES = {
        common: ['servicedesk_l1', 'common'],
        test: ['servicedesk_test', 'test'],
    };

    /** Canonical status -> Russian label (UI only). */
    const STATUS_LABELS = {
        new: 'Новая',
        triaged: 'В очереди у оператора',
        in_progress: 'В работе',
        waiting_on_user: 'Ожидает ответ пользователя',
        waiting_on_vendor: 'Ожидает внешнюю сторону',
        resolved: 'Решён',
        closed: 'Закрыт',
        // Backward compatibility with historical title-case values.
        New: 'Новая',
        Triaged: 'В очереди у оператора',
        'In Progress': 'В работе',
        'Waiting on User': 'Ожидает ответ пользователя',
        'Waiting on Vendor': 'Ожидает внешнюю сторону',
        Resolved: 'Решён',
        Closed: 'Закрыт',
    };
    /** Canonical priority -> Russian label (UI only). */
    const PRIORITY_LABELS = {
        P0: 'Критический',
        P1: 'Высокий',
        P2: 'Средний',
        P3: 'Низкий',
        P4: 'Низкий',
        P5: 'Плановый',
    };

    const QUEUE_NAME_ID = 'pqQueueName';
    const TICKET_CODE_ID = 'pqTicketCode';
    const SEARCH_BTN_ID = 'pqSearchBtn';
    const TBODY_ID = 'pqTbody';
    const LAST_UPDATE_ID = 'pqLastUpdate';
    const SYNC_STATUS_ID = 'pqSyncStatus';
    const KPI_IDS = {
        backlog: 'pqKpiBacklog',
        slaFr: 'pqKpiSlaFr',
        slaRes: 'pqKpiSlaRes',
        avgRes: 'pqKpiAvgRes',
        closedToday: 'pqKpiClosedToday',
    };

    let pollTimer = null;
    let lastEtags = { tickets: null, stats: null };
    const queueContext = { alias: DEFAULT_QUEUE_ALIAS, queueId: null, queueName: '—' };

    function el(id) {
        return document.getElementById(id);
    }

    function normalizeSlug(value) {
        return String(value || '')
            .trim()
            .toLowerCase()
            .replace(/\s+/g, '_')
            .replace(/-/g, '_');
    }

    function statusLabel(canonical) {
        if (!canonical) return '—';
        return STATUS_LABELS[canonical] || STATUS_LABELS[normalizeSlug(canonical)] || 'Неизвестно';
    }

    function priorityLabel(canonical) {
        if (!canonical) return '—';
        const label = PRIORITY_LABELS[canonical] || 'Неизвестно';
        return label + ' (' + canonical + ')';
    }

    function binaryFlagLabel(value, trueLabel, falseLabel) {
        if (value == null) return '—';
        const normalized = Number(value);
        if (Number.isNaN(normalized)) return '—';
        return normalized > 0 ? trueLabel : falseLabel;
    }

    function formatWait(seconds) {
        if (seconds == null) return '—';
        if (seconds < 60) return seconds + ' с';
        if (seconds < 3600) return Math.floor(seconds / 60) + ' мин';
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        return h + ' ч ' + m + ' мин';
    }

    function setSyncStatus(ok, fromCache) {
        const node = el(SYNC_STATUS_ID);
        if (!node) return;
        node.classList.remove('degraded', 'error');
        if (fromCache) node.classList.add('degraded');
        else if (!ok) node.classList.add('error');
    }

    function setLastUpdate() {
        const node = el(LAST_UPDATE_ID);
        if (node) node.textContent = 'Обновлено: ' + new Date().toLocaleTimeString('ru-RU');
    }

    function setQueueCaption(name) {
        const node = el(QUEUE_NAME_ID);
        if (!node) return;
        node.textContent = name || '—';
    }

    function detectQueueAliasFromUrl() {
        const path = window.location.pathname || '';
        if (path.startsWith('/queue/') && path.length > '/queue/'.length) {
            return normalizeSlug(decodeURIComponent(path.slice('/queue/'.length)));
        }
        const params = new URLSearchParams(window.location.search || '');
        return normalizeSlug(
            params.get('queue') ||
            params.get('queue_alias') ||
            DEFAULT_QUEUE_ALIAS
        ) || DEFAULT_QUEUE_ALIAS;
    }

    function resolveQueueByAlias(queues, alias) {
        const normalizedAlias = normalizeSlug(alias) || DEFAULT_QUEUE_ALIAS;
        const aliasCandidates = PUBLIC_QUEUE_ALIAS_TO_CODES[normalizedAlias] || [normalizedAlias];
        const candidates = new Set(aliasCandidates.map(normalizeSlug).filter(Boolean));
        if (!candidates.has(normalizedAlias)) candidates.add(normalizedAlias);

        return (queues || []).find(function (q) {
            const code = normalizeSlug(q.queue_code);
            const name = normalizeSlug(q.queue_name);
            return candidates.has(code) || candidates.has(name);
        }) || null;
    }

    async function fetchQueues(includeEmpty) {
        const url = '/public_api/queues' + (includeEmpty ? '?include_empty=true' : '');
        const r = await fetch(url);
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
    }

    async function fetchTickets(queueId, limit, offset, ticketCode) {
        const params = new URLSearchParams({
            queue_id: String(queueId),
            limit: String(limit || 100),
            offset: String(offset || 0),
        });
        if (ticketCode) params.set('ticket_code', ticketCode);
        const opts = { headers: lastEtags.tickets ? { 'If-None-Match': lastEtags.tickets } : {} };
        const r = await fetch('/public_api/queue/tickets?' + params.toString(), opts);
        if (r.status === 304) return null;
        if (!r.ok) throw new Error(r.statusText);
        const etag = r.headers.get('ETag');
        if (etag) lastEtags.tickets = etag;
        return r.json();
    }

    async function fetchStats(queueId, days) {
        const params = new URLSearchParams({ days: String(days || 7), queue_id: String(queueId) });
        const opts = { headers: lastEtags.stats ? { 'If-None-Match': lastEtags.stats } : {} };
        const r = await fetch('/public_api/queue/stats?' + params.toString(), opts);
        if (r.status === 304) return null;
        if (!r.ok) throw new Error(r.statusText);
        const etag = r.headers.get('ETag');
        if (etag) lastEtags.stats = etag;
        return r.json();
    }

    function renderKpi(data) {
        if (!data) return;
        const set = function (id, text) {
            const n = el(KPI_IDS[id]);
            if (n) n.textContent = text ?? '—';
        };
        set('backlog', data.backlog_open);
        set('slaFr', data.sla_fr_compliance_pct != null ? data.sla_fr_compliance_pct + '%' : '—');
        set('slaRes', data.sla_res_compliance_pct != null ? data.sla_res_compliance_pct + '%' : '—');
        set('avgRes', data.avg_resolution_minutes != null ? data.avg_resolution_minutes : '—');
        set('closedToday', data.closed_today);
    }

    function renderEmpty(message) {
        const tbody = el(TBODY_ID);
        if (!tbody) return;
        tbody.innerHTML = '<tr><td colspan="8" class="pq-empty">' + (message || 'Нет данных') + '</td></tr>';
    }

    function renderTable(tickets, highlightCode) {
        const tbody = el(TBODY_ID);
        if (!tbody) return;
        if (!tickets || tickets.length === 0) {
            renderEmpty('В очереди пока нет заявок');
            return;
        }
        const code = (highlightCode || '').trim().toUpperCase();
        tbody.innerHTML = tickets.map(function (t) {
            const isHighlight = code && (t.ticket_code || '').toUpperCase().indexOf(code) >= 0;
            const rowClass = isHighlight ? ' class="pq-highlight"' : '';
            const requester = t.requester_display_name || t.requester_id || '—';
            const urgency = binaryFlagLabel(t.urgency, 'Да', 'Нет');
            const importance = binaryFlagLabel(t.importance, 'Да', 'Нет');
            return '<tr' + rowClass + '>'
                + '<td>' + t.position + '</td>'
                + '<td><a href="/help?ticket_id=' + encodeURIComponent(t.ticket_id || '') + '">' + (t.ticket_code || '—') + '</a></td>'
                + '<td>' + requester + '</td>'
                + '<td>' + statusLabel(t.status) + '</td>'
                + '<td>' + priorityLabel(t.priority) + '</td>'
                + '<td>' + urgency + '</td>'
                + '<td>' + importance + '</td>'
                + '<td>' + formatWait(t.wait_seconds) + '</td>'
                + '</tr>';
        }).join('');
    }

    async function initQueueContext() {
        queueContext.alias = detectQueueAliasFromUrl();
        try {
            const data = await fetchQueues(true);
            const queue = resolveQueueByAlias(data.queues || [], queueContext.alias);
            if (!queue) {
                queueContext.queueId = null;
                queueContext.queueName = 'Не найдена';
                setQueueCaption('Не найдена (' + queueContext.alias + ')');
                renderEmpty('Очередь по ссылке "' + queueContext.alias + '" не найдена');
                setSyncStatus(false, false);
                return;
            }
            queueContext.queueId = queue.queue_id;
            queueContext.queueName = queue.queue_name || queue.queue_code || String(queue.queue_id);
            setQueueCaption(queueContext.queueName);
        } catch (e) {
            queueContext.queueId = null;
            setQueueCaption('Ошибка загрузки');
            renderEmpty('Не удалось загрузить список очередей');
            setSyncStatus(false, false);
            console.error('Queues load error:', e);
        }
    }

    async function loadTicketsAndStats() {
        const queueId = queueContext.queueId;
        const ticketCode = (el(TICKET_CODE_ID) && el(TICKET_CODE_ID).value.trim()) || undefined;
        if (!queueId) {
            setSyncStatus(false, false);
            return;
        }
        let ticketsData = null;
        let statsData = null;
        try {
            const responses = await Promise.all([
                fetchTickets(queueId, 200, 0, ticketCode),
                fetchStats(queueId, 7),
            ]);
            ticketsData = responses[0];
            statsData = responses[1];
            setSyncStatus(true, false);
            setLastUpdate();
            if (ticketsData) renderTable(ticketsData.tickets || [], ticketCode);
            else {
                const ticketsRes = await fetchTickets(queueId, 200, 0, ticketCode);
                if (ticketsRes) renderTable(ticketsRes.tickets || [], ticketCode);
            }
            if (statsData) renderKpi(statsData);
        } catch (e) {
            setSyncStatus(false, false);
            console.error('Load error:', e);
        }
    }

    function schedulePoll() {
        if (pollTimer) clearTimeout(pollTimer);
        pollTimer = setTimeout(function () {
            loadTicketsAndStats();
            schedulePoll();
        }, POLL_INTERVAL_MS);
    }

    function onSearch() {
        loadTicketsAndStats();
        schedulePoll();
    }

    function init() {
        initQueueContext().then(function () {
            loadTicketsAndStats();
            schedulePoll();
        });
        el(SEARCH_BTN_ID) && el(SEARCH_BTN_ID).addEventListener('click', onSearch);
        el(TICKET_CODE_ID) && el(TICKET_CODE_ID).addEventListener('keydown', function (e) {
            if (e.key === 'Enter') onSearch();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
