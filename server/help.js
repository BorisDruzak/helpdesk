(function () {
    const TOKEN_PREFIX = 'public_ticket_token:';
    const POLL_INTERVAL_MS = 8000;

    let ticketId = null;
    let publicToken = null;
    let pollTimer = null;

    function el(id) {
        return document.getElementById(id);
    }

    function setStatus(text, isError) {
        const node = el('statusBar');
        if (!node) return;
        node.textContent = text;
        node.style.color = isError ? '#b42318' : '';
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function tokenStorageKey(id) {
        return TOKEN_PREFIX + String(id || '');
    }

    function saveToken(id, token) {
        if (!id || !token) return;
        sessionStorage.setItem(tokenStorageKey(id), token);
    }

    function loadToken(id) {
        return sessionStorage.getItem(tokenStorageKey(id)) || '';
    }

    function clearToken(id) {
        if (!id) return;
        sessionStorage.removeItem(tokenStorageKey(id));
    }

    function authHeaders(json) {
        const headers = {};
        if (publicToken) headers.Authorization = 'Bearer ' + publicToken;
        if (json) headers['Content-Type'] = 'application/json';
        return headers;
    }

    function showCreateMode() {
        el('createPanel').hidden = false;
        el('authPanel').hidden = true;
        el('chatPanel').hidden = true;
    }

    function showAuthMode() {
        el('createPanel').hidden = true;
        el('authPanel').hidden = false;
        el('chatPanel').hidden = true;
    }

    function showChatMode() {
        el('createPanel').hidden = true;
        el('authPanel').hidden = false;
        el('chatPanel').hidden = false;
    }

    function showCode(code) {
        const card = el('authCodeCard');
        const value = el('authCodeValue');
        if (!card || !value || !code) return;
        value.textContent = code;
        card.hidden = false;
    }

    function formatTs(value) {
        if (!value) return '';
        try {
            return new Date(value).toLocaleString('ru-RU');
        } catch (err) {
            return String(value);
        }
    }

    function renderMessages(messages) {
        const history = el('chatHistory');
        if (!history) return;
        const items = Array.isArray(messages) ? messages : [];
        if (!items.length) {
            history.innerHTML = '<div class="chat-message"><div class="chat-message-body">Сообщений пока нет.</div></div>';
            return;
        }
        history.innerHTML = items.map((msg) => {
            const role = msg.from_role || 'user';
            return `
                <article class="chat-message" data-role="${escapeHtml(role)}">
                    <div class="chat-message-head">
                        <strong>${escapeHtml(role)}</strong>
                        <span>${escapeHtml(formatTs(msg.ts))}</span>
                    </div>
                    <div class="chat-message-body">${escapeHtml(msg.text || '')}</div>
                </article>
            `;
        }).join('');
        history.scrollTop = history.scrollHeight;
    }

    async function loadTicket() {
        if (!ticketId || !publicToken) return;
        const response = await fetch('/api/tickets/' + encodeURIComponent(ticketId), {
            headers: authHeaders(),
        });
        const data = await response.json().catch(() => ({}));
        if (response.status === 401) {
            clearToken(ticketId);
            publicToken = '';
            showAuthMode();
            setStatus('Сессия истекла. Введите код авторизации повторно.', true);
            return;
        }
        if (!response.ok || data.status !== 'ok') {
            throw new Error(data.error || response.statusText || 'Не удалось загрузить тикет');
        }
        const ticket = data.ticket || {};
        el('chatTitle').textContent = ticket.ticket_code || ticket.ticket_id || 'Тикет';
        el('chatMeta').textContent = 'Статус: ' + (ticket.status || '—');
        renderMessages(data.messages || []);
        showChatMode();
        setStatus('Тикет загружен');
    }

    async function authorizeByCode(code) {
        const response = await fetch('/public_api/tickets/' + encodeURIComponent(ticketId) + '/authorize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: String(code || '').trim() }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.status !== 'ok') {
            throw new Error(data.error || 'Неверный код');
        }
        publicToken = data.public_token || '';
        saveToken(ticketId, publicToken);
        showCode(data.public_access_code || code);
        await loadTicket();
    }

    async function createTicket(event) {
        event.preventDefault();
        const payload = {
            title: 'Заявка с веб-страницы',
            description: el('createDescription').value.trim(),
            user_display_name: el('createDisplayName').value.trim(),
            requester_profile: {
                full_name: el('createFullName').value.trim(),
                building: el('createBuilding').value.trim(),
                room: el('createRoom').value.trim(),
                phone: el('createPhone').value.trim(),
            },
            urgency: el('createUrgency').value === 'true',
            importance: el('createImportance').value === 'true',
            urgency_reason: el('createUrgencyReason').value.trim(),
            importance_reason: el('createImportanceReason').value.trim(),
        };
        const button = el('createSubmitBtn');
        button.disabled = true;
        setStatus('Создаём заявку...');
        try {
            const response = await fetch('/public_api/tickets/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok || data.status !== 'ok') {
                throw new Error(data.error || 'Не удалось создать заявку');
            }
            ticketId = data.ticket && data.ticket.ticket_id;
            publicToken = data.public_token || '';
            saveToken(ticketId, publicToken);
            showCode(data.public_access_code);
            if (ticketId) {
                history.replaceState(null, '', '/help?ticket_id=' + encodeURIComponent(ticketId));
            }
            el('authCodeInput').value = data.public_access_code || '';
            await loadTicket();
        } catch (err) {
            setStatus(err.message || 'Ошибка создания заявки', true);
        } finally {
            button.disabled = false;
        }
    }

    async function submitAuth(event) {
        event.preventDefault();
        const code = el('authCodeInput').value.trim();
        if (!ticketId) {
            setStatus('Не указан ticket_id в ссылке.', true);
            return;
        }
        if (!code) {
            setStatus('Введите код авторизации.', true);
            return;
        }
        setStatus('Проверяем код...');
        try {
            await authorizeByCode(code);
        } catch (err) {
            setStatus(err.message || 'Ошибка авторизации', true);
        }
    }

    async function sendMessage(event) {
        event.preventDefault();
        const input = el('chatMessageInput');
        const text = input.value.trim();
        if (!text) return;
        const button = el('chatSubmitBtn');
        button.disabled = true;
        setStatus('Отправляем сообщение...');
        try {
            const response = await fetch('/api/tickets/' + encodeURIComponent(ticketId) + '/message', {
                method: 'POST',
                headers: authHeaders(true),
                body: JSON.stringify({ text: text, visibility: 'public' }),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok || data.status !== 'ok') {
                throw new Error(data.error || 'Не удалось отправить сообщение');
            }
            input.value = '';
            await loadTicket();
            setStatus('Сообщение отправлено');
        } catch (err) {
            setStatus(err.message || 'Ошибка отправки', true);
        } finally {
            button.disabled = false;
        }
    }

    function startPolling() {
        stopPolling();
        pollTimer = setInterval(() => {
            if (ticketId && publicToken) {
                loadTicket().catch((err) => setStatus(err.message || 'Ошибка обновления', true));
            }
        }, POLL_INTERVAL_MS);
    }

    function stopPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    async function init() {
        const params = new URLSearchParams(window.location.search || '');
        ticketId = params.get('ticket_id') || '';
        const codeFromUrl = (params.get('code') || '').trim();
        if (ticketId) {
            publicToken = loadToken(ticketId);
            if (publicToken) {
                try {
                    await loadTicket();
                } catch (err) {
                    setStatus(err.message || 'Ошибка загрузки тикета', true);
                    showAuthMode();
                }
            } else if (codeFromUrl) {
                showAuthMode();
                el('authCodeInput').value = codeFromUrl;
                setStatus('Авторизация по коду из ссылки...');
                try {
                    await authorizeByCode(codeFromUrl);
                } catch (err) {
                    setStatus(err.message || 'Ошибка авторизации', true);
                    showAuthMode();
                }
            } else {
                showAuthMode();
                setStatus('Введите код авторизации для входа в тикет.');
            }
        } else {
            showCreateMode();
            setStatus('Готово');
        }
        startPolling();
    }

    el('createForm')?.addEventListener('submit', createTicket);
    el('authForm')?.addEventListener('submit', submitAuth);
    el('chatForm')?.addEventListener('submit', sendMessage);
    window.addEventListener('beforeunload', stopPolling);
    init().catch((err) => setStatus(err.message || 'Ошибка инициализации', true));
})();
