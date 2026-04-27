import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Boxes,
  CheckCircle2,
  ChevronRight,
  Copy,
  FileArchive,
  FileCode2,
  FileJson,
  FolderKanban,
  PackagePlus,
  PlayCircle,
  RefreshCcw,
  Save,
  Search,
  ShieldCheck,
  Sparkles,
  Trash2,
  Upload,
  Wand2,
  Wrench,
} from "lucide-react";
import {
  startTransition,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../components/ui/card";
import { SearchField } from "../../components/ui/search-field";
import { Select } from "../../components/ui/select";
import { Tabs } from "../../components/ui/tabs";
import { cn } from "../../shared/ui/cn";
import {
  deleteModuleWorkbenchVersion,
  fetchModuleLiveTestCandidates,
  fetchModuleWorkbenchDetail,
  fetchModuleWorkbenchList,
  patchModuleWorkbenchRolloutSettings,
  runModuleLiveTest,
  saveModuleWorkbenchDraft,
  setModuleWorkbenchPreferredVersion,
  type ModuleLiveTestCandidate,
  type ModuleLiveTestResult,
  type ModuleArchiveUploadPayload,
  type ModuleWorkbenchDraft,
  type ModuleWorkbenchFamilyRecord,
  type ModuleWorkbenchRolloutSettings,
  type ModuleWorkbenchToolDraft,
  type ModuleWorkbenchValidationPayload,
  uploadModuleWorkbenchArchive,
  validateModuleWorkbenchDraft,
} from "./workbench-api";

type WorkspaceTab = "registry" | "development" | "archive";
type DevelopmentTab = "basics" | "tool" | "preview" | "source";
type PreviewTab = "payload" | "curl-validate" | "curl-save";
type ActionFeedback =
  | {
      tone: "success" | "error";
      text: string;
    }
  | null;

const MODULE_NAME_RE = /^[a-z0-9_]+$/;
const TOOL_NAME_RE = /^[a-z0-9_]+(?:\.[a-z0-9_]+)+$/;
const METHOD_NAME_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;
const CONTRACT_PATH_RE = /^[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*$/;
const OUTPUT_CONTRACT_DEFAULT = {
  schema_version: "1.0",
  status_path: "result.status",
  status_values: ["ok", "error"],
  success_values: ["ok"],
  error_values: ["error"],
  summary_path: "result.output.summary",
  error_code_path: "result.error.code",
  compact_fields: [],
} satisfies Record<string, unknown>;

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "Нет данных";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatDuration(value: number | null | undefined): string {
  if (value == null || value <= 0) {
    return "—";
  }
  if (value < 1000) {
    return `${value} мс`;
  }
  return `${(value / 1000).toFixed(1)} с`;
}

function validationTone(value: string | null | undefined) {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (normalized === "passed") {
    return "success" as const;
  }
  if (normalized === "warning") {
    return "warning" as const;
  }
  if (normalized === "failed") {
    return "danger" as const;
  }
  return "neutral" as const;
}

function rolloutModeLabel(value: string) {
  return value === "installed_devices"
    ? "Обновлять установленные устройства"
    : "Только вручную";
}

function buildVersionKey(moduleName: string, version: string) {
  return `${moduleName}:${version}`;
}

function prettyJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

function safeParseJson<T>(raw: string, fallback: T): T {
  const trimmed = raw.trim();
  if (!trimmed) {
    return fallback;
  }
  return JSON.parse(trimmed) as T;
}

function splitLines(raw: string) {
  return raw
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinLines(items: string[] | null | undefined) {
  return (items ?? []).join("\n");
}

function normalizePlatform(value: string): string {
  const normalized = value.trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (normalized === "windows" || normalized === "win" || normalized === "win32" || normalized.startsWith("windows")) {
    return "win32";
  }
  if (normalized === "linux" || normalized.startsWith("linux")) {
    return "linux";
  }
  if (normalized === "mac" || normalized === "macos" || normalized === "darwin" || normalized.startsWith("darwin")) {
    return "darwin";
  }
  return normalized;
}

function targetsWindows(platforms: string[] | null | undefined): boolean {
  return (platforms ?? []).some((platform) => normalizePlatform(platform) === "win32");
}

function platformLabel(value: string): string {
  if (value === "win32") {
    return "Windows";
  }
  if (value === "linux") {
    return "Linux";
  }
  if (value === "darwin") {
    return "macOS";
  }
  return value || "any";
}

function candidateLabel(candidate: ModuleLiveTestCandidate): string {
  const host = candidate.hostname || candidate.device_id;
  const version = candidate.agent_version ? `agent ${candidate.agent_version}` : "agent ?";
  return `${host} · ${platformLabel(candidate.platform)} · ${version}${candidate.online ? "" : " · offline"}`;
}

function stringListFromUnknown(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => String(item ?? "").trim()).filter(Boolean)
    : [];
}

function normalizeOutputContract(value: unknown): Record<string, unknown> {
  const current =
    value && typeof value === "object" && !Array.isArray(value)
      ? (value as Record<string, unknown>)
      : {};
  const statusValues = stringListFromUnknown(current.status_values);
  const normalizedStatusValues = statusValues.length
    ? Array.from(new Set(statusValues))
    : [...OUTPUT_CONTRACT_DEFAULT.status_values];
  const successValues = stringListFromUnknown(current.success_values);
  const errorValues = stringListFromUnknown(current.error_values);
  return {
    ...OUTPUT_CONTRACT_DEFAULT,
    ...current,
    status_path: String(current.status_path ?? OUTPUT_CONTRACT_DEFAULT.status_path),
    status_values: normalizedStatusValues,
    success_values: successValues.length
      ? Array.from(new Set(successValues))
      : normalizedStatusValues.includes("ok")
        ? ["ok"]
        : [normalizedStatusValues[0]],
    error_values: errorValues.length
      ? Array.from(new Set(errorValues))
      : normalizedStatusValues.includes("error")
        ? ["error"]
        : [normalizedStatusValues[normalizedStatusValues.length - 1]],
    summary_path: String(current.summary_path ?? OUTPUT_CONTRACT_DEFAULT.summary_path),
    error_code_path: String(current.error_code_path ?? OUTPUT_CONTRACT_DEFAULT.error_code_path),
    compact_fields: Array.isArray(current.compact_fields) ? current.compact_fields : [],
  };
}

function outputContractString(contract: Record<string, unknown>, key: string): string {
  return String(contract[key] ?? "");
}

function outputContractList(contract: Record<string, unknown>, key: string): string[] {
  return stringListFromUnknown(contract[key]);
}

function createEmptyTool(index: number): ModuleWorkbenchToolDraft {
  const suffix = index + 1;
  return {
    tool_name: `custom.tool_${suffix}`,
    aliases: [],
    method_name: `tool_${suffix}`,
    description: "",
    params_schema: {
      type: "object",
      properties: {},
      required: [],
    },
    output_schema: {
      type: "object",
      properties: {},
    },
    output_contract: normalizeOutputContract(null),
    presets: [],
    capabilities: [],
    metadata: {
      risk_level: "safe_read",
      tool_kind: "diagnostic",
      timeout_sec: 30,
      platforms: ["any"],
      allow_roles: ["admin"],
      scopes: [],
      requires_consent: false,
      idempotent: true,
      side_effects: false,
    },
    contract_version: "1.0.0",
    dependencies: {},
    lifecycle: "stable",
    error_codes: [],
    artifact_types: [],
    redaction: {},
    resources: {
      max_runtime_sec: 30,
      max_stdout_bytes: 65536,
      max_stderr_bytes: 65536,
      max_artifact_count: 2,
      max_artifact_bytes: 5242880,
      max_subprocess_count: 2,
      allowed_filesystem_scope: [],
      allowed_external_hosts: [],
    },
    user_function_body: "return {}",
    reconstruction_strategy: "draft",
  };
}

function createBlankDraft(): ModuleWorkbenchDraft {
  return {
    module_name: "new_module",
    version: "1.0.0",
    module_api_version: "1.0.0",
    owner_scope: "vendor",
    description: "",
    platforms: ["any"],
    requirements: [],
    optional_requirements: [],
    min_agent_version: null,
    entrypoint: "module:register",
    tools: [createEmptyTool(0)],
    warnings: [],
    source: {
      manifest_json_text: "{}",
      module_py_text: "",
      files: [],
      decomposition: {
        resolved_tools: 0,
        unresolved_tools: [],
        available_methods: [],
        available_tool_names: [],
      },
    },
  };
}

function cloneDraft(draft: ModuleWorkbenchDraft): ModuleWorkbenchDraft {
  return JSON.parse(JSON.stringify(draft)) as ModuleWorkbenchDraft;
}

function buildDraftPayload(draft: ModuleWorkbenchDraft) {
  return {
    module_name: draft.module_name.trim(),
    version: draft.version.trim(),
    module_api_version: draft.module_api_version.trim() || "1.0.0",
    owner_scope: draft.owner_scope.trim() || "vendor",
    description: draft.description.trim(),
    platforms: draft.platforms,
    requirements: draft.requirements,
    optional_requirements: draft.optional_requirements,
    min_agent_version: draft.min_agent_version?.trim() || null,
    entrypoint: draft.entrypoint.trim() || "module:register",
    tools: draft.tools.map((tool) => ({
      tool_name: tool.tool_name.trim(),
      aliases: tool.aliases,
      method_name: tool.method_name.trim(),
      description: tool.description.trim(),
      params_schema: tool.params_schema,
      output_schema: tool.output_schema,
      output_contract: normalizeOutputContract(tool.output_contract),
      presets: tool.presets,
      capabilities: tool.capabilities,
      metadata: tool.metadata,
      contract_version: tool.contract_version.trim() || "1.0.0",
      dependencies: tool.dependencies,
      lifecycle: tool.lifecycle.trim() || "stable",
      error_codes: tool.error_codes,
      artifact_types: tool.artifact_types,
      redaction: tool.redaction,
      resources: tool.resources,
      user_function_body: tool.user_function_body,
    })),
  };
}

function buildDraftFingerprint(draft: ModuleWorkbenchDraft | null) {
  return JSON.stringify(draft ? buildDraftPayload(draft) : null);
}

function validateDraft(draft: ModuleWorkbenchDraft | null): string[] {
  if (!draft) {
    return [];
  }

  const issues: string[] = [];
  if (!draft.module_name.trim()) {
    issues.push("Укажите module_name.");
  } else if (!MODULE_NAME_RE.test(draft.module_name.trim())) {
    issues.push("module_name должен содержать только a-z, 0-9 и underscore.");
  }

  if (!draft.version.trim()) {
    issues.push("Укажите версию модуля.");
  }

  if (!draft.tools.length) {
    issues.push("Добавьте хотя бы один инструмент.");
  }

  const toolNames = new Set<string>();
  const methodNames = new Set<string>();
  draft.tools.forEach((tool, index) => {
    const label = tool.tool_name.trim() || `tool #${index + 1}`;
    if (!tool.tool_name.trim()) {
      issues.push(`Инструмент #${index + 1}: задайте tool_name.`);
    } else if (!TOOL_NAME_RE.test(tool.tool_name.trim())) {
      issues.push(`${label}: tool_name должен быть в dotted-формате.`);
    }
    if (toolNames.has(tool.tool_name.trim())) {
      issues.push(`${label}: tool_name повторяется в модуле.`);
    }
    toolNames.add(tool.tool_name.trim());

    if (!tool.method_name.trim()) {
      issues.push(`${label}: задайте method_name.`);
    } else if (!METHOD_NAME_RE.test(tool.method_name.trim())) {
      issues.push(`${label}: method_name должен быть валидным Python-идентификатором.`);
    }
    if (methodNames.has(tool.method_name.trim())) {
      issues.push(`${label}: method_name повторяется.`);
    }
    methodNames.add(tool.method_name.trim());

    if (!tool.user_function_body.trim()) {
      issues.push(`${label}: добавьте тело функции.`);
    }
    const outputContract = normalizeOutputContract(tool.output_contract);
    const statusPath = outputContractString(outputContract, "status_path");
    const summaryPath = outputContractString(outputContract, "summary_path");
    const errorCodePath = outputContractString(outputContract, "error_code_path");
    const statusValues = outputContractList(outputContract, "status_values");
    const successValues = outputContractList(outputContract, "success_values");
    const errorValues = outputContractList(outputContract, "error_values");
    if (!CONTRACT_PATH_RE.test(statusPath)) {
      issues.push(`${label}: output_contract.status_path должен быть dotted path, например result.status.`);
    }
    if (!statusValues.length) {
      issues.push(`${label}: output_contract.status_values должен явно перечислять статусы.`);
    }
    const successOutside = successValues.filter((item) => !statusValues.includes(item));
    const errorOutside = errorValues.filter((item) => !statusValues.includes(item));
    if (successOutside.length) {
      issues.push(`${label}: success statuses должны входить в all statuses: ${successOutside.join(", ")}.`);
    }
    if (errorOutside.length) {
      issues.push(`${label}: error statuses должны входить в all statuses: ${errorOutside.join(", ")}.`);
    }
    if (!CONTRACT_PATH_RE.test(summaryPath)) {
      issues.push(`${label}: output_contract.summary_path должен быть dotted path.`);
    }
    if (!CONTRACT_PATH_RE.test(errorCodePath)) {
      issues.push(`${label}: output_contract.error_code_path должен быть dotted path.`);
    }
  });

  return issues;
}

function familyMatchesSearch(item: ModuleWorkbenchFamilyRecord, query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  const versionSearchBlob = item.versions
    .flatMap((version) => [
      version.version,
      ...(version.tool_ids ?? []),
      ...(version.platforms ?? []),
    ])
    .join(" ");
  return [
    item.module_name,
    item.preferred_version ?? "",
    item.latest_version ?? "",
    versionSearchBlob,
  ].some((value) => value.toLowerCase().includes(normalized));
}

function copyToClipboard(text: string) {
  if (typeof navigator === "undefined" || !navigator.clipboard) {
    return;
  }
  void navigator.clipboard.writeText(text);
}

function parseToolEditorJson(value: string, fieldLabel: string) {
  try {
    return safeParseJson(value, {});
  } catch {
    throw new Error(`Поле «${fieldLabel}» должно содержать валидный JSON.`);
  }
}

function buildPreviewCurl(mode: "validate" | "save", payload: Record<string, unknown>) {
  const action = mode === "validate" ? "validate" : "publish";
  return [
    `curl -X POST http://192.168.100.17:8666/api/modules/authoring/${action} \\`,
    `  -H "Content-Type: application/json" \\`,
    `  -d '${JSON.stringify(payload, null, 2)}'`,
  ].join("\n");
}

function MetaRow({
  label,
  value,
}: {
  label: string;
  value: string | number | null | undefined;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm text-slate-500">{label}</span>
      <span className="text-right text-sm font-medium text-slate-900">
        {value == null || value === "" ? "—" : value}
      </span>
    </div>
  );
}

export function ModulesPanel() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>("registry");
  const [developmentTab, setDevelopmentTab] = useState<DevelopmentTab>("basics");
  const [previewTab, setPreviewTab] = useState<PreviewTab>("payload");
  const [queryDraft, setQueryDraft] = useState("");
  const [selectedModuleName, setSelectedModuleName] = useState<string | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<string | null>(null);
  const [draft, setDraft] = useState<ModuleWorkbenchDraft | null>(null);
  const [baselineFingerprint, setBaselineFingerprint] = useState<string>("null");
  const [requestedDraftKey, setRequestedDraftKey] = useState<string | null>(null);
  const [loadedDraftKey, setLoadedDraftKey] = useState<string | null>(null);
  const [selectedToolIndex, setSelectedToolIndex] = useState(0);
  const [selectedSourcePath, setSelectedSourcePath] = useState<string>("");
  const [serverValidation, setServerValidation] =
    useState<ModuleWorkbenchValidationPayload | null>(null);
  const [actionFeedback, setActionFeedback] = useState<ActionFeedback>(null);
  const [archiveFile, setArchiveFile] = useState<File | null>(null);
  const [archiveModuleName, setArchiveModuleName] = useState("");
  const [archiveVersion, setArchiveVersion] = useState("");
  const [archiveOverwrite, setArchiveOverwrite] = useState(false);
  const [rolloutDraft, setRolloutDraft] = useState<ModuleWorkbenchRolloutSettings | null>(null);
  const [labPlatform, setLabPlatform] = useState("win32");
  const [selectedLabAgentId, setSelectedLabAgentId] = useState("");
  const [selectedLabToolName, setSelectedLabToolName] = useState("");
  const [labTestResult, setLabTestResult] = useState<ModuleLiveTestResult | null>(null);
  const deferredQuery = useDeferredValue(queryDraft);

  const modulesQuery = useQuery({
    queryKey: ["modules-workbench-list", deferredQuery],
    queryFn: () => fetchModuleWorkbenchList(deferredQuery),
    retry: false,
  });

  const visibleFamilies = useMemo(
    () => (modulesQuery.data?.modules ?? []).filter((item) => familyMatchesSearch(item, deferredQuery)),
    [deferredQuery, modulesQuery.data?.modules]
  );

  const selectedFamily =
    visibleFamilies.find((item) => item.module_name === selectedModuleName) ??
    visibleFamilies[0] ??
    null;
  const selectedRecord =
    selectedFamily?.versions.find((item) => item.version === selectedVersion) ??
    selectedFamily?.versions[0] ??
    null;

  const detailQuery = useQuery({
    queryKey: ["modules-workbench-detail", selectedModuleName, selectedVersion],
    queryFn: () => fetchModuleWorkbenchDetail(selectedModuleName!, selectedVersion!),
    enabled: Boolean(selectedModuleName && selectedVersion),
    retry: false,
  });

  useEffect(() => {
    if (!visibleFamilies.length) {
      setSelectedModuleName(null);
      setSelectedVersion(null);
      return;
    }

    if (!selectedModuleName || !visibleFamilies.some((item) => item.module_name === selectedModuleName)) {
      setSelectedModuleName(visibleFamilies[0].module_name);
      setSelectedVersion(visibleFamilies[0].versions[0]?.version ?? null);
      return;
    }

    const activeFamily = visibleFamilies.find((item) => item.module_name === selectedModuleName);
    if (!activeFamily) {
      return;
    }

    if (
      !selectedVersion ||
      !activeFamily.versions.some((item) => item.version === selectedVersion)
    ) {
      setSelectedVersion(activeFamily.versions[0]?.version ?? null);
    }
  }, [selectedModuleName, selectedVersion, visibleFamilies]);

  useEffect(() => {
    if (!draft?.tools.length) {
      setSelectedToolIndex(0);
      return;
    }
    if (selectedToolIndex > draft.tools.length - 1) {
      setSelectedToolIndex(draft.tools.length - 1);
    }
  }, [draft?.tools.length, selectedToolIndex]);

  useEffect(() => {
    if (!detailQuery.data || !selectedModuleName || !selectedVersion) {
      return;
    }
    const versionKey = buildVersionKey(selectedModuleName, selectedVersion);
    if (requestedDraftKey !== versionKey || loadedDraftKey === versionKey) {
      return;
    }
    const nextDraft = cloneDraft(detailQuery.data.editable_spec);
    setDraft(nextDraft);
    setLoadedDraftKey(versionKey);
    setBaselineFingerprint(buildDraftFingerprint(nextDraft));
    setSelectedToolIndex(0);
    setSelectedSourcePath(nextDraft.source.files[0]?.path ?? "");
    setServerValidation(null);
  }, [
    detailQuery.data,
    loadedDraftKey,
    requestedDraftKey,
    selectedModuleName,
    selectedVersion,
  ]);

  useEffect(() => {
    if (!modulesQuery.data?.rollout_settings) {
      return;
    }
    setRolloutDraft({
      preferred_version_rollout_mode:
        modulesQuery.data.rollout_settings.preferred_version_rollout_mode,
      sync_after_preferred_change:
        modulesQuery.data.rollout_settings.sync_after_preferred_change,
    });
  }, [
    modulesQuery.data?.rollout_settings?.preferred_version_rollout_mode,
    modulesQuery.data?.rollout_settings?.sync_after_preferred_change,
  ]);

  const hasUnsavedChanges = buildDraftFingerprint(draft) !== baselineFingerprint;
  const selectedTool = draft?.tools[selectedToolIndex] ?? null;
  const selectedOutputContract = selectedTool
    ? normalizeOutputContract(selectedTool.output_contract)
    : null;
  const localIssues = useMemo(() => validateDraft(draft), [draft]);
  const activeSource = serverValidation?.editable_preview?.source ?? draft?.source ?? null;
  const selectedSourceFile =
    activeSource?.files.find((item) => item.path === selectedSourcePath) ??
    activeSource?.files[0] ??
    null;
  const payloadPreview = draft ? buildDraftPayload(draft) : null;

  const rolloutMutation = useMutation({
    mutationFn: patchModuleWorkbenchRolloutSettings,
    onSuccess: async (settings) => {
      setRolloutDraft(settings);
      setActionFeedback({
        tone: "success",
        text: `Политика preferred-rollout сохранена: ${rolloutModeLabel(
          settings.preferred_version_rollout_mode
        )}.`,
      });
      await queryClient.invalidateQueries({ queryKey: ["modules-workbench-list"] });
    },
    onError: (error) => {
      setActionFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось сохранить настройки раскатки.",
      });
    },
  });

  const preferredMutation = useMutation({
    mutationFn: ({
      moduleName,
      version,
    }: {
      moduleName: string;
      version: string | null;
    }) => setModuleWorkbenchPreferredVersion(moduleName, version),
    onSuccess: async (result) => {
      setActionFeedback({
        tone: "success",
        text:
          result.message ??
          (result.preferred_version
            ? `Preferred-версия обновлена: ${result.module_name} → ${result.preferred_version}.`
            : `Preferred-версия снята для ${result.module_name}.`),
      });
      await queryClient.invalidateQueries({ queryKey: ["modules-workbench-list"] });
      if (selectedModuleName && selectedVersion) {
        await queryClient.invalidateQueries({
          queryKey: ["modules-workbench-detail", selectedModuleName, selectedVersion],
        });
      }
    },
    onError: (error) => {
      setActionFeedback({
        tone: "error",
        text:
          error instanceof Error
            ? error.message
            : "Не удалось обновить preferred-версию.",
      });
    },
  });

  const validateMutation = useMutation({
    mutationFn: validateModuleWorkbenchDraft,
    onSuccess: (result) => {
      setServerValidation(result);
      setActionFeedback({
        tone: result.publish_ready ? "success" : "error",
        text: result.publish_ready
          ? "Server validate прошёл. Модуль готов к публикации."
          : "Проверка завершена: откройте конфликты и предупреждения перед публикацией.",
      });
      if (result.editable_preview?.source?.files?.length) {
        setSelectedSourcePath(result.editable_preview.source.files[0].path);
      }
      setDevelopmentTab("preview");
      setWorkspaceTab("development");
    },
    onError: (error) => {
      setActionFeedback({
        tone: "error",
        text:
          error instanceof Error ? error.message : "Серверная проверка завершилась ошибкой.",
      });
    },
  });

  const saveMutation = useMutation({
    mutationFn: saveModuleWorkbenchDraft,
    onSuccess: async (result) => {
      setActionFeedback({
        tone: "success",
        text:
          result.message ??
          `Модуль ${result.module_name ?? draft?.module_name ?? ""} опубликован в реестр.`,
      });
      if (draft) {
        setBaselineFingerprint(buildDraftFingerprint(draft));
      }
      await queryClient.invalidateQueries({ queryKey: ["modules-workbench-list"] });
      if (result.module_name && result.version) {
        setSelectedModuleName(result.module_name);
        setSelectedVersion(result.version);
        const versionKey = buildVersionKey(result.module_name, result.version);
        setRequestedDraftKey(versionKey);
        setLoadedDraftKey(null);
      }
    },
    onError: (error) => {
      setActionFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось опубликовать модуль.",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: ({
      moduleName,
      version,
    }: {
      moduleName: string;
      version: string;
    }) => deleteModuleWorkbenchVersion(moduleName, version),
    onSuccess: async (result) => {
      setActionFeedback({
        tone: "success",
        text: `Версия ${result.module_name} ${result.version} удалена из реестра.`,
      });
      await queryClient.invalidateQueries({ queryKey: ["modules-workbench-list"] });
    },
    onError: (error) => {
      setActionFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось удалить версию.",
      });
    },
  });

  const uploadMutation = useMutation({
    mutationFn: uploadModuleWorkbenchArchive,
    onSuccess: async (result: ModuleArchiveUploadPayload) => {
      setActionFeedback({
        tone: "success",
        text: `Архив загружен: ${result.module_name} ${result.version}.`,
      });
      setArchiveOverwrite(false);
      setArchiveFile(null);
      setArchiveModuleName(result.module_name);
      setArchiveVersion(result.version);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      await queryClient.invalidateQueries({ queryKey: ["modules-workbench-list"] });
      setSelectedModuleName(result.module_name);
      setSelectedVersion(result.version);
      setRequestedDraftKey(buildVersionKey(result.module_name, result.version));
      setLoadedDraftKey(null);
      setWorkspaceTab("registry");
    },
    onError: (error) => {
      setActionFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось загрузить архив модуля.",
      });
    },
  });

  function mutateDraft(updater: (current: ModuleWorkbenchDraft) => ModuleWorkbenchDraft) {
    setDraft((current) => {
      if (!current) {
        return current;
      }
      return updater(cloneDraft(current));
    });
  }

  function ensureCanLeaveDraft() {
    if (!hasUnsavedChanges) {
      return true;
    }
    return window.confirm(
      "В черновике есть несохранённые изменения. Переключиться и потерять их?"
    );
  }

  function openDraftForVersion(moduleName: string, version: string) {
    if (!ensureCanLeaveDraft()) {
      return;
    }
    setSelectedModuleName(moduleName);
    setSelectedVersion(version);
    setRequestedDraftKey(buildVersionKey(moduleName, version));
    setLoadedDraftKey(null);
    setServerValidation(null);
    setDevelopmentTab("basics");
    setWorkspaceTab("development");
  }

  function startNewDraft() {
    if (!ensureCanLeaveDraft()) {
      return;
    }
    const nextDraft = createBlankDraft();
    setDraft(nextDraft);
    setRequestedDraftKey("new");
    setLoadedDraftKey("new");
    setBaselineFingerprint(buildDraftFingerprint(nextDraft));
    setSelectedToolIndex(0);
    setSelectedSourcePath("");
    setServerValidation(null);
    setDevelopmentTab("basics");
    setWorkspaceTab("development");
  }

  function updateToolStringField(
    field: keyof Pick<ModuleWorkbenchToolDraft, "tool_name" | "method_name" | "description" | "contract_version" | "lifecycle" | "user_function_body">,
    value: string
  ) {
    mutateDraft((current) => {
      current.tools[selectedToolIndex][field] = value as never;
      return current;
    });
  }

  function updateToolJsonField(
    field: keyof Pick<
      ModuleWorkbenchToolDraft,
      | "params_schema"
      | "output_schema"
      | "presets"
      | "metadata"
      | "dependencies"
      | "error_codes"
      | "artifact_types"
      | "redaction"
      | "resources"
    >,
    value: string,
    label: string
  ) {
    try {
      const parsed = parseToolEditorJson(value, label);
      mutateDraft((current) => {
        current.tools[selectedToolIndex][field] = parsed as never;
        return current;
      });
      setActionFeedback(null);
    } catch (error) {
      setActionFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : `Не удалось прочитать JSON поля ${label}.`,
      });
    }
  }

  function updateToolListField(
    field: keyof Pick<ModuleWorkbenchToolDraft, "aliases" | "capabilities">,
    value: string
  ) {
    mutateDraft((current) => {
      current.tools[selectedToolIndex][field] = splitLines(value) as never;
      return current;
    });
  }

  function updateToolOutputContractField(field: string, value: string, list = false) {
    mutateDraft((current) => {
      const tool = current.tools[selectedToolIndex];
      tool.output_contract = normalizeOutputContract({
        ...(tool.output_contract ?? {}),
        [field]: list ? splitLines(value) : value,
      });
      return current;
    });
  }

  function addTool() {
    mutateDraft((current) => {
      current.tools.push(createEmptyTool(current.tools.length));
      return current;
    });
    setSelectedToolIndex(draft?.tools.length ?? 0);
    setDevelopmentTab("tool");
  }

  function duplicateTool() {
    if (!selectedTool) {
      return;
    }
    mutateDraft((current) => {
      const clone = JSON.parse(JSON.stringify(current.tools[selectedToolIndex])) as ModuleWorkbenchToolDraft;
      clone.tool_name = `${clone.tool_name}_copy`;
      clone.method_name = `${clone.method_name}_copy`;
      current.tools.splice(selectedToolIndex + 1, 0, clone);
      return current;
    });
    setSelectedToolIndex(selectedToolIndex + 1);
  }

  function removeTool() {
    if (!draft || draft.tools.length <= 1) {
      return;
    }
    if (!window.confirm("Удалить инструмент из черновика модуля?")) {
      return;
    }
    mutateDraft((current) => {
      current.tools.splice(selectedToolIndex, 1);
      return current;
    });
    setSelectedToolIndex((current) => Math.max(0, current - 1));
  }

  const developmentTabs = [
    { value: "basics", label: "Модуль" },
    { value: "tool", label: "Инструменты", count: draft?.tools.length ?? 0 },
    { value: "preview", label: "Validate" },
    { value: "source", label: "Source" },
  ];

  const workspaceTabs = [
    { value: "registry", label: "Реестр", count: visibleFamilies.length },
    { value: "development", label: "Разработка", count: draft?.tools.length ?? 0 },
    { value: "archive", label: "Архив", count: archiveFile ? 1 : 0 },
  ];

  const previewTabs = [
    { value: "payload", label: "JSON payload" },
    { value: "curl-validate", label: "curl validate" },
    { value: "curl-save", label: "curl save" },
  ];

  const rolloutSettings = rolloutDraft ?? modulesQuery.data?.rollout_settings ?? null;
  const selectedDetailMeta = detailQuery.data?.module ?? selectedRecord;
  const selectedLabModuleName = selectedDetailMeta?.module_name ?? selectedFamily?.module_name ?? null;
  const labPlatformOptions = useMemo(() => {
    const normalized = (selectedDetailMeta?.platforms ?? [])
      .map((platform) => normalizePlatform(platform))
      .filter(Boolean);
    const unique = Array.from(new Set(normalized));
    if (unique.length) {
      return unique;
    }
    return ["win32", "linux"];
  }, [selectedDetailMeta?.platforms]);
  const labToolOptions = selectedDetailMeta?.tool_ids ?? [];

  useEffect(() => {
    if (!labPlatformOptions.length) {
      return;
    }
    if (!labPlatformOptions.includes(labPlatform)) {
      setLabPlatform(
        labPlatformOptions.includes("win32")
          ? "win32"
          : labPlatformOptions.includes("linux")
            ? "linux"
            : labPlatformOptions[0]
      );
    }
  }, [labPlatform, labPlatformOptions]);

  useEffect(() => {
    if (!labToolOptions.length) {
      setSelectedLabToolName("");
      return;
    }
    if (!labToolOptions.includes(selectedLabToolName)) {
      setSelectedLabToolName(labToolOptions[0]);
    }
  }, [labToolOptions, selectedLabToolName]);

  useEffect(() => {
    setLabTestResult(null);
  }, [selectedLabModuleName, selectedDetailMeta?.version, labPlatform]);

  const labCandidatesQuery = useQuery({
    queryKey: [
      "modules-live-test-candidates",
      selectedLabModuleName,
      selectedDetailMeta?.version,
      labPlatform,
    ],
    queryFn: () =>
      fetchModuleLiveTestCandidates(selectedLabModuleName!, selectedDetailMeta!.version, labPlatform),
    enabled: Boolean(
      workspaceTab === "registry" &&
        selectedLabModuleName &&
        selectedDetailMeta?.version &&
        labPlatform
    ),
    retry: false,
  });
  const labCandidates = labCandidatesQuery.data?.candidates ?? [];
  const selectedLabAgent = labCandidates.find((candidate) => candidate.device_id === selectedLabAgentId) ?? null;

  useEffect(() => {
    if (!labCandidatesQuery.data) {
      setSelectedLabAgentId("");
      return;
    }
    const current = labCandidatesQuery.data.candidates.find(
      (candidate) => candidate.device_id === selectedLabAgentId && candidate.compatible
    );
    if (current) {
      return;
    }
    const next =
      labCandidatesQuery.data.candidates.find((candidate) => candidate.compatible && candidate.online) ??
      labCandidatesQuery.data.candidates.find((candidate) => candidate.compatible) ??
      null;
    setSelectedLabAgentId(next?.device_id ?? "");
  }, [labCandidatesQuery.data, selectedLabAgentId]);

  const liveTestMutation = useMutation({
    mutationFn: () => {
      if (!selectedLabModuleName || !selectedDetailMeta?.version || !selectedLabAgentId || !selectedLabToolName) {
        throw new Error("Выберите module version, lab agent и команду для live test.");
      }
      return runModuleLiveTest(selectedLabModuleName, selectedDetailMeta.version, {
        device_id: selectedLabAgentId,
        tool_name: selectedLabToolName,
        params: {},
      });
    },
    onSuccess: async (result) => {
      const isPassed = ["success", "passed", "ok"].includes(String(result.live_test.status).toLowerCase());
      setLabTestResult(result.live_test);
      setActionFeedback({
        tone: isPassed ? "success" : "error",
        text:
          isPassed
            ? `Live test выполнен: trace ${result.live_test.trace_id}.`
            : `Live test завершился на этапе ${result.live_test.stage}: ${result.live_test.error_code ?? "error"}.`,
      });
      await queryClient.invalidateQueries({
        queryKey: [
          "modules-live-test-candidates",
          selectedLabModuleName,
          selectedDetailMeta?.version,
          labPlatform,
        ],
      });
      await queryClient.invalidateQueries({ queryKey: ["modules-workbench-list"] });
      if (selectedLabModuleName && selectedDetailMeta?.version) {
        await queryClient.invalidateQueries({
          queryKey: ["modules-workbench-detail", selectedLabModuleName, selectedDetailMeta.version],
        });
      }
    },
    onError: (error) => {
      setActionFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Live test модуля завершился ошибкой.",
      });
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div className="max-w-3xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-brand-700">
            Registry
          </p>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-slate-950">
            Реестр модулей
          </h2>
          <p className="mt-3 text-sm leading-7 text-slate-500 md:text-base">
            Полный рабочий цикл модулей: реестр версий, preferred-rollout policy, редактор
            спецификации и импорт архивов теперь собраны в одном SaaS workbench.
          </p>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-4">
        <div className="rounded-[1.3rem] border border-border bg-white px-5 py-5 shadow-soft">
          <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Семейств в срезе</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
            {modulesQuery.data?.count ?? 0}
          </p>
          <p className="mt-2 text-sm text-slate-500">
            Поиск, preferred и публикация работают на реальном реестре.
          </p>
        </div>
        <div className="rounded-[1.3rem] border border-border bg-white px-5 py-5 shadow-soft">
          <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Preferred назначений</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
            {modulesQuery.data?.modules.filter((item) => item.preferred_assigned).length ?? 0}
          </p>
          <p className="mt-2 text-sm text-slate-500">
            {rolloutSettings ? rolloutModeLabel(rolloutSettings.preferred_version_rollout_mode) : "Загружаем policy"}
          </p>
        </div>
        <div className="rounded-[1.3rem] border border-border bg-white px-5 py-5 shadow-soft">
          <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Предупреждения</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
            {modulesQuery.data?.modules.filter((item) =>
              item.versions.some((version) => version.validation_status !== "passed")
            ).length ?? 0}
          </p>
          <p className="mt-2 text-sm text-slate-500">
            Включая failed validate и missing archive на диске.
          </p>
        </div>
        <div className="rounded-[1.3rem] border border-border bg-white px-5 py-5 shadow-soft">
          <p className="text-xs uppercase tracking-[0.22em] text-brand-700">Черновик</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
            {draft?.module_name ?? "—"}
          </p>
          <p className="mt-2 text-sm text-slate-500">
            {hasUnsavedChanges ? "Есть несохранённые изменения" : "Черновик синхронизирован"}
          </p>
        </div>
      </div>

      {actionFeedback ? (
        <div
          className={cn(
            "rounded-[1.1rem] border px-4 py-3 text-sm shadow-soft",
            actionFeedback.tone === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : "border-rose-200 bg-rose-50 text-rose-700"
          )}
        >
          {actionFeedback.text}
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
        <div className="space-y-6">
          <Card className="xl:sticky xl:top-[9.5rem]">
            <CardHeader className="gap-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <CardTitle>Рабочий реестр</CardTitle>
                  <CardDescription>
                    Полный перенос модульного цикла: реестр, preferred policy, editor и импорт ZIP.
                  </CardDescription>
                </div>
                <Button
                  leadingIcon={<RefreshCcw className="h-4 w-4" />}
                  onClick={() => {
                    void Promise.all([
                      modulesQuery.refetch(),
                      detailQuery.refetch(),
                    ]);
                  }}
                  size="sm"
                  variant="outline"
                >
                  Обновить
                </Button>
              </div>

              <SearchField
                onChange={(event) => setQueryDraft(event.target.value)}
                placeholder="module_name, tool id или версия"
                value={queryDraft}
              />

              <Tabs
                items={workspaceTabs}
                onValueChange={(value) => setWorkspaceTab(value as WorkspaceTab)}
                value={workspaceTab}
              />
            </CardHeader>

            <CardContent className="space-y-5">
              <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Preferred rollout</p>
                <p className="mt-2 text-lg font-semibold text-slate-950">
                  {rolloutSettings ? rolloutModeLabel(rolloutSettings.preferred_version_rollout_mode) : "Загружаем"}
                </p>
                <p className="mt-2 text-sm text-slate-500">
                  {rolloutSettings?.sync_after_preferred_change
                    ? "После смены preferred сервер запускает reconcile и refresh."
                    : "После смены preferred синхронизация остаётся ручной."}
                </p>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                    Семейства модулей
                  </p>
                  <Button
                    leadingIcon={<PackagePlus className="h-4 w-4" />}
                    onClick={startNewDraft}
                    size="sm"
                  >
                    Новый модуль
                  </Button>
                </div>

                <div className="max-h-[calc(100vh-24rem)] space-y-3 overflow-y-auto pr-1">
                  {modulesQuery.isLoading ? (
                    <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-6 text-sm text-slate-500">
                      Загружаем семейства модулей...
                    </div>
                  ) : null}

                  {modulesQuery.isError ? (
                    <div className="rounded-[1.1rem] border border-dashed border-rose-200 bg-rose-50 px-4 py-6 text-sm text-rose-700">
                      {modulesQuery.error instanceof Error
                        ? modulesQuery.error.message
                        : "Не удалось загрузить реестр модулей."}
                    </div>
                  ) : null}

                  {visibleFamilies.map((family) => {
                    const active = family.module_name === selectedFamily?.module_name;
                    return (
                      <button
                        key={family.module_name}
                        className={cn(
                          "w-full rounded-[1.15rem] border px-4 py-4 text-left transition-colors",
                          active
                            ? "border-brand-200 bg-brand-50"
                            : "border-border bg-white hover:border-brand-100 hover:bg-surface-subtle"
                        )}
                        onClick={() => {
                          startTransition(() => {
                            setSelectedModuleName(family.module_name);
                            setSelectedVersion(family.versions[0]?.version ?? null);
                            setActionFeedback(null);
                          });
                        }}
                        type="button"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-semibold text-slate-950">{family.module_name}</p>
                            <p className="mt-1 text-sm text-slate-500">
                              latest {family.latest_version ?? "—"} • preferred {family.preferred_version ?? "—"}
                            </p>
                          </div>
                          <Badge tone={family.preferred_assigned ? "success" : "neutral"}>
                            {family.preferred_assigned ? "preferred" : "manual"}
                          </Badge>
                        </div>
                        <p className="mt-3 text-sm text-slate-500">
                          {family.versions
                            .flatMap((version) => version.tool_ids ?? [])
                            .slice(0, 3)
                            .join(", ") || "Инструменты пока не заявлены"}
                        </p>
                      </button>
                    );
                  })}

                  {!modulesQuery.isLoading && !modulesQuery.isError && visibleFamilies.length === 0 ? (
                    <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-6 text-sm text-slate-500">
                      Под текущий поиск модулей не найдено.
                    </div>
                  ) : null}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          {workspaceTab === "registry" ? (
            <>
              <Card>
                <CardHeader className="gap-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <CardTitle>Rollout policy</CardTitle>
                      <CardDescription>
                        Управление preferred-version policy без возврата в legacy modules shell.
                      </CardDescription>
                    </div>
                    <Button
                      disabled={!rolloutSettings}
                      leadingIcon={<ShieldCheck className="h-4 w-4" />}
                      onClick={() => {
                        void modulesQuery.refetch();
                        setActionFeedback(null);
                      }}
                      size="sm"
                      variant="outline"
                    >
                      Обновить из сервера
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="grid gap-4 md:grid-cols-[minmax(0,240px)_minmax(0,240px)_auto] md:items-end">
                  <label className="space-y-2 text-sm font-medium text-slate-800">
                    <span>Режим preferred-rollout</span>
                    <Select
                      value={rolloutSettings?.preferred_version_rollout_mode ?? "manual"}
                      onChange={(event) => {
                        const nextMode = event.target.value;
                        if (!rolloutSettings) {
                          return;
                        }
                        setRolloutDraft({
                          ...rolloutSettings,
                          preferred_version_rollout_mode: nextMode,
                        });
                      }}
                    >
                      <option value="manual">Только вручную</option>
                      <option value="installed_devices">Обновлять установленные устройства</option>
                    </Select>
                  </label>

                  <label className="flex h-11 items-center gap-3 rounded-pill border border-border bg-white px-4">
                    <input
                      checked={rolloutSettings?.sync_after_preferred_change ?? true}
                      onChange={(event) => {
                        if (!rolloutSettings) {
                          return;
                        }
                        setRolloutDraft({
                          ...rolloutSettings,
                          sync_after_preferred_change: event.target.checked,
                        });
                      }}
                      type="checkbox"
                    />
                    <span className="text-sm font-medium text-slate-700">
                      После смены preferred запускать reconcile и refresh
                    </span>
                  </label>

                  <Button
                    disabled={rolloutMutation.isPending || !rolloutSettings}
                    leadingIcon={<Save className="h-4 w-4" />}
                    onClick={() => {
                      if (!rolloutSettings) {
                        return;
                      }
                      rolloutMutation.mutate(rolloutSettings);
                    }}
                  >
                    {rolloutMutation.isPending ? "Сохраняем..." : "Сохранить политику"}
                  </Button>
                </CardContent>
              </Card>

              <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
                <Card>
                  <CardHeader className="gap-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <CardTitle>{selectedFamily?.module_name ?? "Карточка семейства"}</CardTitle>
                        <CardDescription>
                          Реестр версий, preferred assignment, validate state и быстрый вход в editor.
                        </CardDescription>
                      </div>
                      {selectedFamily ? (
                        <Button
                          leadingIcon={<Wand2 className="h-4 w-4" />}
                          onClick={() => openDraftForVersion(selectedFamily.module_name, selectedRecord?.version ?? selectedFamily.versions[0]?.version ?? "")}
                          size="sm"
                        >
                          Открыть в editor
                        </Button>
                      ) : null}
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-5">
                    {selectedFamily ? (
                      <>
                        <div className="grid gap-4 md:grid-cols-3">
                          <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
                              Preferred версия
                            </p>
                            <p className="mt-2 text-xl font-semibold text-slate-950">
                              {selectedFamily.preferred_version ?? "Не назначена"}
                            </p>
                            <p className="mt-2 text-sm text-slate-500">
                              Latest: {selectedFamily.latest_version ?? "—"}
                            </p>
                          </div>
                          <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
                              Owner scope / API
                            </p>
                            <p className="mt-2 text-xl font-semibold text-slate-950">
                              {selectedFamily.owner_scope ?? "vendor"}
                            </p>
                            <p className="mt-2 text-sm text-slate-500">
                              Module API {selectedFamily.module_api_version ?? "—"}
                            </p>
                          </div>
                          <div className="rounded-[1.1rem] border border-border bg-surface-subtle px-4 py-4">
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
                              Инструменты
                            </p>
                            <p className="mt-2 text-xl font-semibold text-slate-950">
                              {selectedFamily.versions[0]?.tools_count ?? 0}
                            </p>
                            <p className="mt-2 text-sm text-slate-500">
                              {(selectedFamily.versions[0]?.tool_ids ?? []).join(", ") || "Без tool ids"}
                            </p>
                          </div>
                        </div>

                        <div className="space-y-3">
                          {selectedFamily.versions.map((version) => (
                            <div
                              key={buildVersionKey(selectedFamily.module_name, version.version)}
                              className={cn(
                                "rounded-[1.15rem] border px-4 py-4",
                                version.version === selectedRecord?.version
                                  ? "border-brand-200 bg-brand-50"
                                  : "border-border bg-white"
                              )}
                            >
                              <div className="flex flex-wrap items-start justify-between gap-3">
                                <div>
                                  <div className="flex flex-wrap items-center gap-2">
                                    <p className="text-lg font-semibold text-slate-950">{version.version}</p>
                                    <Badge tone={validationTone(version.validation_status)}>
                                      {version.validation_status_label || version.validation_status}
                                    </Badge>
                                    {version.is_preferred ? (
                                      <Badge tone="success">preferred</Badge>
                                    ) : null}
                                    {!version.file_exists ? (
                                      <Badge tone="danger">archive missing</Badge>
                                    ) : null}
                                  </div>
                                  <p className="mt-2 text-sm text-slate-500">
                                    Загружено {formatDateTime(version.created_at)}
                                    {version.uploaded_by ? ` • ${version.uploaded_by}` : ""}
                                  </p>
                                  <p className="mt-1 text-sm text-slate-500">
                                    {(version.tool_ids ?? []).join(", ") || "Инструменты не обнаружены"}
                                  </p>
                                  {!version.file_exists ? (
                                    <p className="mt-2 text-sm text-rose-600">
                                      Архив отсутствует, нужен повторный upload.
                                    </p>
                                  ) : null}
                                </div>

                                <div className="flex flex-wrap gap-2">
                                  <Button
                                    leadingIcon={<FolderKanban className="h-4 w-4" />}
                                    onClick={() => {
                                      setSelectedVersion(version.version);
                                      setActionFeedback(null);
                                    }}
                                    size="sm"
                                    variant="outline"
                                  >
                                    Выбрать
                                  </Button>
                                  <Button
                                    leadingIcon={<FileCode2 className="h-4 w-4" />}
                                    onClick={() => openDraftForVersion(selectedFamily.module_name, version.version)}
                                    size="sm"
                                    variant="outline"
                                  >
                                    Editor
                                  </Button>
                                  <Button
                                    disabled={preferredMutation.isPending}
                                    leadingIcon={<Sparkles className="h-4 w-4" />}
                                    onClick={() =>
                                      preferredMutation.mutate({
                                        moduleName: selectedFamily.module_name,
                                        version: version.is_preferred ? null : version.version,
                                      })
                                    }
                                    size="sm"
                                  >
                                    {version.is_preferred
                                      ? `Снять preferred с ${version.version}`
                                      : `Сделать preferred для ${version.version}`}
                                  </Button>
                                  <Button
                                    disabled={deleteMutation.isPending}
                                    leadingIcon={<Trash2 className="h-4 w-4" />}
                                    onClick={() => {
                                      if (
                                        window.confirm(
                                          `Удалить ${selectedFamily.module_name} ${version.version} из реестра?`
                                        )
                                      ) {
                                        deleteMutation.mutate({
                                          moduleName: selectedFamily.module_name,
                                          version: version.version,
                                        });
                                      }
                                    }}
                                    size="sm"
                                    variant="outline"
                                  >
                                    Удалить
                                  </Button>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </>
                    ) : (
                      <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                        Выберите семейство модулей слева, чтобы открыть реестр версий.
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card className="h-fit">
                  <CardHeader>
                    <CardTitle>Контекст версии</CardTitle>
                    <CardDescription>
                      Быстрый operational summary по выбранной версии модуля.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {selectedDetailMeta ? (
                      <>
                        <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
                          <p className="text-xs uppercase tracking-[0.2em] text-brand-700">
                            {selectedFamily?.module_name}
                          </p>
                          <p className="mt-3 text-2xl font-semibold text-slate-950">
                            {selectedDetailMeta.version}
                          </p>
                          <p className="mt-2 text-sm text-slate-500">
                            SHA256: {selectedDetailMeta.sha256?.slice(0, 16) ?? "—"}
                          </p>
                        </div>

                        <MetaRow
                          label="Validate"
                          value={
                            selectedDetailMeta.validation_status_label ??
                            selectedDetailMeta.validation_status
                          }
                        />
                        <MetaRow
                          label="Preflight"
                          value={
                            selectedDetailMeta.preflight_status_label ??
                            selectedDetailMeta.preflight_status
                          }
                        />
                        <MetaRow label="Manifest" value={selectedDetailMeta.manifest_version} />
                        <MetaRow
                          label="Размер архива"
                          value={selectedDetailMeta.size ? `${selectedDetailMeta.size} bytes` : "—"}
                        />
                        <MetaRow
                          label="Файл в storage"
                          value={selectedDetailMeta.file_exists ? "доступен" : "отсутствует"}
                        />
                        <MetaRow
                          label="Warnings"
                          value={selectedDetailMeta.warnings?.length ?? 0}
                        />

                        <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                          <p className="text-sm font-semibold text-slate-900">Платформы</p>
                          <div className="mt-3 flex flex-wrap gap-2">
                            {(selectedDetailMeta.platforms ?? ["any"]).map((platform) => (
                              <Badge key={platform} tone="neutral">
                                {platform}
                              </Badge>
                            ))}
                          </div>
                        </div>

                        <div className="rounded-[1.1rem] border border-border bg-white px-4 py-4">
                          <p className="text-sm font-semibold text-slate-900">Инструменты</p>
                          <div className="mt-3 flex flex-wrap gap-2">
                            {(selectedDetailMeta.tool_ids ?? []).length ? (
                              (selectedDetailMeta.tool_ids ?? []).map((toolId) => (
                                <Badge key={toolId} tone="brand">
                                  {toolId}
                                </Badge>
                              ))
                            ) : (
                              <p className="text-sm text-slate-500">Tool ids пока не распознаны.</p>
                            )}
                          </div>
                        </div>

                        <div className="rounded-[1.1rem] border border-brand-100 bg-brand-50/40 px-4 py-4">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-semibold text-slate-900">Lab test agent</p>
                              <p className="mt-1 text-xs leading-5 text-slate-500">
                                Выберите Linux или Windows агент для проверки модуля перед preferred.
                              </p>
                            </div>
                            <Badge tone={labCandidatesQuery.isError ? "danger" : "brand"}>
                              observer
                            </Badge>
                          </div>

                          <div className="mt-4 space-y-3">
                            <label className="space-y-2 text-sm font-medium text-slate-800">
                              <span>Test platform</span>
                              <Select
                                aria-label="Test platform"
                                value={labPlatform}
                                onChange={(event) => {
                                  setLabPlatform(event.target.value);
                                  setSelectedLabAgentId("");
                                }}
                              >
                                {labPlatformOptions.map((platform) => (
                                  <option key={platform} value={platform}>
                                    {platformLabel(platform)}
                                  </option>
                                ))}
                              </Select>
                            </label>

                            <label className="space-y-2 text-sm font-medium text-slate-800">
                              <span>Lab agent</span>
                              <Select
                                aria-label="Lab agent"
                                disabled={labCandidatesQuery.isLoading || !labCandidates.length}
                                value={selectedLabAgentId}
                                onChange={(event) => setSelectedLabAgentId(event.target.value)}
                              >
                                {!labCandidates.length ? (
                                  <option value="">
                                    {labCandidatesQuery.isLoading ? "Загружаем агентов..." : "Нет подходящих агентов"}
                                  </option>
                                ) : null}
                                {labCandidates.map((candidate) => (
                                  <option
                                    disabled={!candidate.compatible}
                                    key={candidate.device_id}
                                    value={candidate.device_id}
                                  >
                                    {candidateLabel(candidate)}
                                  </option>
                                ))}
                              </Select>
                            </label>

                            <label className="space-y-2 text-sm font-medium text-slate-800">
                              <span>Command</span>
                              <Select
                                aria-label="Lab command"
                                disabled={!labToolOptions.length}
                                value={selectedLabToolName}
                                onChange={(event) => setSelectedLabToolName(event.target.value)}
                              >
                                {!labToolOptions.length ? <option value="">Нет команд</option> : null}
                                {labToolOptions.map((toolId) => (
                                  <option key={toolId} value={toolId}>
                                    {toolId}
                                  </option>
                                ))}
                              </Select>
                            </label>

                            {selectedLabAgent && selectedLabAgent.reasons.length ? (
                              <div className="rounded-[0.85rem] border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
                                {selectedLabAgent.reasons.join(", ")}
                              </div>
                            ) : null}

                            <Button
                              className="w-full"
                              disabled={
                                liveTestMutation.isPending ||
                                !selectedLabAgent ||
                                !selectedLabAgent.compatible ||
                                !selectedLabToolName
                              }
                              leadingIcon={<PlayCircle className="h-4 w-4" />}
                              onClick={() => {
                                setLabTestResult(null);
                                liveTestMutation.mutate();
                              }}
                              size="sm"
                            >
                              {liveTestMutation.isPending ? "Запускаем..." : "Запустить live test"}
                            </Button>

                            {labCandidatesQuery.isError ? (
                              <div className="rounded-[0.85rem] border border-rose-200 bg-rose-50 px-3 py-2 text-xs leading-5 text-rose-700">
                                Не удалось загрузить список lab-агентов.
                              </div>
                            ) : null}

                            {labCandidates.length ? (
                              <div className="space-y-2">
                                {labCandidates.slice(0, 4).map((candidate) => (
                                  <div
                                    className="flex items-center justify-between gap-2 rounded-[0.85rem] border border-border bg-white px-3 py-2 text-xs"
                                    key={candidate.device_id}
                                  >
                                    <span className="min-w-0 truncate text-slate-700">
                                      {candidate.hostname || candidate.device_id}
                                    </span>
                                    <div className="flex shrink-0 items-center gap-2">
                                      <Badge tone={candidate.online ? "success" : "neutral"}>
                                        {candidate.online ? "online" : "offline"}
                                      </Badge>
                                      <Badge tone={candidate.compatible ? "success" : "warning"}>
                                        {candidate.compatible ? "compatible" : "blocked"}
                                      </Badge>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            ) : null}

                            {labTestResult ? (
                              <div className="rounded-[0.95rem] border border-border bg-white px-3 py-3 text-xs leading-5 text-slate-600">
                                <div className="flex items-center gap-2 font-semibold text-slate-900">
                                  <Activity className="h-4 w-4 text-brand-700" />
                                  {["success", "passed", "ok"].includes(String(labTestResult.status).toLowerCase()) ? "Live test OK" : "Live test error"}
                                </div>
                                <div className="mt-2 space-y-1">
                                  <p>stage: {labTestResult.stage}</p>
                                  <p>trace: {labTestResult.trace_id}</p>
                                  <p>tool: {labTestResult.tool_name}</p>
                                </div>
                              </div>
                            ) : null}
                          </div>
                        </div>
                      </>
                    ) : (
                      <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                        Контекст появится после выбора версии.
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </>
          ) : null}

          {workspaceTab === "development" ? (
            <Card>
              <CardHeader className="gap-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <CardTitle>
                      {draft ? `${draft.module_name}:${draft.version}` : "Module editor"}
                    </CardTitle>
                    <CardDescription>
                      Полноценный editor для validate-before-publish, редактирования tool metadata и просмотра source preview.
                    </CardDescription>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      disabled={!draft}
                      leadingIcon={<RefreshCcw className="h-4 w-4" />}
                      onClick={() => {
                        if (selectedModuleName && selectedVersion) {
                          openDraftForVersion(selectedModuleName, selectedVersion);
                        } else {
                          startNewDraft();
                        }
                      }}
                      size="sm"
                      variant="outline"
                    >
                      Сбросить
                    </Button>
                    <Button
                      disabled={!draft || validateMutation.isPending || localIssues.length > 0}
                      leadingIcon={<CheckCircle2 className="h-4 w-4" />}
                      onClick={() => {
                        if (!draft) {
                          return;
                        }
                        setActionFeedback(null);
                        validateMutation.mutate(buildDraftPayload(draft));
                      }}
                      size="sm"
                      variant="outline"
                    >
                      {validateMutation.isPending ? "Проверяем..." : "Server validate"}
                    </Button>
                    <Button
                      disabled={!draft || saveMutation.isPending || localIssues.length > 0}
                      leadingIcon={<Save className="h-4 w-4" />}
                      onClick={() => {
                        if (!draft) {
                          return;
                        }
                        setActionFeedback(null);
                        saveMutation.mutate(buildDraftPayload(draft));
                      }}
                      size="sm"
                    >
                      {saveMutation.isPending ? "Публикуем..." : "Опубликовать"}
                    </Button>
                  </div>
                </div>

                <Tabs
                  items={developmentTabs}
                  onValueChange={(value) => setDevelopmentTab(value as DevelopmentTab)}
                  value={developmentTab}
                />
              </CardHeader>

              <CardContent className="space-y-6">
                {!draft ? (
                  <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-4 py-10 text-center text-sm text-slate-500">
                    Откройте существующую версию из реестра или создайте новый модуль.
                  </div>
                ) : null}

                {draft && developmentTab === "basics" ? (
                  <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
                    <div className="space-y-4">
                      <div className="grid gap-4 md:grid-cols-2">
                        <label className="space-y-2 text-sm font-medium text-slate-800">
                          <span>Module name</span>
                          <input
                            className="field-base h-11 w-full px-4 text-sm"
                            onChange={(event) =>
                              mutateDraft((current) => {
                                current.module_name = event.target.value;
                                return current;
                              })
                            }
                            value={draft.module_name}
                          />
                        </label>
                        <label className="space-y-2 text-sm font-medium text-slate-800">
                          <span>Версия</span>
                          <input
                            className="field-base h-11 w-full px-4 text-sm"
                            onChange={(event) =>
                              mutateDraft((current) => {
                                current.version = event.target.value;
                                return current;
                              })
                            }
                            value={draft.version}
                          />
                        </label>
                        <label className="space-y-2 text-sm font-medium text-slate-800">
                          <span>Owner scope</span>
                          <Select
                            onChange={(event) =>
                              mutateDraft((current) => {
                                current.owner_scope = event.target.value;
                                return current;
                              })
                            }
                            value={draft.owner_scope}
                          >
                            <option value="vendor">vendor</option>
                            <option value="core">core</option>
                            <option value="platform">platform</option>
                            <option value="builtin">builtin</option>
                          </Select>
                        </label>
                        <label className="space-y-2 text-sm font-medium text-slate-800">
                          <span>Module API version</span>
                          <input
                            className="field-base h-11 w-full px-4 text-sm"
                            onChange={(event) =>
                              mutateDraft((current) => {
                                current.module_api_version = event.target.value;
                                return current;
                              })
                            }
                            value={draft.module_api_version}
                          />
                        </label>
                      </div>

                      <label className="space-y-2 text-sm font-medium text-slate-800">
                        <span>Описание</span>
                        <textarea
                          className="field-base min-h-[120px] w-full resize-y px-4 py-4 text-sm"
                          onChange={(event) =>
                            mutateDraft((current) => {
                              current.description = event.target.value;
                              return current;
                            })
                          }
                          value={draft.description}
                        />
                      </label>

                      <div className="grid gap-4 md:grid-cols-2">
                        <label className="space-y-2 text-sm font-medium text-slate-800">
                          <span>Entrypoint</span>
                          <input
                            className="field-base h-11 w-full px-4 text-sm"
                            onChange={(event) =>
                              mutateDraft((current) => {
                                current.entrypoint = event.target.value;
                                return current;
                              })
                            }
                            value={draft.entrypoint}
                          />
                        </label>
                        <label className="space-y-2 text-sm font-medium text-slate-800">
                          <span>Min agent version</span>
                          <input
                            className="field-base h-11 w-full px-4 text-sm"
                            onChange={(event) =>
                              mutateDraft((current) => {
                                current.min_agent_version = event.target.value;
                                return current;
                              })
                            }
                            value={draft.min_agent_version ?? ""}
                          />
                        </label>
                      </div>

                      <div className="grid gap-4 md:grid-cols-3">
                        <label className="space-y-2 text-sm font-medium text-slate-800">
                          <span>Platforms</span>
                          <textarea
                            className="field-base min-h-[120px] w-full resize-y px-4 py-4 text-sm"
                            onChange={(event) =>
                              mutateDraft((current) => {
                                current.platforms = splitLines(event.target.value);
                                return current;
                              })
                            }
                            value={joinLines(draft.platforms)}
                          />
                        </label>
                        <label className="space-y-2 text-sm font-medium text-slate-800">
                          <span>Requirements</span>
                          <textarea
                            className="field-base min-h-[120px] w-full resize-y px-4 py-4 text-sm"
                            onChange={(event) =>
                              mutateDraft((current) => {
                                current.requirements = splitLines(event.target.value);
                                return current;
                              })
                            }
                            value={joinLines(draft.requirements)}
                          />
                        </label>
                        <label className="space-y-2 text-sm font-medium text-slate-800">
                          <span>Optional requirements</span>
                          <textarea
                            className="field-base min-h-[120px] w-full resize-y px-4 py-4 text-sm"
                            onChange={(event) =>
                              mutateDraft((current) => {
                                current.optional_requirements = splitLines(event.target.value);
                                return current;
                              })
                            }
                            value={joinLines(draft.optional_requirements)}
                          />
                        </label>
                      </div>

                      {targetsWindows(draft.platforms) ? (
                        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-800">
                          Не проверено на Windows agent. Публикация доступна после server harness, но preferred rollout заблокирован, пока модуль не пройдет live test на Windows agent с подходящей версией.
                        </div>
                      ) : null}
                    </div>

                    <div className="space-y-4">
                      <div className="rounded-[1.2rem] border border-border bg-surface-subtle px-4 py-4">
                        <p className="text-xs uppercase tracking-[0.2em] text-brand-700">
                          Draft summary
                        </p>
                        <p className="mt-3 text-2xl font-semibold text-slate-950">
                          {draft.module_name}
                        </p>
                        <p className="mt-2 text-sm text-slate-500">
                          {draft.tools.length} инструментов • {draft.platforms.join(", ") || "any"}
                        </p>
                      </div>

                      <div className="rounded-[1.2rem] border border-border bg-white px-4 py-4">
                        <div className="flex items-center justify-between gap-2">
                          <p className="font-semibold text-slate-900">Инструменты в модуле</p>
                          <Badge tone="brand">{draft.tools.length}</Badge>
                        </div>
                        <div className="mt-4 space-y-2">
                          {draft.tools.map((tool, index) => (
                            <button
                              key={`${tool.tool_name}:${tool.method_name}:${index}`}
                              className={cn(
                                "flex w-full items-center justify-between rounded-[1rem] border px-3 py-3 text-left transition-colors",
                                selectedToolIndex === index
                                  ? "border-brand-200 bg-brand-50"
                                  : "border-border bg-white hover:border-brand-100 hover:bg-surface-subtle"
                              )}
                              onClick={() => {
                                setSelectedToolIndex(index);
                                setDevelopmentTab("tool");
                              }}
                              type="button"
                            >
                              <div>
                                <p className="font-medium text-slate-900">
                                  {tool.tool_name || `tool #${index + 1}`}
                                </p>
                                <p className="mt-1 text-xs text-slate-500">{tool.method_name}</p>
                              </div>
                              <ChevronRight className="h-4 w-4 text-slate-400" />
                            </button>
                          ))}
                        </div>
                      </div>

                      {draft.warnings.length ? (
                        <div className="rounded-[1.2rem] border border-amber-200 bg-amber-50 px-4 py-4">
                          <div className="flex items-center gap-2">
                            <AlertTriangle className="h-4 w-4 text-amber-600" />
                            <p className="font-semibold text-amber-700">Warnings реконструкции</p>
                          </div>
                          <ul className="mt-3 space-y-2 text-sm text-amber-700">
                            {draft.warnings.map((warning) => (
                              <li key={warning}>{warning}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </div>
                  </div>
                ) : null}

                {draft && developmentTab === "tool" ? (
                  <div className="space-y-6">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <Tabs
                        className="max-w-full overflow-x-auto"
                        items={draft.tools.map((tool, index) => ({
                          value: String(index),
                          label: tool.tool_name || `tool #${index + 1}`,
                        }))}
                        onValueChange={(value) => setSelectedToolIndex(Number(value))}
                        value={String(selectedToolIndex)}
                      />
                      <div className="flex flex-wrap gap-2">
                        <Button
                          leadingIcon={<PackagePlus className="h-4 w-4" />}
                          onClick={addTool}
                          size="sm"
                          variant="outline"
                        >
                          Добавить tool
                        </Button>
                        <Button
                          disabled={!selectedTool}
                          leadingIcon={<Copy className="h-4 w-4" />}
                          onClick={duplicateTool}
                          size="sm"
                          variant="outline"
                        >
                          Дублировать
                        </Button>
                        <Button
                          disabled={draft.tools.length <= 1}
                          leadingIcon={<Trash2 className="h-4 w-4" />}
                          onClick={removeTool}
                          size="sm"
                          variant="outline"
                        >
                          Удалить
                        </Button>
                      </div>
                    </div>

                    {selectedTool ? (
                      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
                        <div className="space-y-4">
                          <div className="grid gap-4 md:grid-cols-2">
                            <label className="space-y-2 text-sm font-medium text-slate-800">
                              <span>Tool name</span>
                              <input
                                className="field-base h-11 w-full px-4 text-sm"
                                onChange={(event) => updateToolStringField("tool_name", event.target.value)}
                                value={selectedTool.tool_name}
                              />
                            </label>
                            <label className="space-y-2 text-sm font-medium text-slate-800">
                              <span>Method name</span>
                              <input
                                className="field-base h-11 w-full px-4 text-sm"
                                onChange={(event) => updateToolStringField("method_name", event.target.value)}
                                value={selectedTool.method_name}
                              />
                            </label>
                            <label className="space-y-2 text-sm font-medium text-slate-800">
                              <span>Lifecycle</span>
                              <input
                                className="field-base h-11 w-full px-4 text-sm"
                                onChange={(event) => updateToolStringField("lifecycle", event.target.value)}
                                value={selectedTool.lifecycle}
                              />
                            </label>
                            <label className="space-y-2 text-sm font-medium text-slate-800">
                              <span>Contract version</span>
                              <input
                                className="field-base h-11 w-full px-4 text-sm"
                                onChange={(event) =>
                                  updateToolStringField("contract_version", event.target.value)
                                }
                                value={selectedTool.contract_version}
                              />
                            </label>
                          </div>

                          <label className="space-y-2 text-sm font-medium text-slate-800">
                            <span>Описание</span>
                            <textarea
                              className="field-base min-h-[100px] w-full resize-y px-4 py-4 text-sm"
                              onChange={(event) =>
                                updateToolStringField("description", event.target.value)
                              }
                              value={selectedTool.description}
                            />
                          </label>

                          <div className="grid gap-4 md:grid-cols-2">
                            <label className="space-y-2 text-sm font-medium text-slate-800">
                              <span>Aliases</span>
                              <textarea
                                className="field-base min-h-[110px] w-full resize-y px-4 py-4 text-sm"
                                onChange={(event) =>
                                  updateToolListField("aliases", event.target.value)
                                }
                                value={joinLines(selectedTool.aliases)}
                              />
                            </label>
                            <label className="space-y-2 text-sm font-medium text-slate-800">
                              <span>Capabilities</span>
                              <textarea
                                className="field-base min-h-[110px] w-full resize-y px-4 py-4 text-sm"
                                onChange={(event) =>
                                  updateToolListField("capabilities", event.target.value)
                                }
                                value={joinLines(selectedTool.capabilities)}
                              />
                            </label>
                          </div>

                          <div className="grid gap-4 md:grid-cols-2">
                            <label className="space-y-2 text-sm font-medium text-slate-800">
                              <span>Params schema</span>
                              <textarea
                                className="field-base min-h-[220px] w-full resize-y px-4 py-4 font-mono text-xs"
                                defaultValue={prettyJson(selectedTool.params_schema)}
                                key={`params-${selectedToolIndex}-${selectedTool.tool_name}`}
                                onBlur={(event) =>
                                  updateToolJsonField(
                                    "params_schema",
                                    event.target.value,
                                    "Params schema"
                                  )
                                }
                              />
                            </label>
                            <label className="space-y-2 text-sm font-medium text-slate-800">
                              <span>Output schema</span>
                              <textarea
                                className="field-base min-h-[220px] w-full resize-y px-4 py-4 font-mono text-xs"
                                defaultValue={prettyJson(selectedTool.output_schema)}
                                key={`output-${selectedToolIndex}-${selectedTool.tool_name}`}
                                onBlur={(event) =>
                                  updateToolJsonField(
                                    "output_schema",
                                    event.target.value,
                                    "Output schema"
                                  )
                                }
                              />
                            </label>
                          </div>

                          {selectedOutputContract ? (
                            <div className="rounded-[1.2rem] border border-border bg-surface-subtle px-4 py-4">
                              <div className="flex flex-wrap items-start justify-between gap-3">
                                <div>
                                  <p className="text-xs uppercase tracking-[0.2em] text-brand-700">
                                    Playbook decision contract
                                  </p>
                                  <p className="mt-2 text-sm text-slate-500">
                                    Эти поля задают варианты условий в low-code playbook builder.
                                  </p>
                                </div>
                                <Badge tone="brand">
                                  {outputContractList(selectedOutputContract, "status_values").join(" / ")}
                                </Badge>
                              </div>
                              <div className="mt-4 grid gap-4 md:grid-cols-3">
                                <label className="space-y-2 text-sm font-medium text-slate-800">
                                  <span>Status path</span>
                                  <input
                                    className="field-base h-11 w-full px-4 text-sm"
                                    onChange={(event) =>
                                      updateToolOutputContractField("status_path", event.target.value)
                                    }
                                    value={outputContractString(selectedOutputContract, "status_path")}
                                  />
                                </label>
                                <label className="space-y-2 text-sm font-medium text-slate-800">
                                  <span>Summary path</span>
                                  <input
                                    className="field-base h-11 w-full px-4 text-sm"
                                    onChange={(event) =>
                                      updateToolOutputContractField("summary_path", event.target.value)
                                    }
                                    value={outputContractString(selectedOutputContract, "summary_path")}
                                  />
                                </label>
                                <label className="space-y-2 text-sm font-medium text-slate-800">
                                  <span>Error code path</span>
                                  <input
                                    className="field-base h-11 w-full px-4 text-sm"
                                    onChange={(event) =>
                                      updateToolOutputContractField("error_code_path", event.target.value)
                                    }
                                    value={outputContractString(selectedOutputContract, "error_code_path")}
                                  />
                                </label>
                              </div>
                              <div className="mt-4 grid gap-4 md:grid-cols-3">
                                <label className="space-y-2 text-sm font-medium text-slate-800">
                                  <span>All statuses</span>
                                  <textarea
                                    className="field-base min-h-[96px] w-full resize-y px-4 py-4 text-sm"
                                    onChange={(event) =>
                                      updateToolOutputContractField("status_values", event.target.value, true)
                                    }
                                    value={joinLines(outputContractList(selectedOutputContract, "status_values"))}
                                  />
                                </label>
                                <label className="space-y-2 text-sm font-medium text-slate-800">
                                  <span>Success statuses</span>
                                  <textarea
                                    className="field-base min-h-[96px] w-full resize-y px-4 py-4 text-sm"
                                    onChange={(event) =>
                                      updateToolOutputContractField("success_values", event.target.value, true)
                                    }
                                    value={joinLines(outputContractList(selectedOutputContract, "success_values"))}
                                  />
                                </label>
                                <label className="space-y-2 text-sm font-medium text-slate-800">
                                  <span>Error statuses</span>
                                  <textarea
                                    className="field-base min-h-[96px] w-full resize-y px-4 py-4 text-sm"
                                    onChange={(event) =>
                                      updateToolOutputContractField("error_values", event.target.value, true)
                                    }
                                    value={joinLines(outputContractList(selectedOutputContract, "error_values"))}
                                  />
                                </label>
                              </div>
                            </div>
                          ) : null}

                          <label className="space-y-2 text-sm font-medium text-slate-800">
                            <span>User function body</span>
                            <textarea
                              className="field-base min-h-[280px] w-full resize-y px-4 py-4 font-mono text-xs"
                              onChange={(event) =>
                                updateToolStringField("user_function_body", event.target.value)
                              }
                              value={selectedTool.user_function_body}
                            />
                          </label>
                        </div>

                        <div className="space-y-4">
                          <div className="rounded-[1.2rem] border border-border bg-surface-subtle px-4 py-4">
                            <p className="text-xs uppercase tracking-[0.2em] text-brand-700">
                              Tool policy
                            </p>
                            <p className="mt-3 text-lg font-semibold text-slate-950">
                              {selectedTool.tool_name}
                            </p>
                            <p className="mt-2 text-sm text-slate-500">
                              Metadata, presets, resources и security envelopes редактируются без legacy wizard.
                            </p>
                          </div>

                          <label className="space-y-2 text-sm font-medium text-slate-800">
                            <span>Metadata JSON</span>
                            <textarea
                              className="field-base min-h-[180px] w-full resize-y px-4 py-4 font-mono text-xs"
                              defaultValue={prettyJson(selectedTool.metadata)}
                              key={`metadata-${selectedToolIndex}-${selectedTool.tool_name}`}
                              onBlur={(event) =>
                                updateToolJsonField("metadata", event.target.value, "Metadata")
                              }
                            />
                          </label>

                          <label className="space-y-2 text-sm font-medium text-slate-800">
                            <span>Presets JSON</span>
                            <textarea
                              className="field-base min-h-[140px] w-full resize-y px-4 py-4 font-mono text-xs"
                              defaultValue={prettyJson(selectedTool.presets)}
                              key={`presets-${selectedToolIndex}-${selectedTool.tool_name}`}
                              onBlur={(event) =>
                                updateToolJsonField("presets", event.target.value, "Presets")
                              }
                            />
                          </label>

                          <label className="space-y-2 text-sm font-medium text-slate-800">
                            <span>Dependencies JSON</span>
                            <textarea
                              className="field-base min-h-[140px] w-full resize-y px-4 py-4 font-mono text-xs"
                              defaultValue={prettyJson(selectedTool.dependencies)}
                              key={`dependencies-${selectedToolIndex}-${selectedTool.tool_name}`}
                              onBlur={(event) =>
                                updateToolJsonField(
                                  "dependencies",
                                  event.target.value,
                                  "Dependencies"
                                )
                              }
                            />
                          </label>

                          <label className="space-y-2 text-sm font-medium text-slate-800">
                            <span>Resources JSON</span>
                            <textarea
                              className="field-base min-h-[180px] w-full resize-y px-4 py-4 font-mono text-xs"
                              defaultValue={prettyJson(selectedTool.resources)}
                              key={`resources-${selectedToolIndex}-${selectedTool.tool_name}`}
                              onBlur={(event) =>
                                updateToolJsonField("resources", event.target.value, "Resources")
                              }
                            />
                          </label>

                          <label className="space-y-2 text-sm font-medium text-slate-800">
                            <span>Redaction JSON</span>
                            <textarea
                              className="field-base min-h-[140px] w-full resize-y px-4 py-4 font-mono text-xs"
                              defaultValue={prettyJson(selectedTool.redaction)}
                              key={`redaction-${selectedToolIndex}-${selectedTool.tool_name}`}
                              onBlur={(event) =>
                                updateToolJsonField("redaction", event.target.value, "Redaction")
                              }
                            />
                          </label>

                          <label className="space-y-2 text-sm font-medium text-slate-800">
                            <span>Artifact types JSON</span>
                            <textarea
                              className="field-base min-h-[110px] w-full resize-y px-4 py-4 font-mono text-xs"
                              defaultValue={prettyJson(selectedTool.artifact_types)}
                              key={`artifacts-${selectedToolIndex}-${selectedTool.tool_name}`}
                              onBlur={(event) =>
                                updateToolJsonField(
                                  "artifact_types",
                                  event.target.value,
                                  "Artifact types"
                                )
                              }
                            />
                          </label>

                          <label className="space-y-2 text-sm font-medium text-slate-800">
                            <span>Error codes JSON</span>
                            <textarea
                              className="field-base min-h-[110px] w-full resize-y px-4 py-4 font-mono text-xs"
                              defaultValue={prettyJson(selectedTool.error_codes)}
                              key={`errors-${selectedToolIndex}-${selectedTool.tool_name}`}
                              onBlur={(event) =>
                                updateToolJsonField(
                                  "error_codes",
                                  event.target.value,
                                  "Error codes"
                                )
                              }
                            />
                          </label>
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : null}

                {draft && developmentTab === "preview" ? (
                  <div className="space-y-6">
                    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
                      <div className="space-y-4">
                        <Card className="border-dashed shadow-none">
                          <CardHeader>
                            <CardTitle>Локальная проверка</CardTitle>
                            <CardDescription>
                              Базовые проблемы структуры черновика до server validate.
                            </CardDescription>
                          </CardHeader>
                          <CardContent>
                            {localIssues.length ? (
                              <ul className="space-y-2 text-sm text-rose-700">
                                {localIssues.map((issue) => (
                                  <li key={issue} className="flex gap-2">
                                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                                    <span>{issue}</span>
                                  </li>
                                ))}
                              </ul>
                            ) : (
                              <div className="flex items-center gap-2 rounded-[1rem] bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                                <CheckCircle2 className="h-4 w-4" />
                                Черновик согласован и готов к server validate.
                              </div>
                            )}
                          </CardContent>
                        </Card>

                        <Card className="border-dashed shadow-none">
                          <CardHeader>
                            <div className="flex items-center justify-between gap-3">
                              <div>
                                <CardTitle>Server validate</CardTitle>
                                <CardDescription>
                                  Preview manifest, preflight и ownership conflicts из реального backend.
                                </CardDescription>
                              </div>
                              <Button
                                disabled={validateMutation.isPending || localIssues.length > 0}
                                leadingIcon={<CheckCircle2 className="h-4 w-4" />}
                                onClick={() => validateMutation.mutate(buildDraftPayload(draft))}
                                size="sm"
                              >
                                {validateMutation.isPending ? "Проверяем..." : "Запустить validate"}
                              </Button>
                            </div>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            {serverValidation ? (
                              <>
                                <div className="grid gap-4 md:grid-cols-3">
                                  <div className="rounded-[1rem] bg-surface-subtle px-4 py-4">
                                    <p className="text-sm text-slate-500">Publish ready</p>
                                    <p className="mt-2 text-xl font-semibold text-slate-950">
                                      {serverValidation.publish_ready ? "Да" : "Нет"}
                                    </p>
                                  </div>
                                  <div className="rounded-[1rem] bg-surface-subtle px-4 py-4">
                                    <p className="text-sm text-slate-500">Module exists</p>
                                    <p className="mt-2 text-xl font-semibold text-slate-950">
                                      {serverValidation.module_exists ? "Да" : "Нет"}
                                    </p>
                                  </div>
                                  <div className="rounded-[1rem] bg-surface-subtle px-4 py-4">
                                    <p className="text-sm text-slate-500">Conflicts</p>
                                    <p className="mt-2 text-xl font-semibold text-slate-950">
                                      {serverValidation.conflicts?.length ?? 0}
                                    </p>
                                  </div>
                                </div>

                                {serverValidation.preflight_errors?.length ? (
                                  <div className="rounded-[1rem] border border-rose-200 bg-rose-50 px-4 py-4">
                                    <p className="font-semibold text-rose-700">Preflight errors</p>
                                    <ul className="mt-3 space-y-2 text-sm text-rose-700">
                                      {serverValidation.preflight_errors.map((item) => (
                                        <li key={item}>{item}</li>
                                      ))}
                                    </ul>
                                  </div>
                                ) : null}

                                {serverValidation.conflicts?.length ? (
                                  <div className="rounded-[1rem] border border-amber-200 bg-amber-50 px-4 py-4">
                                    <p className="font-semibold text-amber-700">Ownership conflicts</p>
                                    <pre className="mt-3 overflow-x-auto text-xs text-amber-700">
                                      {prettyJson(serverValidation.conflicts)}
                                    </pre>
                                  </div>
                                ) : null}

                                <div className="grid gap-4 md:grid-cols-2">
                                  <div className="rounded-[1rem] border border-border bg-white px-4 py-4">
                                    <p className="font-semibold text-slate-900">Manifest preview</p>
                                    <pre className="mt-3 overflow-x-auto rounded-[0.9rem] bg-slate-950 px-4 py-4 text-xs text-slate-100">
                                      {prettyJson(serverValidation.manifest_json)}
                                    </pre>
                                  </div>
                                  <div className="rounded-[1rem] border border-border bg-white px-4 py-4">
                                    <p className="font-semibold text-slate-900">Validation JSON</p>
                                    <pre className="mt-3 overflow-x-auto rounded-[0.9rem] bg-slate-950 px-4 py-4 text-xs text-slate-100">
                                      {prettyJson(serverValidation.validation_json)}
                                    </pre>
                                  </div>
                                </div>
                              </>
                            ) : (
                              <div className="rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-6 text-sm text-slate-500">
                                Запустите проверку, чтобы увидеть manifest preview, source decomposition и конфликты.
                              </div>
                            )}
                          </CardContent>
                        </Card>
                      </div>

                      <div className="space-y-4">
                        <Card className="h-fit border-dashed shadow-none">
                          <CardHeader>
                            <CardTitle>API preview</CardTitle>
                            <CardDescription>
                              Те же payload/curl-сценарии, которые раньше были в legacy workbench.
                            </CardDescription>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            <Tabs
                              items={previewTabs}
                              onValueChange={(value) => setPreviewTab(value as PreviewTab)}
                              value={previewTab}
                            />
                            <div className="rounded-[1rem] border border-border bg-white px-4 py-4">
                              <div className="mb-3 flex items-center justify-between gap-2">
                                <p className="font-semibold text-slate-900">Preview</p>
                                <Button
                                  leadingIcon={<Copy className="h-4 w-4" />}
                                  onClick={() =>
                                    copyToClipboard(
                                      previewTab === "payload"
                                        ? prettyJson(payloadPreview)
                                        : buildPreviewCurl(
                                            previewTab === "curl-validate" ? "validate" : "save",
                                            payloadPreview ?? {}
                                          )
                                    )
                                  }
                                  size="sm"
                                  variant="outline"
                                >
                                  Копировать
                                </Button>
                              </div>
                              <pre className="overflow-x-auto rounded-[0.9rem] bg-slate-950 px-4 py-4 text-xs text-slate-100">
                                {previewTab === "payload"
                                  ? prettyJson(payloadPreview)
                                  : buildPreviewCurl(
                                      previewTab === "curl-validate" ? "validate" : "save",
                                      payloadPreview ?? {}
                                    )}
                              </pre>
                            </div>
                          </CardContent>
                        </Card>

                        <Card className="h-fit border-dashed shadow-none">
                          <CardHeader>
                            <CardTitle>Разложение source</CardTitle>
                            <CardDescription>
                              Сколько методов и tool names backend смог реконструировать из архива.
                            </CardDescription>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            <MetaRow
                              label="Resolved tools"
                              value={activeSource?.decomposition.resolved_tools ?? 0}
                            />
                            <MetaRow
                              label="Unresolved"
                              value={activeSource?.decomposition.unresolved_tools.length ?? 0}
                            />
                            <MetaRow
                              label="Files"
                              value={activeSource?.files.length ?? 0}
                            />
                            <div className="flex flex-wrap gap-2">
                              {(activeSource?.decomposition.available_methods ?? []).slice(0, 6).map((item) => (
                                <Badge key={item} tone="neutral">
                                  {item}
                                </Badge>
                              ))}
                            </div>
                          </CardContent>
                        </Card>
                      </div>
                    </div>
                  </div>
                ) : null}

                {draft && developmentTab === "source" ? (
                  <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
                    <Card className="h-fit">
                      <CardHeader>
                        <CardTitle>Source files</CardTitle>
                        <CardDescription>
                          Архивная декомпозиция после открытия версии или server validate preview.
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        {activeSource?.files.length ? (
                          <div className="max-h-[calc(100vh-24rem)] space-y-2 overflow-y-auto pr-1">
                            {activeSource.files.map((file) => (
                              <button
                                key={file.path}
                                className={cn(
                                  "w-full rounded-[1rem] border px-4 py-3 text-left transition-colors",
                                  selectedSourceFile?.path === file.path
                                    ? "border-brand-200 bg-brand-50"
                                    : "border-border bg-white hover:border-brand-100 hover:bg-surface-subtle"
                                )}
                                onClick={() => setSelectedSourcePath(file.path)}
                                type="button"
                              >
                                <div className="flex items-center justify-between gap-3">
                                  <p className="font-medium text-slate-900">{file.path}</p>
                                  <Badge tone="neutral">{file.language}</Badge>
                                </div>
                                <p className="mt-2 text-xs text-slate-500">{file.size_bytes} bytes</p>
                              </button>
                            ))}
                          </div>
                        ) : (
                          <div className="rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-6 text-sm text-slate-500">
                            Source preview появится после открытия версии или server validate.
                          </div>
                        )}
                      </CardContent>
                    </Card>

                    <Card>
                      <CardHeader>
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <CardTitle>{selectedSourceFile?.path ?? "Source preview"}</CardTitle>
                            <CardDescription>
                              Detected tools, parse errors и содержимое выбранного файла.
                            </CardDescription>
                          </div>
                          {selectedSourceFile ? (
                            <Button
                              leadingIcon={<Copy className="h-4 w-4" />}
                              onClick={() => copyToClipboard(selectedSourceFile.content)}
                              size="sm"
                              variant="outline"
                            >
                              Копировать
                            </Button>
                          ) : null}
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        {selectedSourceFile ? (
                          <>
                            {selectedSourceFile.detected_tools?.length ? (
                              <div className="flex flex-wrap gap-2">
                                {selectedSourceFile.detected_tools.map((item, index) => (
                                  <Badge key={`${item.tool_name ?? item.method ?? index}`} tone="brand">
                                    {item.tool_name ?? item.method ?? "tool"}
                                  </Badge>
                                ))}
                              </div>
                            ) : null}

                            {selectedSourceFile.parse_errors?.length ? (
                              <div className="rounded-[1rem] border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-700">
                                {selectedSourceFile.parse_errors.join("\n")}
                              </div>
                            ) : null}

                            <pre className="max-h-[calc(100vh-24rem)] overflow-auto rounded-[1rem] bg-slate-950 px-4 py-4 text-xs text-slate-100">
                              {selectedSourceFile.content}
                            </pre>
                          </>
                        ) : (
                          <div className="rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                            Выберите файл слева.
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ) : null}

          {workspaceTab === "archive" ? (
            <Card>
              <CardHeader className="gap-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <CardTitle>Импорт ZIP-архива</CardTitle>
                    <CardDescription>
                      Реальный upload в server registry, smoke/preflight и затем быстрый вход в editor.
                    </CardDescription>
                  </div>
                  <Button
                    leadingIcon={<Upload className="h-4 w-4" />}
                    onClick={() => fileInputRef.current?.click()}
                    size="sm"
                    variant="outline"
                  >
                    Выбрать ZIP
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
                  <div className="space-y-4">
                    <input
                      accept=".zip"
                      className="hidden"
                      onChange={(event) => {
                        const file = event.target.files?.[0] ?? null;
                        setArchiveFile(file);
                        if (file && !archiveModuleName.trim()) {
                          const guessed = file.name.replace(/\.zip$/i, "");
                          const semverMatch = guessed.match(/^(.*)-(\d+\.\d+\.\d+(?:[-+][A-Za-z0-9._-]+)?)$/);
                          if (semverMatch) {
                            setArchiveModuleName(semverMatch[1]);
                            setArchiveVersion(semverMatch[2]);
                          } else {
                            setArchiveModuleName(guessed);
                          }
                        }
                      }}
                      ref={fileInputRef}
                      type="file"
                    />

                    <div className="rounded-[1.2rem] border border-dashed border-border bg-surface-subtle px-5 py-5">
                      <div className="flex items-center gap-3">
                        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-700">
                          <FileArchive className="h-5 w-5" />
                        </div>
                        <div>
                          <p className="font-semibold text-slate-950">
                            {archiveFile?.name ?? "ZIP ещё не выбран"}
                          </p>
                          <p className="mt-1 text-sm text-slate-500">
                            {archiveFile ? `${archiveFile.size} bytes` : "Выберите архив вида module-1.2.3.zip или заполните поля вручную."}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="grid gap-4 md:grid-cols-2">
                      <label className="space-y-2 text-sm font-medium text-slate-800">
                        <span>Module name</span>
                        <input
                          className="field-base h-11 w-full px-4 text-sm"
                          onChange={(event) => setArchiveModuleName(event.target.value)}
                          value={archiveModuleName}
                        />
                      </label>
                      <label className="space-y-2 text-sm font-medium text-slate-800">
                        <span>Version</span>
                        <input
                          className="field-base h-11 w-full px-4 text-sm"
                          onChange={(event) => setArchiveVersion(event.target.value)}
                          value={archiveVersion}
                        />
                      </label>
                    </div>

                    <label className="flex h-11 items-center gap-3 rounded-pill border border-border bg-white px-4">
                      <input
                        checked={archiveOverwrite}
                        onChange={(event) => setArchiveOverwrite(event.target.checked)}
                        type="checkbox"
                      />
                      <span className="text-sm font-medium text-slate-700">
                        Разрешить overwrite существующей версии
                      </span>
                    </label>

                    <Button
                      disabled={
                        uploadMutation.isPending ||
                        !archiveFile ||
                        !archiveModuleName.trim() ||
                        !archiveVersion.trim()
                      }
                      leadingIcon={<Upload className="h-4 w-4" />}
                      onClick={() => {
                        if (!archiveFile) {
                          return;
                        }
                        uploadMutation.mutate({
                          file: archiveFile,
                          moduleName: archiveModuleName.trim(),
                          version: archiveVersion.trim(),
                          overwrite: archiveOverwrite,
                        });
                      }}
                    >
                      {uploadMutation.isPending ? "Загружаем..." : "Загрузить архив"}
                    </Button>
                  </div>

                  <div className="space-y-4">
                    <Card className="border-dashed shadow-none">
                      <CardHeader>
                        <CardTitle>Что происходит при upload</CardTitle>
                        <CardDescription>
                          Этот же поток раньше жил в legacy workbench: preflight, smoke и запись в registry.
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-3 text-sm text-slate-600">
                        <div className="flex items-start gap-3 rounded-[1rem] bg-surface-subtle px-4 py-4">
                          <Search className="mt-0.5 h-4 w-4 shrink-0 text-brand-700" />
                          <span>Сервер проверяет manifest, ownership и smoke-сценарии до публикации.</span>
                        </div>
                        <div className="flex items-start gap-3 rounded-[1rem] bg-surface-subtle px-4 py-4">
                          <Boxes className="mt-0.5 h-4 w-4 shrink-0 text-brand-700" />
                          <span>После успешного upload версия попадает в registry и сразу доступна в editor.</span>
                        </div>
                        <div className="flex items-start gap-3 rounded-[1rem] bg-surface-subtle px-4 py-4">
                          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-brand-700" />
                          <span>
                            Overwrite доступен только для административного сценария и сохраняет ту же backend-валидацию.
                          </span>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  );
}
