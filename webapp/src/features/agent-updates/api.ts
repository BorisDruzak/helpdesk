export type AdminDeviceUpdatesPayload = {
  device_id: string;
  device_label: string;
  online: boolean;
  target: string | null;
  current_version: string | null;
  release_channel: string;
  is_release: boolean;
  summary: {
    status: string | null;
    label: string;
    summary: string | null;
  };
  recommendation: {
    update_available: boolean;
    recommendation_source: string;
    recommendation_source_label: string;
    comparison: string;
    comparison_label: string;
    recommended_reason: string | null;
    recommended_reason_label: string | null;
    recommended_build: {
      target: string;
      channel: string;
      version: string;
    } | null;
    assigned_rollout: {
      target: string;
      channel: string;
      version: string;
      updated_at: string | null;
      updated_by: string | null;
    } | null;
  };
  action: {
    enabled: boolean;
    label: string;
    reason_required: boolean;
    endpoint: string;
  };
};

export type AdminDeviceUpdateRunPayload = {
  device_id: string;
  operation_id: string;
  status: string;
  message: string;
  build_source: string;
  poll_url: string;
  build: {
    target: string;
    channel: string;
    version: string;
  };
};

type SuccessResponse<T> = {
  status: "success";
  data: T;
};

type OkResponse<T extends object = Record<string, unknown>> = T & {
  status: "ok";
};

type ErrorResponse = {
  status: "error";
  error?: string;
  error_code?: string;
};

export class AdminDeviceUpdatesApiError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "AdminDeviceUpdatesApiError";
    this.status = status;
    this.errorCode = errorCode;
  }
}

async function readJson<T>(response: Response): Promise<T | null> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }
  return (await response.json()) as T;
}

async function readSuccessResponse<T>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = await readJson<SuccessResponse<T> | ErrorResponse>(response);
  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new AdminDeviceUpdatesApiError(
      errorPayload?.error ?? fallbackMessage,
      response.status,
      errorPayload?.error_code
    );
  }
  return payload.data;
}

async function readOkResponse<T extends object>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = await readJson<OkResponse<T> | ErrorResponse>(response);
  if (!response.ok || !payload || payload.status !== "ok") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new AdminDeviceUpdatesApiError(
      errorPayload?.error ?? fallbackMessage,
      response.status,
      errorPayload?.error_code
    );
  }
  const { status: _status, ...data } = payload;
  return data as T;
}

async function readUploadResponse<T extends object>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = await readJson<(T & { status: "success" }) | ErrorResponse>(response);
  if (!response.ok || !payload || payload.status !== "success") {
    const errorPayload = payload && payload.status === "error" ? payload : null;
    throw new AdminDeviceUpdatesApiError(
      errorPayload?.error ?? fallbackMessage,
      response.status,
      errorPayload?.error_code
    );
  }
  const { status: _status, ...data } = payload;
  return data as T;
}

export async function fetchAdminDeviceUpdates(deviceId: string): Promise<AdminDeviceUpdatesPayload> {
  const response = await fetch(`/api/web/admin/devices/${encodeURIComponent(deviceId)}/updates`, {
    credentials: "same-origin"
  });
  return readSuccessResponse(response, "Не удалось загрузить update workflow устройства");
}

export async function runAdminDeviceUpdate(
  deviceId: string,
  payload: { reason: string; restart_delay_sec?: number | null }
): Promise<AdminDeviceUpdateRunPayload> {
  const response = await fetch(`/api/web/admin/devices/${encodeURIComponent(deviceId)}/updates/run`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  return readSuccessResponse(response, "Не удалось поставить обновление в очередь");
}

export type AgentBuildItem = {
  target: string;
  channel: string;
  version: string;
  artifact_filename: string;
  archive_type: string;
  mime_type: string | null;
  sha256: string;
  size: number;
  notes: string | null;
  created_at: string | null;
  download_path: string;
  is_rollout_assigned: boolean;
  delete_block_reason: string | null;
  assigned_rollout: AgentRolloutAssignment | null;
};

export type AgentBuildsPayload = {
  builds: AgentBuildItem[];
  count: number;
};

export type AgentBuildIdentity = {
  target: string;
  channel: string;
  version: string;
  archive_type?: string;
  artifact_name?: string;
  is_release?: boolean;
  download_path?: string;
};

export type AgentRolloutAssignment = {
  target: string;
  channel: string;
  version: string;
  updated_at: string | null;
  updated_by: string | null;
  build?: AgentBuildIdentity | null;
  build_missing?: boolean;
};

export type AgentRolloutPolicyPayload = {
  assignments: AgentRolloutAssignment[];
  available_targets: string[];
};

export type AgentBuildUploadPayload = {
  target: string;
  channel: string;
  version: string;
  sha256: string;
  size: number;
  download_path: string;
};

export async function fetchAgentBuilds(params: {
  target?: string | null;
  channel?: string | null;
  limit?: number;
} = {}): Promise<AgentBuildsPayload> {
  const searchParams = new URLSearchParams();
  if (params.target) {
    searchParams.set("target", params.target);
  }
  if (params.channel) {
    searchParams.set("channel", params.channel);
  }
  searchParams.set("limit", String(params.limit ?? 200));
  const response = await fetch(`/api/agent_builds?${searchParams.toString()}`, {
    credentials: "same-origin"
  });
  return readOkResponse(response, "Не удалось загрузить реестр сборок агента");
}

export async function fetchAgentRolloutPolicy(): Promise<AgentRolloutPolicyPayload> {
  const response = await fetch("/api/agent_updates/rollout_policy", {
    credentials: "same-origin"
  });
  return readOkResponse(response, "Не удалось загрузить rollout policy агента");
}

export async function uploadAgentBuild(payload: {
  archiveType: "zip" | "tar.gz";
  channel: string;
  file: File;
  notes?: string;
  target: string;
  version: string;
}): Promise<AgentBuildUploadPayload> {
  const formData = new FormData();
  formData.set("file", payload.file);
  formData.set("target", payload.target);
  formData.set("channel", payload.channel);
  formData.set("version", payload.version);
  formData.set("archive_type", payload.archiveType);
  if (payload.notes?.trim()) {
    formData.set("notes", payload.notes.trim());
  }
  const response = await fetch("/api/agent_builds/upload", {
    method: "POST",
    credentials: "same-origin",
    body: formData
  });
  return readUploadResponse(response, "Не удалось загрузить build агента");
}

export async function setAgentRolloutPolicy(payload: {
  target: string;
  channel: string;
  version: string;
}): Promise<{ target: string; assignment: AgentRolloutAssignment; build: AgentBuildIdentity }> {
  const response = await fetch("/api/agent_updates/rollout_policy", {
    method: "PATCH",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  return readOkResponse(response, "Не удалось назначить rollout policy");
}

export async function clearAgentRolloutPolicy(target: string): Promise<{ target: string; cleared: boolean }> {
  const response = await fetch("/api/agent_updates/rollout_policy", {
    method: "PATCH",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ target, clear: true })
  });
  return readOkResponse(response, "Не удалось снять rollout policy");
}

export async function deleteAgentBuild(build: Pick<AgentBuildItem, "target" | "channel" | "version">): Promise<{
  target: string;
  channel: string;
  version: string;
}> {
  const response = await fetch(
    `/api/agent_builds/${encodeURIComponent(build.target)}/${encodeURIComponent(build.channel)}/${encodeURIComponent(build.version)}`,
    {
      method: "DELETE",
      credentials: "same-origin"
    }
  );
  return readOkResponse(response, "Не удалось удалить build агента");
}
