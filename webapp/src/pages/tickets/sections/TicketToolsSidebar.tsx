import {
  ListFilter,
  Wrench,
} from "lucide-react";
import {
  Badge,
} from "../../../components/ui/badge";
import {
  Button,
} from "../../../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import {
  SchemaParamEditor,
} from "../../../components/forms/schema-param-editor";
import {
  SearchField,
} from "../../../components/ui/search-field";
import {
  Select,
} from "../../../components/ui/select";
import {
  supportToolParamFields,
} from "../../../features/queues/tool-param-fields";
import {
  getTicketStatusTone,
} from "../../../features/tickets/status-presentation";
import {
  cn,
} from "../../../shared/ui/cn";
import {
  describeToolRiskLevel,
  formatDiagnosticTarget,
} from '../detail-formatting';
import {
  useTicketDetailController,
} from "../hooks/use-ticket-detail-controller";
export function TicketToolsSidebar({ controller }: { controller: ReturnType<typeof useTicketDetailController> }) {
  const { ticketId, selectedToolName, setSelectedToolName, selectedPresetId, setSelectedPresetId, toolParams, setToolParams, toolSearch, setToolSearch, toolsQuery, toolList, visibleTools, toolMutation, selectedTool, toolAccess } = controller;
  if (!ticketId) return null;
  return (<Card className="overflow-hidden">
    <CardHeader>
      <CardTitle>Инструменты</CardTitle>
      <CardDescription>
        Живой launcher по реальным typed API: поиск, выбор инструмента, presets и параметры.
      </CardDescription>
    </CardHeader>
    <CardContent className="space-y-4">
      {toolsQuery.isLoading ? (
        <p className="text-sm text-slate-500">Загружаем инструменты...</p>
      ) : null}

      {toolsQuery.isError ? (
        <p className="text-sm text-rose-700">
          {toolsQuery.error instanceof Error
            ? toolsQuery.error.message
            : "Не удалось загрузить инструменты."}
        </p>
      ) : null}

      <div className="rounded-[1rem] border border-border bg-surface-subtle px-4 py-3 text-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Цель запуска</p>
        <p className="mt-2 font-semibold text-slate-950">
          {formatDiagnosticTarget(toolsQuery.data?.diagnostic_target, toolsQuery.data?.device_id ?? null)}
        </p>
        {toolsQuery.data?.diagnostic_target?.source ? (
          <p className="mt-1 text-xs text-slate-500">source: {toolsQuery.data.diagnostic_target.source}</p>
        ) : null}
      </div>

      {toolList.length ? (
        <>
          <SearchField
            onChange={(event) => setToolSearch(event.target.value)}
            placeholder="Поиск по tool, module или описанию"
            value={toolSearch}
          />

          <div className="space-y-2 rounded-[1.1rem] border border-border bg-surface-subtle p-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <ListFilter className="h-4 w-4 text-brand-700" />
              Выбор инструмента
            </div>
            <div className="max-h-56 space-y-2 overflow-y-auto pr-1">
              {visibleTools.length ? (
                visibleTools.map((tool) => {
                  const active = tool.tool_name === selectedToolName;
                  return (
                    <button
                      key={tool.tool_name}
                      className={cn(
                        "w-full rounded-[1rem] border px-4 py-4 text-left transition-colors",
                        active
                          ? "border-brand-200 bg-brand-50"
                          : "border-border bg-white hover:border-brand-100 hover:bg-surface-subtle",
                      )}
                      onClick={() => {
                        setSelectedToolName(tool.tool_name);
                        setSelectedPresetId("");
                        setToolParams({});
                      }}
                      type="button"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate font-semibold text-slate-950">{tool.tool_name}</p>
                          <p className="mt-1 truncate text-xs text-slate-500">
                            {tool.module_name ?? "module не указан"}
                          </p>
                        </div>
                        <Badge tone={tool.source === "server" ? "brand" : "info"}>
                          {tool.source}
                        </Badge>
                      </div>
                      <p className="mt-3 text-sm text-slate-600">
                        {tool.description ?? "Описание инструмента не заполнено."}
                      </p>
                    </button>
                  );
                })
              ) : (
                <div className="rounded-[1rem] border border-dashed border-border bg-white px-4 py-6 text-sm text-slate-500">
                  Под текущий поиск инструменты не найдены.
                </div>
              )}
            </div>
          </div>

          {selectedTool ? (
            <>
              <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm text-slate-600">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-semibold text-slate-900">{selectedTool.tool_name}</p>
                  <Badge tone={selectedTool.source === "server" ? "brand" : "info"}>
                    {selectedTool.source}
                  </Badge>
                  <Badge tone={getTicketStatusTone(selectedTool.risk_level)}>
                    {describeToolRiskLevel(selectedTool.risk_level)}
                  </Badge>
                </div>
                <p className="mt-3">
                  {selectedTool.description ?? "Описание инструмента не заполнено."}
                </p>
                <p className="mt-2 text-xs text-slate-500">
                  {selectedTool.requires_consent ? "Требуется подтверждение • " : ""}
                  {selectedTool.install_required ? "Нужна установка на устройстве" : "Готов к запуску"}
                </p>
              </div>

              {selectedTool.presets.length ? (
                <label className="space-y-2 text-sm font-medium text-slate-800">
                  <span>Preset</span>
                  <Select
                    onChange={(event) => {
                      const value = event.target.value;
                      setSelectedPresetId(value);
                      const preset = selectedTool.presets.find((item) => item.preset_id === value);
                      setToolParams(preset?.params ? { ...preset.params } : {});
                    }}
                    value={selectedPresetId}
                  >
                    <option value="">Без preset</option>
                    {selectedTool.presets.map((preset) => (
                      <option key={preset.preset_id} value={preset.preset_id}>
                        {preset.label}
                      </option>
                    ))}
                  </Select>
                </label>
              ) : null}

              {selectedPresetId ? null : (
                <SchemaParamEditor
                  className="space-y-3"
                  fields={supportToolParamFields(selectedTool)}
                  onChange={setToolParams}
                  value={toolParams}
                />
              )}

              {toolMutation.isSuccess ? (
                <p className="text-sm text-emerald-700">{toolMutation.data.message}</p>
              ) : null}

              {toolMutation.isError ? (
                <p className="text-sm text-rose-700">
                  {toolMutation.error instanceof Error
                    ? toolMutation.error.message
                    : "Не удалось запустить инструмент."}
                </p>
              ) : null}

              {!toolAccess.allowed ? (
                <p className="rounded-[0.8rem] border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                  {toolAccess.reason}
                </p>
              ) : null}

              <Button
                className="w-full"
                disabled={!toolAccess.allowed || toolMutation.isPending}
                leadingIcon={<Wrench className="h-4 w-4" />}
                onClick={() => {
                  if (toolAccess.allowed) {
                    void toolMutation.mutateAsync();
                  }
                }}
              >
                {toolMutation.isPending ? "Запускаем..." : "Запустить инструмент"}
              </Button>
            </>
          ) : (
            <p className="text-sm text-slate-500">
              Выберите инструмент слева, чтобы открыть presets и параметры.
            </p>
          )}
        </>
      ) : (
        <p className="text-sm text-slate-500">Для этого тикета пока нет доступных инструментов.</p>
      )}
    </CardContent>
  </Card>);
}