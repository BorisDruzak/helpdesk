(function () {
    const shared = window.PcClientWebShared;
    const PACK_KEY = "request_forms";
    const FIELD_TYPES = [
        { value: "text", label: "Текст" },
        { value: "textarea", label: "Большой текст" },
        { value: "select", label: "Список" },
        { value: "radio", label: "Переключатели" },
        { value: "checkbox", label: "Флажок" },
    ];

    const state = {
        initialized: false,
        fragmentLoaded: false,
        loading: false,
        pack: null,
        versions: [],
        selectedFormKey: "",
        selectedFieldKey: "",
    };

    function html(value) {
        if (window.escapeHtml) {
            return window.escapeHtml(value);
        }
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function clone(value) {
        return JSON.parse(JSON.stringify(value));
    }

    function byId(id) {
        return document.getElementById(id);
    }

    function getAuthHeaders(includeContentType) {
        if (typeof window.getAuthHeaders === "function") {
            return window.getAuthHeaders(includeContentType);
        }
        return shared.authHeaders(includeContentType, "admin_auth_token");
    }

    async function responseToJson(response) {
        if (typeof window.responseToJson === "function") {
            return window.responseToJson(response);
        }
        return shared.responseToJson(response, "Сервер вернул не JSON.");
    }

    function setStatus(message, kind) {
        const node = byId("ticketFormsBuilderStatus");
        if (!node) {
            return;
        }
        if (!message) {
            node.style.display = "none";
            node.textContent = "";
            node.className = "loading";
            return;
        }
        node.style.display = "block";
        node.textContent = message;
        node.className = kind === "error" ? "error-message" : kind === "success" ? "success-message" : "loading";
    }

    function createBlankPack() {
        return {
            pack_key: PACK_KEY,
            version: "1.0.0",
            title: "Каталог заявок",
            description: "",
            forms: [],
        };
    }

    function createBlankForm(index) {
        return {
            key: `request_${index}`,
            request_kind: `request_${index}`,
            title: `Новый тип ${index}`,
            description: "",
            fields: [],
        };
    }

    function createBlankField(index) {
        return {
            key: `field_${index}`,
            label: `Поле ${index}`,
            type: "text",
            required: false,
            placeholder: "",
            help_text: "",
            options: [],
            visible_when: null,
        };
    }

    function ensurePack(rawPack) {
        const pack = clone(rawPack || createBlankPack());
        pack.pack_key = PACK_KEY;
        pack.version = String(pack.version || "").trim() || "1.0.0";
        pack.title = String(pack.title || "").trim() || "Каталог заявок";
        pack.description = String(pack.description || "").trim();
        pack.forms = Array.isArray(pack.forms) ? pack.forms : [];
        pack.forms = pack.forms.map((form, index) => ({
            key: String(form?.key || `request_${index + 1}`).trim() || `request_${index + 1}`,
            request_kind: String(form?.request_kind || form?.key || `request_${index + 1}`).trim() || `request_${index + 1}`,
            title: String(form?.title || `Тип ${index + 1}`).trim() || `Тип ${index + 1}`,
            description: String(form?.description || "").trim(),
            fields: Array.isArray(form?.fields) ? form.fields.map((field, fieldIndex) => ({
                key: String(field?.key || `field_${fieldIndex + 1}`).trim() || `field_${fieldIndex + 1}`,
                label: String(field?.label || `Поле ${fieldIndex + 1}`).trim() || `Поле ${fieldIndex + 1}`,
                type: String(field?.type || "text").trim() || "text",
                required: Boolean(field?.required),
                placeholder: String(field?.placeholder || "").trim(),
                help_text: String(field?.help_text || "").trim(),
                options: Array.isArray(field?.options) ? field.options.map((option) => ({
                    value: String(option?.value || "").trim(),
                    label: String(option?.label || "").trim(),
                })).filter((option) => option.value && option.label) : [],
                visible_when: field?.visible_when && typeof field.visible_when === "object"
                    ? clone(field.visible_when)
                    : null,
            })) : [],
        }));
        return pack;
    }

    function packForms() {
        return Array.isArray(state.pack?.forms) ? state.pack.forms : [];
    }

    function getSelectedForm() {
        return packForms().find((form) => form.key === state.selectedFormKey) || null;
    }

    function getSelectedField() {
        const form = getSelectedForm();
        if (!form) {
            return null;
        }
        return (form.fields || []).find((field) => field.key === state.selectedFieldKey) || null;
    }

    function syncPackMetaFromInputs() {
        if (!state.pack) {
            return;
        }
        state.pack.title = String(byId("ticketFormsPackTitle")?.value || "").trim() || "Каталог заявок";
        state.pack.version = String(byId("ticketFormsPackVersion")?.value || "").trim() || "1.0.0";
        state.pack.description = String(byId("ticketFormsPackDescription")?.value || "").trim();
    }

    function uniqueKey(existingKeys, seed) {
        const normalized = String(seed || "item").trim() || "item";
        if (!existingKeys.has(normalized)) {
            return normalized;
        }
        let index = 2;
        while (existingKeys.has(`${normalized}_${index}`)) {
            index += 1;
        }
        return `${normalized}_${index}`;
    }

    function ensureSelection() {
        const forms = packForms();
        if (!forms.length) {
            state.selectedFormKey = "";
            state.selectedFieldKey = "";
            return;
        }
        if (!forms.some((form) => form.key === state.selectedFormKey)) {
            state.selectedFormKey = forms[0].key;
        }
        const form = getSelectedForm();
        const fields = Array.isArray(form?.fields) ? form.fields : [];
        if (!fields.length) {
            state.selectedFieldKey = "";
            return;
        }
        if (!fields.some((field) => field.key === state.selectedFieldKey)) {
            state.selectedFieldKey = fields[0].key;
        }
    }

    function optionsToText(options) {
        return (options || [])
            .map((option) => `${option.value} | ${option.label}`)
            .join("\n");
    }

    function textToOptions(rawText) {
        return String(rawText || "")
            .split(/\r?\n/)
            .map((line) => line.trim())
            .filter(Boolean)
            .map((line) => {
                const parts = line.split("|");
                const value = String(parts[0] || "").trim();
                const label = String(parts.slice(1).join("|") || parts[0] || "").trim();
                return { value, label };
            })
            .filter((option) => option.value && option.label);
    }

    function visibleWhenFieldOptions(form, currentFieldKey) {
        return (form?.fields || [])
            .filter((field) => field.key !== currentFieldKey)
            .map((field) => `<option value="${html(field.key)}">${html(field.label || field.key)}</option>`)
            .join("");
    }

    function renderVersions() {
        const node = byId("ticketFormsVersionsList");
        if (!node) {
            return;
        }
        if (!state.versions.length) {
            node.innerHTML = `<div style="color: var(--muted); font-size: 13px;">Пока сохранена только встроенная версия или список ещё не загружен.</div>`;
            return;
        }
        node.innerHTML = state.versions.map((pack) => {
            const active = state.pack && pack.version === state.pack.version;
            return `
                <div style="border: 1px solid #e5e5ea; border-radius: 12px; padding: 10px 12px; background: ${active ? "#f5fbfa" : "#fff"};">
                    <div style="display: flex; justify-content: space-between; gap: 10px; align-items: center;">
                        <div>
                            <strong>${html(pack.version || "—")}</strong>
                            ${pack.is_preferred ? '<span style="margin-left: 8px; color: #0f766e; font-weight: 700;">active</span>' : ""}
                            <div style="font-size: 12px; color: var(--muted); margin-top: 4px;">${html(pack.created_by || "system")}</div>
                        </div>
                        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                            <button type="button" class="btn btn-secondary btn-sm" data-action="load-version" data-version="${html(pack.version)}">Открыть</button>
                            <button type="button" class="btn btn-secondary btn-sm" data-action="set-preferred" data-version="${html(pack.version)}">Сделать активной</button>
                        </div>
                    </div>
                    <div style="font-size: 12px; color: var(--muted); margin-top: 8px;">${html(pack.description || pack.notes || "")}</div>
                </div>
            `;
        }).join("");
    }

    function renderFormsList() {
        const node = byId("ticketFormsFormsList");
        if (!node) {
            return;
        }
        const forms = packForms();
        if (!forms.length) {
            node.innerHTML = `<div style="color: var(--muted); font-size: 13px;">Добавьте первый тип заявки.</div>`;
            return;
        }
        node.innerHTML = forms.map((form) => {
            const active = form.key === state.selectedFormKey;
            return `
                <button
                    type="button"
                    class="btn ${active ? "btn-primary" : "btn-secondary"}"
                    style="text-align: left; display: grid; gap: 4px;"
                    data-action="select-form"
                    data-form-key="${html(form.key)}"
                >
                    <strong>${html(form.title || form.key)}</strong>
                    <span style="font-size: 12px; opacity: 0.8;">${html(form.request_kind || form.key)} · ${(form.fields || []).length} полей</span>
                </button>
            `;
        }).join("");
    }

    function renderFormEditor() {
        const node = byId("ticketFormsFormEditor");
        if (!node) {
            return;
        }
        const form = getSelectedForm();
        if (!form) {
            node.innerHTML = `<div style="color: var(--muted); font-size: 13px;">Выберите тип заявки слева.</div>`;
            return;
        }
        node.innerHTML = `
            <div class="form-group">
                <label for="ticketFormsFormKey">Системный ключ</label>
                <input type="text" id="ticketFormsFormKey" data-form-prop="key" value="${html(form.key)}" placeholder="printer">
            </div>
            <div class="form-group">
                <label for="ticketFormsFormRequestKind">ticket_type / request_kind</label>
                <input type="text" id="ticketFormsFormRequestKind" data-form-prop="request_kind" value="${html(form.request_kind)}" placeholder="printer">
            </div>
            <div class="form-group">
                <label for="ticketFormsFormTitle">Название</label>
                <input type="text" id="ticketFormsFormTitle" data-form-prop="title" value="${html(form.title)}" placeholder="Печать / принтер">
            </div>
            <div class="form-group">
                <label for="ticketFormsFormDescription">Подсказка</label>
                <textarea id="ticketFormsFormDescription" data-form-prop="description" rows="4" placeholder="Какие случаи покрывает эта форма">${html(form.description)}</textarea>
            </div>
        `;
    }

    function renderFieldsList() {
        const node = byId("ticketFormsFieldsList");
        if (!node) {
            return;
        }
        const form = getSelectedForm();
        const fields = Array.isArray(form?.fields) ? form.fields : [];
        if (!form) {
            node.innerHTML = "";
            return;
        }
        if (!fields.length) {
            node.innerHTML = `<div style="color: var(--muted); font-size: 13px;">У выбранной формы ещё нет полей.</div>`;
            return;
        }
        node.innerHTML = fields.map((field) => {
            const active = field.key === state.selectedFieldKey;
            return `
                <button
                    type="button"
                    class="btn ${active ? "btn-primary" : "btn-secondary"}"
                    style="text-align: left; display: grid; gap: 4px;"
                    data-action="select-field"
                    data-field-key="${html(field.key)}"
                >
                    <strong>${html(field.label || field.key)}</strong>
                    <span style="font-size: 12px; opacity: 0.8;">${html(field.key)} · ${html(field.type)}${field.required ? " · required" : ""}</span>
                </button>
            `;
        }).join("");
    }

    function renderFieldEditor() {
        const node = byId("ticketFormsFieldEditor");
        if (!node) {
            return;
        }
        const form = getSelectedForm();
        const field = getSelectedField();
        if (!form) {
            node.innerHTML = "";
            return;
        }
        if (!field) {
            node.innerHTML = `<div style="color: var(--muted); font-size: 13px;">Выберите поле в списке выше или добавьте новое.</div>`;
            return;
        }
        const visibleWhen = field.visible_when && typeof field.visible_when === "object" ? field.visible_when : {};
        const visibleMode = visibleWhen.equals !== undefined ? "equals" : "";
        const visibleField = String(visibleWhen.field || "");
        const visibleValue = String(visibleWhen.equals || "");
        node.innerHTML = `
            <div class="form-group">
                <label for="ticketFormsFieldKey">Ключ поля</label>
                <input type="text" id="ticketFormsFieldKey" data-field-prop="key" value="${html(field.key)}" placeholder="printer_model">
            </div>
            <div class="form-group">
                <label for="ticketFormsFieldLabel">Заголовок</label>
                <input type="text" id="ticketFormsFieldLabel" data-field-prop="label" value="${html(field.label)}" placeholder="Модель принтера">
            </div>
            <div class="form-group">
                <label for="ticketFormsFieldType">Тип</label>
                <select id="ticketFormsFieldType" data-field-prop="type">
                    ${FIELD_TYPES.map((item) => `<option value="${html(item.value)}"${item.value === field.type ? " selected" : ""}>${html(item.label)}</option>`).join("")}
                </select>
            </div>
            <div class="form-group">
                <label style="display: inline-flex; gap: 8px; align-items: center;">
                    <input type="checkbox" id="ticketFormsFieldRequired" data-field-prop="required"${field.required ? " checked" : ""}>
                    <span>Обязательное поле</span>
                </label>
            </div>
            <div class="form-group">
                <label for="ticketFormsFieldPlaceholder">Placeholder</label>
                <input type="text" id="ticketFormsFieldPlaceholder" data-field-prop="placeholder" value="${html(field.placeholder)}" placeholder="Например HP LaserJet Pro">
            </div>
            <div class="form-group">
                <label for="ticketFormsFieldHelpText">Подсказка под полем</label>
                <input type="text" id="ticketFormsFieldHelpText" data-field-prop="help_text" value="${html(field.help_text)}" placeholder="Что пользователь должен указать">
            </div>
            <div class="form-group">
                <label for="ticketFormsFieldOptions">Опции</label>
                <textarea id="ticketFormsFieldOptions" rows="5" placeholder="value | label&#10;single | У одного">${html(optionsToText(field.options))}</textarea>
                <div style="font-size: 12px; color: var(--muted); margin-top: 4px;">Нужно для типов select и radio.</div>
            </div>
            <div class="form-group">
                <label for="ticketFormsVisibleMode">Условие показа</label>
                <select id="ticketFormsVisibleMode">
                    <option value="">Всегда показывать</option>
                    <option value="equals"${visibleMode === "equals" ? " selected" : ""}>Показывать при точном значении</option>
                </select>
            </div>
            <div class="form-group">
                <label for="ticketFormsVisibleField">Зависит от поля</label>
                <select id="ticketFormsVisibleField">
                    <option value="">Выберите поле</option>
                    ${visibleWhenFieldOptions(form, field.key)}
                </select>
            </div>
            <div class="form-group">
                <label for="ticketFormsVisibleValue">Значение для показа</label>
                <input type="text" id="ticketFormsVisibleValue" value="${html(visibleValue)}" placeholder="site_down">
            </div>
        `;
        const visibleFieldNode = byId("ticketFormsVisibleField");
        if (visibleFieldNode && visibleField) {
            visibleFieldNode.value = visibleField;
        }
    }

    function renderPreview() {
        const node = byId("ticketFormsPreview");
        if (!node) {
            return;
        }
        node.value = JSON.stringify(state.pack || createBlankPack(), null, 2);
    }

    function renderPackMeta() {
        if (!state.pack) {
            return;
        }
        if (byId("ticketFormsPackTitle")) {
            byId("ticketFormsPackTitle").value = state.pack.title || "";
        }
        if (byId("ticketFormsPackVersion")) {
            byId("ticketFormsPackVersion").value = state.pack.version || "";
        }
        if (byId("ticketFormsPackDescription")) {
            byId("ticketFormsPackDescription").value = state.pack.description || "";
        }
    }

    function render() {
        ensureSelection();
        renderPackMeta();
        renderVersions();
        renderFormsList();
        renderFormEditor();
        renderFieldsList();
        renderFieldEditor();
        renderPreview();
    }

    async function loadVersions() {
        const response = await fetch(`/api/ticket_forms/packs?pack_key=${encodeURIComponent(PACK_KEY)}`, {
            headers: getAuthHeaders(),
            cache: "no-store",
        });
        const data = await responseToJson(response);
        if (!response.ok || data.status !== "ok") {
            throw new Error(data.error || "Не удалось загрузить список версий");
        }
        state.versions = Array.isArray(data.packs) ? data.packs : [];
    }

    async function loadCurrentPack(version) {
        if (state.loading) {
            return;
        }
        state.loading = true;
        setStatus("Загружаем каталог форм...", "loading");
        try {
            await ensureFragment();
            let response;
            if (version) {
                response = await fetch(`/api/ticket_forms/packs/${encodeURIComponent(PACK_KEY)}/${encodeURIComponent(version)}`, {
                    headers: getAuthHeaders(),
                    cache: "no-store",
                });
            } else {
                response = await fetch(`/api/ticket_forms/current?pack_key=${encodeURIComponent(PACK_KEY)}`, {
                    headers: getAuthHeaders(),
                    cache: "no-store",
                });
            }
            const data = await responseToJson(response);
            if (!response.ok || data.status !== "ok") {
                throw new Error(data.error || "Не удалось загрузить каталог форм");
            }
            state.pack = ensurePack(data.pack);
            await loadVersions();
            render();
            setStatus(`Каталог форм загружен: версия ${state.pack.version}`, "success");
        } catch (error) {
            console.error("ticket forms builder load failed", error);
            setStatus(error.message || "Не удалось загрузить каталог форм", "error");
        } finally {
            state.loading = false;
        }
    }

    async function savePack() {
        if (!state.pack) {
            return;
        }
        syncPackMetaFromInputs();
        setStatus("Сохраняем каталог форм...", "loading");
        try {
            const response = await fetch("/api/ticket_forms/packs/save", {
                method: "POST",
                headers: getAuthHeaders(true),
                body: JSON.stringify({
                    pack: state.pack,
                    make_preferred: byId("ticketFormsMakePreferred")?.checked !== false,
                }),
            });
            const data = await responseToJson(response);
            if (!response.ok || data.status !== "ok") {
                throw new Error((data.details && JSON.stringify(data.details)) || data.error || "Не удалось сохранить каталог");
            }
            await loadCurrentPack(state.pack.version);
            setStatus(`Версия ${state.pack.version} сохранена`, "success");
        } catch (error) {
            console.error("ticket forms builder save failed", error);
            setStatus(error.message || "Не удалось сохранить каталог", "error");
        }
    }

    async function setPreferred(version) {
        setStatus(`Делаем версию ${version} активной...`, "loading");
        try {
            const response = await fetch(`/api/ticket_forms/packs/${encodeURIComponent(PACK_KEY)}/${encodeURIComponent(version)}/preferred`, {
                method: "PATCH",
                headers: getAuthHeaders(true),
                body: JSON.stringify({}),
            });
            const data = await responseToJson(response);
            if (!response.ok || data.status !== "ok") {
                throw new Error(data.error || "Не удалось переключить активную версию");
            }
            await loadCurrentPack(version);
            setStatus(`Активная версия обновлена: ${version}`, "success");
        } catch (error) {
            console.error("ticket forms builder set preferred failed", error);
            setStatus(error.message || "Не удалось переключить активную версию", "error");
        }
    }

    function addForm() {
        state.pack = ensurePack(state.pack);
        const keys = new Set(packForms().map((form) => form.key));
        const form = createBlankForm(packForms().length + 1);
        form.key = uniqueKey(keys, form.key);
        form.request_kind = form.key;
        state.pack.forms.push(form);
        state.selectedFormKey = form.key;
        state.selectedFieldKey = "";
        render();
    }

    function deleteSelectedForm() {
        if (!state.pack || !state.selectedFormKey) {
            return;
        }
        state.pack.forms = packForms().filter((form) => form.key !== state.selectedFormKey);
        state.selectedFormKey = "";
        state.selectedFieldKey = "";
        render();
    }

    function addField() {
        const form = getSelectedForm();
        if (!form) {
            return;
        }
        const keys = new Set((form.fields || []).map((field) => field.key));
        const field = createBlankField((form.fields || []).length + 1);
        field.key = uniqueKey(keys, field.key);
        form.fields = Array.isArray(form.fields) ? form.fields : [];
        form.fields.push(field);
        state.selectedFieldKey = field.key;
        render();
    }

    function deleteSelectedField() {
        const form = getSelectedForm();
        if (!form || !state.selectedFieldKey) {
            return;
        }
        form.fields = (form.fields || []).filter((field) => field.key !== state.selectedFieldKey);
        state.selectedFieldKey = "";
        render();
    }

    function syncVisibleWhen() {
        const field = getSelectedField();
        if (!field) {
            return;
        }
        const mode = String(byId("ticketFormsVisibleMode")?.value || "");
        const sourceField = String(byId("ticketFormsVisibleField")?.value || "").trim();
        const sourceValue = String(byId("ticketFormsVisibleValue")?.value || "").trim();
        if (mode === "equals" && sourceField && sourceValue) {
            field.visible_when = {
                field: sourceField,
                equals: sourceValue,
            };
        } else {
            field.visible_when = null;
        }
        renderPreview();
    }

    function handleRootClick(event) {
        const target = event.target.closest("[data-action]");
        if (!target) {
            return;
        }
        const action = target.getAttribute("data-action");
        if (action === "select-form") {
            state.selectedFormKey = String(target.getAttribute("data-form-key") || "");
            state.selectedFieldKey = "";
            render();
            return;
        }
        if (action === "select-field") {
            state.selectedFieldKey = String(target.getAttribute("data-field-key") || "");
            render();
            return;
        }
        if (action === "add-form") {
            addForm();
            return;
        }
        if (action === "delete-form") {
            deleteSelectedForm();
            return;
        }
        if (action === "add-field") {
            addField();
            return;
        }
        if (action === "delete-field") {
            deleteSelectedField();
            return;
        }
        if (action === "load-version") {
            loadCurrentPack(String(target.getAttribute("data-version") || ""));
            return;
        }
        if (action === "set-preferred") {
            setPreferred(String(target.getAttribute("data-version") || ""));
        }
    }

    function handleRootInput(event) {
        if (!state.pack) {
            return;
        }
        const target = event.target;
        const isChangeEvent = event.type === "change";
        if (target.id === "ticketFormsPackTitle" || target.id === "ticketFormsPackVersion" || target.id === "ticketFormsPackDescription") {
            syncPackMetaFromInputs();
            renderPreview();
            return;
        }

        const form = getSelectedForm();
        if (form && target.dataset.formProp) {
            const prop = String(target.dataset.formProp || "");
            form[prop] = String(target.value || "").trim();
            if (prop === "key" && !form.request_kind) {
                form.request_kind = form.key;
            }
            if (prop === "key") {
                state.selectedFormKey = form.key;
            }
            if (isChangeEvent) {
                render();
            } else {
                renderPreview();
            }
            return;
        }

        const field = getSelectedField();
        if (field && target.dataset.fieldProp) {
            const prop = String(target.dataset.fieldProp || "");
            if (prop === "required") {
                field.required = Boolean(target.checked);
            } else {
                field[prop] = String(target.value || "").trim();
                if (prop === "key") {
                    state.selectedFieldKey = field.key;
                }
            }
            if (isChangeEvent || prop === "type" || prop === "required") {
                render();
            } else {
                renderPreview();
            }
            return;
        }

        if (field && target.id === "ticketFormsFieldOptions") {
            field.options = textToOptions(target.value);
            renderPreview();
            return;
        }

        if (field && (target.id === "ticketFormsVisibleMode" || target.id === "ticketFormsVisibleField" || target.id === "ticketFormsVisibleValue")) {
            syncVisibleWhen();
        }
    }

    async function ensureFragment() {
        const host = byId("ticket-forms-builder-host");
        if (!host) {
            return;
        }
        if (state.fragmentLoaded) {
            return;
        }
        const response = await fetch("/admin_ticket_forms_builder.html", {
            headers: getAuthHeaders(),
            cache: "no-store",
        });
        const markup = await response.text();
        if (!response.ok) {
            throw new Error("Не удалось загрузить интерфейс конструктора форм");
        }
        host.innerHTML = markup;
        if (!host.dataset.bound) {
            host.dataset.bound = "1";
            host.addEventListener("click", handleRootClick);
            host.addEventListener("input", handleRootInput);
            host.addEventListener("change", handleRootInput);
        }
        byId("ticketFormsRefreshBtn")?.addEventListener("click", () => loadCurrentPack());
        byId("ticketFormsSaveBtn")?.addEventListener("click", savePack);
        state.fragmentLoaded = true;
    }

    async function loadTab() {
        await ensureFragment();
        if (!state.pack) {
            await loadCurrentPack();
            return;
        }
        render();
    }

    function init() {
        if (state.initialized) {
            return;
        }
        state.initialized = true;
    }

    window.TicketFormsBuilderWorkbench = {
        init,
        loadTab,
    };
})();
