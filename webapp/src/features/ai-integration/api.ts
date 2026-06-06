export type AiIntegrationMcpPayload = {
  status: string;
  generated_at?: string;
  mcp: {
    manifest: {
      name: string;
      mode: string;
      tools: string[];
      safety?: Record<string, boolean>;
    };
    db_health: {
      status: string;
      reachable?: boolean;
      latency_ms?: number;
      error?: string | null;
    };
    context_freshness: {
      status: string;
      reason?: string;
      stale_sources_count?: number;
      recommended_command?: string | null;
    };
    runtime_status: {
      status: string;
      runtime_snapshot_available?: boolean;
      confidence?: string;
      collected_at?: string;
      expires_at?: string;
      snapshot?: {
        git_revision?: string;
        service_health?: Record<string, unknown>;
        connected_agents?: Record<string, unknown>;
        mcp?: Record<string, unknown>;
      };
    };
    reload: {
      required_after_deploy: boolean;
      codex_restart_recommended: boolean;
      status_text: string;
    };
  };
};

export async function fetchAiIntegrationMcpStatus(): Promise<AiIntegrationMcpPayload> {
  const response = await fetch("/api/web/admin/ai-integration/mcp", { credentials: "same-origin" });
  if (!response.ok) {
    throw new Error(`AI integration status failed: ${response.status}`);
  }
  return (await response.json()) as AiIntegrationMcpPayload;
}
