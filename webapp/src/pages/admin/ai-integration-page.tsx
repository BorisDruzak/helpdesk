import { useQuery } from "@tanstack/react-query";
import { Bot, Database, RefreshCcw, RotateCcw, ShieldCheck } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { fetchAiIntegrationMcpStatus } from "../../features/ai-integration/api";

type BadgeTone = "success" | "warning" | "danger" | "neutral";

function toneForStatus(status?: string): BadgeTone {
  if (status === "ok" || status === "fresh") return "success";
  if (status === "partial" || status === "stale" || status === "unknown") return "warning";
  if (status === "error" || status === "failed") return "danger";
  return "neutral";
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "нет данных";
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}

export function AdminAiIntegrationPage() {
  const query = useQuery({
    queryKey: ["admin-ai-integration-mcp"],
    queryFn: fetchAiIntegrationMcpStatus,
    refetchInterval: 15_000,
    retry: false,
  });
  const payload = query.data;
  const mcp = payload?.mcp;
  const runtimeSnapshot = mcp?.runtime_status.snapshot;
  const serviceHealth = runtimeSnapshot?.service_health ?? {};
  const connectedAgents = runtimeSnapshot?.connected_agents ?? {};

  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <Button leadingIcon={<RefreshCcw className="h-4 w-4" />} onClick={() => void query.refetch()} size="sm" variant="outline">
            Обновить
          </Button>
        }
        description="MCP, read-only диагностика Codex, runtime snapshots и инструкции по reload после deploy."
        eyebrow="Admin workspace"
        title="Интеграция ИИ"
      />

      {query.isLoading ? <p className="text-sm text-slate-500">Загружаем статус MCP сервера...</p> : null}
      {query.isError ? (
        <p className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">
          {query.error instanceof Error ? query.error.message : "Не удалось загрузить статус Интеграции ИИ."}
        </p>
      ) : null}

      {mcp ? (
        <>
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Bot className="h-4 w-4" />
                  MCP сервер
                </CardTitle>
                <CardDescription>{mcp.manifest.name}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <Badge tone="info">{mcp.manifest.mode}</Badge>
                <p className="text-sm text-slate-600">Инструментов: {mcp.manifest.tools.length}</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Database className="h-4 w-4" />
                  PostgreSQL
                </CardTitle>
                <CardDescription>DB health через MCP bootstrap</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <Badge tone={toneForStatus(mcp.db_health.status)}>{mcp.db_health.status}</Badge>
                <p className="text-sm text-slate-600">Latency: {formatValue(mcp.db_health.latency_ms)} ms</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <RotateCcw className="h-4 w-4" />
                  Reload
                </CardTitle>
                <CardDescription>После deploy stdio MCP держит старый import graph.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <Badge tone={mcp.reload.required_after_deploy ? "warning" : "success"}>
                  {mcp.reload.required_after_deploy ? "restart required" : "ok"}
                </Badge>
                <p className="text-sm text-slate-600">{mcp.reload.status_text}</p>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
            <Card>
              <CardHeader>
                <CardTitle>Runtime snapshot</CardTitle>
                <CardDescription>Persisted evidence из живого aiohttp server process.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Status</p>
                  <Badge tone={toneForStatus(mcp.runtime_status.status)}>{mcp.runtime_status.status}</Badge>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Confidence</p>
                  <p className="text-sm font-medium">{formatValue(mcp.runtime_status.confidence)}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Git revision</p>
                  <p className="font-mono text-sm">{formatValue(runtimeSnapshot?.git_revision)}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Agent WS</p>
                  <p className="text-sm font-medium">{formatValue(serviceHealth.agent_ws_connections)}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Connected agents evidence</p>
                  <p className="text-sm font-medium">{Object.keys(connectedAgents).length}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Collected</p>
                  <p className="text-sm font-medium">{formatValue(mcp.runtime_status.collected_at)}</p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4" />
                  Safety contract
                </CardTitle>
                <CardDescription>Readonly MCP режим без business mutation.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {Object.entries(mcp.manifest.safety ?? {}).map(([key, value]) => (
                  <div key={key} className="flex items-center justify-between gap-4 rounded-lg bg-slate-50 px-3 py-2 text-sm">
                    <span className="font-mono text-slate-600">{key}</span>
                    <Badge tone={value ? "success" : "warning"}>{formatValue(value)}</Badge>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </>
      ) : null}
    </section>
  );
}
