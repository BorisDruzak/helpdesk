(function () {
    const TOKEN_PREFIX = "public_ticket_token:";
    const POLL_INTERVAL_MS = 8000;
    const FORM_PACK_KEY = "request_forms";

    let ticketId = null;
    let publicToken = null;
    let pollTimer = null;
    let currentFormPack = null;
    let selectedFormKey = "";
    let formValues = {};

    function el(id) {
        return document.getElementById(id);
    }

    function setStatus(text, isError) {
        const node = el("statusBar");
        if (!node) return;
        node.textContent = text;
        node.style.color = isError ? "#b42318" : "";
    }

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function tokenStorageKey(id) {
        return TOKEN_PREFIX + String(id || "");
    }

    function saveToken(id, token) {
        if (!id || !token) return;
        sessionStorage.setItem(tokenStorageKey(id), token);
    }

    function loadToken(id) {
        return sessionStorage.getItem(tokenStorageKey(id)) || "";
    }

    function clearToken(id) {
        if (!id) return;
        sessionStorage.removeItem(tokenStorageKey(id));
    }

    function authHeaders(json) {
        const headers = {};
        if (publicToken) headers.Authorization = "Bearer " + publicToken;
        if (json) headers["Content-Type"] = "application/json";
        return headers;
    }

    function showCreateMode() {
        el("createPanel").hidden = false;
        el("authPanel").hidden = true;
        el("chatPanel").hidden = true;
    }

    function showAuthMode() {
        el("createPanel").hidden = true;
        el("authPanel").hidden = false;
        el("chatPanel").hidden = true;
    }

    function showChatMode() {
        el("createPanel").hidden = true;
        el("authPanel").hidden = false;
        el("chatPanel").hidden = false;
    }

    function showCode(code) {
        const card = el("authCodeCard");
        const value = el("authCodeValue");
        if (!card || !value || !code) return;
        value.textContent = code;
        card.hidden = false;
    }

    function formatTs(value) {
        if (!value) return "";
        try {
            return new Date(value).toLocaleString("ru-RU");
        } catch (_err) {
            return String(value);
        }
    }

    function renderMessages(messages) {
        const history = el("chatHistory");
        if (!history) return;
        const items = Array.isArray(messages) ? messages : [];
        if (!items.length) {
            history.innerHTML = '<div class="chat-message"><div class="chat-message-body">Сообщений пока нет.</div></div>';
            return;
        }
        history.innerHTML = items.map((msg) => {
            const role = msg.from_role || "user";
            return `
                <article class="chat-message" data-role="${escapeHtml(role)}">
                    <div class="chat-message-head">
                        <strong>${escapeHtml(role)}</strong>
                        <span>${escapeHtml(formatTs(msg.ts))}</span>
                    </div>
                    <div class="chat-message-body">${escapeHtml(msg.text || "")}</div>
                </article>
            `;
        }).join("");
        history.scrollTop = history.scrollHeight;
    }

    function currentForms() {
        return Array.isArray(currentFormPack?.forms) ? currentFormPack.forms : [];
    }

    function getSelectedForm() {
        return currentForms().find((form) => form.key === selectedFormKey) || currentForms()[0] || null;
    }

    function isFieldVisible(fieldDef, values) {
        const rule = fieldDef && fieldDef.visible_when;
        if (!rule || typeof rule !== "object") return true;
        const currentValue = values[rule.field];
        if (Object.prototype.hasOwnProperty.call(rule, "equals")) {
            return String(currentValue || "").trim() === String(rule.equals || "").trim();
        }
        if (Array.isArray(rule.in)) {
            return rule.in.map((item) => String(item || "").trim()).includes(String(currentValue || "").trim());
        }
        return true;
    }

    function visibleFields(form) {
        return ((form && form.fields) || []).filter((field) => isFieldVisible(field, formValues));
    }

    function readFieldValue(fieldDef, rootNode) {
        const fieldKey = String(fieldDef.key || "");
        if (fieldDef.type === "checkbox") {
            return rootNode?.querySelector(`[data-field-key="${fieldKey}"]`)?.checked === true;
        }
        if (fieldDef.type === "radio") {
            const checked = rootNode?.querySelector(`input[name="form-field-${fieldKey}"]:checked`);
            return checked ? String(checked.value || "").trim() : "";
        }
        const control = rootNode?.querySelector(`[data-field-key="${fieldKey}"]`);
        return String(control?.value || "").trim();
    }

    function syncFormValuesFromDom() {
        const form = getSelectedForm();
        const root = el("dynamicFields");
        if (!form || !root) return;
        visibleFields(form).forEach((fieldDef) => {
            formValues[fieldDef.key] = readFieldValue(fieldDef, root);
        });
    }

    function renderRequestTypeOptions() {
        const root = el("requestTypeOptions");
        const hint = el("requestTypeHint");
        if (!root) return;
        const forms = currentForms();
        if (!forms.length) {
            root.innerHTML = '<div class="request-type-empty">Каталог форм временно недоступен. Вы можете оставить обычное описание проблемы.</div>';
            if (hint) hint.textContent = "Сервер не отдал каталог форм, поэтому используется свободное описание обращения.";
            return;
        }
        if (!selectedFormKey || !forms.some((form) => form.key === selectedFormKey)) {
            selectedFormKey = forms[0].key;
        }
        root.innerHTML = forms.map((form) => `
            <button
                type="button"
                class="request-type-option${form.key === selectedFormKey ? " is-active" : ""}"
                data-form-key="${escapeHtml(form.key)}"
            >
                <strong>${escapeHtml(form.title || form.key)}</strong>
                <span>${escapeHtml(form.description || "")}</span>
            </button>
        `).join("");
        if (hint) hint.textContent = "Выберите шаблон, чтобы форма подсказала нужные поля для маршрутизации.";
    }

    function renderDynamicFields() {
        const intro = el("dynamicFormIntro");
        const title = el("dynamicFormTitle");
        const description = el("dynamicFormDescription");
        const root = el("dynamicFields");
        const form = getSelectedForm();
        if (!root) return;
        if (!form) {
            if (intro) intro.hidden = true;
            root.innerHTML = "";
            return;
        }
        const fields = visibleFields(form);
        if (intro) intro.hidden = false;
        if (title) title.textContent = form.title || "Форма заявки";
        if (description) description.textContent = form.description || "Уточните детали обращения, чтобы сократить лишние вопросы.";
        root.innerHTML = fields.map((fieldDef) => {
            const fieldKey = String(fieldDef.key || "");
            const value = formValues[fieldKey];
            const requiredMark = fieldDef.required ? " *" : "";
            const helpText = fieldDef.help_text ? `<small class="dynamic-help">${escapeHtml(fieldDef.help_text)}</small>` : "";
            if (fieldDef.type === "textarea") {
                return `
                    <label class="dynamic-field">
                        <span>${escapeHtml(fieldDef.label || fieldKey)}${requiredMark}</span>
                        <textarea rows="4" data-field-key="${escapeHtml(fieldKey)}" placeholder="${escapeHtml(fieldDef.placeholder || "")}">${escapeHtml(value || "")}</textarea>
                        ${helpText}
                    </label>
                `;
            }
            if (fieldDef.type === "select") {
                const options = (fieldDef.options || []).map((option) => `
                    <option value="${escapeHtml(option.value)}"${String(value || "") === String(option.value || "") ? " selected" : ""}>${escapeHtml(option.label || option.value)}</option>
                `).join("");
                return `
                    <label class="dynamic-field">
                        <span>${escapeHtml(fieldDef.label || fieldKey)}${requiredMark}</span>
                        <select data-field-key="${escapeHtml(fieldKey)}">
                            <option value="">Выберите...</option>
                            ${options}
                        </select>
                        ${helpText}
                    </label>
                `;
            }
            if (fieldDef.type === "radio") {
                const options = (fieldDef.options || []).map((option) => `
                    <label class="dynamic-radio-option">
                        <input type="radio" name="form-field-${escapeHtml(fieldKey)}" value="${escapeHtml(option.value)}"${String(value || "") === String(option.value || "") ? " checked" : ""}>
                        <span>${escapeHtml(option.label || option.value)}</span>
                    </label>
                `).join("");
                return `
                    <div class="dynamic-field">
                        <span>${escapeHtml(fieldDef.label || fieldKey)}${requiredMark}</span>
                        <div class="dynamic-radio-group">${options}</div>
                        ${helpText}
                    </div>
                `;
            }
            if (fieldDef.type === "checkbox") {
                return `
                    <label class="dynamic-checkbox">
                        <input type="checkbox" data-field-key="${escapeHtml(fieldKey)}"${value ? " checked" : ""}>
                        <span>${escapeHtml(fieldDef.label || fieldKey)}${requiredMark}</span>
                    </label>
                `;
            }
            return `
                <label class="dynamic-field">
                    <span>${escapeHtml(fieldDef.label || fieldKey)}${requiredMark}</span>
                    <input type="text" data-field-key="${escapeHtml(fieldKey)}" value="${escapeHtml(value || "")}" placeholder="${escapeHtml(fieldDef.placeholder || "")}">
                    ${helpText}
                </label>
            `;
        }).join("");
    }

    function selectForm(formKey) {
        selectedFormKey = formKey;
        syncFormValuesFromDom();
        renderRequestTypeOptions();
        renderDynamicFields();
    }

    function collectVisibleFormPayload() {
        const form = getSelectedForm();
        const payload = {};
        if (!form) return payload;
        syncFormValuesFromDom();
        visibleFields(form).forEach((fieldDef) => {
            payload[fieldDef.key] = formValues[fieldDef.key];
        });
        return payload;
    }

    function validateVisibleFields() {
        const form = getSelectedForm();
        if (!form) return [];
        syncFormValuesFromDom();
        return visibleFields(form)
            .filter((fieldDef) => fieldDef.required)
            .filter((fieldDef) => {
                const value = formValues[fieldDef.key];
                return fieldDef.type === "checkbox" ? value !== true : !String(value || "").trim();
            })
            .map((fieldDef) => fieldDef.label || fieldDef.key);
    }

    async function loadFormPack() {
        try {
            const response = await fetch(`/public_api/ticket_forms/current?pack_key=${encodeURIComponent(FORM_PACK_KEY)}`, {
                cache: "no-store",
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok || data.status !== "ok" || !data.pack) {
                throw new Error(data.error || "catalog_unavailable");
            }
            currentFormPack = data.pack;
            if (!selectedFormKey) {
                selectedFormKey = currentForms()[0]?.key || "";
            }
        } catch (_err) {
            currentFormPack = null;
        }
        renderRequestTypeOptions();
        renderDynamicFields();
    }

    async function loadTicket() {
        if (!ticketId || !publicToken) return;
        const response = await fetch("/api/tickets/" + encodeURIComponent(ticketId), {
            headers: authHeaders(),
        });
        const data = await response.json().catch(() => ({}));
        if (response.status === 401) {
            clearToken(ticketId);
            publicToken = "";
            showAuthMode();
            setStatus("Сессия истекла. Введите код авторизации повторно.", true);
            return;
        }
        if (!response.ok || data.status !== "ok") {
            throw new Error(data.error || response.statusText || "Не удалось загрузить тикет");
        }
        const ticket = data.ticket || {};
        el("chatTitle").textContent = ticket.ticket_code || ticket.ticket_id || "Тикет";
        el("chatMeta").textContent = "Статус: " + (ticket.status || "—");
        renderMessages(data.messages || []);
        showChatMode();
        setStatus("Тикет загружен");
    }

    async function authorizeByCode(code) {
        const response = await fetch("/public_api/tickets/" + encodeURIComponent(ticketId) + "/authorize", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code: String(code || "").trim() }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.status !== "ok") {
            throw new Error(data.error || "Неверный код");
        }
        publicToken = data.public_token || "";
        saveToken(ticketId, publicToken);
        showCode(data.public_access_code || code);
        await loadTicket();
    }

    async function createTicket(event) {
        event.preventDefault();
        const form = getSelectedForm();
        const missingFields = validateVisibleFields();
        if (missingFields.length) {
            setStatus("Заполните обязательные поля: " + missingFields.join(", "), true);
            return;
        }

        const payload = {
            title: form ? `Заявка: ${form.title || form.key}` : "Заявка с веб-страницы",
            description: el("createDescription").value.trim(),
            user_display_name: el("createDisplayName").value.trim(),
            requester_profile: {
                full_name: el("createFullName").value.trim(),
                building: el("createBuilding").value.trim(),
                room: el("createRoom").value.trim(),
                phone: el("createPhone").value.trim(),
            },
            urgency: el("createUrgency").value === "true",
            importance: el("createImportance").value === "true",
            urgency_reason: el("createUrgencyReason").value.trim(),
            importance_reason: el("createImportanceReason").value.trim(),
        };

        if (form && currentFormPack) {
            payload.form_key = form.key;
            payload.form_pack_key = currentFormPack.pack_key;
            payload.form_pack_version = currentFormPack.version;
            payload.form_payload = collectVisibleFormPayload();
            payload.ticket_type = form.request_kind || form.key || "request";
        }

        const button = el("createSubmitBtn");
        button.disabled = true;
        setStatus("Создаём заявку...");
        try {
            const response = await fetch("/public_api/tickets/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok || data.status !== "ok") {
                throw new Error((data.details && JSON.stringify(data.details)) || data.error || "Не удалось создать заявку");
            }
            ticketId = data.ticket && data.ticket.ticket_id;
            publicToken = data.public_token || "";
            saveToken(ticketId, publicToken);
            showCode(data.public_access_code);
            if (ticketId) {
                history.replaceState(null, "", "/help?ticket_id=" + encodeURIComponent(ticketId));
            }
            el("authCodeInput").value = data.public_access_code || "";
            await loadTicket();
        } catch (err) {
            setStatus(err.message || "Ошибка создания заявки", true);
        } finally {
            button.disabled = false;
        }
    }

    async function submitAuth(event) {
        event.preventDefault();
        const code = el("authCodeInput").value.trim();
        if (!ticketId) {
            setStatus("Не указан ticket_id в ссылке.", true);
            return;
        }
        if (!code) {
            setStatus("Введите код авторизации.", true);
            return;
        }
        setStatus("Проверяем код...");
        try {
            await authorizeByCode(code);
        } catch (err) {
            setStatus(err.message || "Ошибка авторизации", true);
        }
    }

    async function sendMessage(event) {
        event.preventDefault();
        const input = el("chatMessageInput");
        const text = input.value.trim();
        if (!text) return;
        const button = el("chatSubmitBtn");
        button.disabled = true;
        setStatus("Отправляем сообщение...");
        try {
            const response = await fetch("/api/tickets/" + encodeURIComponent(ticketId) + "/message", {
                method: "POST",
                headers: authHeaders(true),
                body: JSON.stringify({ text: text, visibility: "public" }),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok || data.status !== "ok") {
                throw new Error(data.error || "Не удалось отправить сообщение");
            }
            input.value = "";
            await loadTicket();
            setStatus("Сообщение отправлено");
        } catch (err) {
            setStatus(err.message || "Ошибка отправки", true);
        } finally {
            button.disabled = false;
        }
    }

    function startPolling() {
        stopPolling();
        pollTimer = setInterval(() => {
            if (ticketId && publicToken) {
                loadTicket().catch((err) => setStatus(err.message || "Ошибка обновления", true));
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
        const params = new URLSearchParams(window.location.search || "");
        ticketId = params.get("ticket_id") || "";
        const codeFromUrl = (params.get("code") || "").trim();

        await loadFormPack();

        if (ticketId) {
            publicToken = loadToken(ticketId);
            if (publicToken) {
                try {
                    await loadTicket();
                } catch (err) {
                    setStatus(err.message || "Ошибка загрузки тикета", true);
                    showAuthMode();
                }
            } else if (codeFromUrl) {
                showAuthMode();
                el("authCodeInput").value = codeFromUrl;
                setStatus("Авторизация по коду из ссылки...");
                try {
                    await authorizeByCode(codeFromUrl);
                } catch (err) {
                    setStatus(err.message || "Ошибка авторизации", true);
                    showAuthMode();
                }
            } else {
                showAuthMode();
                setStatus("Введите код авторизации для входа в тикет.");
            }
        } else {
            showCreateMode();
            setStatus("Готово");
        }
        startPolling();
    }

    el("requestTypeOptions")?.addEventListener("click", (event) => {
        const button = event.target.closest("[data-form-key]");
        if (!button) return;
        selectForm(String(button.getAttribute("data-form-key") || ""));
    });
    el("dynamicFields")?.addEventListener("input", () => {
        syncFormValuesFromDom();
    });
    el("dynamicFields")?.addEventListener("change", () => {
        syncFormValuesFromDom();
        renderDynamicFields();
    });
    el("createForm")?.addEventListener("submit", createTicket);
    el("authForm")?.addEventListener("submit", submitAuth);
    el("chatForm")?.addEventListener("submit", sendMessage);
    window.addEventListener("beforeunload", stopPolling);
    init().catch((err) => setStatus(err.message || "Ошибка инициализации", true));
})();
