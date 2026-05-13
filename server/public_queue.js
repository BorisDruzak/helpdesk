/**
 * Public queue page. Uses only the unauthenticated safe projection.
 */
(function () {
    const POLL_INTERVAL_MS = 15000;
    const DEFAULT_QUEUE_ALIAS = 'common';
    const PUBLIC_QUEUE_ALIAS_TO_CODES = {
        common: ['servicedesk_l1', 'common'],
        test: ['servicedesk_test', 'test'],
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
    const queueContext = { alias: DEFAULT_QUEUE_ALIAS, queueCode: null, queueName: '—' };

    function el(id) {
        return document.getElementById(id);
    }

    function normalizeSlug(value) {
        return String(value || '').trim().toLowerCase().replace(/\s+/g, '_').replace(/-/g, '_');
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
        if (node) node.textContent = name || '—';
    }

    function detectQueueAliasFromUrl() {
        const path = window.location.pathname || '';
        if (path.startsWith('/queue/') && path.length > '/queue/'.length) {
            return normalizeSlug(decodeURIComponent(path.slice('/queue/'.length)));
        }
        const params = new URLSearchParams(window.location.search || '');
        return normalizeSlug(params.get('queue') || params.get('queue_alias') || DEFAULT_QUEUE_ALIAS) || DEFAULT_QUEUE_ALIAS;
    }

    function resolveQueueByAlias(queues, alias) {
        const normalizedAlias = normalizeSlug(alias) || DEFAULT_QUEUE_ALIAS;
        const aliasCandidates = PUBLIC_QUEUE_ALIAS_TO_CODES[normalizedAlias] || [normalizedAlias];
        const candidates = new Set(aliasCandidates.map(normalizeSlug).filter(Boolean));
        candidates.add(normalizedAlias);

        return (queues || []).find(function (queue) {
            const code = normalizeSlug(queue.queue_code);
            const name = normalizeSlug(queue.queue_name);
            return candidates.has(code) || candidates.has(name);
        }) || null;
    }

    async function fetchQueues(includeEmpty) {
        const url = '/public_api/queues' + (includeEmpty ? '?include_empty=true' : '');
        const response = await fetch(url);
        if (!response.ok) throw new Error(response.statusText);
        return response.json();
    }

    async function fetchTickets(queueCode, limit, offset, ticketCode) {
        const params = new URLSearchParams({
            queue_code: String(queueCode),
            limit: String(limit || 100),
            offset: String(offset || 0),
        });
        if (ticketCode) params.set('ticket_code', ticketCode);
        const opts = { headers: lastEtags.tickets ? { 'If-None-Match': lastEtags.tickets } : {} };
        const response = await fetch('/public_api/queue/tickets?' + params.toString(), opts);
        if (response.status === 304) return null;
        if (!response.ok) throw new Error(response.statusText);
        const etag = response.headers.get('ETag');
        if (etag) lastEtags.tickets = etag;
        return response.json();
    }

    async function fetchStats(queueCode, days) {
        const params = new URLSearchParams({ days: String(days || 7), queue_code: String(queueCode) });
        const opts = { headers: lastEtags.stats ? { 'If-None-Match': lastEtags.stats } : {} };
        const response = await fetch('/public_api/queue/stats?' + params.toString(), opts);
        if (response.status === 304) return null;
        if (!response.ok) throw new Error(response.statusText);
        const etag = response.headers.get('ETag');
        if (etag) lastEtags.stats = etag;
        return response.json();
    }

    function renderKpi(data) {
        if (!data) return;
        const set = function (id, text) {
            const node = el(KPI_IDS[id]);
            if (node) node.textContent = text ?? '—';
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
        tbody.innerHTML = '<tr><td colspan="5" class="pq-empty">' + (message || 'Нет данных') + '</td></tr>';
    }

    function renderTable(tickets, highlightCode) {
        const tbody = el(TBODY_ID);
        if (!tbody) return;
        if (!tickets || tickets.length === 0) {
            renderEmpty('В очереди пока нет заявок');
            return;
        }
        const code = (highlightCode || '').trim().toUpperCase();
        tbody.innerHTML = tickets.map(function (ticket) {
            const isHighlight = code && (ticket.ticket_code || '').toUpperCase().indexOf(code) >= 0;
            const rowClass = isHighlight ? ' class="pq-highlight"' : '';
            return '<tr' + rowClass + '>'
                + '<td>' + (ticket.public_position ?? '—') + '</td>'
                + '<td>' + (ticket.ticket_code || '—') + '</td>'
                + '<td>' + (ticket.queue_code || '—') + '</td>'
                + '<td>' + (ticket.public_status_label || ticket.public_status || '—') + '</td>'
                + '<td>' + (ticket.wait_bucket || '—') + '</td>'
                + '</tr>';
        }).join('');
    }

    async function initQueueContext() {
        queueContext.alias = detectQueueAliasFromUrl();
        try {
            const data = await fetchQueues(true);
            const queue = resolveQueueByAlias(data.queues || [], queueContext.alias);
            if (!queue) {
                queueContext.queueCode = null;
                queueContext.queueName = 'Не найдена';
                setQueueCaption('Не найдена (' + queueContext.alias + ')');
                renderEmpty('Очередь по ссылке "' + queueContext.alias + '" не найдена');
                setSyncStatus(false, false);
                return;
            }
            queueContext.queueCode = queue.queue_code;
            queueContext.queueName = queue.queue_name || queue.queue_code;
            setQueueCaption(queueContext.queueName);
        } catch (error) {
            queueContext.queueCode = null;
            setQueueCaption('Ошибка загрузки');
            renderEmpty('Не удалось загрузить список очередей');
            setSyncStatus(false, false);
            console.error('Queues load error:', error);
        }
    }

    async function loadTicketsAndStats() {
        const queueCode = queueContext.queueCode;
        const ticketCode = (el(TICKET_CODE_ID) && el(TICKET_CODE_ID).value.trim()) || undefined;
        if (!queueCode) {
            setSyncStatus(false, false);
            return;
        }
        try {
            const responses = await Promise.all([
                fetchTickets(queueCode, 200, 0, ticketCode),
                fetchStats(queueCode, 7),
            ]);
            setSyncStatus(true, false);
            setLastUpdate();
            if (responses[0]) renderTable(responses[0].tickets || [], ticketCode);
            if (responses[1]) renderKpi(responses[1]);
        } catch (error) {
            setSyncStatus(false, false);
            console.error('Load error:', error);
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
        lastEtags.tickets = null;
        loadTicketsAndStats();
        schedulePoll();
    }

    function init() {
        initQueueContext().then(function () {
            loadTicketsAndStats();
            schedulePoll();
        });
        el(SEARCH_BTN_ID) && el(SEARCH_BTN_ID).addEventListener('click', onSearch);
        el(TICKET_CODE_ID) && el(TICKET_CODE_ID).addEventListener('keydown', function (event) {
            if (event.key === 'Enter') onSearch();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
