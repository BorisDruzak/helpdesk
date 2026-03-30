(function () {
    const AUTH_TOKEN_KEY = 'admin_auth_token';
    const USER_LOGIN_KEY = 'admin_user_login';
    const ROLE_KEY = 'admin_actor_role';
    const LOGIN_SHELL_VERSION = '20260330a';
    const ADMIN_SHELL_VERSION = '20260330b';
    const SUPPORT_SHELL_VERSION = '20260330b';
    const ROLE_META = {
        admin: {
            title: 'Вход в админку',
            description: 'Управление системой, пользователями, очередями, правилами маршрутизации и техпанелью.',
            destination: '/admin?_shell=' + ADMIN_SHELL_VERSION,
            linkLabel: 'Открыть админку',
        },
        support: {
            title: 'Вход в support workspace',
            description: 'Операторская очередь, чат по тикету, наблюдение за чужими тикетами и рабочие инструменты.',
            destination: '/support?_shell=' + SUPPORT_SHELL_VERSION,
            linkLabel: 'Открыть support',
        },
    };

    let targetRole = 'admin';

    function byId(id) {
        return document.getElementById(id);
    }

    function setMessage(text, isError) {
        const errorNode = byId('loginError');
        const hintNode = byId('loginHint');
        if (!errorNode || !hintNode) {
            return;
        }
        if (isError) {
            errorNode.textContent = text || '';
            errorNode.classList.toggle('hidden', !text);
            hintNode.textContent = '';
            hintNode.classList.add('hidden');
            return;
        }
        hintNode.textContent = text || '';
        hintNode.classList.toggle('hidden', !text);
        errorNode.textContent = '';
        errorNode.classList.add('hidden');
    }

    function persistSession(data) {
        localStorage.setItem(AUTH_TOKEN_KEY, data.token || '');
        localStorage.setItem(USER_LOGIN_KEY, data.user_login || '');
        localStorage.setItem(ROLE_KEY, data.actor_role || '');
    }

    function clearSession() {
        localStorage.removeItem(AUTH_TOKEN_KEY);
        localStorage.removeItem(USER_LOGIN_KEY);
        localStorage.removeItem(ROLE_KEY);
    }

    function getTargetFromUrl() {
        const params = new URLSearchParams(window.location.search);
        const target = String(params.get('target') || '').trim().toLowerCase();
        return ROLE_META[target] ? target : 'admin';
    }

    function getMessageFromUrl() {
        const params = new URLSearchParams(window.location.search);
        return String(params.get('message') || '').trim();
    }

    function applyRoleUi() {
        const meta = ROLE_META[targetRole];
        const roleCard = byId('roleCard');
        const title = byId('roleTitle');
        const description = byId('roleDescription');
        const directLink = byId('directTargetLink');
        if (roleCard) {
            roleCard.dataset.target = targetRole;
        }
        if (title) {
            title.textContent = meta.title;
        }
        if (description) {
            description.textContent = meta.description;
        }
        if (directLink) {
            directLink.href = meta.destination;
            directLink.textContent = meta.linkLabel;
        }
        document.querySelectorAll('#roleSwitch .role-chip').forEach((button) => {
            const active = button.getAttribute('data-target') === targetRole;
            button.classList.toggle('active', active);
            button.setAttribute('aria-selected', active ? 'true' : 'false');
        });
        const params = new URLSearchParams(window.location.search);
        params.set('_shell', LOGIN_SHELL_VERSION);
        params.set('target', targetRole);
        history.replaceState({}, '', '/login?' + params.toString());
    }

    async function responseToJson(response) {
        const text = await response.text();
        if (!text || !text.trim()) {
            return {};
        }
        try {
            return JSON.parse(text);
        } catch (error) {
            throw new Error('Сервер вернул некорректный ответ.');
        }
    }

    async function fetchCurrentSession() {
        const token = localStorage.getItem(AUTH_TOKEN_KEY);
        if (!token) {
            return null;
        }
        const response = await fetch('/api/ui_session', {
            headers: { Authorization: 'Bearer ' + token },
        });
        if (response.status === 401) {
            clearSession();
            return null;
        }
        const data = await responseToJson(response);
        if (!response.ok || data.status !== 'success') {
            clearSession();
            return null;
        }
        return data;
    }

    function redirectForRole(role) {
        const meta = ROLE_META[role];
        window.location.href = meta ? meta.destination : ROLE_META.admin.destination;
    }

    async function handleSubmit(event) {
        event.preventDefault();
        setMessage('', false);
        const login = String(byId('loginInput')?.value || '').trim();
        const password = String(byId('passwordInput')?.value || '').trim();
        if (!login || !password) {
            setMessage('Введите логин и пароль.', true);
            return;
        }
        const submitBtn = byId('submitBtn');
        if (submitBtn) {
            submitBtn.disabled = true;
        }
        try {
            const response = await fetch('/api/ui_login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ login, password, expected_role: targetRole }),
            });
            const data = await responseToJson(response);
            if (!response.ok || data.status !== 'success') {
                throw new Error(data.error || 'Не удалось выполнить вход.');
            }
            if (data.actor_role !== targetRole) {
                clearSession();
                throw new Error('Эта учетная запись не подходит для выбранной рабочей зоны.');
            }
            persistSession(data);
            redirectForRole(targetRole);
        } catch (error) {
            clearSession();
            setMessage(error.message || 'Не удалось выполнить вход.', true);
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
            }
        }
    }

    async function init() {
        targetRole = getTargetFromUrl();
        applyRoleUi();
        const initialMessage = getMessageFromUrl();
        if (initialMessage) {
            setMessage(initialMessage, false);
        }
        document.querySelectorAll('#roleSwitch .role-chip').forEach((button) => {
            button.addEventListener('click', () => {
                targetRole = button.getAttribute('data-target') || 'admin';
                const nextMessage = getMessageFromUrl();
                setMessage(nextMessage, false);
                applyRoleUi();
            });
        });
        byId('loginForm')?.addEventListener('submit', handleSubmit);

        const session = await fetchCurrentSession();
        if (!session) {
            return;
        }
        if (session.actor_role === targetRole) {
            redirectForRole(targetRole);
            return;
        }
        setMessage(
            'Текущая сессия открыта под ролью "' + session.actor_role + '". Для входа в "' + targetRole + '" выполните повторный вход.',
            false
        );
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            init().catch((error) => {
                setMessage(error.message || 'Не удалось открыть страницу входа.', true);
            });
        });
    } else {
        init().catch((error) => {
            setMessage(error.message || 'Не удалось открыть страницу входа.', true);
        });
    }
})();
