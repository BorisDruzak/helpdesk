(function () {
    const DEFAULT_AUTH_TOKEN_KEY = 'admin_auth_token';

    function getToken(tokenKey) {
        const key = tokenKey || DEFAULT_AUTH_TOKEN_KEY;
        const token = localStorage.getItem(key);
        return typeof token === 'string' ? token.trim() : '';
    }

    function authHeaders(includeContentType, tokenKey) {
        const headers = {};
        const token = getToken(tokenKey);
        if (token) {
            headers.Authorization = 'Bearer ' + token;
        }
        if (includeContentType) {
            headers['Content-Type'] = 'application/json';
        }
        return headers;
    }

    function webSessionHeaders(includeContentType) {
        const headers = {};
        if (includeContentType) {
            headers['Content-Type'] = 'application/json';
        }
        return headers;
    }

    function fetchWebSession(url, options) {
        const requestOptions = Object.assign({}, options || {});
        requestOptions.credentials = requestOptions.credentials || 'same-origin';
        return fetch(url, requestOptions);
    }

    async function responseToJson(response, nonJsonMessage) {
        const text = await response.text();
        if (!text || !text.trim()) {
            return {};
        }
        try {
            return JSON.parse(text);
        } catch (error) {
            const preview = text.slice(0, 120).replace(/\s+/g, ' ');
            const prefix = String(nonJsonMessage || 'Сервер вернул не JSON.');
            throw new Error(preview ? prefix + ' ' + preview : prefix);
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
        if (value instanceof Date) {
            return Number.isNaN(value.getTime()) ? null : value;
        }
        const normalized = String(value)
            .trim()
            .replace(/\.(\d{3})\d+([+-]\d{2}:\d{2}|Z)$/i, '.$1$2');
        const date = new Date(normalized);
        return Number.isNaN(date.getTime()) ? null : date;
    }

    function formatDate(value, locale) {
        const date = parseServerDate(value);
        if (!date) {
            return '—';
        }
        return date.toLocaleString(locale || 'ru-RU');
    }

    function boolLabel(value, yesLabel, noLabel) {
        return value ? (yesLabel || 'Да') : (noLabel || 'Нет');
    }

    window.PcClientWebShared = Object.freeze({
        authHeaders,
        boolLabel,
        escapeHtml,
        fetchWebSession,
        formatDate,
        getToken,
        parseServerDate,
        responseToJson,
        webSessionHeaders,
    });
})();
