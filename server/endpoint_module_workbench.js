(function () {
    "use strict";

    const API_ROOT = "/api/web/admin/endpoint-modules";
    const CAPABILITIES = {
        "dns.resolve": "DNS resolve",
        "network.ping": "Network ping",
        "tcp.connect": "TCP connect",
    };
    const state = {
        initialized: false,
        modules: [],
        message: "",
        messageKind: "",
    };

    const shared = window.PcClientWebShared;
    const html = shared?.escapeHtml || ((value) => String(value ?? ""));
    const headers = (json) => shared?.authHeaders?.(json) || (json ? { "Content-Type": "application/json" } : {});

    function host() {
        return document.getElementById("endpoint-module-workbench-host");
    }

    function defaultDraft() {
        return {
            moduleKey: "network.basic.check",
            displayName: "Network basic check",
            version: "1.0.0",
            platforms: ["linux_amd64", "windows_amd64"],
            inputs: [{ name: "target", valueType: "string" }],
            steps: [
                { stepId: "dns", capability: "dns.resolve", targetInput: "target" },
                { stepId: "ping", capability: "network.ping", targetInput: "target" },
                { stepId: "tcp", capability: "tcp.connect", targetInput: "target" },
            ],
        };
    }

    function setMessage(kind, message) {
        state.messageKind = kind || "";
        state.message = message || "";
        render();
    }

    function inputRows(draft) {
        return draft.inputs.map((input, index) => `
            <div class="endpoint-module-row" data-endpoint-input-row="${index}">
                <label>Имя <input data-endpoint-input-name value="${html(input.name)}" maxlength="64" required></label>
                <label>Тип
                    <select data-endpoint-input-type>
                        <option value="string" ${input.valueType === "string" ? "selected" : ""}>string</option>
                        <option value="integer" ${input.valueType === "integer" ? "selected" : ""}>integer</option>
                    </select>
                </label>
                <button class="btn btn-secondary btn-sm" type="button" data-endpoint-remove-input="${index}">Удалить</button>
            </div>`).join("");
    }

    function stepRows(draft) {
        const targetInputs = draft.inputs.filter((item) => item.valueType === "string");
        const targetOptions = targetInputs.map((item) => `<option value="${html(item.name)}">${html(item.name)}</option>`).join("");
        return draft.steps.map((step, index) => `
            <article class="endpoint-module-step" data-endpoint-step-row="${index}">
                <div class="endpoint-module-row">
                    <label>Шаг <input data-endpoint-step-id value="${html(step.stepId)}" maxlength="64" required></label>
                    <label>Разрешённая capability
                        <select data-endpoint-step-capability>
                            ${Object.entries(CAPABILITIES).map(([key, label]) => `<option value="${key}" ${step.capability === key ? "selected" : ""}>${label}</option>`).join("")}
                        </select>
                    </label>
                    <label>Источник target
                        <select data-endpoint-step-target required>
                            ${targetOptions || '<option value="">Добавьте string input</option>'}
                        </select>
                    </label>
                    <button class="btn btn-secondary btn-sm" type="button" data-endpoint-remove-step="${index}">Удалить</button>
                </div>
                <p class="muted-text">Параметры capability создаются из фиксированной allowlist: target из input; family=any, count=3, timeout_ms=1000, port=443. Пользовательский код и произвольные команды не поддерживаются.</p>
            </article>`).join("");
    }

    function moduleRows() {
        if (!state.modules.length) {
            return '<tr><td colspan="4" class="muted-text">Авторитетный каталог Endpoint пока пуст или недоступен.</td></tr>';
        }
        return state.modules.map((item) => {
            const key = html(item.module_key);
            const version = html(item.version || "—");
            const stateLabel = html(item.state || "unknown");
            const actions = item.version ? `
                <button class="btn btn-secondary btn-sm" type="button" data-endpoint-action="validate" data-module-key="${key}" data-module-version="${version}">Validate</button>
                <button class="btn btn-primary btn-sm" type="button" data-endpoint-action="publish" data-module-key="${key}" data-module-version="${version}" ${item.state === "published" ? "disabled" : ""}>Publish</button>
                <button class="btn btn-secondary btn-sm" type="button" data-endpoint-action="deprecate" data-module-key="${key}" data-module-version="${version}" ${item.state === "deprecated" ? "disabled" : ""}>Deprecate</button>` : "—";
            return `<tr><td><code>${key}</code></td><td>${html(item.display_name)}</td><td>${version}<br><span class="endpoint-module-state">${stateLabel}</span></td><td class="endpoint-module-actions">${actions}</td></tr>`;
        }).join("");
    }

    function render(draft) {
        const root = host();
        if (!root) return;
        const current = draft || readDraft() || defaultDraft();
        root.innerHTML = `
            <style>
                .endpoint-module-workbench { display: grid; gap: 16px; }
                .endpoint-module-workbench .endpoint-module-card { background: #fff; border: 1px solid #dbe3ec; border-radius: 12px; padding: 16px; }
                .endpoint-module-workbench .endpoint-module-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
                .endpoint-module-workbench .endpoint-module-row { display: flex; gap: 10px; align-items: end; flex-wrap: wrap; margin: 8px 0; }
                .endpoint-module-workbench .endpoint-module-row label { display: grid; gap: 4px; min-width: 150px; font-size: 13px; }
                .endpoint-module-workbench .endpoint-module-step { border-top: 1px solid #e5e7eb; padding-top: 8px; margin-top: 8px; }
                .endpoint-module-workbench .endpoint-module-actions { display: flex; gap: 6px; flex-wrap: wrap; }
                .endpoint-module-workbench .endpoint-module-message { border-radius: 8px; padding: 10px; background: #eff6ff; color: #1e3a8a; }
                .endpoint-module-workbench .endpoint-module-message.error { background: #fef2f2; color: #991b1b; }
                .endpoint-module-workbench .endpoint-module-message.success { background: #ecfdf5; color: #065f46; }
                .endpoint-module-workbench .endpoint-module-state { font-size: 12px; color: #475569; }
                .endpoint-module-workbench table { width: 100%; border-collapse: collapse; }
                .endpoint-module-workbench th, .endpoint-module-workbench td { padding: 9px; border-bottom: 1px solid #e5e7eb; text-align: left; vertical-align: top; }
            </style>
            <div class="endpoint-module-workbench">
                <section class="endpoint-module-card">
                    <h2>Endpoint Recipe modules</h2>
                    <p class="muted-text">Декларативные рецепты исполняются Endpoint Platform. Helpdesk отправляет только BFF-команды и не хранит recipe source, capability-реализации или секреты.</p>
                    ${state.message ? `<div class="endpoint-module-message ${html(state.messageKind)}" role="status">${html(state.message)}</div>` : ""}
                </section>
                <section class="endpoint-module-card">
                    <div class="section-header"><h3>Создать draft версии</h3><button class="btn btn-secondary btn-sm" type="button" id="endpoint-module-reset">Сбросить форму</button></div>
                    <form id="endpoint-module-create-form">
                        <div class="endpoint-module-grid">
                            <label>Module key <input id="endpoint-module-key" value="${html(current.moduleKey)}" placeholder="network.basic.check" required></label>
                            <label>Display name <input id="endpoint-module-name" value="${html(current.displayName)}" maxlength="128" required></label>
                            <label>Version <input id="endpoint-module-version" value="${html(current.version)}" placeholder="1.0.0" required></label>
                        </div>
                        <fieldset><legend>Платформы</legend>
                            <label><input type="checkbox" data-endpoint-platform="linux_amd64" ${current.platforms.includes("linux_amd64") ? "checked" : ""}> Linux AMD64</label>
                            <label><input type="checkbox" data-endpoint-platform="windows_amd64" ${current.platforms.includes("windows_amd64") ? "checked" : ""}> Windows AMD64</label>
                        </fieldset>
                        <h4>Inputs</h4><div id="endpoint-module-inputs">${inputRows(current)}</div>
                        <button class="btn btn-secondary btn-sm" type="button" id="endpoint-module-add-input">Добавить input</button>
                        <h4>Шаги allowlist</h4><div id="endpoint-module-steps">${stepRows(current)}</div>
                        <button class="btn btn-secondary btn-sm" type="button" id="endpoint-module-add-step">Добавить шаг</button>
                        <div style="margin-top: 14px"><button class="btn btn-primary" type="submit">Создать draft в Endpoint</button></div>
                    </form>
                </section>
                <section class="endpoint-module-card">
                    <div class="section-header"><h3>Авторитетный каталог Endpoint</h3><button class="btn btn-secondary btn-sm" type="button" id="endpoint-module-refresh">Обновить</button></div>
                    <table><thead><tr><th>Module key</th><th>Название</th><th>Последняя версия</th><th>Lifecycle</th></tr></thead><tbody>${moduleRows()}</tbody></table>
                </section>
            </div>`;
        current.steps.forEach((step, index) => {
            const select = root.querySelector(`[data-endpoint-step-row="${index}"] [data-endpoint-step-target]`);
            if (select) select.value = step.targetInput || "";
        });
        bind();
    }

    function readDraft() {
        const root = host();
        if (!root || !root.querySelector("#endpoint-module-create-form")) return null;
        const inputs = Array.from(root.querySelectorAll("[data-endpoint-input-row]")).map((row) => ({
            name: row.querySelector("[data-endpoint-input-name]")?.value.trim() || "",
            valueType: row.querySelector("[data-endpoint-input-type]")?.value || "string",
        }));
        const steps = Array.from(root.querySelectorAll("[data-endpoint-step-row]")).map((row) => ({
            stepId: row.querySelector("[data-endpoint-step-id]")?.value.trim() || "",
            capability: row.querySelector("[data-endpoint-step-capability]")?.value || "dns.resolve",
            targetInput: row.querySelector("[data-endpoint-step-target]")?.value || "",
        }));
        return {
            moduleKey: root.querySelector("#endpoint-module-key")?.value.trim() || "",
            displayName: root.querySelector("#endpoint-module-name")?.value.trim() || "",
            version: root.querySelector("#endpoint-module-version")?.value.trim() || "",
            platforms: Array.from(root.querySelectorAll("[data-endpoint-platform]:checked")).map((item) => item.getAttribute("data-endpoint-platform")),
            inputs,
            steps,
        };
    }

    function parametersFor(step) {
        const target = { kind: "input", name: step.targetInput };
        if (step.capability === "dns.resolve") return { target, family: { kind: "literal", value: "any" } };
        if (step.capability === "network.ping") return { target, count: { kind: "literal", value: 3 }, timeout_ms: { kind: "literal", value: 1000 } };
        return { target, port: { kind: "literal", value: 443 }, timeout_ms: { kind: "literal", value: 1000 } };
    }

    function payloadFromDraft(draft) {
        return {
            schema_version: "module_version_create_v1",
            display_name: draft.displayName,
            version: draft.version,
            recipe: {
                schema_version: "endpoint_recipe_module_v1",
                module_key: draft.moduleKey,
                supported_platforms: draft.platforms,
                inputs: draft.inputs.map((item) => ({ name: item.name, value_type: item.valueType })),
                steps: draft.steps.map((step) => ({ step_id: step.stepId, capability: step.capability, parameters: parametersFor(step) })),
            },
        };
    }

    async function readResponse(response) {
        const data = await (shared?.responseToJson?.(response) || response.json());
        if (!response.ok) throw new Error(data.error_code || "Endpoint request failed");
        return data.data || data;
    }

    async function load(options) {
        const root = host();
        if (!root) return;
        const preserveMessage = Boolean(options?.preserveMessage);
        try {
            const response = await fetch(API_ROOT, { headers: headers(false), cache: "no-store" });
            state.modules = await readResponse(response);
            if (!preserveMessage) state.message = "";
        } catch (error) {
            state.modules = [];
            state.messageKind = "error";
            state.message = `Каталог Endpoint недоступен: ${error.message}`;
        }
        render();
    }

    async function createDraft(event) {
        event.preventDefault();
        const draft = readDraft();
        if (!draft.platforms.length || !draft.inputs.length || !draft.steps.length || draft.steps.some((step) => !step.targetInput)) {
            setMessage("error", "Укажите минимум одну платформу, input и шаг с string target input.");
            return;
        }
        try {
            const created = await readResponse(await fetch(API_ROOT, { method: "POST", headers: headers(true), body: JSON.stringify(payloadFromDraft(draft)) }));
            state.messageKind = "success";
            state.message = `Создан draft ${created.module_key}@${created.version}. Выполните Validate, затем Publish.`;
            await load({ preserveMessage: true });
        } catch (error) {
            setMessage("error", `Draft не создан: ${error.message}`);
        }
    }

    async function lifecycle(action, moduleKey, version) {
        try {
            const result = await readResponse(await fetch(`${API_ROOT}/${encodeURIComponent(moduleKey)}/${encodeURIComponent(version)}/${action}`, { method: "POST", headers: headers(true), body: "{}" }));
            const status = result.state || result.status || "accepted";
            state.messageKind = "success";
            state.message = `${action} для ${moduleKey}@${version}: ${status}.`;
            await load({ preserveMessage: true });
        } catch (error) {
            setMessage("error", `${action} не выполнен: ${error.message}`);
        }
    }

    function bind() {
        const root = host();
        root.querySelector("#endpoint-module-create-form")?.addEventListener("submit", createDraft);
        root.querySelector("#endpoint-module-refresh")?.addEventListener("click", load);
        root.querySelector("#endpoint-module-reset")?.addEventListener("click", () => render(defaultDraft()));
        root.querySelector("#endpoint-module-add-input")?.addEventListener("click", () => {
            const draft = readDraft(); draft.inputs.push({ name: "", valueType: "string" }); render(draft);
        });
        root.querySelector("#endpoint-module-add-step")?.addEventListener("click", () => {
            const draft = readDraft(); draft.steps.push({ stepId: "", capability: "dns.resolve", targetInput: draft.inputs.find((item) => item.valueType === "string")?.name || "" }); render(draft);
        });
        root.querySelectorAll("[data-endpoint-remove-input]").forEach((button) => button.addEventListener("click", () => {
            const draft = readDraft(); draft.inputs.splice(Number(button.getAttribute("data-endpoint-remove-input")), 1); render(draft);
        }));
        root.querySelectorAll("[data-endpoint-remove-step]").forEach((button) => button.addEventListener("click", () => {
            const draft = readDraft(); draft.steps.splice(Number(button.getAttribute("data-endpoint-remove-step")), 1); render(draft);
        }));
        root.querySelectorAll("[data-endpoint-action]").forEach((button) => button.addEventListener("click", () => lifecycle(
            button.getAttribute("data-endpoint-action"), button.getAttribute("data-module-key"), button.getAttribute("data-module-version")
        )));
    }

    window.EndpointModuleWorkbench = Object.freeze({ load });
})();
