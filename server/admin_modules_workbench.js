(function () {
    const state = {
        initialized: false,
        catalog: [],
        selectedFamily: null,
        selectedVersion: null,
        currentDraft: null,
        selectedToolIndex: 0,
    };

    const DEFAULT_TOOL = () => ({
        tool_name: '',
        aliases: [],
        method_name: 'run',
        description: '',
        params_schema: { type: 'object', properties: {}, additionalProperties: true },
        output_schema: { type: 'object', properties: {} },
        presets: [],
        capabilities: [],
        metadata: {
            domain: 'custom',
            platforms: ['any'],
            risk_level: 'safe_read',
            requires_consent: false,
            timeout_sec: 30,
            idempotent: true,
            side_effects: false,
            allow_roles: ['admin'],
            scopes: ['custom'],
            origin: 'managed',
            tool_kind: 'diagnostic',
        },
        contract_version: '1.0.0',
        dependencies: {
            min_agent_version: null,
            required_binaries: [],
            required_python_packages: [],
            required_services: [],
            required_permissions: [],
        },
        lifecycle: 'stable',
        error_codes: [],
        artifact_types: [],
        redaction: {
            enabled: true,
            redact_headers: true,
            redact_env: true,
            redact_fields: ['authorization', 'cookie', 'token', 'password', 'secret', 'api_key'],
            allow_raw_sensitive_data: false,
        },
        resources: {
            max_runtime_sec: 30,
            max_stdout_bytes: 65536,
            max_stderr_bytes: 65536,
            max_artifact_count: 0,
            max_artifact_bytes: 0,
            max_subprocess_count: 2,
            allowed_filesystem_scope: [],
            allowed_external_hosts: [],
        },
        user_function_body: 'return {"ok": True}',
    });

    function host() {
        return document.getElementById('modules-workbench-host');
    }

    function messageEl() {
        return document.getElementById('modules-workbench-message');
    }

    function parseJsonField(value, fallback, label) {
        const raw = String(value || '').trim();
        if (!raw) {
            return fallback;
        }
        try {
            return JSON.parse(raw);
        } catch (error) {
            throw new Error(label + ': ' + error.message);
        }
    }

    function setMessage(kind, text, detailsHtml) {
        const el = messageEl();
        if (!el) {
            return;
        }
        if (!text) {
            el.innerHTML = '';
            return;
        }
        const className = kind === 'error' ? 'error-message' : kind === 'warning' ? 'preflight-warning' : 'success-message';
        el.innerHTML = `<div class="${className}" style="display:block; margin-bottom: 12px;">${escapeHtml(text)}${detailsHtml ? '<div style="margin-top:8px;">' + detailsHtml + '</div>' : ''}</div>`;
    }

    function createEmptyDraft() {
        return {
            module_name: '',
            version: '',
            module_api_version: '1.0.0',
            owner_scope: 'vendor',
            description: '',
            platforms: ['any'],
            requirements: [],
            optional_requirements: [],
            min_agent_version: null,
            entrypoint: 'module:register',
            tools: [DEFAULT_TOOL()],
            warnings: [],
            source: { files: [], manifest_json_text: '', module_py_text: '' },
        };
    }

    async function ensureReady() {
        if (state.initialized) {
            return;
        }
        const root = host();
        if (!root) {
            return;
        }
        const response = await fetch('/admin_modules_workbench.html', { headers: getAuthHeaders() });
        const html = await response.text();
        root.innerHTML = html;
        bindEvents();
        state.initialized = true;
    }

    function bindEvents() {
        document.getElementById('modules-workbench-refresh-btn')?.addEventListener('click', () => load());
        document.getElementById('modules-workbench-new-btn')?.addEventListener('click', () => {
            state.selectedFamily = null;
            state.selectedVersion = null;
            state.currentDraft = createEmptyDraft();
            state.selectedToolIndex = 0;
            setMessage('success', 'Создан новый локальный draft. Заполните поля и сохраните модуль.');
            renderEditor();
        });
        document.getElementById('modules-workbench-load-selected-btn')?.addEventListener('click', () => {
            if (!state.selectedFamily || !state.selectedVersion) {
                setMessage('warning', 'Сначала выберите семейство и версию слева.');
                return;
            }
            loadVersionDetail(state.selectedFamily, state.selectedVersion);
        });
        document.getElementById('modules-workbench-add-tool-btn')?.addEventListener('click', () => {
            if (!state.currentDraft) {
                state.currentDraft = createEmptyDraft();
            }
            state.currentDraft.tools.push(DEFAULT_TOOL());
            state.selectedToolIndex = state.currentDraft.tools.length - 1;
            renderToolTabs();
            renderToolEditor();
        });
        document.getElementById('modules-workbench-save-btn')?.addEventListener('click', () => saveDraft());
        document.getElementById('modules-workbench-set-preferred-btn')?.addEventListener('click', () => setPreferredVersion());
    }

    async function load() {
        await ensureReady();
        const list = document.getElementById('modules-workbench-list');
        if (!list) {
            return;
        }
        list.innerHTML = '<div class="loading">Загрузка реестра модулей...</div>';
        try {
            const response = await fetch('/api/modules/workbench', { headers: getAuthHeaders() });
            const data = await responseToJson(response);
            if (!response.ok || data.status !== 'ok') {
                list.innerHTML = '<div class="error-message">Не удалось загрузить модульный workbench.</div>';
                return;
            }
            state.catalog = data.modules || [];
            renderCatalog();
            if (!state.currentDraft) {
                state.currentDraft = createEmptyDraft();
                renderEditor();
            }
        } catch (error) {
            list.innerHTML = '<div class="error-message">' + escapeHtml(error.message) + '</div>';
        }
    }

    function renderCatalog() {
        const list = document.getElementById('modules-workbench-list');
        if (!list) {
            return;
        }
        if (!state.catalog.length) {
            list.innerHTML = '<div class="empty">В реестре пока нет модулей.</div>';
            return;
        }
        list.innerHTML = state.catalog.map((family) => {
            const selected = family.module_name === state.selectedFamily;
            const currentVersion = selected ? (state.selectedVersion || family.preferred_version || family.latest_version || '') : (family.preferred_version || family.latest_version || '');
            const versionsOptions = (family.versions || []).map((versionItem) => {
                const label = versionItem.version + (versionItem.is_preferred ? ' • приоритет' : '');
                return `<option value="${escapeHtml(versionItem.version)}" ${versionItem.version === currentVersion ? 'selected' : ''}>${escapeHtml(label)}</option>`;
            }).join('');
            const toolsPreview = (family.versions?.[0]?.tool_ids || []).slice(0, 4).map((toolId) => `<code>${escapeHtml(toolId)}</code>`).join(' ');
            return `
                <div class="device-item ${selected ? 'selected' : ''}" data-module-family="${escapeHtml(family.module_name)}" style="cursor: default;">
                    <div style="display:flex; justify-content:space-between; gap:8px; align-items:flex-start;">
                        <div>
                            <h3 style="margin-bottom:4px;">${escapeHtml(family.module_name)}</h3>
                            <div class="meta">
                                latest ${escapeHtml(family.latest_version || '—')} • preferred ${escapeHtml(family.preferred_version || '—')}
                            </div>
                        </div>
                        <span class="badge ${family.preferred_assigned ? 'badge-active' : 'badge-installed'}">${family.preferred_assigned ? 'manual' : 'auto'}</span>
                    </div>
                    <div style="margin-top:10px;" class="muted">${toolsPreview || '<span class="muted">нет tool ids</span>'}</div>
                    <div style="display:grid; grid-template-columns: minmax(0,1fr) auto auto; gap:8px; margin-top:12px; align-items:center;">
                        <select data-version-select="${escapeHtml(family.module_name)}">${versionsOptions}</select>
                        <button type="button" class="btn btn-secondary btn-sm" data-open-family="${escapeHtml(family.module_name)}">Открыть</button>
                        <button type="button" class="btn btn-secondary btn-sm" data-preferred-family="${escapeHtml(family.module_name)}">Приоритет</button>
                    </div>
                </div>
            `;
        }).join('');

        list.querySelectorAll('[data-open-family]').forEach((button) => {
            button.addEventListener('click', () => {
                const moduleName = button.getAttribute('data-open-family');
                const select = list.querySelector(`[data-version-select="${CSS.escape(moduleName)}"]`);
                const version = select ? select.value : '';
                state.selectedFamily = moduleName;
                state.selectedVersion = version;
                renderCatalog();
                loadVersionDetail(moduleName, version);
            });
        });
        list.querySelectorAll('[data-preferred-family]').forEach((button) => {
            button.addEventListener('click', async () => {
                const moduleName = button.getAttribute('data-preferred-family');
                const select = list.querySelector(`[data-version-select="${CSS.escape(moduleName)}"]`);
                const version = select ? select.value : '';
                state.selectedFamily = moduleName;
                state.selectedVersion = version;
                await setPreferredVersion();
            });
        });
        list.querySelectorAll('[data-version-select]').forEach((select) => {
            select.addEventListener('change', () => {
                state.selectedFamily = select.getAttribute('data-version-select');
                state.selectedVersion = select.value;
                renderCatalog();
            });
        });
    }

    async function loadVersionDetail(moduleName, version) {
        setMessage(null, '');
        try {
            const response = await fetch(`/api/modules/workbench/${encodeURIComponent(moduleName)}/${encodeURIComponent(version)}`, {
                headers: getAuthHeaders(),
            });
            const data = await responseToJson(response);
            if (!response.ok || data.status !== 'ok') {
                setMessage('error', data.error || 'Не удалось загрузить модуль.');
                return;
            }
            state.selectedFamily = moduleName;
            state.selectedVersion = version;
            state.currentDraft = data.editable_spec || createEmptyDraft();
            state.currentDraft.module_name = moduleName;
            state.currentDraft.version = version;
            state.selectedToolIndex = 0;
            renderCatalog();
            renderEditor(data.module || {});
            if (state.currentDraft.warnings?.length) {
                setMessage(
                    'warning',
                    'Часть кода не удалось автоматически разложить по полям.',
                    state.currentDraft.warnings.map((item) => escapeHtml(item)).join('<br>')
                );
            }
        } catch (error) {
            setMessage('error', error.message);
        }
    }

    function renderEditor(moduleMeta) {
        const draft = state.currentDraft || createEmptyDraft();
        document.getElementById('modules-workbench-editor-title').textContent = draft.module_name
            ? `Редактор модуля ${draft.module_name}`
            : 'Редактор модуля';
        document.getElementById('modules-workbench-editor-subtitle').textContent = draft.version
            ? `Редактируется версия ${draft.version}. Сохранение создаёт или перезаписывает server package.`
            : 'Соберите новый модуль из manifest-полей и tool-фрагментов.';
        document.getElementById('modules-workbench-selected-module').textContent = draft.module_name || '—';
        document.getElementById('modules-workbench-selected-version').textContent = draft.version || '—';
        document.getElementById('modules-workbench-selected-preferred').textContent = moduleMeta?.preferred_version || '—';

        document.getElementById('modules-workbench-module-name').value = draft.module_name || '';
        document.getElementById('modules-workbench-module-version').value = draft.version || '';
        document.getElementById('modules-workbench-module-description').value = draft.description || '';
        document.getElementById('modules-workbench-owner-scope').value = draft.owner_scope || 'vendor';
        document.getElementById('modules-workbench-module-api-version').value = draft.module_api_version || '1.0.0';
        document.getElementById('modules-workbench-entrypoint').value = draft.entrypoint || 'module:register';
        document.getElementById('modules-workbench-min-agent-version').value = draft.min_agent_version || '';
        document.getElementById('modules-workbench-platforms').value = JSON.stringify(draft.platforms || ['any'], null, 2);
        document.getElementById('modules-workbench-requirements').value = JSON.stringify({
            requirements: draft.requirements || [],
            optional_requirements: draft.optional_requirements || [],
        }, null, 2);

        renderToolTabs();
        renderToolEditor();
        renderSourceFiles();
    }

    function renderToolTabs() {
        const wrap = document.getElementById('modules-workbench-tool-tabs');
        if (!wrap) {
            return;
        }
        const tools = state.currentDraft?.tools || [];
        wrap.innerHTML = tools.map((tool, index) => `
            <button type="button" class="btn ${index === state.selectedToolIndex ? 'btn-primary' : 'btn-secondary'} btn-sm" data-tool-tab="${index}">
                ${escapeHtml(tool.tool_name || `tool_${index + 1}`)}
            </button>
        `).join('');
        wrap.querySelectorAll('[data-tool-tab]').forEach((button) => {
            button.addEventListener('click', () => {
                state.selectedToolIndex = Number(button.getAttribute('data-tool-tab') || '0');
                renderToolTabs();
                renderToolEditor();
            });
        });
    }

    function updateDraftFromTopFields() {
        if (!state.currentDraft) {
            state.currentDraft = createEmptyDraft();
        }
        state.currentDraft.module_name = document.getElementById('modules-workbench-module-name').value.trim();
        state.currentDraft.version = document.getElementById('modules-workbench-module-version').value.trim();
        state.currentDraft.description = document.getElementById('modules-workbench-module-description').value.trim();
        state.currentDraft.owner_scope = document.getElementById('modules-workbench-owner-scope').value.trim();
        state.currentDraft.module_api_version = document.getElementById('modules-workbench-module-api-version').value.trim() || '1.0.0';
        state.currentDraft.entrypoint = document.getElementById('modules-workbench-entrypoint').value.trim() || 'module:register';
        state.currentDraft.min_agent_version = document.getElementById('modules-workbench-min-agent-version').value.trim() || null;
        state.currentDraft.platforms = parseJsonField(
            document.getElementById('modules-workbench-platforms').value,
            ['any'],
            'Platforms JSON'
        );
        const requirementsPayload = parseJsonField(
            document.getElementById('modules-workbench-requirements').value,
            { requirements: [], optional_requirements: [] },
            'Requirements JSON'
        );
        state.currentDraft.requirements = Array.isArray(requirementsPayload.requirements) ? requirementsPayload.requirements : [];
        state.currentDraft.optional_requirements = Array.isArray(requirementsPayload.optional_requirements) ? requirementsPayload.optional_requirements : [];
    }

    function renderToolEditor() {
        const wrap = document.getElementById('modules-workbench-tool-editor');
        if (!wrap) {
            return;
        }
        const tool = state.currentDraft?.tools?.[state.selectedToolIndex];
        if (!tool) {
            wrap.innerHTML = '<div class="empty">Добавьте хотя бы один tool.</div>';
            return;
        }
        wrap.innerHTML = `
            <div style="display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:12px; margin-bottom:12px;">
                <div class="form-group">
                    <label for="modules-workbench-tool-name">Canonical tool id</label>
                    <input type="text" id="modules-workbench-tool-name" value="${escapeHtml(tool.tool_name || '')}" placeholder="dns.resolve">
                </div>
                <div class="form-group">
                    <label for="modules-workbench-tool-method">Method</label>
                    <input type="text" id="modules-workbench-tool-method" value="${escapeHtml(tool.method_name || '')}" placeholder="resolve_dns">
                </div>
                <div class="form-group">
                    <label for="modules-workbench-tool-contract-version">Contract version</label>
                    <input type="text" id="modules-workbench-tool-contract-version" value="${escapeHtml(tool.contract_version || '1.0.0')}" placeholder="1.0.0">
                </div>
                <div class="form-group">
                    <label for="modules-workbench-tool-lifecycle">Lifecycle</label>
                    <select id="modules-workbench-tool-lifecycle">
                        ${['experimental', 'stable', 'deprecated', 'removed'].map((item) => `<option value="${item}" ${tool.lifecycle === item ? 'selected' : ''}>${item}</option>`).join('')}
                    </select>
                </div>
            </div>
            <div class="form-group">
                <label for="modules-workbench-tool-description">Описание</label>
                <input type="text" id="modules-workbench-tool-description" value="${escapeHtml(tool.description || '')}" placeholder="Что делает этот tool">
            </div>
            <div style="display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap:12px; margin-top:12px;">
                <div class="form-group">
                    <label for="modules-workbench-tool-aliases">Aliases (JSON array)</label>
                    <textarea id="modules-workbench-tool-aliases" rows="3">${escapeHtml(JSON.stringify(tool.aliases || [], null, 2))}</textarea>
                </div>
                <div class="form-group">
                    <label for="modules-workbench-tool-error-codes">Error codes (JSON array)</label>
                    <textarea id="modules-workbench-tool-error-codes" rows="3">${escapeHtml(JSON.stringify(tool.error_codes || [], null, 2))}</textarea>
                </div>
            </div>
            <div style="display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap:12px; margin-top:12px;">
                <div class="form-group">
                    <label for="modules-workbench-tool-params-schema">Params schema (JSON object)</label>
                    <textarea id="modules-workbench-tool-params-schema" rows="10">${escapeHtml(JSON.stringify(tool.params_schema || {}, null, 2))}</textarea>
                </div>
                <div class="form-group">
                    <label for="modules-workbench-tool-output-schema">Output schema (JSON object)</label>
                    <textarea id="modules-workbench-tool-output-schema" rows="10">${escapeHtml(JSON.stringify(tool.output_schema || {}, null, 2))}</textarea>
                </div>
            </div>
            <div style="display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap:12px; margin-top:12px;">
                <div class="form-group">
                    <label for="modules-workbench-tool-metadata">Metadata (JSON object)</label>
                    <textarea id="modules-workbench-tool-metadata" rows="12">${escapeHtml(JSON.stringify(tool.metadata || {}, null, 2))}</textarea>
                </div>
                <div class="form-group">
                    <label for="modules-workbench-tool-dependencies">Dependencies (JSON object)</label>
                    <textarea id="modules-workbench-tool-dependencies" rows="12">${escapeHtml(JSON.stringify(tool.dependencies || {}, null, 2))}</textarea>
                </div>
            </div>
            <div style="display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap:12px; margin-top:12px;">
                <div class="form-group">
                    <label for="modules-workbench-tool-artifacts">Artifact types (JSON array)</label>
                    <textarea id="modules-workbench-tool-artifacts" rows="8">${escapeHtml(JSON.stringify(tool.artifact_types || [], null, 2))}</textarea>
                </div>
                <div class="form-group">
                    <label for="modules-workbench-tool-redaction">Redaction (JSON object)</label>
                    <textarea id="modules-workbench-tool-redaction" rows="8">${escapeHtml(JSON.stringify(tool.redaction || {}, null, 2))}</textarea>
                </div>
                <div class="form-group">
                    <label for="modules-workbench-tool-resources">Resources (JSON object)</label>
                    <textarea id="modules-workbench-tool-resources" rows="8">${escapeHtml(JSON.stringify(tool.resources || {}, null, 2))}</textarea>
                </div>
            </div>
            <div class="form-group" style="margin-top:12px;">
                <label for="modules-workbench-tool-code">Код tool-фрагмента</label>
                <textarea id="modules-workbench-tool-code" rows="14" placeholder="return {&quot;ok&quot;: True}">${escapeHtml(tool.user_function_body || '')}</textarea>
            </div>
        `;

        [
            'modules-workbench-tool-name',
            'modules-workbench-tool-method',
            'modules-workbench-tool-contract-version',
            'modules-workbench-tool-lifecycle',
            'modules-workbench-tool-description',
            'modules-workbench-tool-aliases',
            'modules-workbench-tool-error-codes',
            'modules-workbench-tool-params-schema',
            'modules-workbench-tool-output-schema',
            'modules-workbench-tool-metadata',
            'modules-workbench-tool-dependencies',
            'modules-workbench-tool-artifacts',
            'modules-workbench-tool-redaction',
            'modules-workbench-tool-resources',
            'modules-workbench-tool-code',
        ].forEach((id) => {
            document.getElementById(id)?.addEventListener('input', syncCurrentToolFromEditor);
            document.getElementById(id)?.addEventListener('change', syncCurrentToolFromEditor);
        });
    }

    function syncCurrentToolFromEditor() {
        try {
            updateDraftFromTopFields();
            const tool = state.currentDraft.tools[state.selectedToolIndex];
            tool.tool_name = document.getElementById('modules-workbench-tool-name').value.trim();
            tool.method_name = document.getElementById('modules-workbench-tool-method').value.trim();
            tool.contract_version = document.getElementById('modules-workbench-tool-contract-version').value.trim() || '1.0.0';
            tool.lifecycle = document.getElementById('modules-workbench-tool-lifecycle').value.trim() || 'stable';
            tool.description = document.getElementById('modules-workbench-tool-description').value.trim();
            tool.aliases = parseJsonField(document.getElementById('modules-workbench-tool-aliases').value, [], 'Aliases');
            tool.error_codes = parseJsonField(document.getElementById('modules-workbench-tool-error-codes').value, [], 'Error codes');
            tool.params_schema = parseJsonField(document.getElementById('modules-workbench-tool-params-schema').value, {}, 'Params schema');
            tool.output_schema = parseJsonField(document.getElementById('modules-workbench-tool-output-schema').value, {}, 'Output schema');
            tool.metadata = parseJsonField(document.getElementById('modules-workbench-tool-metadata').value, {}, 'Metadata');
            tool.dependencies = parseJsonField(document.getElementById('modules-workbench-tool-dependencies').value, {}, 'Dependencies');
            tool.artifact_types = parseJsonField(document.getElementById('modules-workbench-tool-artifacts').value, [], 'Artifact types');
            tool.redaction = parseJsonField(document.getElementById('modules-workbench-tool-redaction').value, {}, 'Redaction');
            tool.resources = parseJsonField(document.getElementById('modules-workbench-tool-resources').value, {}, 'Resources');
            tool.user_function_body = document.getElementById('modules-workbench-tool-code').value.trim();
            renderToolTabs();
        } catch (error) {
            setMessage('warning', error.message);
        }
    }

    function renderSourceFiles() {
        const wrap = document.getElementById('modules-workbench-source-files');
        if (!wrap) {
            return;
        }
        const files = state.currentDraft?.source?.files || [];
        if (!files.length) {
            wrap.innerHTML = '<div class="empty">Архив исходников пока не загружен.</div>';
            return;
        }
        wrap.innerHTML = files.map((file) => `
            <details style="margin-bottom: 10px;">
                <summary><code>${escapeHtml(file.path)}</code> • ${file.size_bytes} bytes</summary>
                <pre style="margin-top: 8px; max-height: 260px; overflow: auto;">${escapeHtml(file.content || '')}</pre>
            </details>
        `).join('');
    }

    async function setPreferredVersion() {
        if (!state.selectedFamily || !state.selectedVersion) {
            setMessage('warning', 'Выберите семейство и версию, которую нужно сделать приоритетной.');
            return;
        }
        try {
            const response = await fetch(`/api/modules/${encodeURIComponent(state.selectedFamily)}/preferred`, {
                method: 'PATCH',
                headers: getAuthHeaders(true),
                body: JSON.stringify({ version: state.selectedVersion }),
            });
            const data = await responseToJson(response);
            if (!response.ok || data.status !== 'ok') {
                setMessage('error', data.error || 'Не удалось назначить приоритетную версию.');
                return;
            }
            setMessage('success', `Приоритетная версия для ${state.selectedFamily} обновлена: ${state.selectedVersion}.`);
            await load();
        } catch (error) {
            setMessage('error', error.message);
        }
    }

    async function saveDraft() {
        try {
            syncCurrentToolFromEditor();
            const draft = state.currentDraft;
            if (!draft) {
                setMessage('warning', 'Нет draft для сохранения.');
                return;
            }
            const tools = (draft.tools || []).map((tool) => ({
                tool_name: tool.tool_name,
                aliases: tool.aliases || [],
                method_name: tool.method_name,
                description: tool.description,
                params_schema: tool.params_schema || {},
                output_schema: tool.output_schema || {},
                presets: tool.presets || [],
                capabilities: tool.capabilities || [],
                metadata: tool.metadata || {},
                contract_version: tool.contract_version || '1.0.0',
                dependencies: tool.dependencies || {},
                lifecycle: tool.lifecycle || 'stable',
                error_codes: tool.error_codes || [],
                artifact_types: tool.artifact_types || [],
                redaction: tool.redaction || {},
                resources: tool.resources || {},
                user_function_body: tool.user_function_body || 'return {"ok": True}',
            }));
            const payload = {
                module_name: draft.module_name,
                version: draft.version,
                description: draft.description,
                tool_name: tools[0]?.tool_name || '',
                method_name: tools[0]?.method_name || 'run',
                user_function_body: tools[0]?.user_function_body || 'return {"ok": True}',
                platforms: draft.platforms || ['any'],
                requirements: draft.requirements || [],
                optional_requirements: draft.optional_requirements || [],
                min_agent_version: draft.min_agent_version || null,
                owner_scope: draft.owner_scope || 'vendor',
                module_api_version: draft.module_api_version || '1.0.0',
                entrypoint: draft.entrypoint || 'module:register',
                tools,
                overwrite: true,
                set_preferred: true,
            };
            const response = await fetch('/api/modules/workbench/save', {
                method: 'POST',
                headers: getAuthHeaders(true),
                body: JSON.stringify(payload),
            });
            const data = await responseToJson(response);
            if (!response.ok || data.status !== 'success') {
                const details = Array.isArray(data.preflight_errors)
                    ? data.preflight_errors.map((item) => escapeHtml(item)).join('<br>')
                    : '';
                setMessage('error', data.error || 'Не удалось сохранить модуль.', details);
                return;
            }
            setMessage('success', `Модуль ${data.module_name}/${data.version} сохранён на сервере и назначен приоритетным.`);
            state.selectedFamily = data.module_name;
            state.selectedVersion = data.version;
            await load();
            await loadVersionDetail(data.module_name, data.version);
        } catch (error) {
            setMessage('error', error.message);
        }
    }

    window.ModuleWorkbench = {
        ensureReady,
        load,
    };
})();
