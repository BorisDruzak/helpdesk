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
    const KEY_HINT_REGEX = /^[a-z0-9_]+$/;
    const VIEW_MODES = ["catalog", "create", "edit"];

    const state = {
        initialized: false,
        fragmentLoaded: false,
        loading: false,
        pack: null,
        selectedFormKey: "",
        selectedFieldKey: "",
        currentView: "catalog",
        wizardStep: 1,
        draftForm: null,
        draftFieldKey: "",
        lastLoadedSignature: "",
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

    function packSignature(pack) {
        return JSON.stringify(ensurePack(pack || createBlankPack()));
    }

    function hasUnsavedChanges() {
        if (!state.pack) {
            return false;
        }
        return packSignature(state.pack) !== state.lastLoadedSignature;
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

    function fieldTypeLabel(type) {
        return FIELD_TYPES.find((item) => item.value === type)?.label || type || "Поле";
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
            title: `Новая форма ${index}`,
            description: "",
            fields: [],
        };
    }

    function createBlankField(index, type) {
        return {
            key: `field_${index}`,
            label: `Поле ${index}`,
            type: type || "text",
            required: false,
            placeholder: "",
            help_text: "",
            options: [],
            visible_when: null,
        };
    }

    function normalizeOptions(rawOptions) {
        if (!Array.isArray(rawOptions)) {
            return [];
        }
        return rawOptions
            .map((option) => ({
                value: String(option?.value || "").trim(),
                label: String(option?.label || "").trim(),
            }))
            .filter((option) => option.value && option.label);
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
                type: String(field?.type || "text").trim().toLowerCase() || "text",
                required: Boolean(field?.required),
                placeholder: String(field?.placeholder || "").trim(),
                help_text: String(field?.help_text || "").trim(),
                options: normalizeOptions(field?.options),
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

    function getDraftForm() {
        if (!state.draftForm) {
            const form = createBlankForm(packForms().length + 1);
            const existingKeys = new Set(packForms().map((item) => item.key));
            form.key = uniqueKey(existingKeys, form.key);
            form.request_kind = form.key;
            state.draftForm = form;
        }
        return state.draftForm;
    }

    function getDraftField() {
        const form = getDraftForm();
        return (form.fields || []).find((field) => field.key === state.draftFieldKey) || null;
    }

    function activeTarget() {
        return state.currentView === "create" ? "draft" : "edit";
    }

    function activeFormForView() {
        if (state.currentView === "create") {
            return getDraftForm();
        }
        if (state.currentView === "edit") {
            return getSelectedForm();
        }
        return null;
    }

    function activeFieldForView() {
        if (state.currentView === "create") {
            return getDraftField();
        }
        if (state.currentView === "edit") {
            return getSelectedField();
        }
        return null;
    }

    function syncPackMetaFromInputs() {
        if (!state.pack) {
            return;
        }
        const titleInput = byId("ticketFormsPackTitle");
        const descriptionInput = byId("ticketFormsPackDescription");
        if (titleInput) {
            state.pack.title = String(titleInput.value || "").trim() || "Каталог заявок";
        }
        if (descriptionInput) {
            state.pack.description = String(descriptionInput.value || "").trim();
        }
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

    function isConditionalField(field) {
        return Boolean(field?.visible_when && typeof field.visible_when === "object");
    }

    function formSummary(form) {
        const fields = Array.isArray(form?.fields) ? form.fields : [];
        const requiredCount = fields.filter((field) => field.required).length;
        const conditionalCount = fields.filter((field) => isConditionalField(field)).length;
        return {
            fieldsCount: fields.length,
            requiredCount,
            conditionalCount,
        };
    }

    function formIssues(form, options) {
        const existingForms = Array.isArray(options?.existingForms) ? options.existingForms : [];
        const issues = [];
        const formKey = String(form?.key || "").trim();
        const requestKind = String(form?.request_kind || "").trim();
        const title = String(form?.title || "").trim();
        const fields = Array.isArray(form?.fields) ? form.fields : [];

        if (!title) {
            issues.push("Укажите название формы.");
        }
        if (!formKey) {
            issues.push("Укажите системный ключ формы.");
        } else if (!KEY_HINT_REGEX.test(formKey)) {
            issues.push("Ключ формы лучше держать в латинице snake_case: только a-z, 0-9 и _.");
        }
        if (!requestKind) {
            issues.push("У формы должен быть request_kind. Обычно он совпадает с ключом.");
        }
        if (formKey) {
            const duplicate = existingForms.some((item) => item !== form && item.key === formKey);
            if (duplicate) {
                issues.push(`Ключ формы ${formKey} уже используется в этом каталоге.`);
            }
        }
        if (!fields.length) {
            issues.push("Добавьте хотя бы одно поле.");
        }

        const seenFieldKeys = new Set();
        fields.forEach((field, index) => {
            const fieldKey = String(field?.key || "").trim();
            const label = String(field?.label || "").trim();
            const type = String(field?.type || "text").trim();
            if (!label) {
                issues.push(`Поле ${index + 1}: укажите название.`);
            }
            if (!fieldKey) {
                issues.push(`Поле ${index + 1}: укажите системный ключ.`);
            } else {
                if (!KEY_HINT_REGEX.test(fieldKey)) {
                    issues.push(`Поле ${label || index + 1}: ключ лучше держать в латинице snake_case.`);
                }
                if (seenFieldKeys.has(fieldKey)) {
                    issues.push(`Поле ${label || fieldKey}: ключ ${fieldKey} повторяется.`);
                }
                seenFieldKeys.add(fieldKey);
            }
            if (!FIELD_TYPES.some((item) => item.value === type)) {
                issues.push(`Поле ${label || fieldKey || index + 1}: тип ${type} не поддерживается.`);
            }
            if ((type === "select" || type === "radio") && !normalizeOptions(field?.options).length) {
                issues.push(`Поле ${label || fieldKey || index + 1}: для списка и переключателей нужны варианты.`);
            }
        });
        return issues;
    }

    function visibleWhenFieldOptions(form, currentFieldKey, selectedKey) {
        return (form?.fields || [])
            .filter((field) => field.key !== currentFieldKey)
            .map((field) => `<option value="${html(field.key)}"${field.key === selectedKey ? " selected" : ""}>${html(field.label || field.key)}</option>`)
            .join("");
    }

    function renderPackMeta() {
        if (!state.pack) {
            return;
        }
        const titleInput = byId("ticketFormsPackTitle");
        const descriptionInput = byId("ticketFormsPackDescription");
        if (titleInput) {
            titleInput.value = state.pack.title || "";
        }
        if (descriptionInput) {
            descriptionInput.value = state.pack.description || "";
        }
    }

    function renderVersions() {
        // История версий остаётся внутренней серверной механикой и не показывается в обычном UI.
    }

    function renderCatalogFormsList() {
        const node = byId("ticketFormsCatalogForms");
        if (!node) {
            return;
        }
        const forms = packForms();
        if (!forms.length) {
            node.innerHTML = `
                <div class="tfb-empty">
                    Форм пока нет. Создайте первую форму в отдельном пошаговом режиме.
                    <div style="margin-top: 12px;">
                        <button type="button" class="btn btn-primary btn-sm" data-action="open-create">Создать форму</button>
                    </div>
                </div>
            `;
            return;
        }

        node.innerHTML = forms.map((form) => {
            const summary = formSummary(form);
            const active = form.key === state.selectedFormKey;
            return `
                <div class="tfb-form-card${active ? " is-active" : ""}">
                    <div class="tfb-section-head">
                        <div>
                            <strong>${html(form.title || form.key)}</strong>
                            <div class="tfb-subtle">${html(form.key)} · ${summary.fieldsCount} полей</div>
                        </div>
                        <span class="tfb-chip${summary.conditionalCount ? " is-warning" : ""}">${summary.requiredCount} обязательных</span>
                    </div>
                    <div class="tfb-subtle" style="margin-top: 8px;">${html(form.description || "Без описания формы")}</div>
                    <div class="tfb-form-actions" style="margin-top: 12px;">
                        <button type="button" class="btn btn-secondary btn-sm" data-action="select-form" data-form-key="${html(form.key)}">Выбрать</button>
                        <button type="button" class="btn btn-primary btn-sm" data-action="open-edit-form" data-form-key="${html(form.key)}">Редактировать</button>
                    </div>
                </div>
            `;
        }).join("");
    }

    function buildPreviewFields(form) {
        const fields = Array.isArray(form?.fields) ? form.fields : [];
        if (!fields.length) {
            return `<div class="tfb-empty">У формы пока нет полей.</div>`;
        }
        return fields.map((field) => `
            <div class="tfb-preview-field">
                <div class="tfb-section-head">
                    <strong>${html(field.label || field.key)}</strong>
                    <div class="tfb-preview-tags">
                        <span class="tfb-chip">${html(fieldTypeLabel(field.type))}</span>
                        ${field.required ? '<span class="tfb-chip is-accent">обязательное</span>' : ""}
                        ${isConditionalField(field) ? '<span class="tfb-chip is-warning">по условию</span>' : ""}
                    </div>
                </div>
                <div class="tfb-subtle">${html(field.key)}</div>
                ${field.help_text ? `<div class="tfb-subtle">${html(field.help_text)}</div>` : ""}
            </div>
        `).join("");
    }

    function findDuplicateFormKey(form) {
        const formKey = String(form?.key || "").trim();
        if (!formKey) {
            return "";
        }
        return packForms().some((item) => item !== form && item.key === formKey)
            ? `Ключ ${formKey} уже занят другой формой в каталоге.`
            : "";
    }

    function findDuplicateFieldKey(form, field) {
        const fieldKey = String(field?.key || "").trim();
        if (!fieldKey) {
            return "";
        }
        return (form?.fields || []).some((item) => item !== field && item.key === fieldKey)
            ? `Ключ ${fieldKey} уже занят другим полем в этой форме.`
            : "";
    }

    function buildFormBasicsMarkup(form, target) {
        const prefix = target === "draft" ? "ticketFormsDraft" : "ticketFormsEdit";
        const requestKindNote = String(form.request_kind || "").trim() === String(form.key || "").trim()
            ? "Оставьте как есть, если ticket_type должен совпадать с ключом формы."
            : "Переопределён отдельно от ключа формы.";
        const duplicateFormKey = findDuplicateFormKey(form);
        return `
            <div class="tfb-grid-2">
                <div class="form-group">
                    <label for="${prefix}FormTitle">Название формы</label>
                    <input
                        type="text"
                        id="${prefix}FormTitle"
                        data-form-target="${target}"
                        data-form-prop="title"
                        value="${html(form.title || "")}"
                        placeholder="Печать / принтер"
                    >
                    <div class="tfb-subtle" style="margin-top: 6px;">Это имя увидит пользователь при выборе типа заявки.</div>
                </div>
                <div class="form-group">
                    <label for="${prefix}FormKey">Системный ключ</label>
                    <input
                        type="text"
                        id="${prefix}FormKey"
                        data-form-target="${target}"
                        data-form-prop="key"
                        value="${html(form.key || "")}"
                        placeholder="printer"
                    >
                    <div class="tfb-subtle" style="margin-top: 6px;">Используйте латиницу и snake_case: <code>printer</code>, <code>site_system</code>.</div>
                    ${duplicateFormKey ? `<div class="error-message" style="margin-top: 8px;">${html(duplicateFormKey)}</div>` : ""}
                </div>
            </div>
            <details class="tfb-advanced">
                <summary>Расширенные настройки формы</summary>
                <div class="tfb-grid-2">
                    <div class="form-group">
                        <label for="${prefix}FormRequestKind">request_kind / ticket_type</label>
                        <input
                            type="text"
                            id="${prefix}FormRequestKind"
                            data-form-target="${target}"
                            data-form-prop="request_kind"
                            value="${html(form.request_kind || "")}"
                            placeholder="printer"
                        >
                        <div class="tfb-subtle" style="margin-top: 6px;">${html(requestKindNote)}</div>
                    </div>
                    <div class="form-group">
                        <label for="${prefix}FormDescription">Описание формы</label>
                        <textarea
                            id="${prefix}FormDescription"
                            rows="4"
                            data-form-target="${target}"
                            data-form-prop="description"
                            placeholder="Когда использовать эту форму"
                        >${html(form.description || "")}</textarea>
                    </div>
                </div>
            </details>
        `;
    }

    function buildFieldListMarkup(form, target, selectedKey) {
        const fields = Array.isArray(form?.fields) ? form.fields : [];
        if (!fields.length) {
            return `<div class="tfb-empty">Добавьте первое поле, чтобы форма стала полезной для маршрутизации.</div>`;
        }
        return fields.map((field) => `
            <button
                type="button"
                class="tfb-field-btn${field.key === selectedKey ? " is-active" : ""}"
                data-action="select-${target}-field"
                data-field-key="${html(field.key)}"
            >
                <strong>${html(field.label || field.key)}</strong>
                <div class="tfb-subtle">${html(field.key)} · ${html(fieldTypeLabel(field.type))}</div>
                <div class="tfb-preview-tags" style="margin-top: 8px;">
                    ${field.required ? '<span class="tfb-chip is-accent">обязательное</span>' : '<span class="tfb-chip">необязательное</span>'}
                    ${isConditionalField(field) ? '<span class="tfb-chip is-warning">по условию</span>' : ""}
                </div>
            </button>
        `).join("");
    }

    function buildFieldEditorMarkup(form, field, target) {
        if (!field) {
            return `<div class="tfb-empty">Выберите поле слева или добавьте новое.</div>`;
        }
        const prefix = target === "draft" ? "ticketFormsDraft" : "ticketFormsEdit";
        const visibleWhen = field.visible_when && typeof field.visible_when === "object" ? field.visible_when : {};
        const visibleMode = Object.prototype.hasOwnProperty.call(visibleWhen, "equals") ? "equals" : "";
        const visibleField = String(visibleWhen.field || "");
        const visibleValue = String(visibleWhen.equals || "");
        const needsOptions = field.type === "select" || field.type === "radio";
        const duplicateFieldKey = findDuplicateFieldKey(form, field);
        return `
            <div class="tfb-card">
                <div class="tfb-section-head">
                    <div>
                        <h4 style="margin: 0;">Параметры поля</h4>
                        <div class="tfb-subtle">На базовом пути оставляем только название, ключ, тип и обязательность.</div>
                    </div>
                    <div class="tfb-inline-actions">
                        <span class="tfb-chip">${html(fieldTypeLabel(field.type))}</span>
                        <button type="button" class="btn btn-danger btn-sm" data-action="delete-${target}-field">Удалить поле</button>
                    </div>
                </div>
                <div class="tfb-grid-2" style="margin-top: 14px;">
                    <div class="form-group">
                        <label for="${prefix}FieldLabel">Название поля</label>
                        <input
                            type="text"
                            id="${prefix}FieldLabel"
                            data-field-target="${target}"
                            data-field-prop="label"
                            value="${html(field.label || "")}"
                            placeholder="Модель принтера"
                        >
                    </div>
                    <div class="form-group">
                        <label for="${prefix}FieldKey">Системный ключ</label>
                        <input
                            type="text"
                            id="${prefix}FieldKey"
                            data-field-target="${target}"
                            data-field-prop="key"
                        value="${html(field.key || "")}"
                        placeholder="printer_model"
                    >
                    ${duplicateFieldKey ? `<div class="error-message" style="margin-top: 8px;">${html(duplicateFieldKey)}</div>` : ""}
                </div>
            </div>
                <div class="tfb-grid-2">
                    <div class="form-group">
                        <label for="${prefix}FieldType">Тип поля</label>
                        <select id="${prefix}FieldType" data-field-target="${target}" data-field-prop="type">
                            ${FIELD_TYPES.map((item) => `<option value="${html(item.value)}"${item.value === field.type ? " selected" : ""}>${html(item.label)}</option>`).join("")}
                        </select>
                    </div>
                    <div class="form-group">
                        <label style="display: inline-flex; align-items: center; gap: 8px; margin-top: 30px;">
                            <input
                                type="checkbox"
                                id="${prefix}FieldRequired"
                                data-field-target="${target}"
                                data-field-prop="required"
                                ${field.required ? " checked" : ""}
                            >
                            <span>Обязательное поле</span>
                        </label>
                    </div>
                </div>
                ${needsOptions ? `
                    <div class="form-group">
                        <label for="${prefix}FieldOptions">Варианты ответа</label>
                        <textarea
                            id="${prefix}FieldOptions"
                            rows="5"
                            data-field-target="${target}"
                            data-field-options="true"
                            placeholder="single | У одного&#10;multiple | У нескольких"
                        >${html(optionsToText(field.options))}</textarea>
                        <div class="tfb-subtle" style="margin-top: 6px;">Один вариант на строку: <code>value | label</code>.</div>
                    </div>
                ` : ""}
                <details class="tfb-advanced">
                    <summary>Расширенные настройки поля</summary>
                    <div class="tfb-grid-2">
                        <div class="form-group">
                            <label for="${prefix}FieldPlaceholder">Placeholder</label>
                            <input
                                type="text"
                                id="${prefix}FieldPlaceholder"
                                data-field-target="${target}"
                                data-field-prop="placeholder"
                                value="${html(field.placeholder || "")}"
                                placeholder="Например HP LaserJet Pro"
                            >
                        </div>
                        <div class="form-group">
                            <label for="${prefix}FieldHelpText">Подсказка под полем</label>
                            <input
                                type="text"
                                id="${prefix}FieldHelpText"
                                data-field-target="${target}"
                                data-field-prop="help_text"
                                value="${html(field.help_text || "")}"
                                placeholder="Что должен указать пользователь"
                            >
                        </div>
                    </div>
                    <div class="tfb-grid-3">
                        <div class="form-group">
                            <label for="${prefix}VisibleMode">Условие показа</label>
                            <select id="${prefix}VisibleMode" data-field-target="${target}" data-visible-prop="mode">
                                <option value="">Показывать всегда</option>
                                <option value="equals"${visibleMode === "equals" ? " selected" : ""}>Показывать при точном значении</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="${prefix}VisibleField">Зависит от поля</label>
                            <select id="${prefix}VisibleField" data-field-target="${target}" data-visible-prop="field">
                                <option value="">Выберите поле</option>
                                ${visibleWhenFieldOptions(form, field.key, visibleField)}
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="${prefix}VisibleValue">Значение для показа</label>
                            <input
                                type="text"
                                id="${prefix}VisibleValue"
                                data-field-target="${target}"
                                data-visible-prop="value"
                                value="${html(visibleValue)}"
                                placeholder="site_down"
                            >
                        </div>
                    </div>
                </details>
            </div>
        `;
    }

    function renderViewButtons() {
        return null;
    }

    function buildFormListCards(selectedKey) {
        const forms = packForms();
        if (!forms.length) {
            return `
                <div class="tfb-empty">
                    Форм пока нет. Создайте первую форму и сразу начните заполнять её поля.
                </div>
            `;
        }
        return forms.map((form) => {
            const summary = formSummary(form);
            const active = form.key === selectedKey;
            return `
                <button
                    type="button"
                    class="tfb-form-card${active ? " is-active" : ""}"
                    data-action="open-edit-form"
                    data-form-key="${html(form.key)}"
                >
                    <div class="tfb-section-head">
                        <div>
                            <strong>${html(form.title || form.key)}</strong>
                            <div class="tfb-subtle">${html(form.key)} · ${summary.fieldsCount} полей</div>
                        </div>
                        <span class="tfb-chip${summary.conditionalCount ? " is-warning" : ""}">${summary.requiredCount} обязательных</span>
                    </div>
                    <div class="tfb-subtle" style="margin-top: 8px;">${html(form.description || "Без описания формы")}</div>
                </button>
            `;
        }).join("");
    }

    function renderNavigator() {
        const node = byId("ticketFormsNavigator");
        if (!node || !state.pack) {
            return;
        }
        const forms = packForms();
        const dirty = hasUnsavedChanges();
        if (state.currentView === "catalog") {
            node.innerHTML = `
                <div class="tfb-card">
                    <div class="tfb-section-head">
                        <div>
                            <h3>Все формы</h3>
                            <div class="tfb-subtle">Нажмите на форму, чтобы сразу открыть её поля и параметры без лишних кнопок.</div>
                        </div>
                        <button type="button" class="btn btn-primary btn-sm" data-action="open-create">Новая форма</button>
                    </div>
                    <div class="tfb-summary-grid" style="margin-top: 14px;">
                        <div class="tfb-summary-item">
                            <label>Форм</label>
                            <strong>${forms.length}</strong>
                        </div>
                        <div class="tfb-summary-item">
                            <label>Сохранение</label>
                            <strong>${dirty ? "есть изменения" : "всё сохранено"}</strong>
                        </div>
                        <div class="tfb-summary-item">
                            <label>Каталог</label>
                            <strong>один рабочий</strong>
                        </div>
                    </div>
                </div>
                <div class="tfb-side-card" style="min-height: 0;">
                    <div class="tfb-section-head">
                        <div>
                            <h3 style="margin: 0;">Список форм</h3>
                            <div class="tfb-subtle">Левая колонка прокручивается отдельно, поэтому рабочая область не прыгает по высоте.</div>
                        </div>
                    </div>
                    <div class="tfb-scroll-stack" style="margin-top: 12px;">
                        ${buildFormListCards(state.selectedFormKey)}
                    </div>
                </div>
            `;
            return;
        }

        const form = activeFormForView();
        if (!form) {
            node.innerHTML = `
                <div class="tfb-card">
                    <div class="tfb-inline-note">
                        Вернитесь ко всем формам или создайте новую форму, чтобы продолжить работу.
                    </div>
                </div>
            `;
            return;
        }
        const target = activeTarget();
        const selectedFieldKey = target === "draft" ? state.draftFieldKey : state.selectedFieldKey;
        const summary = formSummary(form);
        node.innerHTML = `
            <div class="tfb-card">
                <div class="tfb-header-actions">
                    <button type="button" class="btn btn-secondary btn-sm" data-action="open-forms-catalog">Все формы</button>
                    ${state.currentView === "edit"
                        ? '<button type="button" class="btn btn-secondary btn-sm" data-action="open-create">Новая форма</button>'
                        : '<button type="button" class="btn btn-secondary btn-sm" data-action="reset-draft-form">Сбросить черновик</button>'}
                </div>
                <div style="margin-top: 12px;">
                    <h3 style="margin: 0 0 6px;">${html(form?.title || "Новая форма")}</h3>
                    <div class="tfb-subtle">${html(form?.key || "Ключ формы ещё не заполнен")}</div>
                </div>
                <div class="tfb-preview-tags" style="margin-top: 12px;">
                    <span class="tfb-chip is-info">${state.currentView === "create" ? "Создание" : "Редактирование"}</span>
                    <span class="tfb-chip">${summary.fieldsCount} полей</span>
                    <span class="tfb-chip is-accent">${summary.requiredCount} обязательных</span>
                </div>
                <div class="tfb-inline-note" style="margin-top: 12px;">
                    После выбора формы слева показываются её поля. Нажмите на поле, и его параметры откроются справа.
                </div>
            </div>

            <div class="tfb-side-card" style="min-height: 0;">
                <div class="tfb-section-head">
                    <div>
                        <h3 style="margin: 0;">Поля формы</h3>
                        <div class="tfb-subtle">Добавляйте поле через раскрывающийся список, потом сразу редактируйте его параметры справа.</div>
                    </div>
                </div>
                <details class="tfb-add-menu">
                    <summary>Добавить поле</summary>
                    <div class="tfb-add-menu-grid">
                        ${FIELD_TYPES.map((item) => `
                            <button
                                type="button"
                                class="btn btn-secondary btn-sm"
                                data-action="add-current-field"
                                data-field-type="${html(item.value)}"
                            >
                                ${html(item.label)}
                            </button>
                        `).join("")}
                    </div>
                </details>
                <div class="tfb-scroll-stack" style="margin-top: 12px;">
                    ${buildFieldListMarkup(form, target, selectedFieldKey)}
                </div>
            </div>
        `;
    }

    function renderPrimaryPanel() {
        const node = byId("ticketFormsPrimaryPanel");
        if (!node || !state.pack) {
            return;
        }
        if (state.currentView === "catalog") {
            const selectedForm = getSelectedForm() || packForms()[0] || null;
            const selectedSummary = selectedForm ? formSummary(selectedForm) : { fieldsCount: 0, requiredCount: 0, conditionalCount: 0 };
            node.innerHTML = `
                <div class="tfb-doc-card">
                    <h3>Как теперь устроен экран</h3>
                    <ul class="tfb-doc-list">
                        <li>В системе один рабочий каталог, поэтому основной сценарий строится вокруг форм, а не вокруг настроек каталога.</li>
                        <li>Список форм и рабочая область живут в одном окне и имеют согласованную высоту.</li>
                        <li>Из списка форм вы сразу проваливаетесь в поля и параметры, без кнопок «выбрать» и «редактировать».</li>
                    </ul>
                </div>
                ${selectedForm ? `
                    <div class="tfb-preview-card">
                        <div class="tfb-section-head">
                            <div>
                                <h3>Выбранная форма</h3>
                                <div class="tfb-subtle">${html(selectedForm.description || "Описание формы пока не заполнено.")}</div>
                            </div>
                            <div class="tfb-preview-tags">
                                <span class="tfb-chip">${selectedSummary.fieldsCount} полей</span>
                                <span class="tfb-chip is-accent">${selectedSummary.requiredCount} обязательных</span>
                                ${selectedSummary.conditionalCount ? `<span class="tfb-chip is-warning">${selectedSummary.conditionalCount} по условию</span>` : ""}
                            </div>
                        </div>
                        <div class="tfb-grid-2" style="margin-top: 14px;">
                            ${buildPreviewFields(selectedForm)}
                        </div>
                        <div class="tfb-header-actions" style="margin-top: 14px;">
                            <button type="button" class="btn btn-primary btn-sm" data-action="open-edit-form" data-form-key="${html(selectedForm.key)}">Открыть форму</button>
                            <button type="button" class="btn btn-secondary btn-sm" data-action="open-create">Создать новую форму</button>
                        </div>
                    </div>
                ` : `
                    <div class="tfb-empty">
                        Каталог пуст. Создайте первую форму, и она сразу откроется в рабочей области.
                    </div>
                `}
            `;
            return;
        }

        const form = activeFormForView();
        if (!form) {
            node.innerHTML = `
                <div class="tfb-empty">
                    Форма не выбрана. Вернитесь ко всем формам или создайте новую.
                </div>
            `;
            return;
        }
        const target = activeTarget();
        const summary = formSummary(form);
        const issues = formIssues(form, { existingForms: packForms() });
        node.innerHTML = `
            <div class="tfb-card">
                <div class="tfb-section-head">
                    <div>
                        <h3>${state.currentView === "create" ? "Новая форма" : "Основные параметры формы"}</h3>
                        <div class="tfb-subtle">
                            ${state.currentView === "create"
                                ? "Сначала задайте название и ключ, затем добавьте поля слева. После сохранения каталог сразу станет активным."
                                : "Здесь живут основные параметры формы. Поля и их детальная настройка вынесены в соседние колонки, чтобы всё помещалось на один экран."}
                        </div>
                    </div>
                    <div class="tfb-preview-tags">
                        <span class="tfb-chip is-info">${state.currentView === "create" ? "Шаг 1: форма" : "Форма"}</span>
                        <span class="tfb-chip">${summary.fieldsCount} полей</span>
                        ${state.currentView === "edit"
                            ? '<button type="button" class="btn btn-danger btn-sm" data-action="delete-form">Удалить форму</button>'
                            : ""}
                    </div>
                </div>
                <div class="tfb-doc-card" style="margin-top: 14px;">
                    <h3 style="margin-bottom: 8px;">Базовый путь</h3>
                    <ul class="tfb-doc-list">
                        <li>Название формы должно быть понятным человеку, который создаёт заявку.</li>
                        <li>Ключ формы и ключи полей нужны для маршрутизации, аналитики и API, поэтому они должны быть уникальными.</li>
                        <li>Сложные вещи вроде <code>request_kind</code> и условного показа спрятаны в расширенных настройках.</li>
                    </ul>
                </div>
                <div style="margin-top: 14px;">
                    ${buildFormBasicsMarkup(form, target)}
                </div>
            </div>

            ${issues.length ? `
                <div class="tfb-card">
                    <h3 style="margin-bottom: 8px;">Что ещё стоит поправить</h3>
                    <ul class="tfb-issues-list">
                        ${issues.map((issue) => `<li>${html(issue)}</li>`).join("")}
                    </ul>
                    ${state.currentView === "create" ? `
                        <div class="tfb-header-actions" style="margin-top: 14px;">
                            <button type="button" class="btn btn-primary" data-action="commit-draft-form" disabled>Добавить форму в каталог</button>
                        </div>
                    ` : ""}
                </div>
            ` : `
                <div class="tfb-doc-card">
                    <h3 style="margin-bottom: 8px;">Форма выглядит целостно</h3>
                    <div class="tfb-subtle">
                        ${state.currentView === "create"
                            ? "Форма готова к добавлению в каталог. Сначала добавьте её в рабочий список, потом сохраните изменения каталога одной кнопкой."
                            : "Когда структура готова, просто нажмите «Сохранить изменения». Сервер сам выпустит новую активную редакцию без видимых версий в интерфейсе."}
                    </div>
                    ${state.currentView === "create" ? `
                        <div class="tfb-header-actions" style="margin-top: 14px;">
                            <button type="button" class="btn btn-primary" data-action="commit-draft-form">Добавить форму в каталог</button>
                        </div>
                    ` : ""}
                </div>
            `}

            <div class="tfb-preview-card">
                <div class="tfb-section-head">
                    <div>
                        <h3>Как форма выглядит сейчас</h3>
                        <div class="tfb-subtle">${html(form.description || "Описание формы пока не заполнено.")}</div>
                    </div>
                    <div class="tfb-preview-tags">
                        <span class="tfb-chip">${summary.fieldsCount} полей</span>
                        <span class="tfb-chip is-accent">${summary.requiredCount} обязательных</span>
                    </div>
                </div>
                <div class="tfb-grid-2" style="margin-top: 14px;">
                    ${buildPreviewFields(form)}
                </div>
            </div>
        `;
    }

    function renderSecondaryPanel() {
        const node = byId("ticketFormsSecondaryPanel");
        if (!node || !state.pack) {
            return;
        }
        const dirty = hasUnsavedChanges();
        if (state.currentView === "catalog") {
            const selectedForm = getSelectedForm() || packForms()[0] || null;
            const packPreview = JSON.stringify(state.pack, null, 2);
            node.innerHTML = `
                <div class="tfb-side-card">
                    <div class="tfb-section-head">
                        <div>
                            <h3>Публикация</h3>
                            <div class="tfb-subtle">Сохранение всегда делает текущий каталог активным. Никаких ручных версий или переключателей в обычной работе больше нет.</div>
                        </div>
                        <span class="tfb-chip ${dirty ? "is-warning" : "is-accent"}">${dirty ? "есть изменения" : "всё сохранено"}</span>
                    </div>
                    <div class="tfb-inline-note" style="margin-top: 12px;">
                        Название и описание каталога сейчас не обязательны для ежедневной работы, потому что в системе используется один рабочий каталог обращений.
                    </div>
                </div>

                <div class="tfb-side-card">
                    <h3>Служебные настройки каталога</h3>
                    <div class="tfb-service-note">
                        Эти поля оставлены только как задел на масштабирование: отдельные порталы, филиалы или разные витрины форм. Пока интерфейс не заставляет вас думать об этом в ежедневном сценарии.
                    </div>
                    <details class="tfb-advanced">
                        <summary>Открыть служебные настройки</summary>
                        <div class="form-group">
                            <label for="ticketFormsPackTitle">Название каталога</label>
                            <input type="text" id="ticketFormsPackTitle" placeholder="Каталог заявок">
                        </div>
                        <div class="form-group" style="margin-top: 12px;">
                            <label for="ticketFormsPackDescription">Описание каталога</label>
                            <textarea id="ticketFormsPackDescription" rows="5" placeholder="Служебное описание каталога"></textarea>
                        </div>
                    </details>
                </div>

                <div class="tfb-preview-card">
                    <h3>Технический preview</h3>
                    <div class="tfb-subtle" style="margin-bottom: 12px;">
                        Оставлен внизу как расширенный контроль для проверки структуры перед публикацией.
                    </div>
                    <details class="tfb-advanced">
                        <summary>JSON preview каталога</summary>
                        <pre class="tfb-code">${html(packPreview)}</pre>
                    </details>
                </div>

                ${selectedForm ? `
                    <div class="tfb-doc-card">
                        <h3>Сейчас выбрана форма</h3>
                        <div class="tfb-subtle">${html(selectedForm.title || selectedForm.key)}</div>
                    </div>
                ` : ""}
            `;
            return;
        }

        const form = activeFormForView();
        if (!form) {
            node.innerHTML = `
                <div class="tfb-empty">
                    Выберите форму, чтобы открыть параметры её полей.
                </div>
            `;
            return;
        }
        const target = activeTarget();
        const field = activeFieldForView();
        node.innerHTML = `
            <div class="tfb-side-card">
                <div class="tfb-section-head">
                    <div>
                        <h3>Параметры поля</h3>
                        <div class="tfb-subtle">Базовые настройки поля всегда видны сразу. Всё сложное спрятано в расширенных настройках внутри карточки.</div>
                    </div>
                    <span class="tfb-chip is-info">${field ? fieldTypeLabel(field.type) : "поле не выбрано"}</span>
                </div>
                <div style="margin-top: 14px;">
                    ${buildFieldEditorMarkup(form, field, target)}
                </div>
            </div>

            <div class="tfb-doc-card">
                <h3>Как читать этот экран</h3>
                <ul class="tfb-doc-list">
                    <li>Слева выбирается форма или поле.</li>
                    <li>В центре остаются только основные параметры формы.</li>
                    <li>Справа редактируется выбранное поле, поэтому экран не расползается вниз.</li>
                </ul>
            </div>
        `;
    }

    function renderCreateView() {
        return null;
    }

    function renderEditView() {
        return null;
    }

    function render() {
        ensureSelection();
        renderNavigator();
        renderPrimaryPanel();
        renderSecondaryPanel();
        renderPackMeta();
    }

    async function loadVersions() {
        return null;
    }

    async function loadCurrentPack(version) {
        if (state.loading) {
            return;
        }
        state.loading = true;
        setStatus("Загружаем каталог форм...", "loading");
        try {
            await ensureFragment();
            const response = await fetch(
                version
                    ? `/api/ticket_forms/packs/${encodeURIComponent(PACK_KEY)}/${encodeURIComponent(version)}`
                    : `/api/ticket_forms/current?pack_key=${encodeURIComponent(PACK_KEY)}`,
                {
                    headers: getAuthHeaders(),
                    cache: "no-store",
                }
            );
            const data = await responseToJson(response);
            if (!response.ok || data.status !== "ok") {
                throw new Error(data.error || "Не удалось загрузить каталог форм");
            }
            state.pack = ensurePack(data.pack);
            state.lastLoadedSignature = packSignature(state.pack);
            if (!state.currentView || !VIEW_MODES.includes(state.currentView)) {
                state.currentView = "catalog";
            }
            render();
            setStatus("Каталог форм загружен.", "success");
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
        setStatus("Сохраняем изменения каталога...", "loading");
        try {
            const payloadPack = clone(state.pack);
            delete payloadPack.version;
            const response = await fetch("/api/ticket_forms/packs/save", {
                method: "POST",
                headers: getAuthHeaders(true),
                body: JSON.stringify({
                    pack: payloadPack,
                    auto_publish: true,
                }),
            });
            const data = await responseToJson(response);
            if (!response.ok || data.status !== "ok") {
                throw new Error((data.details && JSON.stringify(data.details)) || data.error || "Не удалось сохранить каталог");
            }
            await loadCurrentPack();
            setStatus("Изменения сохранены и уже стали активными.", "success");
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

    function setCurrentView(view) {
        if (!VIEW_MODES.includes(view)) {
            return;
        }
        state.currentView = view;
        if (view === "create") {
            getDraftForm();
        }
        render();
    }

    function setWizardStep(step) {
        state.wizardStep = Math.max(1, Math.min(3, Number(step) || 1));
        render();
    }

    function startDraftForm() {
        state.draftForm = null;
        state.draftFieldKey = "";
        state.wizardStep = 1;
        getDraftForm();
        render();
    }

    function commitDraftForm() {
        const draft = ensurePack({ forms: [getDraftForm()] }).forms[0];
        const issues = formIssues(draft, { existingForms: packForms() });
        if (issues.length) {
            setStatus(issues[0], "error");
            return;
        }
        state.pack.forms.push(draft);
        state.selectedFormKey = draft.key;
        state.selectedFieldKey = draft.fields[0]?.key || "";
        state.draftForm = null;
        state.draftFieldKey = "";
        state.currentView = "edit";
        render();
        setStatus("Форма добавлена в каталог. Теперь сохраните изменения, чтобы она сразу стала активной.", "success");
    }

    function addField(target, type) {
        const form = target === "draft" ? getDraftForm() : getSelectedForm();
        if (!form) {
            return;
        }
        form.fields = Array.isArray(form.fields) ? form.fields : [];
        const existingKeys = new Set(form.fields.map((field) => field.key));
        const field = createBlankField(form.fields.length + 1, type || "text");
        field.key = uniqueKey(existingKeys, field.key);
        if ((type || "text") === "select" || (type || "text") === "radio") {
            field.options = [{ value: "option_1", label: "Вариант 1" }];
        }
        form.fields.push(field);
        if (target === "draft") {
            state.draftFieldKey = field.key;
        } else {
            state.selectedFieldKey = field.key;
        }
        render();
    }

    function deleteField(target) {
        const form = target === "draft" ? getDraftForm() : getSelectedForm();
        if (!form) {
            return;
        }
        const currentKey = target === "draft" ? state.draftFieldKey : state.selectedFieldKey;
        if (!currentKey) {
            return;
        }
        form.fields = (form.fields || []).filter((field) => field.key !== currentKey);
        if (target === "draft") {
            state.draftFieldKey = form.fields[0]?.key || "";
        } else {
            state.selectedFieldKey = form.fields[0]?.key || "";
        }
        render();
    }

    function deleteSelectedForm() {
        if (!state.pack || !state.selectedFormKey) {
            return;
        }
        state.pack.forms = packForms().filter((form) => form.key !== state.selectedFormKey);
        state.selectedFormKey = state.pack.forms[0]?.key || "";
        state.selectedFieldKey = state.pack.forms[0]?.fields?.[0]?.key || "";
        state.currentView = state.pack.forms.length ? "catalog" : "create";
        render();
        setStatus("Форма удалена из черновика каталога. Сохраните изменения, чтобы обновить активный каталог.", "success");
    }

    function selectField(target, key) {
        if (target === "draft") {
            state.draftFieldKey = key;
        } else {
            state.selectedFieldKey = key;
        }
        render();
    }

    function workingForm(target) {
        return target === "draft" ? getDraftForm() : getSelectedForm();
    }

    function workingField(target) {
        return target === "draft" ? getDraftField() : getSelectedField();
    }

    function syncVisibleWhen(target) {
        const field = workingField(target);
        const prefix = target === "draft" ? "ticketFormsDraft" : "ticketFormsEdit";
        if (!field) {
            return;
        }
        const mode = String(byId(`${prefix}VisibleMode`)?.value || "");
        const sourceField = String(byId(`${prefix}VisibleField`)?.value || "").trim();
        const sourceValue = String(byId(`${prefix}VisibleValue`)?.value || "").trim();
        if (mode === "equals" && sourceField && sourceValue) {
            field.visible_when = {
                field: sourceField,
                equals: sourceValue,
            };
        } else {
            field.visible_when = null;
        }
    }

    function updateFormProp(target, prop, rawValue) {
        const form = workingForm(target);
        if (!form) {
            return;
        }
        const value = String(rawValue || "").trim();
        if (prop === "key") {
            const prevKey = form.key;
            form.key = value;
            if (!String(form.request_kind || "").trim() || String(form.request_kind || "").trim() === String(prevKey || "").trim()) {
                form.request_kind = value;
            }
            if (target === "edit" && state.selectedFormKey === prevKey) {
                state.selectedFormKey = value;
            }
            return;
        }
        form[prop] = value;
    }

    function updateFieldProp(target, prop, rawValue, checked) {
        const field = workingField(target);
        if (!field) {
            return;
        }
        if (prop === "required") {
            field.required = Boolean(checked);
            return;
        }
        const value = String(rawValue || "").trim();
        if (prop === "key") {
            const prevKey = field.key;
            field.key = value;
            if (target === "edit" && state.selectedFieldKey === prevKey) {
                state.selectedFieldKey = value;
            }
            if (target === "draft" && state.draftFieldKey === prevKey) {
                state.draftFieldKey = value;
            }
            return;
        }
        field[prop] = value;
        if (prop === "type") {
            if (value !== "select" && value !== "radio") {
                field.options = [];
            } else if (!normalizeOptions(field.options).length) {
                field.options = [{ value: "option_1", label: "Вариант 1" }];
            }
        }
    }

    function handleRootClick(event) {
        const viewButton = event.target.closest("[data-view]");
        if (viewButton) {
            setCurrentView(String(viewButton.getAttribute("data-view") || "catalog"));
            return;
        }

        const target = event.target.closest("[data-action]");
        if (!target) {
            return;
        }
        const action = target.getAttribute("data-action");
        if (action === "select-form") {
            state.selectedFormKey = String(target.getAttribute("data-form-key") || "");
            state.currentView = "edit";
            render();
            return;
        }
        if (action === "open-edit-form") {
            state.selectedFormKey = String(target.getAttribute("data-form-key") || state.selectedFormKey);
            state.currentView = "edit";
            render();
            return;
        }
        if (action === "open-forms-catalog") {
            state.currentView = "catalog";
            render();
            return;
        }
        if (action === "open-create") {
            state.currentView = "create";
            state.wizardStep = 1;
            state.draftForm = null;
            state.draftFieldKey = "";
            getDraftForm();
            render();
            return;
        }
        if (action === "reset-draft-form") {
            startDraftForm();
            return;
        }
        if (action === "commit-draft-form") {
            commitDraftForm();
            return;
        }
        if (action === "delete-form") {
            deleteSelectedForm();
            return;
        }
        if (action === "add-edit-field") {
            addField("edit", String(target.getAttribute("data-field-type") || "text"));
            return;
        }
        if (action === "add-draft-field") {
            addField("draft", String(target.getAttribute("data-field-type") || "text"));
            return;
        }
        if (action === "add-current-field") {
            addField(activeTarget(), String(target.getAttribute("data-field-type") || "text"));
            return;
        }
        if (action === "delete-edit-field") {
            deleteField("edit");
            return;
        }
        if (action === "delete-draft-field") {
            deleteField("draft");
            return;
        }
        if (action === "select-edit-field") {
            selectField("edit", String(target.getAttribute("data-field-key") || ""));
            return;
        }
        if (action === "select-draft-field") {
            selectField("draft", String(target.getAttribute("data-field-key") || ""));
            return;
        }
        if (action === "wizard-prev") {
            setWizardStep(state.wizardStep - 1);
            return;
        }
        if (action === "wizard-next") {
            setWizardStep(state.wizardStep + 1);
            return;
        }
        if (action === "set-wizard-step") {
            setWizardStep(target.getAttribute("data-step"));
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
        const target = event.target;
        const isChangeEvent = event.type === "change";

        if (target.id === "ticketFormsPackTitle" || target.id === "ticketFormsPackDescription") {
            syncPackMetaFromInputs();
            if (isChangeEvent) {
                render();
            }
            return;
        }

        if (target.dataset.formProp) {
            updateFormProp(String(target.dataset.formTarget || ""), String(target.dataset.formProp || ""), target.value);
            if (isChangeEvent) {
                render();
            }
            return;
        }

        if (target.dataset.fieldProp) {
            updateFieldProp(
                String(target.dataset.fieldTarget || ""),
                String(target.dataset.fieldProp || ""),
                target.value,
                target.checked
            );
            if (isChangeEvent) {
                render();
            }
            return;
        }

        if (target.dataset.fieldOptions === "true") {
            const field = workingField(String(target.dataset.fieldTarget || ""));
            if (field) {
                field.options = textToOptions(target.value);
                if (isChangeEvent) {
                    render();
                }
            }
            return;
        }

        if (target.dataset.visibleProp) {
            syncVisibleWhen(String(target.dataset.fieldTarget || ""));
            if (isChangeEvent) {
                render();
            }
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
