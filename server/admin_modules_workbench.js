(function () {
    const SEMVER_RE = /^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9._-]+)?$/;
    const MODULE_NAME_RE = /^[a-z0-9_]+$/;
    const TOOL_NAME_RE = /^[a-z0-9_]+(?:\.[a-z0-9_]+)+$/;
    const METHOD_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;
    const RESERVED_NAMESPACES = new Set(["dns", "network", "tcp", "http", "tls", "system", "service", "file", "process", "browser"]);
    const API_PREVIEW_MODES = ["payload", "curl-validate", "curl-save", "fetch-save"];
    const PLATFORM_OPTIONS = [
        { value: "any", label: "Любая" },
        { value: "linux", label: "Linux" },
        { value: "win32", label: "Windows" },
        { value: "darwin", label: "macOS" },
    ];
    const OWNER_SCOPE_OPTIONS = ["vendor", "core", "platform", "builtin"];
    const TOOL_SCHEMA_EXAMPLES = {
        params: {
            type: "object",
            properties: {
                hostname: { type: "string", minLength: 1 },
                record_type: { type: "string", enum: ["A", "AAAA", "CNAME", "MX", "TXT"] },
            },
            required: ["hostname"],
            additionalProperties: false,
        },
        output: {
            type: "object",
            properties: {
                hostname: { type: "string" },
                answers: { type: "array", items: { type: "string" } },
                resolver: { type: "string" },
            },
            required: ["hostname", "answers"],
        },
    };
    const TOOL_TEMPLATE_OPTIONS = [
        { key: "blank", label: "Пустой diagnostic tool" },
        { key: "dns_resolve", label: "Шаблон DNS resolve" },
        { key: "network_ping", label: "Шаблон network ping" },
        { key: "tcp_connect", label: "Шаблон TCP connect" },
        { key: "route_get", label: "Шаблон route.get" },
        { key: "adapter_list", label: "Шаблон adapter.list" },
        { key: "http_request", label: "Шаблон HTTP request" },
        { key: "system_service_status", label: "Шаблон service status" },
    ];

    const SCHEMA_FIELD_TYPES = new Map([
        ["string", { type: "string" }],
        ["integer", { type: "integer" }],
        ["number", { type: "number" }],
        ["boolean", { type: "boolean" }],
        ["object", { type: "object", additionalProperties: true }],
    ]);

    const state = {
        initialized: false,
        catalog: [],
        rolloutSettings: {
            preferred_version_rollout_mode: "manual",
            sync_after_preferred_change: true,
        },
        selectedFamily: null,
        selectedVersion: null,
        currentDraft: null,
        selectedToolIndex: 0,
        selectedSourcePath: null,
        serverValidation: null,
        apiPreviewMode: "payload",
        currentView: "development",
        currentWizardStep: 1,
    };

    const html = window.escapeHtml || ((value) => String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;"));

    function clone(value) {
        return JSON.parse(JSON.stringify(value));
    }

    function pretty(value) {
        return JSON.stringify(value, null, 2);
    }

    function uniqueStrings(values) {
        return Array.from(new Set((values || []).map((item) => String(item || "").trim()).filter(Boolean)));
    }

    function parseListInput(raw) {
        return uniqueStrings(String(raw || "")
            .split(/\r?\n|,/)
            .map((item) => item.trim()));
    }

    function formatListInput(values) {
        return uniqueStrings(values).join("\n");
    }

    function schemaTypeFromBlueprint(rawType) {
        const type = String(rawType || "").trim().toLowerCase();
        if (!type) {
            return null;
        }
        if (SCHEMA_FIELD_TYPES.has(type)) {
            return clone(SCHEMA_FIELD_TYPES.get(type));
        }
        const arrayMatch = type.match(/^array\[(string|integer|number|boolean|object)\]$/);
        if (arrayMatch) {
            const itemType = arrayMatch[1];
            return {
                type: "array",
                items: SCHEMA_FIELD_TYPES.has(itemType)
                    ? clone(SCHEMA_FIELD_TYPES.get(itemType))
                    : { type: itemType },
            };
        }
        return null;
    }

    function schemaTypeToBlueprint(definition) {
        if (!definition || typeof definition !== "object") {
            return "";
        }
        if (definition.type === "array") {
            const itemType = definition.items?.type;
            if (typeof itemType === "string" && SCHEMA_FIELD_TYPES.has(itemType)) {
                return `array[${itemType}]`;
            }
            return "";
        }
        return typeof definition.type === "string" && SCHEMA_FIELD_TYPES.has(definition.type)
            ? definition.type
            : "";
    }

    function buildSchemaFromBlueprint(raw, allowAdditional, label, errors) {
        const lines = String(raw || "")
            .split(/\r?\n/)
            .map((line) => line.trim())
            .filter(Boolean);
        if (!lines.length) {
            return { schema: null, fieldCount: 0, requiredCount: 0 };
        }
        const properties = {};
        const required = [];
        lines.forEach((line, index) => {
            const [left, descriptionPart] = line.split("|").map((item) => item.trim());
            const match = String(left || "").match(/^([A-Za-z_][A-Za-z0-9_]*):([A-Za-z\[\]0-9_]+)(!)?$/);
            if (!match) {
                errors.push(`${label}: строка ${index + 1} должна быть в формате name:type! | Описание.`);
                return;
            }
            const [, fieldName, rawType, requiredMark] = match;
            const schemaType = schemaTypeFromBlueprint(rawType);
            if (!schemaType) {
                errors.push(`${label}: строка ${index + 1} содержит неподдерживаемый тип ${rawType}.`);
                return;
            }
            if (descriptionPart) {
                schemaType.description = descriptionPart;
            }
            properties[fieldName] = schemaType;
            if (requiredMark) {
                required.push(fieldName);
            }
        });
        if (errors.length) {
            return { schema: null, fieldCount: 0, requiredCount: 0 };
        }
        return {
            schema: {
                type: "object",
                properties,
                required,
                additionalProperties: allowAdditional === true,
            },
            fieldCount: Object.keys(properties).length,
            requiredCount: required.length,
        };
    }

    function formatSchemaBlueprint(schema) {
        if (!schema || typeof schema !== "object" || schema.type !== "object" || !schema.properties || typeof schema.properties !== "object") {
            return "";
        }
        const required = new Set(Array.isArray(schema.required) ? schema.required : []);
        const lines = Object.entries(schema.properties).map(([fieldName, definition]) => {
            const typeLabel = schemaTypeToBlueprint(definition);
            if (!typeLabel) {
                return "";
            }
            const description = typeof definition?.description === "string" ? definition.description.trim() : "";
            return `${fieldName}:${typeLabel}${required.has(fieldName) ? "!" : ""}${description ? ` | ${description}` : ""}`;
        }).filter(Boolean);
        return lines.join("\n");
    }

    function syncSchemaBlueprintControls(options) {
        const linesEl = byId(options.linesId);
        const jsonEl = byId(options.jsonId);
        const statusEl = byId(options.statusId);
        const allowAdditional = byId(options.additionalId)?.checked === true;
        if (!linesEl || !jsonEl || !statusEl) {
            return { valid: true, used: false, errors: [] };
        }
        const raw = String(linesEl.value || "").trim();
        if (!raw) {
            statusEl.textContent = "Быстрый конструктор не заполнен. Можно оставить raw JSON schema вручную.";
            statusEl.classList.remove("is-danger", "is-success");
            return { valid: true, used: false, errors: [] };
        }
        const errors = [];
        const result = buildSchemaFromBlueprint(raw, allowAdditional, options.label, errors);
        if (errors.length || !result.schema) {
            statusEl.textContent = errors[0] || `${options.label}: не удалось собрать схему.`;
            statusEl.classList.add("is-danger");
            statusEl.classList.remove("is-success");
            return { valid: false, used: true, errors };
        }
        jsonEl.value = pretty(result.schema);
        statusEl.textContent = `Собрано ${result.fieldCount} полей, обязательных: ${result.requiredCount}. JSON schema обновлена автоматически.`;
        statusEl.classList.remove("is-danger");
        statusEl.classList.add("is-success");
        return { valid: true, used: true, errors: [] };
    }

    function bindSchemaBlueprintControls(options, onValidSync) {
        [options.linesId, options.additionalId].forEach((id) => {
            const el = byId(id);
            if (!el || el.dataset.bound === "1") {
                return;
            }
            el.dataset.bound = "1";
            const handler = () => {
                const result = syncSchemaBlueprintControls(options);
                if (result.valid && result.used && typeof onValidSync === "function") {
                    onValidSync();
                }
            };
            el.addEventListener("input", handler);
            el.addEventListener("change", handler);
        });
    }

    function formatArtifactKinds(artifacts) {
        return (artifacts || [])
            .map((item) => {
                if (typeof item === "string") {
                    return item.trim();
                }
                if (item && typeof item === "object") {
                    return String(item.kind || "").trim();
                }
                return "";
            })
            .filter(Boolean)
            .join("\n");
    }

    function parseArtifactKinds(raw) {
        return parseListInput(raw).map((kind) => ({ kind }));
    }

    function platformCheckboxId(prefix, value) {
        return `${prefix}-${value}`;
    }

    function renderPlatformControls(prefix, label, note) {
        return `
            <div class="form-group">
                <label>${html(label)}</label>
                <div class="mw-choice-grid">
                    ${PLATFORM_OPTIONS.map((item) => `
                        <label class="mw-choice-pill">
                            <input type="checkbox" id="${platformCheckboxId(prefix, item.value)}" data-platform-group="${prefix}" data-platform-value="${item.value}">
                            <span>${html(item.label)}</span>
                        </label>
                    `).join("")}
                </div>
                ${note ? `<div class="mw-field-note">${html(note)}</div>` : ""}
            </div>
        `;
    }

    function writePlatformControls(prefix, values) {
        const selected = new Set(uniqueStrings(values));
        PLATFORM_OPTIONS.forEach((item) => {
            const checkbox = byId(platformCheckboxId(prefix, item.value));
            if (checkbox) {
                checkbox.checked = selected.has(item.value);
            }
        });
    }

    function readPlatformControls(prefix) {
        return PLATFORM_OPTIONS
            .filter((item) => byId(platformCheckboxId(prefix, item.value))?.checked)
            .map((item) => item.value);
    }

    function enforcePlatformSelection(prefix, changedValue) {
        const values = readPlatformControls(prefix);
        if (changedValue === "any" && values.includes("any")) {
            PLATFORM_OPTIONS.filter((item) => item.value !== "any").forEach((item) => {
                const checkbox = byId(platformCheckboxId(prefix, item.value));
                if (checkbox) {
                    checkbox.checked = false;
                }
            });
            return;
        }
        if (changedValue !== "any" && values.includes(changedValue)) {
            const anyCheckbox = byId(platformCheckboxId(prefix, "any"));
            if (anyCheckbox) {
                anyCheckbox.checked = false;
            }
        }
    }

    function bindPlatformControls(prefix, handler) {
        document.querySelectorAll(`[data-platform-group="${prefix}"]`).forEach((checkbox) => {
            if (checkbox.dataset.bound === "1") {
                return;
            }
            checkbox.dataset.bound = "1";
            checkbox.addEventListener("change", () => {
                enforcePlatformSelection(prefix, checkbox.getAttribute("data-platform-value") || "");
                handler();
            });
        });
    }

    function readIntInput(id, fallback) {
        const raw = Number(byId(id)?.value);
        return Number.isFinite(raw) ? raw : fallback;
    }

    function safeParseJson(raw, fallback, label, errors) {
        const text = String(raw || "").trim();
        if (!text) {
            return clone(fallback);
        }
        try {
            return JSON.parse(text);
        } catch (error) {
            errors.push(`${label}: ${error.message}`);
            return clone(fallback);
        }
    }

    function host() {
        return document.getElementById("modules-workbench-host");
    }

    function byId(id) {
        return document.getElementById(id);
    }

    function normalizeView(view) {
        return ["development", "list", "editor"].includes(view) ? view : "development";
    }

    function requestModulesSubtab(view) {
        if (typeof window.switchModulesSubtab === "function") {
            window.switchModulesSubtab(view);
        }
    }

    function setCurrentView(view, options) {
        state.currentView = normalizeView(view);
        if (options && Number.isInteger(options.wizardStep)) {
            state.currentWizardStep = Math.min(4, Math.max(1, options.wizardStep));
        }
        renderVisibleView();
        renderTopFields();
        renderToolTabs();
        renderToolEditor();
        renderCatalog();
        renderDevelopmentWizard();
        renderSummary();
        renderLocalValidation();
        renderServerValidation();
        renderApiPreviewTabs();
        renderApiPreview();
        renderSourceExplorer();
        renderWorkbenchHeader();
    }

    function setWizardStep(step) {
        state.currentWizardStep = Math.min(4, Math.max(1, Number(step) || 1));
        renderDevelopmentWizard();
        renderWorkbenchHeader();
    }

    function setMessage(kind, text, detailsHtml) {
        const el = byId("modules-workbench-message");
        if (!el) {
            return;
        }
        if (!text) {
            el.innerHTML = "";
            return;
        }
        const className = kind === "error" ? "error-message" : kind === "warning" ? "preflight-warning" : "success-message";
        el.innerHTML = `<div class="${className}" style="display:block; margin-bottom: 12px;">${html(text)}${detailsHtml ? `<div style="margin-top:8px;">${detailsHtml}</div>` : ""}</div>`;
    }

    function blankTool() {
        return {
            tool_name: "",
            aliases: [],
            method_name: "run",
            description: "",
            params_schema: { type: "object", properties: {}, additionalProperties: true },
            output_schema: { type: "object", properties: {} },
            presets: [],
            capabilities: [],
            metadata: {
                domain: "custom",
                platforms: ["any"],
                risk_level: "safe_read",
                requires_consent: false,
                timeout_sec: 30,
                idempotent: true,
                side_effects: false,
                allow_roles: ["admin"],
                scopes: ["custom"],
                origin: "managed",
                tool_kind: "diagnostic",
            },
            contract_version: "1.0.0",
            dependencies: {
                min_agent_version: null,
                required_binaries: [],
                required_python_packages: [],
                required_services: [],
                required_permissions: [],
            },
            lifecycle: "stable",
            error_codes: ["VALIDATION_ERROR"],
            artifact_types: [],
            redaction: {
                enabled: true,
                redact_headers: true,
                redact_env: true,
                redact_fields: ["authorization", "cookie", "token", "password", "secret", "api_key"],
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
            reconstruction_strategy: "draft",
        };
    }

    function normalizeToolDraft(tool) {
        const base = blankTool();
        const current = tool && typeof tool === "object" ? tool : {};
        return {
            ...base,
            ...current,
            aliases: Array.isArray(current.aliases) ? current.aliases : base.aliases,
            presets: Array.isArray(current.presets) ? current.presets : base.presets,
            capabilities: Array.isArray(current.capabilities) ? current.capabilities : base.capabilities,
            error_codes: Array.isArray(current.error_codes) ? current.error_codes : base.error_codes,
            artifact_types: Array.isArray(current.artifact_types) ? current.artifact_types : base.artifact_types,
            metadata: { ...base.metadata, ...(current.metadata || {}) },
            dependencies: { ...base.dependencies, ...(current.dependencies || {}) },
            redaction: { ...base.redaction, ...(current.redaction || {}) },
            resources: { ...base.resources, ...(current.resources || {}) },
            params_schema: current.params_schema && typeof current.params_schema === "object" ? current.params_schema : base.params_schema,
            output_schema: current.output_schema && typeof current.output_schema === "object" ? current.output_schema : base.output_schema,
        };
    }

    function rolloutModeLabel(mode) {
        if (mode === "installed_devices") {
            return "автообновление существующих установок";
        }
        return "только ручной preferred";
    }

    function rolloutSummaryText(summary) {
        if (!summary || typeof summary !== "object") {
            return "";
        }
        if (summary.mode !== "installed_devices") {
            return "Auto-rollout не запускался: режим manual.";
        }
        const reconciled = Number(summary.sync_enqueued || 0);
        const refreshed = Number(summary.refresh_enqueued || 0);
        return `Auto-rollout: updated desired state for ${Number(summary.desired_updates || 0)} device(s), reconcile triggered for ${reconciled}, refresh queued for ${refreshed}.`;
    }

    function renderRolloutSettings() {
        const modeEl = byId("modules-workbench-rollout-mode");
        const syncEl = byId("modules-workbench-rollout-sync");
        const summaryEl = byId("modules-workbench-rollout-summary");
        const noteEl = byId("modules-workbench-rollout-note");
        const settings = state.rolloutSettings || {
            preferred_version_rollout_mode: "manual",
            sync_after_preferred_change: true,
        };
        if (modeEl) {
            modeEl.value = settings.preferred_version_rollout_mode || "manual";
        }
        if (syncEl) {
            syncEl.checked = settings.sync_after_preferred_change !== false;
        }
        if (summaryEl) {
            summaryEl.textContent = rolloutModeLabel(settings.preferred_version_rollout_mode || "manual");
        }
        if (noteEl) {
            noteEl.textContent = settings.preferred_version_rollout_mode === "installed_devices"
                ? "При смене preferred сервер обновит desired version для устройств, где этот модуль уже установлен или уже desired=installed."
                : "Смена preferred только меняет приоритетную версию в реестре. Устройства обновятся позже через run_tool/manual install.";
        }
    }

    function createToolTemplate(templateKey) {
        const base = blankTool();
        if (templateKey === "dns_resolve") {
            return {
                ...base,
                tool_name: "dns.resolve",
                method_name: "resolve_dns",
                description: "Resolve hostname to IPv4/IPv6 addresses on the device.",
                params_schema: {
                    type: "object",
                    required: ["hostname"],
                    properties: {
                        hostname: { type: "string" },
                        family: { type: "string", enum: ["any", "ipv4", "ipv6"], default: "any" },
                    },
                    additionalProperties: false,
                },
                output_schema: {
                    type: "object",
                    properties: {
                        ok: { type: "boolean" },
                        hostname: { type: "string" },
                        best_ip: { type: "string" },
                        addresses: { type: "array" },
                    },
                },
                metadata: {
                    ...base.metadata,
                    domain: "dns",
                    scopes: ["network", "dns"],
                    allow_roles: ["admin", "support", "agent", "llm"],
                },
                error_codes: ["VALIDATION_ERROR", "DNS_NXDOMAIN"],
                user_function_body: [
                    'import socket',
                    'hostname = str(params.get("hostname") or "").strip()',
                    'family = str(params.get("family") or "any").strip().lower()',
                    'if not hostname:',
                    '    return {"ok": False, "error_code": "VALIDATION_ERROR", "error": "hostname is required"}',
                    'family_map = {"any": socket.AF_UNSPEC, "ipv4": socket.AF_INET, "ipv6": socket.AF_INET6}',
                    'if family not in family_map:',
                    '    return {"ok": False, "error_code": "VALIDATION_ERROR", "error": "family must be any|ipv4|ipv6"}',
                    "records = []",
                    "seen = set()",
                    "try:",
                    "    info = socket.getaddrinfo(hostname, None, family_map[family], socket.SOCK_STREAM)",
                    "except socket.gaierror as exc:",
                    '    return {"ok": False, "error_code": "DNS_NXDOMAIN", "error": str(exc), "hostname": hostname, "addresses": []}',
                    "for entry_family, _socktype, _proto, canonname, sockaddr in info:",
                    "    ip = sockaddr[0] if sockaddr else None",
                    "    if not ip:",
                    "        continue",
                    '    family_label = "ipv6" if entry_family == socket.AF_INET6 else "ipv4"',
                    "    key = (family_label, ip)",
                    "    if key in seen:",
                    "        continue",
                    "    seen.add(key)",
                    '    records.append({"family": family_label, "ip": ip, "canonical_name": canonname or hostname})',
                    'return {"ok": True, "hostname": hostname, "best_ip": records[0]["ip"] if records else "", "addresses": records}',
                ].join("\\n"),
            };
        }
        if (templateKey === "network_ping") {
            return {
                ...base,
                tool_name: "network.ping",
                method_name: "ping_target",
                description: "Check reachability of a host using ICMP or shell ping.",
                params_schema: {
                    type: "object",
                    required: ["target"],
                    properties: {
                        target: { type: "string" },
                        timeout_sec: { type: "integer", minimum: 1, maximum: 30, default: 3 },
                    },
                    additionalProperties: false,
                },
                output_schema: {
                    type: "object",
                    properties: {
                        ok: { type: "boolean" },
                        reachable: { type: "boolean" },
                        target: { type: "string" },
                    },
                },
                metadata: {
                    ...base.metadata,
                    domain: "network",
                    scopes: ["network", "diagnostic"],
                },
                error_codes: ["VALIDATION_ERROR", "TIMEOUT"],
                user_function_body: [
                    'import platform, subprocess',
                    'target = str(params.get("target") or "").strip()',
                    'timeout_sec = int(params.get("timeout_sec") or 3)',
                    'if not target:',
                    '    return {"ok": False, "error_code": "VALIDATION_ERROR", "error": "target is required"}',
                    'command = ["ping", "-n" if platform.system().lower().startswith("win") else "-c", "1", target]',
                    "try:",
                    "    proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout_sec, check=False)",
                    "except subprocess.TimeoutExpired:",
                    '    return {"ok": False, "reachable": False, "error_code": "TIMEOUT", "target": target}',
                    'return {"ok": proc.returncode == 0, "reachable": proc.returncode == 0, "target": target}',
                ].join("\\n"),
            };
        }
        if (templateKey === "tcp_connect") {
            return {
                ...base,
                tool_name: "tcp.connect",
                method_name: "tcp_connect",
                description: "Attempt a TCP connection to a host and port from the device.",
                params_schema: {
                    type: "object",
                    required: ["host", "port"],
                    properties: {
                        host: { type: "string" },
                        port: { type: "integer", minimum: 1, maximum: 65535 },
                        timeout_sec: { type: "integer", minimum: 1, maximum: 30, default: 5 },
                    },
                    additionalProperties: false,
                },
                output_schema: {
                    type: "object",
                    properties: {
                        ok: { type: "boolean" },
                        reachable: { type: "boolean" },
                        host: { type: "string" },
                        port: { type: "integer" },
                        latency_ms: { type: "integer" },
                    },
                },
                metadata: {
                    ...base.metadata,
                    domain: "tcp",
                    scopes: ["network", "tcp"],
                },
                error_codes: ["VALIDATION_ERROR", "TCP_CONNECT_FAILED", "TIMEOUT"],
                user_function_body: [
                    "import socket, time",
                    'host = str(params.get("host") or "").strip()',
                    'port = int(params.get("port") or 0)',
                    'timeout_sec = int(params.get("timeout_sec") or 5)',
                    'if not host or port <= 0:',
                    '    return {"ok": False, "error_code": "VALIDATION_ERROR", "error": "host and port are required"}',
                    "sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)",
                    "sock.settimeout(timeout_sec)",
                    "started = time.perf_counter()",
                    "try:",
                    "    sock.connect((host, port))",
                    "    latency_ms = int((time.perf_counter() - started) * 1000)",
                    '    return {"ok": True, "reachable": True, "host": host, "port": port, "latency_ms": latency_ms}',
                    "except socket.timeout:",
                    '    return {"ok": False, "reachable": False, "host": host, "port": port, "error_code": "TIMEOUT"}',
                    "except OSError as exc:",
                    '    return {"ok": False, "reachable": False, "host": host, "port": port, "error_code": "TCP_CONNECT_FAILED", "error": str(exc)}',
                    "finally:",
                    "    sock.close()",
                ].join("\\n"),
            };
        }
        if (templateKey === "route_get") {
            return {
                ...base,
                tool_name: "route.get",
                method_name: "route_get",
                description: "Collect route information for a destination or show the default route.",
                params_schema: {
                    type: "object",
                    properties: {
                        destination: { type: "string" },
                    },
                    additionalProperties: false,
                },
                output_schema: {
                    type: "object",
                    properties: {
                        ok: { type: "boolean" },
                        destination: { type: "string" },
                        command: { type: "array" },
                        output_preview: { type: "string" },
                    },
                },
                metadata: {
                    ...base.metadata,
                    domain: "network",
                    scopes: ["network", "route"],
                },
                dependencies: {
                    ...base.dependencies,
                    required_binaries: ["route"],
                },
                error_codes: ["VALIDATION_ERROR", "DEPENDENCY_MISSING", "UNSUPPORTED_PLATFORM"],
                user_function_body: [
                    "import platform, shutil, subprocess",
                    'destination = str(params.get("destination") or "").strip()',
                    'binary = "route"',
                    "if shutil.which(binary) is None:",
                    '    return {"ok": False, "error_code": "DEPENDENCY_MISSING", "error": "route binary is not available"}',
                    "is_windows = platform.system().lower().startswith('win')",
                    "if is_windows:",
                    '    command = [binary, "PRINT"] + ([destination] if destination else [])',
                    "else:",
                    '    command = [binary, "-n"]',
                    "proc = subprocess.run(command, capture_output=True, text=True, check=False)",
                    'preview = (proc.stdout or proc.stderr or "")[:2000]',
                    'return {"ok": proc.returncode == 0, "destination": destination or "default", "command": command, "output_preview": preview}',
                ].join("\\n"),
            };
        }
        if (templateKey === "adapter_list") {
            return {
                ...base,
                tool_name: "adapter.list",
                method_name: "adapter_list",
                description: "List local network adapters and basic status details.",
                params_schema: {
                    type: "object",
                    properties: {},
                    additionalProperties: false,
                },
                output_schema: {
                    type: "object",
                    properties: {
                        ok: { type: "boolean" },
                        adapters: { type: "array" },
                    },
                },
                metadata: {
                    ...base.metadata,
                    domain: "network",
                    scopes: ["network", "inventory"],
                },
                error_codes: ["DEPENDENCY_MISSING"],
                user_function_body: [
                    "import platform, shutil, subprocess",
                    "is_windows = platform.system().lower().startswith('win')",
                    'command = ["ipconfig", "/all"] if is_windows else ["ip", "-brief", "address"]',
                    "if shutil.which(command[0]) is None:",
                    '    return {"ok": False, "error_code": "DEPENDENCY_MISSING", "error": f"{command[0]} is not available"}',
                    "proc = subprocess.run(command, capture_output=True, text=True, check=False)",
                    "lines = [line.strip() for line in (proc.stdout or '').splitlines() if line.strip()]",
                    'return {"ok": proc.returncode == 0, "adapters": lines[:80]}',
                ].join("\\n"),
            };
        }
        if (templateKey === "http_request") {
            return {
                ...base,
                tool_name: "http.request",
                method_name: "http_request",
                description: "Perform a typed HTTP request for diagnostics.",
                params_schema: {
                    type: "object",
                    required: ["url"],
                    properties: {
                        url: { type: "string" },
                        method: { type: "string", enum: ["GET", "HEAD", "POST"], default: "GET" },
                        timeout_sec: { type: "integer", minimum: 1, maximum: 60, default: 10 },
                    },
                    additionalProperties: false,
                },
                output_schema: {
                    type: "object",
                    properties: {
                        ok: { type: "boolean" },
                        status_code: { type: "integer" },
                        latency_ms: { type: "integer" },
                    },
                },
                metadata: {
                    ...base.metadata,
                    domain: "http",
                    scopes: ["network", "http"],
                },
                error_codes: ["VALIDATION_ERROR", "TIMEOUT", "HTTP_407_PROXY_AUTH"],
                artifact_types: [{ kind: "http_headers", mime: "application/json", sensitivity: "internal" }],
                user_function_body: [
                    "import time",
                    "from urllib import request as urllib_request, error as urllib_error",
                    'url = str(params.get("url") or "").strip()',
                    'method = str(params.get("method") or "GET").upper()',
                    'timeout_sec = int(params.get("timeout_sec") or 10)',
                    'if not url:',
                    '    return {"ok": False, "error_code": "VALIDATION_ERROR", "error": "url is required"}',
                    "req = urllib_request.Request(url=url, method=method)",
                    "started = time.perf_counter()",
                    "try:",
                    "    with urllib_request.urlopen(req, timeout=timeout_sec) as resp:",
                    "        latency_ms = int((time.perf_counter() - started) * 1000)",
                    '        return {"ok": True, "status_code": getattr(resp, "status", 200), "latency_ms": latency_ms}',
                    "except urllib_error.HTTPError as exc:",
                    '    return {"ok": False, "status_code": exc.code, "error_code": "HTTP_407_PROXY_AUTH" if exc.code == 407 else "HTTP_ERROR"}',
                    "except Exception as exc:",
                    '    return {"ok": False, "error_code": "TIMEOUT" if "timed out" in str(exc).lower() else "REQUEST_FAILED", "error": str(exc)}',
                ].join("\\n"),
            };
        }
        if (templateKey === "system_service_status") {
            return {
                ...base,
                tool_name: "system.service_status",
                method_name: "service_status",
                description: "Return status of a named OS service.",
                params_schema: {
                    type: "object",
                    required: ["service_name"],
                    properties: {
                        service_name: { type: "string" },
                    },
                    additionalProperties: false,
                },
                output_schema: {
                    type: "object",
                    properties: {
                        ok: { type: "boolean" },
                        service_name: { type: "string" },
                        status: { type: "string" },
                    },
                },
                metadata: {
                    ...base.metadata,
                    domain: "system",
                    scopes: ["system", "diagnostic"],
                },
                error_codes: ["VALIDATION_ERROR", "UNSUPPORTED_PLATFORM"],
                user_function_body: [
                    "import platform, subprocess",
                    'service_name = str(params.get("service_name") or "").strip()',
                    'if not service_name:',
                    '    return {"ok": False, "error_code": "VALIDATION_ERROR", "error": "service_name is required"}',
                    "is_windows = platform.system().lower().startswith('win')",
                    "if is_windows:",
                    '    command = ["sc", "query", service_name]',
                    "else:",
                    '    command = ["systemctl", "status", service_name, "--no-pager"]',
                    "proc = subprocess.run(command, capture_output=True, text=True, check=False)",
                    'status = "running" if proc.returncode == 0 else "unknown"',
                    'return {"ok": proc.returncode == 0, "service_name": service_name, "status": status, "exit_code": proc.returncode}',
                ].join("\\n"),
            };
        }
        return base;
    }

    function createEmptyDraft() {
        return {
            module_name: "",
            version: "",
            module_api_version: "1.0.0",
            owner_scope: "vendor",
            description: "",
            platforms: ["any"],
            requirements: [],
            optional_requirements: [],
            min_agent_version: null,
            entrypoint: "module:register",
            tools: [blankTool()],
            warnings: [],
            source: {
                files: [],
                manifest_json_text: "",
                module_py_text: "",
                decomposition: { resolved_tools: 0, unresolved_tools: [], available_methods: [], available_tool_names: [] },
            },
        };
    }

    function familyMatchesSearch(family, search) {
        if (!search) {
            return true;
        }
        const hay = [
            family.module_name,
            ...(family.versions || []).flatMap((version) => version.tool_ids || []),
        ].join(" ").toLowerCase();
        return hay.includes(search.toLowerCase());
    }

    async function ensureReady() {
        if (state.initialized) {
            return;
        }
        const root = host();
        if (!root) {
            return;
        }
        const response = await fetch("/admin_modules_workbench.html", { headers: getAuthHeaders(), cache: "no-store" });
        root.innerHTML = await response.text();
        bindEvents();
        state.initialized = true;
    }

    function populateToolTemplateOptions() {
        ["modules-workbench-tool-template", "modules-workbench-wizard-tool-template"].forEach((id) => {
            const select = byId(id);
            if (!select) {
                return;
            }
            const currentValue = select.value || "blank";
            select.innerHTML = TOOL_TEMPLATE_OPTIONS.map((item) => `<option value="${item.key}">${html(item.label)}</option>`).join("");
            select.value = TOOL_TEMPLATE_OPTIONS.some((item) => item.key === currentValue) ? currentValue : "blank";
        });
    }

    function renderVisibleView() {
        document.querySelectorAll("[data-workbench-view]").forEach((section) => {
            section.hidden = section.getAttribute("data-workbench-view") !== state.currentView;
        });
    }

    function renderWorkbenchHeader() {
        const badge = byId("modules-workbench-current-view-badge");
        if (badge) {
            const labels = {
                development: "Пошаговая разработка",
                list: "Список модулей",
                editor: "Advanced-редактор",
            };
            badge.textContent = labels[state.currentView] || state.currentView;
        }
        const stepChip = byId("modules-workbench-current-step-chip");
        if (stepChip) {
            stepChip.textContent = `Шаг ${state.currentWizardStep}`;
        }
    }

    async function refreshOuterModuleInstallViews() {
        if (typeof window.loadModulesList === "function") {
            await window.loadModulesList();
        }
        if (typeof window.updateDeployModuleSelect === "function") {
            window.updateDeployModuleSelect();
        }
    }

    function guessArchiveIdentity(fileName) {
        const normalized = String(fileName || "").trim();
        if (!normalized) {
            return { moduleName: "", version: "" };
        }
        const zipName = normalized.replace(/\.zip$/i, "");
        const semverMatch = zipName.match(/^(.*)-(\d+\.\d+\.\d+(?:[-+][A-Za-z0-9._-]+)?)$/);
        if (semverMatch) {
            return {
                moduleName: String(semverMatch[1] || "").trim(),
                version: String(semverMatch[2] || "").trim(),
            };
        }
        return { moduleName: zipName, version: "" };
    }

    function renderArchiveImportNote(message, isError) {
        const note = byId("modules-workbench-archive-note");
        if (!note) {
            return;
        }
        note.textContent = message || "Имя и версия нужны только для upload contract. Канонические значения сервер возьмёт из manifest.json внутри архива.";
        note.classList.toggle("is-danger", Boolean(isError));
        note.classList.toggle("is-success", !isError && Boolean(message));
    }

    function resetArchiveImportForm() {
        const fileInput = byId("modules-workbench-archive-file");
        const moduleInput = byId("modules-workbench-archive-module-name");
        const versionInput = byId("modules-workbench-archive-version");
        const overwriteInput = byId("modules-workbench-archive-overwrite");
        const openAfterInput = byId("modules-workbench-archive-open-after");
        if (fileInput) {
            fileInput.value = "";
        }
        if (moduleInput) {
            moduleInput.value = "";
        }
        if (versionInput) {
            versionInput.value = "";
        }
        if (overwriteInput) {
            overwriteInput.checked = false;
        }
        if (openAfterInput) {
            openAfterInput.checked = true;
        }
        renderArchiveImportNote("", false);
    }

    function syncArchiveIdentityFromFile() {
        const file = byId("modules-workbench-archive-file")?.files?.[0];
        const moduleInput = byId("modules-workbench-archive-module-name");
        const versionInput = byId("modules-workbench-archive-version");
        if (!file || !moduleInput || !versionInput) {
            renderArchiveImportNote("", false);
            return;
        }
        const guessed = guessArchiveIdentity(file.name);
        if (!String(moduleInput.value || "").trim() && guessed.moduleName) {
            moduleInput.value = guessed.moduleName;
        }
        if (!String(versionInput.value || "").trim() && guessed.version) {
            versionInput.value = guessed.version;
        }
        const guessedParts = [];
        if (guessed.moduleName) {
            guessedParts.push(`module_name=${guessed.moduleName}`);
        }
        if (guessed.version) {
            guessedParts.push(`version=${guessed.version}`);
        }
        renderArchiveImportNote(
            guessedParts.length
                ? `Файл ${file.name}. Подсказка из имени архива: ${guessedParts.join(", ")}. При конфликте источником истины останется manifest.json.`
                : `Файл ${file.name}. Если имя и версия не читаются из названия, заполните их вручную перед upload.`,
            false
        );
    }

    async function uploadArchiveModule() {
        const file = byId("modules-workbench-archive-file")?.files?.[0];
        const moduleName = String(byId("modules-workbench-archive-module-name")?.value || "").trim();
        const version = String(byId("modules-workbench-archive-version")?.value || "").trim();
        const overwrite = byId("modules-workbench-archive-overwrite")?.checked === true;
        const openAfter = byId("modules-workbench-archive-open-after")?.checked !== false;
        if (!file) {
            renderArchiveImportNote("Сначала выберите ZIP-архив.", true);
            setMessage("warning", "Сначала выберите ZIP-архив для импорта.");
            return;
        }
        if (!moduleName) {
            renderArchiveImportNote("Укажите имя модуля или выберите архив с говорящим именем вроде module-1.2.3.zip.", true);
            setMessage("warning", "Для upload нужен module_name.");
            return;
        }
        if (!version) {
            renderArchiveImportNote("Укажите версию модуля. Сервер потом сверит её с manifest.json.", true);
            setMessage("warning", "Для upload нужна версия модуля.");
            return;
        }

        const uploadBtn = byId("modules-workbench-archive-upload-btn");
        const previousLabel = uploadBtn?.textContent || "";
        if (uploadBtn) {
            uploadBtn.disabled = true;
            uploadBtn.textContent = "Загрузка...";
        }
        renderArchiveImportNote(`Загружаем ${file.name} и прогоняем server preflight...`, false);
        try {
            const form = new FormData();
            form.append("file", file);
            form.append("module_name", moduleName);
            form.append("version", version);
            if (overwrite) {
                form.append("overwrite", "true");
            }
            const response = await fetch("/api/modules/upload", {
                method: "POST",
                headers: getAuthHeaders(),
                body: form,
            });
            const data = await responseToJson(response);
            if (!response.ok || data.status !== "success") {
                const preflightErrors = Array.isArray(data.preflight_errors) ? data.preflight_errors.join(" | ") : "";
                renderArchiveImportNote(preflightErrors || data.error || "Загрузка архива не прошла server validate.", true);
                setMessage("error", data.error || "Не удалось загрузить архив модуля.", preflightErrors ? html(preflightErrors) : "");
                return;
            }

            renderArchiveImportNote(
                `Архив принят: ${data.module_name}/${data.version}. Сервер сохранил версию и завершил preflight со статусом ${data.validation_status || "passed"}.`,
                false
            );
            setMessage("success", `Архив ${data.module_name}/${data.version} загружен в server registry.`);
            await load();
            await refreshOuterModuleInstallViews();
            state.selectedFamily = data.module_name;
            state.selectedVersion = data.version;
            resetArchiveImportForm();
            if (openAfter) {
                requestModulesSubtab("editor");
                await loadVersionDetail(data.module_name, data.version, { view: "editor" });
            } else {
                requestModulesSubtab("list");
                setCurrentView("list");
            }
        } catch (error) {
            renderArchiveImportNote(error.message, true);
            setMessage("error", error.message);
        } finally {
            if (uploadBtn) {
                uploadBtn.disabled = false;
                uploadBtn.textContent = previousLabel || "Загрузить архив";
            }
        }
    }

    function bindEvents() {
        populateToolTemplateOptions();
        byId("modules-workbench-refresh-btn")?.addEventListener("click", () => load());
        byId("modules-workbench-new-btn")?.addEventListener("click", () => {
            state.selectedFamily = null;
            state.selectedVersion = null;
            state.selectedToolIndex = 0;
            state.selectedSourcePath = null;
            state.currentDraft = createEmptyDraft();
            state.serverValidation = null;
            state.currentWizardStep = 1;
            setCurrentView("development", { wizardStep: 1 });
            requestModulesSubtab("development");
            setMessage("success", "Создан новый draft. Заполните каркас, добавьте инструменты и проверьте модуль перед публикацией.");
            renderAll();
        });
        byId("modules-workbench-load-selected-btn")?.addEventListener("click", async () => {
            if (!state.selectedFamily || !state.selectedVersion) {
                setMessage("warning", "Сначала выберите модуль и нужную версию в списке.");
                return;
            }
            await loadVersionDetail(state.selectedFamily, state.selectedVersion);
        });
        byId("modules-workbench-set-preferred-btn")?.addEventListener("click", async () => setPreferredVersion());
        byId("modules-workbench-save-btn")?.addEventListener("click", async () => saveDraft());
        byId("modules-workbench-validate-btn")?.addEventListener("click", async () => validateDraftOnServer());
        byId("modules-workbench-family-search")?.addEventListener("input", () => renderCatalog());
        byId("modules-workbench-apply-template-btn")?.addEventListener("click", () => {
            applyTemplateToCurrentTool(byId("modules-workbench-tool-template")?.value || "blank");
        });
        byId("modules-workbench-add-template-btn")?.addEventListener("click", () => {
            addToolFromTemplate(byId("modules-workbench-tool-template")?.value || "blank");
        });
        byId("modules-workbench-duplicate-tool-btn")?.addEventListener("click", () => duplicateCurrentTool());
        byId("modules-workbench-remove-tool-btn")?.addEventListener("click", () => removeCurrentTool());
        byId("modules-workbench-save-rollout-btn")?.addEventListener("click", async () => saveRolloutSettings());
        byId("modules-workbench-open-list-btn")?.addEventListener("click", () => {
            requestModulesSubtab("list");
            setCurrentView("list");
        });
        byId("modules-workbench-open-editor-btn")?.addEventListener("click", () => {
            requestModulesSubtab("editor");
            setCurrentView("editor");
        });
        byId("modules-workbench-editor-open-list-btn")?.addEventListener("click", () => {
            requestModulesSubtab("list");
            setCurrentView("list");
        });
        byId("modules-workbench-editor-open-development-btn")?.addEventListener("click", () => {
            requestModulesSubtab("development");
            setCurrentView("development", { wizardStep: 4 });
        });
        byId("modules-workbench-list-new-btn")?.addEventListener("click", () => byId("modules-workbench-new-btn")?.click());
        byId("modules-workbench-wizard-apply-template-btn")?.addEventListener("click", () => {
            applyTemplateToCurrentTool(byId("modules-workbench-wizard-tool-template")?.value || "blank");
            renderDevelopmentWizard();
        });
        byId("modules-workbench-wizard-add-template-btn")?.addEventListener("click", () => {
            addToolFromTemplate(byId("modules-workbench-wizard-tool-template")?.value || "blank");
            renderDevelopmentWizard();
        });
        byId("modules-workbench-wizard-duplicate-tool-btn")?.addEventListener("click", () => {
            duplicateCurrentTool();
            renderDevelopmentWizard();
        });
        byId("modules-workbench-wizard-remove-tool-btn")?.addEventListener("click", () => {
            removeCurrentTool();
            renderDevelopmentWizard();
        });
        byId("modules-workbench-wizard-back-btn")?.addEventListener("click", () => setWizardStep(state.currentWizardStep - 1));
        byId("modules-workbench-wizard-next-btn")?.addEventListener("click", () => setWizardStep(state.currentWizardStep + 1));
        byId("modules-workbench-archive-reset-btn")?.addEventListener("click", () => resetArchiveImportForm());
        byId("modules-workbench-archive-file")?.addEventListener("change", () => syncArchiveIdentityFromFile());
        byId("modules-workbench-archive-upload-btn")?.addEventListener("click", async () => uploadArchiveModule());
    }

    async function load() {
        await ensureReady();
        const list = byId("modules-workbench-list");
        if (list) {
            list.innerHTML = '<div class="mw-empty">Загрузка реестра модулей...</div>';
        }
        try {
            const response = await fetch("/api/modules/workbench", { headers: getAuthHeaders() });
            const data = await responseToJson(response);
            if (!response.ok || data.status !== "ok") {
                if (list) {
                    list.innerHTML = `<div class="error-message" style="display:block;">${html(data.error || "Не удалось загрузить реестр модулей.")}</div>`;
                }
                return;
            }
            state.catalog = data.modules || [];
            state.rolloutSettings = data.rollout_settings || {
                preferred_version_rollout_mode: "manual",
                sync_after_preferred_change: true,
            };
            if (!state.currentDraft) {
                state.currentDraft = createEmptyDraft();
            }
            renderAll();
        } catch (error) {
            if (list) {
                list.innerHTML = `<div class="error-message" style="display:block;">${html(error.message)}</div>`;
            }
        }
    }

    function renderAll() {
        renderVisibleView();
        renderWorkbenchHeader();
        renderRolloutSettings();
        renderCatalog();
        renderSummary();
        renderTopFields();
        renderToolTabs();
        renderToolEditor();
        renderDevelopmentWizard();
        renderLocalValidation();
        renderServerValidation();
        renderApiPreviewTabs();
        renderApiPreview();
        renderSourceExplorer();
    }

    function activeTool() {
        const tool = state.currentDraft?.tools?.[state.selectedToolIndex];
        if (!tool) {
            return null;
        }
        const normalized = normalizeToolDraft(tool);
        state.currentDraft.tools[state.selectedToolIndex] = normalized;
        return normalized;
    }

    function splitCsv(raw) {
        return String(raw || "")
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean);
    }

    function renderDevelopmentWizard() {
        const steps = [
            { id: 1, title: "Каркас", note: "Имя, версия, платформы и границы модуля." },
            { id: 2, title: "Инструменты", note: "Шаблон, схемы и код выбранного tool." },
            { id: 3, title: "Политики", note: "Риск, роли, scopes и runtime-поведение." },
            { id: 4, title: "Проверка", note: "Validate, preview и публикация в registry." },
        ];
        const stepper = byId("modules-workbench-stepper");
        if (stepper) {
            stepper.innerHTML = steps.map((step) => `
                <button type="button" class="mw-stepper-btn ${step.id === state.currentWizardStep ? "is-active" : ""}" data-wizard-step-target="${step.id}">
                    <strong>Шаг ${step.id}. ${html(step.title)}</strong>
                    <span class="mw-subtle">${html(step.note)}</span>
                </button>
            `).join("");
            stepper.querySelectorAll("[data-wizard-step-target]").forEach((button) => {
                button.addEventListener("click", () => setWizardStep(Number(button.getAttribute("data-wizard-step-target") || "1")));
            });
        }
        document.querySelectorAll("[data-wizard-step]").forEach((section) => {
            section.hidden = Number(section.getAttribute("data-wizard-step")) !== state.currentWizardStep;
        });
        byId("modules-workbench-wizard-back-btn")?.toggleAttribute("disabled", state.currentWizardStep <= 1);
        byId("modules-workbench-wizard-next-btn")?.toggleAttribute("disabled", state.currentWizardStep >= 4);

        renderWizardSummary();
        renderWizardBasics();
        renderWizardToolEditor();
        renderWizardPolicyEditor();
    }

    function renderWizardSummary() {
        const el = byId("modules-workbench-wizard-summary");
        if (!el) {
            return;
        }
        const draft = state.currentDraft || createEmptyDraft();
        const tool = activeTool();
        el.innerHTML = `
            <label>Текущий draft</label>
            <strong>${html(draft.module_name || "Новый модуль")}</strong>
            <div class="mw-subtle" style="margin-top: 6px;">Версия: ${html(draft.version || "—")} • tools: ${html(String((draft.tools || []).length))}</div>
            <div class="mw-chip-row" style="margin-top: 12px;">
                <span class="mw-chip is-accent">${html(draft.owner_scope || "vendor")}</span>
                <span class="mw-chip">${html((draft.platforms || ["any"]).join(", "))}</span>
                <span class="mw-chip">${html(tool?.tool_name || "tool не выбран")}</span>
            </div>
        `;
    }

    function renderWizardBasics() {
        const draft = state.currentDraft || createEmptyDraft();
        const set = (id, value) => {
            const el = byId(id);
            if (el && document.activeElement !== el) {
                el.value = value ?? "";
            }
        };
        set("modules-workbench-wizard-module-name", draft.module_name || "");
        set("modules-workbench-wizard-module-version", draft.version || "");
        set("modules-workbench-wizard-module-description", draft.description || "");
        set("modules-workbench-wizard-owner-scope", draft.owner_scope || "vendor");
        set("modules-workbench-wizard-min-agent-version", draft.min_agent_version || "");
        set("modules-workbench-wizard-module-api-version", draft.module_api_version || "1.0.0");
        set("modules-workbench-wizard-entrypoint", draft.entrypoint || "module:register");
        set("modules-workbench-wizard-requirements", formatListInput(draft.requirements || []));
        set("modules-workbench-wizard-optional-requirements", formatListInput(draft.optional_requirements || []));
        writePlatformControls("modules-workbench-wizard-platforms", draft.platforms || ["any"]);
        [
            "modules-workbench-wizard-module-name",
            "modules-workbench-wizard-module-version",
            "modules-workbench-wizard-module-description",
            "modules-workbench-wizard-owner-scope",
            "modules-workbench-wizard-min-agent-version",
            "modules-workbench-wizard-module-api-version",
            "modules-workbench-wizard-entrypoint",
            "modules-workbench-wizard-requirements",
            "modules-workbench-wizard-optional-requirements",
        ].forEach((id) => {
            const el = byId(id);
            if (!el || el.dataset.bound === "1") {
                return;
            }
            el.dataset.bound = "1";
            const handler = () => {
                syncWizardBasicsFromDom();
                renderSummary();
                renderTopFields();
                renderWizardSummary();
            };
            el.addEventListener("input", handler);
            el.addEventListener("change", handler);
        });
        bindPlatformControls("modules-workbench-wizard-platforms", () => {
            syncWizardBasicsFromDom();
            renderSummary();
            renderTopFields();
            renderWizardSummary();
        });
    }

    function syncWizardBasicsFromDom() {
        if (!state.currentDraft) {
            state.currentDraft = createEmptyDraft();
        }
        const errors = [];
        state.currentDraft.module_name = String(byId("modules-workbench-wizard-module-name")?.value || "").trim();
        state.currentDraft.version = String(byId("modules-workbench-wizard-module-version")?.value || "").trim();
        state.currentDraft.description = String(byId("modules-workbench-wizard-module-description")?.value || "").trim();
        state.currentDraft.owner_scope = String(byId("modules-workbench-wizard-owner-scope")?.value || "vendor").trim();
        state.currentDraft.min_agent_version = String(byId("modules-workbench-wizard-min-agent-version")?.value || "").trim() || null;
        state.currentDraft.module_api_version = String(byId("modules-workbench-wizard-module-api-version")?.value || "1.0.0").trim() || "1.0.0";
        state.currentDraft.entrypoint = String(byId("modules-workbench-wizard-entrypoint")?.value || "module:register").trim() || "module:register";
        state.currentDraft.platforms = readPlatformControls("modules-workbench-wizard-platforms");
        state.currentDraft.requirements = parseListInput(byId("modules-workbench-wizard-requirements")?.value || "");
        state.currentDraft.optional_requirements = parseListInput(byId("modules-workbench-wizard-optional-requirements")?.value || "");
        return errors;
    }

    function renderWizardToolEditor() {
        const tool = activeTool();
        const tabs = byId("modules-workbench-wizard-tool-tabs");
        if (tabs) {
            const tools = state.currentDraft?.tools || [];
            tabs.innerHTML = tools.map((item, index) => `
                <button type="button" class="mw-tab-btn ${index === state.selectedToolIndex ? "is-active" : ""}" data-wizard-tool-tab="${index}">
                    ${html(item.tool_name || `tool_${index + 1}`)}
                </button>
            `).join("");
            tabs.querySelectorAll("[data-wizard-tool-tab]").forEach((button) => {
                button.addEventListener("click", () => {
                    state.selectedToolIndex = Number(button.getAttribute("data-wizard-tool-tab") || "0");
                    renderDevelopmentWizard();
                    renderToolTabs();
                    renderToolEditor();
                    renderApiPreview();
                });
            });
        }
        if (!tool) {
            return;
        }
        const set = (id, value) => {
            const el = byId(id);
            if (el && document.activeElement !== el) {
                if (el.type === "checkbox") {
                    el.checked = Boolean(value);
                } else {
                    el.value = value ?? "";
                }
            }
        };
        set("modules-workbench-wizard-tool-name", tool.tool_name || "");
        set("modules-workbench-wizard-tool-method", tool.method_name || "");
        set("modules-workbench-wizard-tool-description", tool.description || "");
        set("modules-workbench-wizard-tool-params-schema-lines", formatSchemaBlueprint(tool.params_schema || {}));
        set("modules-workbench-wizard-tool-params-schema-additional", tool.params_schema?.additionalProperties === true);
        set("modules-workbench-wizard-tool-params-schema", pretty(tool.params_schema || {}));
        set("modules-workbench-wizard-tool-output-schema-lines", formatSchemaBlueprint(tool.output_schema || {}));
        set("modules-workbench-wizard-tool-output-schema-additional", tool.output_schema?.additionalProperties === true);
        set("modules-workbench-wizard-tool-output-schema", pretty(tool.output_schema || {}));
        set("modules-workbench-wizard-tool-code", tool.user_function_body || "");
        [
            "modules-workbench-wizard-tool-name",
            "modules-workbench-wizard-tool-method",
            "modules-workbench-wizard-tool-description",
            "modules-workbench-wizard-tool-params-schema",
            "modules-workbench-wizard-tool-output-schema",
            "modules-workbench-wizard-tool-code",
        ].forEach((id) => {
            const el = byId(id);
            if (!el || el.dataset.bound === "1") {
                return;
            }
            el.dataset.bound = "1";
            const handler = () => {
                syncWizardToolCoreFromDom();
                renderToolTabs();
                renderToolEditor();
                renderWizardSummary();
                renderLocalValidation();
                renderApiPreview();
            };
            el.addEventListener("input", handler);
            el.addEventListener("change", handler);
        });
        bindSchemaBlueprintControls({
            linesId: "modules-workbench-wizard-tool-params-schema-lines",
            additionalId: "modules-workbench-wizard-tool-params-schema-additional",
            jsonId: "modules-workbench-wizard-tool-params-schema",
            statusId: "modules-workbench-wizard-tool-params-schema-status",
            label: "Params schema",
        }, () => {
            syncWizardToolCoreFromDom();
            renderToolTabs();
            renderToolEditor();
            renderWizardSummary();
            renderLocalValidation();
            renderApiPreview();
        });
        bindSchemaBlueprintControls({
            linesId: "modules-workbench-wizard-tool-output-schema-lines",
            additionalId: "modules-workbench-wizard-tool-output-schema-additional",
            jsonId: "modules-workbench-wizard-tool-output-schema",
            statusId: "modules-workbench-wizard-tool-output-schema-status",
            label: "Output schema",
        }, () => {
            syncWizardToolCoreFromDom();
            renderToolTabs();
            renderToolEditor();
            renderWizardSummary();
            renderLocalValidation();
            renderApiPreview();
        });
        syncSchemaBlueprintControls({
            linesId: "modules-workbench-wizard-tool-params-schema-lines",
            additionalId: "modules-workbench-wizard-tool-params-schema-additional",
            jsonId: "modules-workbench-wizard-tool-params-schema",
            statusId: "modules-workbench-wizard-tool-params-schema-status",
            label: "Params schema",
        });
        syncSchemaBlueprintControls({
            linesId: "modules-workbench-wizard-tool-output-schema-lines",
            additionalId: "modules-workbench-wizard-tool-output-schema-additional",
            jsonId: "modules-workbench-wizard-tool-output-schema",
            statusId: "modules-workbench-wizard-tool-output-schema-status",
            label: "Output schema",
        });
        const paramsExampleBtn = byId("modules-workbench-wizard-params-example-btn");
        if (paramsExampleBtn && paramsExampleBtn.dataset.bound !== "1") {
            paramsExampleBtn.dataset.bound = "1";
            paramsExampleBtn.addEventListener("click", () => {
                const linesEl = byId("modules-workbench-wizard-tool-params-schema-lines");
                const additionalEl = byId("modules-workbench-wizard-tool-params-schema-additional");
                if (linesEl) {
                    linesEl.value = formatSchemaBlueprint(TOOL_SCHEMA_EXAMPLES.params);
                }
                if (additionalEl) {
                    additionalEl.checked = TOOL_SCHEMA_EXAMPLES.params.additionalProperties === true;
                }
                syncSchemaBlueprintControls({
                    linesId: "modules-workbench-wizard-tool-params-schema-lines",
                    additionalId: "modules-workbench-wizard-tool-params-schema-additional",
                    jsonId: "modules-workbench-wizard-tool-params-schema",
                    statusId: "modules-workbench-wizard-tool-params-schema-status",
                    label: "Params schema",
                });
                syncWizardToolCoreFromDom();
                renderToolTabs();
                renderToolEditor();
                renderWizardSummary();
                renderLocalValidation();
                renderApiPreview();
            });
        }
        const outputExampleBtn = byId("modules-workbench-wizard-output-example-btn");
        if (outputExampleBtn && outputExampleBtn.dataset.bound !== "1") {
            outputExampleBtn.dataset.bound = "1";
            outputExampleBtn.addEventListener("click", () => {
                const linesEl = byId("modules-workbench-wizard-tool-output-schema-lines");
                const additionalEl = byId("modules-workbench-wizard-tool-output-schema-additional");
                if (linesEl) {
                    linesEl.value = formatSchemaBlueprint(TOOL_SCHEMA_EXAMPLES.output);
                }
                if (additionalEl) {
                    additionalEl.checked = TOOL_SCHEMA_EXAMPLES.output.additionalProperties === true;
                }
                syncSchemaBlueprintControls({
                    linesId: "modules-workbench-wizard-tool-output-schema-lines",
                    additionalId: "modules-workbench-wizard-tool-output-schema-additional",
                    jsonId: "modules-workbench-wizard-tool-output-schema",
                    statusId: "modules-workbench-wizard-tool-output-schema-status",
                    label: "Output schema",
                });
                syncWizardToolCoreFromDom();
                renderToolTabs();
                renderToolEditor();
                renderWizardSummary();
                renderLocalValidation();
                renderApiPreview();
            });
        }
    }

    function syncWizardToolCoreFromDom() {
        const tool = activeTool();
        if (!tool) {
            return [];
        }
        const errors = [];
        tool.tool_name = String(byId("modules-workbench-wizard-tool-name")?.value || "").trim();
        tool.method_name = String(byId("modules-workbench-wizard-tool-method")?.value || "").trim();
        tool.description = String(byId("modules-workbench-wizard-tool-description")?.value || "").trim();
        tool.params_schema = safeParseJson(byId("modules-workbench-wizard-tool-params-schema")?.value, { type: "object", properties: {} }, "Params schema", errors);
        tool.output_schema = safeParseJson(byId("modules-workbench-wizard-tool-output-schema")?.value, { type: "object", properties: {} }, "Output schema", errors);
        tool.user_function_body = String(byId("modules-workbench-wizard-tool-code")?.value || "").trim();
        return errors;
    }

    function renderWizardPolicyEditor() {
        const tool = activeTool();
        if (!tool) {
            return;
        }
        tool.metadata = { ...blankTool().metadata, ...(tool.metadata || {}) };
        const set = (id, value) => {
            const el = byId(id);
            if (el && document.activeElement !== el) {
                if (el.type === "checkbox") {
                    el.checked = Boolean(value);
                } else {
                    el.value = value ?? "";
                }
            }
        };
        set("modules-workbench-wizard-tool-domain", tool.metadata.domain || "");
        set("modules-workbench-wizard-tool-kind", tool.metadata.tool_kind || "diagnostic");
        set("modules-workbench-wizard-risk-level", tool.metadata.risk_level || "safe_read");
        set("modules-workbench-wizard-tool-roles", (tool.metadata.allow_roles || []).join(", "));
        set("modules-workbench-wizard-tool-scopes", (tool.metadata.scopes || []).join(", "));
        set("modules-workbench-wizard-tool-timeout", tool.metadata.timeout_sec || 30);
        set("modules-workbench-wizard-tool-contract-version", tool.contract_version || "1.0.0");
        set("modules-workbench-wizard-tool-lifecycle", tool.lifecycle || "stable");
        set("modules-workbench-wizard-tool-requires-consent", tool.metadata.requires_consent);
        set("modules-workbench-wizard-tool-idempotent", tool.metadata.idempotent !== false);
        set("modules-workbench-wizard-tool-side-effects", tool.metadata.side_effects);
        writePlatformControls("modules-workbench-wizard-tool-platforms", tool.metadata.platforms || ["any"]);
        [
            "modules-workbench-wizard-tool-domain",
            "modules-workbench-wizard-tool-kind",
            "modules-workbench-wizard-risk-level",
            "modules-workbench-wizard-tool-roles",
            "modules-workbench-wizard-tool-scopes",
            "modules-workbench-wizard-tool-timeout",
            "modules-workbench-wizard-tool-contract-version",
            "modules-workbench-wizard-tool-lifecycle",
            "modules-workbench-wizard-tool-requires-consent",
            "modules-workbench-wizard-tool-idempotent",
            "modules-workbench-wizard-tool-side-effects",
        ].forEach((id) => {
            const el = byId(id);
            if (!el || el.dataset.bound === "1") {
                return;
            }
            el.dataset.bound = "1";
            const handler = () => {
                syncWizardToolPolicyFromDom();
                renderToolEditor();
                renderWizardSummary();
                renderLocalValidation();
            };
            el.addEventListener("input", handler);
            el.addEventListener("change", handler);
        });
        bindPlatformControls("modules-workbench-wizard-tool-platforms", () => {
            syncWizardToolPolicyFromDom();
            renderToolEditor();
            renderWizardSummary();
            renderLocalValidation();
        });
    }

    function syncWizardToolPolicyFromDom() {
        const tool = activeTool();
        if (!tool) {
            return;
        }
        tool.metadata = { ...blankTool().metadata, ...(tool.metadata || {}) };
        tool.metadata.domain = String(byId("modules-workbench-wizard-tool-domain")?.value || "").trim() || "custom";
        tool.metadata.tool_kind = String(byId("modules-workbench-wizard-tool-kind")?.value || "diagnostic").trim();
        tool.metadata.risk_level = String(byId("modules-workbench-wizard-risk-level")?.value || "safe_read").trim();
        tool.metadata.allow_roles = splitCsv(byId("modules-workbench-wizard-tool-roles")?.value || "");
        tool.metadata.scopes = splitCsv(byId("modules-workbench-wizard-tool-scopes")?.value || "");
        tool.metadata.platforms = readPlatformControls("modules-workbench-wizard-tool-platforms");
        tool.metadata.timeout_sec = Number(byId("modules-workbench-wizard-tool-timeout")?.value || 30) || 30;
        tool.metadata.requires_consent = byId("modules-workbench-wizard-tool-requires-consent")?.checked === true;
        tool.metadata.idempotent = byId("modules-workbench-wizard-tool-idempotent")?.checked !== false;
        tool.metadata.side_effects = byId("modules-workbench-wizard-tool-side-effects")?.checked === true;
        tool.contract_version = String(byId("modules-workbench-wizard-tool-contract-version")?.value || "1.0.0").trim() || "1.0.0";
        tool.lifecycle = String(byId("modules-workbench-wizard-tool-lifecycle")?.value || "stable").trim() || "stable";
    }

    async function saveRolloutSettings() {
        const mode = String(byId("modules-workbench-rollout-mode")?.value || "manual").trim() || "manual";
        const syncAfterPreferredChange = byId("modules-workbench-rollout-sync")?.checked !== false;
        try {
            const response = await fetch("/api/modules/rollout_settings", {
                method: "PATCH",
                headers: {
                    ...getAuthHeaders(),
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    preferred_version_rollout_mode: mode,
                    sync_after_preferred_change: syncAfterPreferredChange,
                }),
            });
            const data = await responseToJson(response);
            if (!response.ok || data.status !== "ok") {
                throw new Error(data.error || "Не удалось сохранить настройки rollout.");
            }
            state.rolloutSettings = data.rollout_settings || state.rolloutSettings;
            renderRolloutSettings();
            setMessage("success", "Настройки rollout модулей сохранены.");
        } catch (error) {
            setMessage("error", error.message);
        }
    }

    function renderCatalog() {
        const list = byId("modules-workbench-list");
        if (!list) {
            return;
        }
        const search = String(byId("modules-workbench-family-search")?.value || "").trim();
        const families = (state.catalog || []).filter((family) => familyMatchesSearch(family, search));
        if (!families.length) {
            list.innerHTML = '<div class="mw-empty">По текущему фильтру модули не найдены.</div>';
            return;
        }
        list.innerHTML = families.map((family) => {
            const selected = family.module_name === state.selectedFamily;
            const currentVersion = selected
                ? (state.selectedVersion || family.preferred_version || family.latest_version || "")
                : (family.preferred_version || family.latest_version || "");
            const versionsOptions = (family.versions || []).map((item) => {
                const label = `${item.version}${item.is_preferred ? " • приоритет" : ""}`;
                return `<option value="${html(item.version)}" ${item.version === currentVersion ? "selected" : ""}>${html(label)}</option>`;
            }).join("");
            const toolPreview = (family.versions?.[0]?.tool_ids || []).slice(0, 4).map((toolId) => `<span class="mw-chip">${html(toolId)}</span>`).join("");
            return `
                <div class="mw-family-card ${selected ? "is-selected" : ""}">
                    <div class="mw-toolbar">
                        <div>
                            <h3 style="margin: 0 0 4px;">${html(family.module_name)}</h3>
                            <div class="mw-subtle">Последняя ${html(family.latest_version || "—")} • preferred ${html(family.preferred_version || "—")}</div>
                        </div>
                        <span class="mw-badge ${family.preferred_assigned ? "is-accent" : ""}">${family.preferred_assigned ? "preferred задан" : "без preferred"}</span>
                    </div>
                    <div class="mw-chip-row" style="margin-top: 10px;">${toolPreview || '<span class="mw-subtle">tool ids пока не обнаружены</span>'}</div>
                    <div class="mw-grid-4" style="margin-top: 12px; align-items: center;">
                        <select data-version-select="${html(family.module_name)}">${versionsOptions}</select>
                        <button type="button" class="btn btn-secondary btn-sm" data-open-family="${html(family.module_name)}">Открыть в редакторе</button>
                        <button type="button" class="btn btn-secondary btn-sm" data-preferred-family="${html(family.module_name)}">Сделать preferred</button>
                        <button type="button" class="btn btn-danger btn-sm" data-delete-family="${html(family.module_name)}">Удалить версию</button>
                    </div>
                </div>
            `;
        }).join("");

        list.querySelectorAll("[data-version-select]").forEach((select) => {
            select.addEventListener("change", () => {
                state.selectedFamily = select.getAttribute("data-version-select");
                state.selectedVersion = select.value;
                renderCatalog();
            });
        });
        list.querySelectorAll("[data-open-family]").forEach((button) => {
            button.addEventListener("click", async () => {
                const moduleName = button.getAttribute("data-open-family");
                const select = list.querySelector(`[data-version-select="${CSS.escape(moduleName)}"]`);
                state.selectedFamily = moduleName;
                state.selectedVersion = select ? select.value : "";
                requestModulesSubtab("editor");
                await loadVersionDetail(moduleName, state.selectedVersion, { view: "editor" });
            });
        });
        list.querySelectorAll("[data-preferred-family]").forEach((button) => {
            button.addEventListener("click", async () => {
                const moduleName = button.getAttribute("data-preferred-family");
                const select = list.querySelector(`[data-version-select="${CSS.escape(moduleName)}"]`);
                state.selectedFamily = moduleName;
                state.selectedVersion = select ? select.value : "";
                await setPreferredVersion();
            });
        });
        list.querySelectorAll("[data-delete-family]").forEach((button) => {
            button.addEventListener("click", async () => {
                const moduleName = button.getAttribute("data-delete-family");
                const select = list.querySelector(`[data-version-select="${CSS.escape(moduleName)}"]`);
                const version = select ? select.value : "";
                await deleteModuleVersion(moduleName, version);
            });
        });
    }

    async function loadVersionDetail(moduleName, version, options) {
        setMessage(null, "");
        try {
            const response = await fetch(`/api/modules/workbench/${encodeURIComponent(moduleName)}/${encodeURIComponent(version)}`, {
                headers: getAuthHeaders(),
                cache: "no-store",
            });
            const data = await responseToJson(response);
            if (!response.ok || data.status !== "ok") {
                setMessage("error", data.error || "Не удалось загрузить версию модуля.");
                return;
            }
            state.selectedFamily = moduleName;
            state.selectedVersion = version;
            state.selectedToolIndex = 0;
            state.selectedSourcePath = null;
            state.currentDraft = data.editable_spec || createEmptyDraft();
            state.currentDraft.module_name = moduleName;
            state.currentDraft.version = version;
            state.serverValidation = null;
            if (options?.view) {
                state.currentView = normalizeView(options.view);
            }
            if (options?.wizardStep) {
                state.currentWizardStep = Math.min(4, Math.max(1, Number(options.wizardStep) || 1));
            }
            if ((state.currentDraft.warnings || []).length) {
                setMessage("warning", "Часть кода удалось восстановить не полностью. Ниже всё равно показаны доступные source-файлы и найденные методы.", (state.currentDraft.warnings || []).map((item) => html(item)).join("<br>"));
            }
            renderAll();
        } catch (error) {
            setMessage("error", error.message);
        }
    }

    function renderSummary() {
        const draft = state.currentDraft || createEmptyDraft();
        byId("modules-workbench-editor-title").textContent = draft.module_name ? `Редактор модуля ${draft.module_name}` : "Редактор модуля";
        byId("modules-workbench-editor-subtitle").textContent = draft.version
            ? `Редактируется версия ${draft.version}. Можно validate без публикации и только потом сохранить в server registry.`
            : "Соберите модуль из blueprint, tool templates и кода атомарных функций.";
        byId("modules-workbench-selected-module").textContent = draft.module_name || "—";
        byId("modules-workbench-selected-version").textContent = draft.version || "—";
        byId("modules-workbench-selected-preferred").textContent = state.selectedFamily
            ? (state.catalog.find((item) => item.module_name === state.selectedFamily)?.preferred_version || "—")
            : "—";
        byId("modules-workbench-selected-tools-count").textContent = String((draft.tools || []).length);
    }

    function renderTopFields() {
        const draft = state.currentDraft || createEmptyDraft();
        const set = (id, value) => {
            const el = byId(id);
            if (el && document.activeElement !== el) {
                el.value = value ?? "";
            }
        };
        set("modules-workbench-module-name", draft.module_name || "");
        set("modules-workbench-module-version", draft.version || "");
        set("modules-workbench-module-description", draft.description || "");
        set("modules-workbench-owner-scope", draft.owner_scope || "vendor");
        set("modules-workbench-module-api-version", draft.module_api_version || "1.0.0");
        set("modules-workbench-entrypoint", draft.entrypoint || "module:register");
        set("modules-workbench-min-agent-version", draft.min_agent_version || "");
        set("modules-workbench-requirements", formatListInput(draft.requirements || []));
        set("modules-workbench-optional-requirements", formatListInput(draft.optional_requirements || []));
        writePlatformControls("modules-workbench-platforms", draft.platforms || ["any"]);

        [
            "modules-workbench-module-name",
            "modules-workbench-module-version",
            "modules-workbench-module-description",
            "modules-workbench-owner-scope",
            "modules-workbench-module-api-version",
            "modules-workbench-entrypoint",
            "modules-workbench-min-agent-version",
            "modules-workbench-requirements",
            "modules-workbench-optional-requirements",
        ].forEach((id) => {
            const el = byId(id);
            if (!el || el.dataset.bound === "1") {
                return;
            }
            el.dataset.bound = "1";
            const handler = () => {
                syncTopFieldsFromDom();
                refreshDraftViews();
            };
            el.addEventListener("input", handler);
            el.addEventListener("change", handler);
        });
        bindPlatformControls("modules-workbench-platforms", () => {
            syncTopFieldsFromDom();
            refreshDraftViews();
        });
    }

    function syncTopFieldsFromDom() {
        if (!state.currentDraft) {
            state.currentDraft = createEmptyDraft();
        }
        const errors = [];
        state.currentDraft.module_name = String(byId("modules-workbench-module-name")?.value || "").trim();
        state.currentDraft.version = String(byId("modules-workbench-module-version")?.value || "").trim();
        state.currentDraft.description = String(byId("modules-workbench-module-description")?.value || "").trim();
        state.currentDraft.owner_scope = String(byId("modules-workbench-owner-scope")?.value || "vendor").trim();
        state.currentDraft.module_api_version = String(byId("modules-workbench-module-api-version")?.value || "1.0.0").trim() || "1.0.0";
        state.currentDraft.entrypoint = String(byId("modules-workbench-entrypoint")?.value || "module:register").trim() || "module:register";
        state.currentDraft.min_agent_version = String(byId("modules-workbench-min-agent-version")?.value || "").trim() || null;
        state.currentDraft.platforms = readPlatformControls("modules-workbench-platforms");
        state.currentDraft.requirements = parseListInput(byId("modules-workbench-requirements")?.value || "");
        state.currentDraft.optional_requirements = parseListInput(byId("modules-workbench-optional-requirements")?.value || "");
        return errors;
    }

    function renderToolTabs() {
        const wrap = byId("modules-workbench-tool-tabs");
        if (!wrap) {
            return;
        }
        const tools = state.currentDraft?.tools || [];
        wrap.innerHTML = tools.map((tool, index) => {
            const active = index === state.selectedToolIndex;
            const label = tool.tool_name || `tool_${index + 1}`;
            const strategy = tool.reconstruction_strategy && tool.reconstruction_strategy !== "draft"
                ? `<span class="mw-chip ${tool.reconstruction_strategy === "ast" ? "is-accent" : ""}" style="margin-left: 6px;">${html(tool.reconstruction_strategy)}</span>`
                : "";
            return `<button type="button" class="mw-tab-btn ${active ? "is-active" : ""}" data-tool-tab="${index}">${html(label)}${strategy}</button>`;
        }).join("");
        wrap.querySelectorAll("[data-tool-tab]").forEach((button) => {
            button.addEventListener("click", () => {
                state.selectedToolIndex = Number(button.getAttribute("data-tool-tab") || "0");
                renderToolTabs();
                renderToolEditor();
                renderLocalValidation();
                renderApiPreview();
            });
        });
    }

    function renderToolEditor() {
        const wrap = byId("modules-workbench-tool-editor");
        if (!wrap) {
            return;
        }
        const tool = activeTool();
        if (!tool) {
            wrap.innerHTML = '<div class="mw-empty">Добавьте хотя бы один tool.</div>';
            return;
        }
        wrap.innerHTML = `
            <div class="mw-chip-row" style="margin-bottom: 12px;">
                <span class="mw-chip ${tool.metadata?.tool_kind === "remediation" ? "is-warning" : "is-accent"}">${html(tool.metadata?.tool_kind || "diagnostic")}</span>
                <span class="mw-chip">${html(tool.metadata?.risk_level || "safe_read")}</span>
                <span class="mw-chip">${html(tool.lifecycle || "stable")}</span>
                <span class="mw-chip">${html(tool.contract_version || "1.0.0")}</span>
            </div>
            <div class="mw-grid-4">
                <div class="form-group">
                    <label for="modules-workbench-tool-name">Canonical tool id</label>
                    <input type="text" id="modules-workbench-tool-name" value="${html(tool.tool_name || "")}" placeholder="dns.resolve">
                </div>
                <div class="form-group">
                    <label for="modules-workbench-tool-method">Method</label>
                    <input type="text" id="modules-workbench-tool-method" value="${html(tool.method_name || "")}" placeholder="resolve_dns">
                </div>
                <div class="form-group">
                    <label for="modules-workbench-tool-contract-version">Contract version</label>
                    <input type="text" id="modules-workbench-tool-contract-version" value="${html(tool.contract_version || "1.0.0")}" placeholder="1.0.0">
                </div>
                <div class="form-group">
                    <label for="modules-workbench-tool-lifecycle">Lifecycle</label>
                    <select id="modules-workbench-tool-lifecycle">
                        ${["experimental", "stable", "deprecated", "removed"].map((item) => `<option value="${item}" ${tool.lifecycle === item ? "selected" : ""}>${item}</option>`).join("")}
                    </select>
                </div>
            </div>
            <div class="form-group" style="margin-top: 12px;">
                <label for="modules-workbench-tool-description">Описание</label>
                <input type="text" id="modules-workbench-tool-description" value="${html(tool.description || "")}" placeholder="Что делает этот tool">
            </div>
            <div class="mw-grid-2" style="margin-top: 12px;">
                <div class="form-group">
                    <label for="modules-workbench-tool-aliases">Aliases</label>
                    <textarea id="modules-workbench-tool-aliases" rows="4" placeholder="По одному alias на строку">${html(formatListInput(tool.aliases || []))}</textarea>
                    <div class="mw-field-note">Alias нужен как compatibility bridge, а не как основной идентификатор.</div>
                </div>
                <div class="form-group">
                    <label for="modules-workbench-tool-error-codes">Error codes</label>
                    <textarea id="modules-workbench-tool-error-codes" rows="4" placeholder="VALIDATION_ERROR&#10;TIMEOUT">${html(formatListInput(tool.error_codes || []))}</textarea>
                    <div class="mw-field-note">Используйте стабильные коды из runtime contract, чтобы решения были предсказуемыми.</div>
                </div>
            </div>
            <div class="mw-grid-2" style="margin-top: 12px;">
                <div class="form-group">
                    <label for="modules-workbench-tool-params-schema-lines">Params schema без JSON</label>
                    <textarea id="modules-workbench-tool-params-schema-lines" rows="6" placeholder="hostname:string! | Имя хоста&#10;record_type:string | Тип записи">${html(formatSchemaBlueprint(tool.params_schema || {}))}</textarea>
                    <label style="display: inline-flex; align-items: center; gap: 8px; margin-top: 8px;">
                        <input type="checkbox" id="modules-workbench-tool-params-schema-additional" ${tool.params_schema?.additionalProperties === true ? "checked" : ""}>
                        Разрешить дополнительные поля
                    </label>
                    <div id="modules-workbench-tool-params-schema-status" class="mw-field-note" style="margin-top: 8px;"></div>
                    <label for="modules-workbench-tool-params-schema" style="margin-top: 10px;">Raw JSON schema</label>
                    <textarea id="modules-workbench-tool-params-schema" rows="10">${html(pretty(tool.params_schema || {}))}</textarea>
                    <div class="mw-inline-actions" style="margin-top: 8px;">
                        <button type="button" class="btn btn-secondary btn-sm" id="modules-workbench-tool-params-example-btn">Подставить пример</button>
                        <span class="mw-field-note">Формат строки: <code>name:type! | Описание</code>. Типы: string, integer, number, boolean, object, array[string].</span>
                    </div>
                </div>
                <div class="form-group">
                    <label for="modules-workbench-tool-output-schema-lines">Output schema без JSON</label>
                    <textarea id="modules-workbench-tool-output-schema-lines" rows="6" placeholder="ok:boolean! | Успешное выполнение&#10;answers:array[string] | Список ответов">${html(formatSchemaBlueprint(tool.output_schema || {}))}</textarea>
                    <label style="display: inline-flex; align-items: center; gap: 8px; margin-top: 8px;">
                        <input type="checkbox" id="modules-workbench-tool-output-schema-additional" ${tool.output_schema?.additionalProperties === true ? "checked" : ""}>
                        Разрешить дополнительные поля
                    </label>
                    <div id="modules-workbench-tool-output-schema-status" class="mw-field-note" style="margin-top: 8px;"></div>
                    <label for="modules-workbench-tool-output-schema" style="margin-top: 10px;">Raw JSON schema</label>
                    <textarea id="modules-workbench-tool-output-schema" rows="10">${html(pretty(tool.output_schema || {}))}</textarea>
                    <div class="mw-inline-actions" style="margin-top: 8px;">
                        <button type="button" class="btn btn-secondary btn-sm" id="modules-workbench-tool-output-example-btn">Подставить пример</button>
                        <span class="mw-field-note">Output schema лучше держать структурированной, а не полагаться на stdout/stderr.</span>
                    </div>
                </div>
            </div>
            <div class="mw-section">
                <div class="mw-section-head">
                    <div>
                        <h4 style="margin: 0;">Политики и доступ</h4>
                        <div class="mw-subtle">Заполняется по guide: domain, platform support, роли, scopes и базовые runtime-флаги.</div>
                    </div>
                </div>
                <div class="mw-grid-4" style="margin-top: 12px;">
                    <div class="form-group">
                        <label for="modules-workbench-tool-domain">Domain</label>
                        <input type="text" id="modules-workbench-tool-domain" value="${html(tool.metadata?.domain || "")}" placeholder="network">
                    </div>
                    <div class="form-group">
                        <label for="modules-workbench-tool-kind">Tool kind</label>
                        <select id="modules-workbench-tool-kind">
                            ${["diagnostic", "inventory", "remediation", "automation"].map((item) => `<option value="${item}" ${tool.metadata?.tool_kind === item ? "selected" : ""}>${item}</option>`).join("")}
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="modules-workbench-tool-risk-level">Risk level</label>
                        <select id="modules-workbench-tool-risk-level">
                            ${["safe_read", "safe_readonly", "moderate", "dangerous"].map((item) => `<option value="${item}" ${tool.metadata?.risk_level === item ? "selected" : ""}>${item}</option>`).join("")}
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="modules-workbench-tool-timeout">Timeout, сек</label>
                        <input type="number" id="modules-workbench-tool-timeout" min="1" max="3600" step="1" value="${html(String(tool.metadata?.timeout_sec || 30))}">
                    </div>
                </div>
                ${renderPlatformControls("modules-workbench-tool-platforms", "Поддерживаемые платформы", "В docs рекомендуют указывать platforms честно, чтобы validate и runtime decisions были предсказуемыми.")}
                <div class="mw-grid-2" style="margin-top: 12px;">
                    <div class="form-group">
                        <label for="modules-workbench-tool-roles">Разрешённые роли</label>
                        <textarea id="modules-workbench-tool-roles" rows="4" placeholder="admin&#10;support">${html(formatListInput(tool.metadata?.allow_roles || []))}</textarea>
                    </div>
                    <div class="form-group">
                        <label for="modules-workbench-tool-scopes">Scopes</label>
                        <textarea id="modules-workbench-tool-scopes" rows="4" placeholder="network&#10;diagnostics">${html(formatListInput(tool.metadata?.scopes || []))}</textarea>
                    </div>
                </div>
                <div class="mw-grid-3" style="margin-top: 8px;">
                    <label style="display: inline-flex; align-items: center; gap: 8px;"><input type="checkbox" id="modules-workbench-tool-requires-consent" ${tool.metadata?.requires_consent ? "checked" : ""}> Требует consent</label>
                    <label style="display: inline-flex; align-items: center; gap: 8px;"><input type="checkbox" id="modules-workbench-tool-idempotent" ${tool.metadata?.idempotent !== false ? "checked" : ""}> Idempotent</label>
                    <label style="display: inline-flex; align-items: center; gap: 8px;"><input type="checkbox" id="modules-workbench-tool-side-effects" ${tool.metadata?.side_effects ? "checked" : ""}> Есть side effects</label>
                </div>
            </div>
            <div class="mw-section">
                <div class="mw-section-head">
                    <div>
                        <h4 style="margin: 0;">Совместимость и зависимости</h4>
                        <div class="mw-subtle">Dependencies нужны, чтобы validate и runtime понимали совместимость ещё до запуска.</div>
                    </div>
                </div>
                <div class="mw-grid-3" style="margin-top: 12px;">
                    <div class="form-group">
                        <label for="modules-workbench-tool-dependency-min-agent-version">Min agent version</label>
                        <input type="text" id="modules-workbench-tool-dependency-min-agent-version" value="${html(tool.dependencies?.min_agent_version || "")}" placeholder="3.1.0">
                    </div>
                    <div class="form-group">
                        <label for="modules-workbench-tool-required-binaries">Required binaries</label>
                        <textarea id="modules-workbench-tool-required-binaries" rows="4" placeholder="ping&#10;traceroute">${html(formatListInput(tool.dependencies?.required_binaries || []))}</textarea>
                    </div>
                    <div class="form-group">
                        <label for="modules-workbench-tool-required-python-packages">Required Python packages</label>
                        <textarea id="modules-workbench-tool-required-python-packages" rows="4" placeholder="psutil&#10;requests">${html(formatListInput(tool.dependencies?.required_python_packages || []))}</textarea>
                    </div>
                </div>
                <div class="mw-grid-2" style="margin-top: 12px;">
                    <div class="form-group">
                        <label for="modules-workbench-tool-required-services">Required services</label>
                        <textarea id="modules-workbench-tool-required-services" rows="4" placeholder="dns-client">${html(formatListInput(tool.dependencies?.required_services || []))}</textarea>
                    </div>
                    <div class="form-group">
                        <label for="modules-workbench-tool-required-permissions">Required permissions</label>
                        <textarea id="modules-workbench-tool-required-permissions" rows="4" placeholder="network.read">${html(formatListInput(tool.dependencies?.required_permissions || []))}</textarea>
                    </div>
                </div>
            </div>
            <div class="mw-section">
                <div class="mw-section-head">
                    <div>
                        <h4 style="margin: 0;">Безопасность и лимиты</h4>
                        <div class="mw-subtle">Redaction и resources по docs обязательны: это защита от утечек и runaway tool.</div>
                    </div>
                </div>
                <div class="mw-grid-2" style="margin-top: 12px;">
                    <div class="form-group">
                        <label for="modules-workbench-tool-artifacts">Artifact types</label>
                        <textarea id="modules-workbench-tool-artifacts" rows="4" placeholder="screenshot&#10;log_bundle">${html(formatArtifactKinds(tool.artifact_types || []))}</textarea>
                    </div>
                    <div class="form-group">
                        <label for="modules-workbench-tool-redaction-fields">Redaction fields</label>
                        <textarea id="modules-workbench-tool-redaction-fields" rows="4" placeholder="authorization&#10;cookie&#10;token">${html(formatListInput(tool.redaction?.redact_fields || []))}</textarea>
                    </div>
                </div>
                <div class="mw-grid-4" style="margin-top: 8px;">
                    <label style="display: inline-flex; align-items: center; gap: 8px;"><input type="checkbox" id="modules-workbench-tool-redaction-enabled" ${tool.redaction?.enabled !== false ? "checked" : ""}> Redaction включён</label>
                    <label style="display: inline-flex; align-items: center; gap: 8px;"><input type="checkbox" id="modules-workbench-tool-redaction-headers" ${tool.redaction?.redact_headers !== false ? "checked" : ""}> Redact headers</label>
                    <label style="display: inline-flex; align-items: center; gap: 8px;"><input type="checkbox" id="modules-workbench-tool-redaction-env" ${tool.redaction?.redact_env !== false ? "checked" : ""}> Redact env</label>
                    <label style="display: inline-flex; align-items: center; gap: 8px;"><input type="checkbox" id="modules-workbench-tool-redaction-allow-raw" ${tool.redaction?.allow_raw_sensitive_data ? "checked" : ""}> Разрешить raw sensitive data</label>
                </div>
                <div class="mw-grid-3" style="margin-top: 12px;">
                    <div class="form-group">
                        <label for="modules-workbench-tool-resource-runtime">Max runtime, сек</label>
                        <input type="number" id="modules-workbench-tool-resource-runtime" min="1" max="3600" step="1" value="${html(String(tool.resources?.max_runtime_sec || 30))}">
                    </div>
                    <div class="form-group">
                        <label for="modules-workbench-tool-resource-stdout">Max stdout bytes</label>
                        <input type="number" id="modules-workbench-tool-resource-stdout" min="0" step="1" value="${html(String(tool.resources?.max_stdout_bytes || 65536))}">
                    </div>
                    <div class="form-group">
                        <label for="modules-workbench-tool-resource-stderr">Max stderr bytes</label>
                        <input type="number" id="modules-workbench-tool-resource-stderr" min="0" step="1" value="${html(String(tool.resources?.max_stderr_bytes || 65536))}">
                    </div>
                </div>
                <div class="mw-grid-3" style="margin-top: 12px;">
                    <div class="form-group">
                        <label for="modules-workbench-tool-resource-artifact-count">Max artifact count</label>
                        <input type="number" id="modules-workbench-tool-resource-artifact-count" min="0" step="1" value="${html(String(tool.resources?.max_artifact_count || 0))}">
                    </div>
                    <div class="form-group">
                        <label for="modules-workbench-tool-resource-artifact-bytes">Max artifact bytes</label>
                        <input type="number" id="modules-workbench-tool-resource-artifact-bytes" min="0" step="1" value="${html(String(tool.resources?.max_artifact_bytes || 0))}">
                    </div>
                    <div class="form-group">
                        <label for="modules-workbench-tool-resource-subprocess-count">Max subprocess count</label>
                        <input type="number" id="modules-workbench-tool-resource-subprocess-count" min="0" step="1" value="${html(String(tool.resources?.max_subprocess_count || 2))}">
                    </div>
                </div>
                <div class="mw-grid-2" style="margin-top: 12px;">
                    <div class="form-group">
                        <label for="modules-workbench-tool-resource-filesystem-scope">Allowed filesystem scope</label>
                        <textarea id="modules-workbench-tool-resource-filesystem-scope" rows="4" placeholder="C:\\Temp&#10;/var/log">${html(formatListInput(tool.resources?.allowed_filesystem_scope || []))}</textarea>
                    </div>
                    <div class="form-group">
                        <label for="modules-workbench-tool-resource-external-hosts">Allowed external hosts</label>
                        <textarea id="modules-workbench-tool-resource-external-hosts" rows="4" placeholder="api.example.com&#10;8.8.8.8">${html(formatListInput(tool.resources?.allowed_external_hosts || []))}</textarea>
                    </div>
                </div>
            </div>
            <div class="form-group" style="margin-top: 12px;">
                <label for="modules-workbench-tool-code">Код atomic tool-фрагмента</label>
                <textarea id="modules-workbench-tool-code" rows="16" placeholder='return {"ok": True}'>${html(tool.user_function_body || "")}</textarea>
            </div>
        `;

        [
            "modules-workbench-tool-name",
            "modules-workbench-tool-method",
            "modules-workbench-tool-contract-version",
            "modules-workbench-tool-lifecycle",
            "modules-workbench-tool-description",
            "modules-workbench-tool-aliases",
            "modules-workbench-tool-error-codes",
            "modules-workbench-tool-params-schema",
            "modules-workbench-tool-output-schema",
            "modules-workbench-tool-artifacts",
            "modules-workbench-tool-domain",
            "modules-workbench-tool-kind",
            "modules-workbench-tool-risk-level",
            "modules-workbench-tool-timeout",
            "modules-workbench-tool-roles",
            "modules-workbench-tool-scopes",
            "modules-workbench-tool-dependency-min-agent-version",
            "modules-workbench-tool-required-binaries",
            "modules-workbench-tool-required-python-packages",
            "modules-workbench-tool-required-services",
            "modules-workbench-tool-required-permissions",
            "modules-workbench-tool-redaction-fields",
            "modules-workbench-tool-resource-runtime",
            "modules-workbench-tool-resource-stdout",
            "modules-workbench-tool-resource-stderr",
            "modules-workbench-tool-resource-artifact-count",
            "modules-workbench-tool-resource-artifact-bytes",
            "modules-workbench-tool-resource-subprocess-count",
            "modules-workbench-tool-resource-filesystem-scope",
            "modules-workbench-tool-resource-external-hosts",
            "modules-workbench-tool-requires-consent",
            "modules-workbench-tool-idempotent",
            "modules-workbench-tool-side-effects",
            "modules-workbench-tool-redaction-enabled",
            "modules-workbench-tool-redaction-headers",
            "modules-workbench-tool-redaction-env",
            "modules-workbench-tool-redaction-allow-raw",
            "modules-workbench-tool-code"
        ].forEach((id) => {
            const el = byId(id);
            if (!el || el.dataset.bound === "1") {
                return;
            }
            el.dataset.bound = "1";
            const handler = () => {
                syncCurrentToolFromEditor();
                refreshDraftViews();
            };
            el.addEventListener("input", handler);
            el.addEventListener("change", handler);
        });
        bindPlatformControls("modules-workbench-tool-platforms", () => {
            syncCurrentToolFromEditor();
            refreshDraftViews();
        });
        bindSchemaBlueprintControls({
            linesId: "modules-workbench-tool-params-schema-lines",
            additionalId: "modules-workbench-tool-params-schema-additional",
            jsonId: "modules-workbench-tool-params-schema",
            statusId: "modules-workbench-tool-params-schema-status",
            label: "Params schema"
        }, () => {
            syncCurrentToolFromEditor();
            refreshDraftViews();
        });
        bindSchemaBlueprintControls({
            linesId: "modules-workbench-tool-output-schema-lines",
            additionalId: "modules-workbench-tool-output-schema-additional",
            jsonId: "modules-workbench-tool-output-schema",
            statusId: "modules-workbench-tool-output-schema-status",
            label: "Output schema"
        }, () => {
            syncCurrentToolFromEditor();
            refreshDraftViews();
        });
        syncSchemaBlueprintControls({
            linesId: "modules-workbench-tool-params-schema-lines",
            additionalId: "modules-workbench-tool-params-schema-additional",
            jsonId: "modules-workbench-tool-params-schema",
            statusId: "modules-workbench-tool-params-schema-status",
            label: "Params schema"
        });
        syncSchemaBlueprintControls({
            linesId: "modules-workbench-tool-output-schema-lines",
            additionalId: "modules-workbench-tool-output-schema-additional",
            jsonId: "modules-workbench-tool-output-schema",
            statusId: "modules-workbench-tool-output-schema-status",
            label: "Output schema"
        });
        const paramsExampleBtn = byId("modules-workbench-tool-params-example-btn");
        if (paramsExampleBtn && paramsExampleBtn.dataset.bound !== "1") {
            paramsExampleBtn.dataset.bound = "1";
            paramsExampleBtn.addEventListener("click", () => {
                const linesEl = byId("modules-workbench-tool-params-schema-lines");
                const additionalEl = byId("modules-workbench-tool-params-schema-additional");
                if (linesEl) {
                    linesEl.value = formatSchemaBlueprint(TOOL_SCHEMA_EXAMPLES.params);
                }
                if (additionalEl) {
                    additionalEl.checked = TOOL_SCHEMA_EXAMPLES.params.additionalProperties === true;
                }
                syncSchemaBlueprintControls({
                    linesId: "modules-workbench-tool-params-schema-lines",
                    additionalId: "modules-workbench-tool-params-schema-additional",
                    jsonId: "modules-workbench-tool-params-schema",
                    statusId: "modules-workbench-tool-params-schema-status",
                    label: "Params schema"
                });
                syncCurrentToolFromEditor();
                refreshDraftViews();
            });
        }
        const outputExampleBtn = byId("modules-workbench-tool-output-example-btn");
        if (outputExampleBtn && outputExampleBtn.dataset.bound !== "1") {
            outputExampleBtn.dataset.bound = "1";
            outputExampleBtn.addEventListener("click", () => {
                const linesEl = byId("modules-workbench-tool-output-schema-lines");
                const additionalEl = byId("modules-workbench-tool-output-schema-additional");
                if (linesEl) {
                    linesEl.value = formatSchemaBlueprint(TOOL_SCHEMA_EXAMPLES.output);
                }
                if (additionalEl) {
                    additionalEl.checked = TOOL_SCHEMA_EXAMPLES.output.additionalProperties === true;
                }
                syncSchemaBlueprintControls({
                    linesId: "modules-workbench-tool-output-schema-lines",
                    additionalId: "modules-workbench-tool-output-schema-additional",
                    jsonId: "modules-workbench-tool-output-schema",
                    statusId: "modules-workbench-tool-output-schema-status",
                    label: "Output schema"
                });
                syncCurrentToolFromEditor();
                refreshDraftViews();
            });
        }
    }

    function syncCurrentToolFromEditor() {
        const tool = activeTool();
        if (!tool) {
            return [];
        }
        const errors = [];
        tool.tool_name = String(byId("modules-workbench-tool-name")?.value || "").trim();
        tool.method_name = String(byId("modules-workbench-tool-method")?.value || "").trim();
        tool.contract_version = String(byId("modules-workbench-tool-contract-version")?.value || "1.0.0").trim() || "1.0.0";
        tool.lifecycle = String(byId("modules-workbench-tool-lifecycle")?.value || "stable").trim() || "stable";
        tool.description = String(byId("modules-workbench-tool-description")?.value || "").trim();
        tool.aliases = parseListInput(byId("modules-workbench-tool-aliases")?.value || "");
        tool.error_codes = parseListInput(byId("modules-workbench-tool-error-codes")?.value || "");
        tool.params_schema = safeParseJson(byId("modules-workbench-tool-params-schema")?.value, { type: "object", properties: {} }, "Params schema", errors);
        tool.output_schema = safeParseJson(byId("modules-workbench-tool-output-schema")?.value, { type: "object", properties: {} }, "Output schema", errors);
        tool.metadata = {
            ...blankTool().metadata,
            ...(tool.metadata || {}),
            domain: String(byId("modules-workbench-tool-domain")?.value || "").trim() || "custom",
            platforms: readPlatformControls("modules-workbench-tool-platforms"),
            risk_level: String(byId("modules-workbench-tool-risk-level")?.value || "safe_read").trim() || "safe_read",
            requires_consent: byId("modules-workbench-tool-requires-consent")?.checked === true,
            timeout_sec: readIntInput("modules-workbench-tool-timeout", 30),
            idempotent: byId("modules-workbench-tool-idempotent")?.checked !== false,
            side_effects: byId("modules-workbench-tool-side-effects")?.checked === true,
            allow_roles: parseListInput(byId("modules-workbench-tool-roles")?.value || ""),
            scopes: parseListInput(byId("modules-workbench-tool-scopes")?.value || ""),
            origin: "managed",
            tool_kind: String(byId("modules-workbench-tool-kind")?.value || "diagnostic").trim() || "diagnostic",
        };
        tool.dependencies = {
            min_agent_version: String(byId("modules-workbench-tool-dependency-min-agent-version")?.value || "").trim() || null,
            required_binaries: parseListInput(byId("modules-workbench-tool-required-binaries")?.value || ""),
            required_python_packages: parseListInput(byId("modules-workbench-tool-required-python-packages")?.value || ""),
            required_services: parseListInput(byId("modules-workbench-tool-required-services")?.value || ""),
            required_permissions: parseListInput(byId("modules-workbench-tool-required-permissions")?.value || ""),
        };
        tool.artifact_types = parseArtifactKinds(byId("modules-workbench-tool-artifacts")?.value || "");
        tool.redaction = {
            enabled: byId("modules-workbench-tool-redaction-enabled")?.checked !== false,
            redact_headers: byId("modules-workbench-tool-redaction-headers")?.checked !== false,
            redact_env: byId("modules-workbench-tool-redaction-env")?.checked !== false,
            redact_fields: parseListInput(byId("modules-workbench-tool-redaction-fields")?.value || ""),
            allow_raw_sensitive_data: byId("modules-workbench-tool-redaction-allow-raw")?.checked === true,
        };
        tool.resources = {
            max_runtime_sec: readIntInput("modules-workbench-tool-resource-runtime", 30),
            max_stdout_bytes: readIntInput("modules-workbench-tool-resource-stdout", 65536),
            max_stderr_bytes: readIntInput("modules-workbench-tool-resource-stderr", 65536),
            max_artifact_count: readIntInput("modules-workbench-tool-resource-artifact-count", 0),
            max_artifact_bytes: readIntInput("modules-workbench-tool-resource-artifact-bytes", 0),
            max_subprocess_count: readIntInput("modules-workbench-tool-resource-subprocess-count", 2),
            allowed_filesystem_scope: parseListInput(byId("modules-workbench-tool-resource-filesystem-scope")?.value || ""),
            allowed_external_hosts: parseListInput(byId("modules-workbench-tool-resource-external-hosts")?.value || ""),
        };
        tool.user_function_body = String(byId("modules-workbench-tool-code")?.value || "").trim();
        return errors;
    }

    function applyTemplateToCurrentTool(templateKey) {
        if (!state.currentDraft?.tools?.length) {
            state.currentDraft = createEmptyDraft();
        }
        state.currentDraft.tools[state.selectedToolIndex] = createToolTemplate(templateKey);
        state.serverValidation = null;
        renderToolTabs();
        renderToolEditor();
        refreshDraftViews();
    }

    function addToolFromTemplate(templateKey) {
        if (!state.currentDraft) {
            state.currentDraft = createEmptyDraft();
        }
        state.currentDraft.tools.push(createToolTemplate(templateKey));
        state.selectedToolIndex = state.currentDraft.tools.length - 1;
        state.serverValidation = null;
        renderToolTabs();
        renderToolEditor();
        refreshDraftViews();
    }

    function duplicateCurrentTool() {
        const tool = state.currentDraft?.tools?.[state.selectedToolIndex];
        if (!tool) {
            return;
        }
        const copy = clone(tool);
        copy.tool_name = copy.tool_name ? `${copy.tool_name}_copy`.replace(/\.+/g, ".") : "";
        copy.method_name = copy.method_name ? `${copy.method_name}_copy` : "run_copy";
        copy.reconstruction_strategy = "draft";
        state.currentDraft.tools.splice(state.selectedToolIndex + 1, 0, copy);
        state.selectedToolIndex += 1;
        state.serverValidation = null;
        renderToolTabs();
        renderToolEditor();
        refreshDraftViews();
    }

    function removeCurrentTool() {
        if (!state.currentDraft?.tools?.length) {
            return;
        }
        if (state.currentDraft.tools.length === 1) {
            setMessage("warning", "У модуля должен остаться хотя бы один tool.");
            return;
        }
        state.currentDraft.tools.splice(state.selectedToolIndex, 1);
        state.selectedToolIndex = Math.max(0, state.selectedToolIndex - 1);
        state.serverValidation = null;
        renderToolTabs();
        renderToolEditor();
        refreshDraftViews();
    }

    function refreshDraftViews() {
        renderSummary();
        renderTopFields();
        renderToolTabs();
        renderToolEditor();
        renderDevelopmentWizard();
        renderLocalValidation();
        renderApiPreview();
    }

    function validateDraftLocally() {
        const errors = [];
        const warnings = [];
        const draft = state.currentDraft || createEmptyDraft();
        const topErrors = syncTopFieldsFromDom();
        const toolSyncErrors = syncCurrentToolFromEditor();
        const wizardErrors = [
            ...(syncWizardBasicsFromDom() || []),
            ...(syncWizardToolCoreFromDom() || []),
        ];
        syncWizardToolPolicyFromDom();
        errors.push(...topErrors, ...toolSyncErrors, ...wizardErrors);
        [
            {
                linesId: "modules-workbench-wizard-tool-params-schema-lines",
                additionalId: "modules-workbench-wizard-tool-params-schema-additional",
                jsonId: "modules-workbench-wizard-tool-params-schema",
                statusId: "modules-workbench-wizard-tool-params-schema-status",
                label: "Params schema",
            },
            {
                linesId: "modules-workbench-wizard-tool-output-schema-lines",
                additionalId: "modules-workbench-wizard-tool-output-schema-additional",
                jsonId: "modules-workbench-wizard-tool-output-schema",
                statusId: "modules-workbench-wizard-tool-output-schema-status",
                label: "Output schema",
            },
            {
                linesId: "modules-workbench-tool-params-schema-lines",
                additionalId: "modules-workbench-tool-params-schema-additional",
                jsonId: "modules-workbench-tool-params-schema",
                statusId: "modules-workbench-tool-params-schema-status",
                label: "Params schema",
            },
            {
                linesId: "modules-workbench-tool-output-schema-lines",
                additionalId: "modules-workbench-tool-output-schema-additional",
                jsonId: "modules-workbench-tool-output-schema",
                statusId: "modules-workbench-tool-output-schema-status",
                label: "Output schema",
            },
        ].forEach((options) => {
            const result = syncSchemaBlueprintControls(options);
            if (result.errors?.length) {
                errors.push(...result.errors);
            }
        });

        if (!draft.module_name) {
            errors.push("Нужно указать имя модуля.");
        } else if (!MODULE_NAME_RE.test(draft.module_name)) {
            errors.push("Имя модуля должно состоять из lowercase букв, цифр и underscore.");
        }
        if (!OWNER_SCOPE_OPTIONS.includes(String(draft.owner_scope || "").trim())) {
            errors.push(`Owner scope должен быть одним из: ${OWNER_SCOPE_OPTIONS.join(", ")}.`);
        }
        if (!draft.version) {
            errors.push("Нужно указать версию модуля.");
        } else if (!SEMVER_RE.test(draft.version)) {
            warnings.push("Версия выглядит не как semver. Для production лучше придерживаться x.y.z.");
        }
        if (!draft.description) {
            errors.push("Описание модуля обязательно.");
        }
        if (!Array.isArray(draft.tools) || !draft.tools.length) {
            errors.push("Нужно определить хотя бы один tool.");
        }
        if (!Array.isArray(draft.platforms)) {
            errors.push("Платформы модуля не распознаны.");
        } else if (!draft.platforms.length) {
            errors.push("Нужно выбрать хотя бы одну платформу модуля.");
        } else if (draft.platforms.includes("any") && draft.platforms.length > 1) {
            errors.push("Платформа 'any' не должна сочетаться с конкретными платформами.");
        }

        (draft.tools || []).forEach((tool, index) => {
            const label = tool.tool_name || `tool #${index + 1}`;
            if (!tool.tool_name) {
                errors.push(`Tool #${index + 1}: нужен canonical tool id.`);
            } else if (!TOOL_NAME_RE.test(tool.tool_name)) {
                errors.push(`${label}: canonical tool id должен быть semantic вида dns.resolve.`);
            }
            const namespace = String(tool.tool_name || "").split(".")[0];
            if ((draft.owner_scope || "vendor") === "vendor" && RESERVED_NAMESPACES.has(namespace)) {
                errors.push(`${label}: reserved namespace ${namespace}.* нельзя публиковать как vendor module.`);
            }
            if (!tool.method_name || !METHOD_RE.test(tool.method_name)) {
                errors.push(`${label}: method должен быть корректным Python identifier.`);
            }
            if (!tool.description) {
                errors.push(`${label}: описание обязательно.`);
            }
            if (!tool.contract_version) {
                errors.push(`${label}: contract_version обязателен.`);
            } else if (!SEMVER_RE.test(String(tool.contract_version))) {
                warnings.push(`${label}: contract_version лучше держать в semver формате.`);
            }
            if (!tool.user_function_body) {
                errors.push(`${label}: код tool-фрагмента пустой.`);
            }
            if (!tool.params_schema || tool.params_schema.type !== "object") {
                warnings.push(`${label}: params_schema обычно должен быть JSON Schema object.`);
            }
            if (!tool.output_schema || tool.output_schema.type !== "object") {
                warnings.push(`${label}: output_schema обычно должен быть JSON Schema object.`);
            }
            if (!Array.isArray(tool.aliases)) {
                errors.push(`${label}: aliases должны быть массивом.`);
            }
            if (!Array.isArray(tool.error_codes) || !tool.error_codes.length) {
                warnings.push(`${label}: лучше явно указать error_codes, чтобы playbook decisions были предсказуемыми.`);
            }
            if (!tool.metadata || typeof tool.metadata !== "object") {
                errors.push(`${label}: metadata должны быть объектом.`);
            } else {
                if (!tool.metadata.domain) {
                    warnings.push(`${label}: metadata.domain не заполнен.`);
                }
                if (!Array.isArray(tool.metadata.platforms) || !tool.metadata.platforms.length) {
                    errors.push(`${label}: нужно выбрать хотя бы одну platform в metadata.`);
                } else if (tool.metadata.platforms.includes("any") && tool.metadata.platforms.length > 1) {
                    errors.push(`${label}: metadata.platforms не может сочетать any с конкретными платформами.`);
                }
                if (!tool.metadata.risk_level) {
                    warnings.push(`${label}: metadata.risk_level не указан.`);
                }
            }
            if (!tool.dependencies || typeof tool.dependencies !== "object") {
                errors.push(`${label}: dependencies должны быть заполнены.`);
            }
            if (!tool.redaction || typeof tool.redaction !== "object") {
                errors.push(`${label}: redaction должна быть заполнена.`);
            }
            if (!tool.resources || typeof tool.resources !== "object") {
                errors.push(`${label}: resources должны быть заполнены.`);
            }
        });

        return { errors, warnings };
    }

    function renderLocalValidation() {
        const el = byId("modules-workbench-local-validation");
        if (!el) {
            return;
        }
        const result = validateDraftLocally();
        if (!result.errors.length && !result.warnings.length) {
            el.innerHTML = '<div class="mw-chip is-accent">Форма выглядит согласованной ещё до server validate.</div>';
            return;
        }
        const blocks = [];
        if (result.errors.length) {
            blocks.push(`
                <div class="mw-empty" style="border-style: solid; border-color: rgba(185, 28, 28, 0.25);">
                    <div class="mw-chip is-danger" style="margin-bottom: 8px;">Ошибки: ${result.errors.length}</div>
                    <ul class="mw-validation-list">${result.errors.map((item) => `<li>${html(item)}</li>`).join("")}</ul>
                </div>
            `);
        }
        if (result.warnings.length) {
            blocks.push(`
                <div class="mw-empty" style="border-style: solid; border-color: rgba(180, 83, 9, 0.25);">
                    <div class="mw-chip is-warning" style="margin-bottom: 8px;">Предупреждения: ${result.warnings.length}</div>
                    <ul class="mw-validation-list">${result.warnings.map((item) => `<li>${html(item)}</li>`).join("")}</ul>
                </div>
            `);
        }
        el.innerHTML = blocks.join("");
    }

    function renderServerValidation() {
        const el = byId("modules-workbench-server-validation");
        if (!el) {
            return;
        }
        const data = state.serverValidation;
        if (!data) {
            el.innerHTML = '<div class="mw-empty">Нажмите «Проверить», чтобы получить server-side preflight, smoke и preview собранного пакета.</div>';
            return;
        }
        if (data.status === "error") {
            const errors = data.preflight_errors || [data.error || "Server validate failed"];
            el.innerHTML = `
                <div class="mw-empty" style="border-style: solid; border-color: rgba(185, 28, 28, 0.25);">
                    <div class="mw-chip is-danger" style="margin-bottom: 8px;">Validate failed</div>
                    <ul class="mw-validation-list">${errors.map((item) => `<li>${html(item)}</li>`).join("")}</ul>
                </div>
            `;
            return;
        }

        const chips = [
            `<span class="mw-chip is-accent">preflight: ${html(data.preflight_status || "passed")}</span>`,
            `<span class="mw-chip">${html(data.validation_status || "passed")}</span>`,
            `<span class="mw-chip">${html(String(data.tools_count || 0))} tool(s)</span>`,
            `<span class="mw-chip ${data.publish_ready ? "is-accent" : "is-warning"}">${data.publish_ready ? "publish-ready" : "conflicts detected"}</span>`,
            data.module_exists ? '<span class="mw-chip is-warning">version already exists</span>' : "",
        ].filter(Boolean).join("");
        const warnings = data.warnings || [];
        const conflicts = data.conflicts || [];
        el.innerHTML = `
            <div class="mw-chip-row">${chips}</div>
            ${warnings.length ? `<div class="mw-empty" style="margin-top: 12px;"><div class="mw-chip is-warning" style="margin-bottom: 8px;">Warnings</div><ul class="mw-validation-list">${warnings.map((item) => `<li>${html(item)}</li>`).join("")}</ul></div>` : ""}
            ${conflicts.length ? `<div class="mw-empty" style="margin-top: 12px; border-style: solid; border-color: rgba(185, 28, 28, 0.25);"><div class="mw-chip is-danger" style="margin-bottom: 8px;">Ownership conflicts</div><ul class="mw-validation-list">${conflicts.map((item) => `<li>${html(item.identifier)} already owned by ${html(item.existing_module_name)} ${html(item.existing_version)}</li>`).join("")}</ul></div>` : ""}
        `;
    }

    function draftToPayload() {
        syncTopFieldsFromDom();
        syncCurrentToolFromEditor();
        syncWizardBasicsFromDom();
        syncWizardToolCoreFromDom();
        syncWizardToolPolicyFromDom();
        const draft = clone(state.currentDraft || createEmptyDraft());
        return {
            module_name: draft.module_name,
            version: draft.version,
            module_api_version: draft.module_api_version,
            owner_scope: draft.owner_scope,
            description: draft.description,
            platforms: draft.platforms,
            requirements: draft.requirements,
            optional_requirements: draft.optional_requirements,
            min_agent_version: draft.min_agent_version,
            entrypoint: draft.entrypoint,
            tools: (draft.tools || []).map((tool) => ({
                tool_name: tool.tool_name,
                aliases: tool.aliases || [],
                method_name: tool.method_name,
                description: tool.description,
                params_schema: tool.params_schema,
                output_schema: tool.output_schema,
                presets: tool.presets || [],
                capabilities: tool.capabilities || [],
                metadata: tool.metadata || {},
                contract_version: tool.contract_version,
                dependencies: tool.dependencies || {},
                lifecycle: tool.lifecycle || "stable",
                error_codes: tool.error_codes || [],
                artifact_types: tool.artifact_types || [],
                redaction: tool.redaction || {},
                resources: tool.resources || {},
                user_function_body: tool.user_function_body || "",
            })),
        };
    }

    function renderApiPreviewTabs() {
        const wrap = byId("modules-workbench-api-tabs");
        if (!wrap) {
            return;
        }
        wrap.innerHTML = API_PREVIEW_MODES.map((mode) => {
            const labels = {
                payload: "JSON payload",
                "curl-validate": "curl validate",
                "curl-save": "curl save",
                "fetch-save": "fetch save",
            };
            return `<button type="button" class="mw-tab-btn ${state.apiPreviewMode === mode ? "is-active" : ""}" data-api-preview-mode="${mode}">${labels[mode]}</button>`;
        }).join("");
        wrap.querySelectorAll("[data-api-preview-mode]").forEach((button) => {
            button.addEventListener("click", () => {
                state.apiPreviewMode = button.getAttribute("data-api-preview-mode");
                renderApiPreviewTabs();
                renderApiPreview();
            });
        });
    }

    function renderApiPreview() {
        const pre = byId("modules-workbench-api-preview");
        if (!pre) {
            return;
        }
        let payload;
        try {
            payload = draftToPayload();
        } catch (error) {
            pre.textContent = `Cannot build preview yet: ${error.message}`;
            return;
        }
        if (state.apiPreviewMode === "payload") {
            pre.textContent = pretty(payload);
            return;
        }
        if (state.apiPreviewMode === "curl-validate") {
            pre.textContent = [
                "curl -X POST http://192.168.100.17:8666/api/modules/workbench/validate \\",
                '  -H "Authorization: Bearer <admin-token>" \\',
                '  -H "Content-Type: application/json" \\',
                `  -d '${JSON.stringify(payload)}'`,
            ].join("\n");
            return;
        }
        if (state.apiPreviewMode === "curl-save") {
            pre.textContent = [
                "curl -X POST http://192.168.100.17:8666/api/modules/workbench/save \\",
                '  -H "Authorization: Bearer <admin-token>" \\',
                '  -H "Content-Type: application/json" \\',
                `  -d '${JSON.stringify(payload)}'`,
            ].join("\n");
            return;
        }
        pre.textContent = [
            "const payload = " + pretty(payload) + ";",
            "",
            "const response = await fetch('/api/modules/workbench/save', {",
            "  method: 'POST',",
            "  headers: {",
            "    ...getAuthHeaders(true),",
            "  },",
            "  body: JSON.stringify(payload),",
            "});",
            "const data = await response.json();",
            "console.log(data);",
        ].join("\n");
    }

    function getActiveSource() {
        return state.serverValidation?.editable_preview?.source || state.currentDraft?.source || null;
    }

    function renderSourceExplorer() {
        const summaryWrap = byId("modules-workbench-source-summary");
        const listWrap = byId("modules-workbench-source-files");
        const metaWrap = byId("modules-workbench-source-meta");
        const contentWrap = byId("modules-workbench-source-content");
        if (!summaryWrap || !listWrap || !metaWrap || !contentWrap) {
            return;
        }
        const source = getActiveSource();
        const files = source?.files || [];
        const decomposition = source?.decomposition || {};
        summaryWrap.innerHTML = [
            `<span class="mw-chip is-accent">resolved ${html(String(decomposition.resolved_tools || 0))}</span>`,
            (decomposition.unresolved_tools || []).length ? `<span class="mw-chip is-warning">unresolved ${(decomposition.unresolved_tools || []).length}</span>` : "",
            (decomposition.available_methods || []).length ? `<span class="mw-chip">${html((decomposition.available_methods || []).length)} methods detected</span>` : "",
            (decomposition.available_tool_names || []).length ? `<span class="mw-chip">${html((decomposition.available_tool_names || []).length)} tool ids detected</span>` : "",
        ].filter(Boolean).join("");

        if (!files.length) {
            listWrap.innerHTML = '<div class="mw-empty">Сырые source-файлы появятся после открытия версии или server validate preview.</div>';
            metaWrap.textContent = "Файл не выбран.";
            contentWrap.textContent = "";
            return;
        }

        if (!state.selectedSourcePath || !files.some((file) => file.path === state.selectedSourcePath)) {
            state.selectedSourcePath = files[0].path;
        }
        listWrap.innerHTML = files.map((file) => `
            <button type="button" class="mw-file-btn ${file.path === state.selectedSourcePath ? "is-active" : ""}" data-source-path="${html(file.path)}">
                <div style="font-weight: 600; margin-bottom: 4px;">${html(file.path)}</div>
                <div class="mw-subtle">${html(file.language || "text")} • ${html(String(file.size_bytes || 0))} bytes • detected ${(file.detected_tools || []).length}</div>
            </button>
        `).join("");
        listWrap.querySelectorAll("[data-source-path]").forEach((button) => {
            button.addEventListener("click", () => {
                state.selectedSourcePath = button.getAttribute("data-source-path");
                renderSourceExplorer();
            });
        });
        const activeFile = files.find((file) => file.path === state.selectedSourcePath) || files[0];
        metaWrap.innerHTML = [
            `<strong>${html(activeFile.path)}</strong>`,
            `${html(activeFile.language || "text")} • ${html(String(activeFile.size_bytes || 0))} bytes`,
            (activeFile.detected_tools || []).length
                ? `• ${html((activeFile.detected_tools || []).map((item) => `${item.tool_name || item.method} (${item.strategy})`).join(", "))}`
                : "",
            (activeFile.parse_errors || []).length
                ? `• parse warnings: ${html((activeFile.parse_errors || []).join("; "))}`
                : "",
        ].filter(Boolean).join(" ");
        contentWrap.textContent = activeFile.content || "";
    }

    async function validateDraftOnServer() {
        const local = validateDraftLocally();
        if (local.errors.length) {
            setMessage("warning", "Сначала исправьте локальные ошибки формы — после этого server validate будет полезнее.");
            renderLocalValidation();
            return;
        }
        try {
            const response = await fetch("/api/modules/workbench/validate", {
                method: "POST",
                headers: getAuthHeaders(true),
                body: JSON.stringify(draftToPayload()),
            });
            const data = await responseToJson(response);
            state.serverValidation = data;
            if (!response.ok || data.status === "error") {
                setMessage("error", data.error || "Server validate failed.");
            } else if ((data.conflicts || []).length) {
                setMessage("warning", "Validate завершён, но publish пока заблокирован конфликтами ownership.");
            } else {
                setMessage("success", "Server validate прошёл. Можно смотреть manifest preview, generated sources и публиковать модуль.");
            }
            renderServerValidation();
            renderApiPreview();
            renderSourceExplorer();
        } catch (error) {
            setMessage("error", error.message);
        }
    }

    async function saveDraft() {
        const local = validateDraftLocally();
        if (local.errors.length) {
            setMessage("warning", "Сохранение заблокировано: есть локальные ошибки формы.");
            renderLocalValidation();
            return;
        }
        try {
            const response = await fetch("/api/modules/workbench/save", {
                method: "POST",
                headers: getAuthHeaders(true),
                body: JSON.stringify(draftToPayload()),
            });
            const data = await responseToJson(response);
            if (!response.ok || data.status !== "success") {
                setMessage("error", data.error || "Не удалось сохранить модуль.", (data.preflight_errors || []).map((item) => html(item)).join("<br>"));
                return;
            }
            const rolloutMessage = rolloutSummaryText(data.rollout_summary);
            setMessage(
                "success",
                `Модуль ${data.module_name}/${data.version} сохранён в server registry.`,
                rolloutMessage ? html(rolloutMessage) : ""
            );
            await load();
            await refreshOuterModuleInstallViews();
            state.selectedFamily = data.module_name;
            state.selectedVersion = data.version;
            await loadVersionDetail(data.module_name, data.version);
        } catch (error) {
            setMessage("error", error.message);
        }
    }

    async function deleteModuleVersion(moduleName, version) {
        if (!moduleName || !version) {
            setMessage("warning", "Сначала выберите семейство и версию, которую нужно удалить.");
            return;
        }
        const confirmed = window.confirm(`Удалить модуль ${moduleName} версии ${version} с сервера? Это удалит запись из registry и архив с диска.`);
        if (!confirmed) {
            return;
        }
        try {
            const response = await fetch(`/api/modules/${encodeURIComponent(moduleName)}/${encodeURIComponent(version)}`, {
                method: "DELETE",
                headers: getAuthHeaders(true),
            });
            const data = await responseToJson(response);
            if (!response.ok || data.status !== "ok") {
                setMessage("error", data.error || "Не удалось удалить модуль.");
                return;
            }
            if (state.selectedFamily === moduleName && state.selectedVersion === version) {
                state.selectedFamily = null;
                state.selectedVersion = null;
                state.selectedToolIndex = 0;
                state.selectedSourcePath = null;
                state.currentDraft = createEmptyDraft();
                state.serverValidation = null;
            }
            await load();
            await refreshOuterModuleInstallViews();
            requestModulesSubtab("list");
            setCurrentView("list");
            setMessage("success", `Модуль ${moduleName}/${version} удалён из server registry.`);
        } catch (error) {
            setMessage("error", error.message);
        }
    }

    async function setPreferredVersion() {
        if (!state.selectedFamily || !state.selectedVersion) {
            setMessage("warning", "Сначала выберите семейство и версию, которую нужно сделать приоритетной.");
            return;
        }
        try {
            const response = await fetch(`/api/modules/${encodeURIComponent(state.selectedFamily)}/preferred`, {
                method: "PATCH",
                headers: getAuthHeaders(true),
                body: JSON.stringify({ version: state.selectedVersion }),
            });
            const data = await responseToJson(response);
            if (!response.ok || data.status !== "ok") {
                setMessage("error", data.error || "Не удалось назначить приоритетную версию.");
                return;
            }
            const rolloutMessage = rolloutSummaryText(data.rollout_summary);
            setMessage(
                "success",
                `Приоритетная версия для ${state.selectedFamily} обновлена: ${state.selectedVersion}.`,
                rolloutMessage ? html(rolloutMessage) : ""
            );
            await load();
            await refreshOuterModuleInstallViews();
        } catch (error) {
            setMessage("error", error.message);
        }
    }

    window.ModuleWorkbench = {
        load,
        switchView(view, options) {
            setCurrentView(view, options);
        },
    };
})();


