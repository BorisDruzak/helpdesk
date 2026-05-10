import { Maximize2, MonitorX, MousePointer2, RotateCcw, Scaling, ShieldCheck, Upload, X } from "lucide-react";
import type { ChangeEvent, ClipboardEvent, DragEvent, KeyboardEvent, MouseEvent, WheelEvent } from "react";
import { useEffect, useRef, useState } from "react";

import { endRemoteAssistSession, failRemoteAssistSession, fetchRemoteAssistViewer, requestRemoteAssist } from "./api";
import type { RemoteAssistViewerInfo } from "./api";

type ViewerState = "loading" | "connecting" | "active" | "ended" | "failed";
type ScaleMode = "fit" | "actual";
type ClipboardState = "off" | "syncing" | "unavailable" | "error";
type FileTransferState = "off" | "ready" | "transferring" | "done" | "error";

type RemoteAssistViewerProps = {
  sessionId: string;
  onClose: () => void;
  onEnded?: () => void;
  canRequestElevated?: boolean;
  onElevatedRequested?: (sessionId: string) => void;
};

function buildSignalingUrl(baseUrl: string, token: string) {
  const url = new URL(baseUrl, window.location.href);
  url.searchParams.set("role", "operator");
  url.searchParams.set("token", token);
  return url.toString();
}

function waitForIceGatheringComplete(pc: RTCPeerConnection, timeoutMs = 5000) {
  if (pc.iceGatheringState === "complete") {
    return Promise.resolve();
  }
  return new Promise<void>((resolve) => {
    let done = false;
    const finish = () => {
      if (done) {
        return;
      }
      done = true;
      window.clearTimeout(timer);
      pc.removeEventListener("icegatheringstatechange", onStateChange);
      resolve();
    };
    const onStateChange = () => {
      if (pc.iceGatheringState === "complete") {
        finish();
      }
    };
    const timer = window.setTimeout(finish, timeoutMs);
    pc.addEventListener("icegatheringstatechange", onStateChange);
  });
}

function controlModifiers(event: KeyboardEvent<HTMLElement>) {
  const modifiers: string[] = [];
  if (event.ctrlKey) {
    modifiers.push("Control");
  }
  if (event.altKey) {
    modifiers.push("Alt");
  }
  if (event.shiftKey) {
    modifiers.push("Shift");
  }
  if (event.metaKey) {
    modifiers.push("Meta");
  }
  return modifiers;
}

function isModifierKey(key: string) {
  return ["Control", "Alt", "Shift", "Meta"].includes(key);
}

function pointerButton(button: number) {
  if (button === 1) {
    return "middle";
  }
  if (button === 2) {
    return "right";
  }
  return "left";
}

async function textHash(text: string) {
  const bytes = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((item) => item.toString(16).padStart(2, "0"))
    .join("");
}

function browserClipboardAvailable() {
  return Boolean(
    window.isSecureContext &&
      navigator.clipboard &&
      typeof navigator.clipboard.readText === "function" &&
      typeof navigator.clipboard.writeText === "function" &&
      crypto.subtle,
  );
}

export function extractClipboardFiles(data: DataTransfer | null) {
  if (!data) {
    return [];
  }
  const files: File[] = [];
  for (const file of Array.from(data.files ?? [])) {
    files.push(file);
  }
  for (const item of Array.from(data.items ?? [])) {
    if (item.kind !== "file") {
      continue;
    }
    const file = item.getAsFile();
    if (!file) {
      continue;
    }
    const duplicate = files.some(
      (existing) => existing.name === file.name && existing.size === file.size && existing.lastModified === file.lastModified,
    );
    if (!duplicate) {
      files.push(file);
    }
  }
  return files;
}

export function RemoteAssistViewer({ sessionId, onClose, onEnded, canRequestElevated = false, onElevatedRequested }: RemoteAssistViewerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const controlChannelRef = useRef<RTCDataChannel | null>(null);
  const fileChannelRef = useRef<RTCDataChannel | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const lastMouseMoveRef = useRef(0);
  const pendingClickTimerRef = useRef<number | null>(null);
  const pointerDownRef = useRef<{
    button: string;
    xRatio: number;
    yRatio: number;
    clientX: number;
    clientY: number;
    dragging: boolean;
  } | null>(null);
  const clipboardPollRef = useRef<number | null>(null);
  const clipboardHashRef = useRef<string | null>(null);
  const clipboardApplyingRemoteRef = useRef(false);
  const pendingFilesRef = useRef<Map<string, { name: string; size: number }>>(new Map());
  const lastVideoFrameAtRef = useRef(0);
  const lastVideoTimeRef = useRef(0);
  const videoStalledRef = useRef(false);
  const [state, setState] = useState<ViewerState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState("view_only");
  const [mediaLabel, setMediaLabel] = useState("");
  const [scaleMode, setScaleMode] = useState<ScaleMode>("fit");
  const [videoSize, setVideoSize] = useState<{ width: number; height: number } | null>(null);
  const [controlEnabled, setControlEnabled] = useState(false);
  const [clipboardState, setClipboardState] = useState<ClipboardState>("off");
  const [clipboardError, setClipboardError] = useState<string | null>(null);
  const [fileTransferState, setFileTransferState] = useState<FileTransferState>("off");
  const [fileTransferMessage, setFileTransferMessage] = useState<string | null>(null);
  const [fileTransferMaxBytes, setFileTransferMaxBytes] = useState(0);
  const [sessionInfo, setSessionInfo] = useState<RemoteAssistViewerInfo | null>(null);
  const [elevating, setElevating] = useState(false);
  const [connectNonce, setConnectNonce] = useState(0);
  const [videoStalled, setVideoStalled] = useState(false);

  useEffect(() => {
    let disposed = false;
    let connectTimer: number | null = null;
    let videoWatchdogTimer: number | null = null;
    let videoFrameCallbackHandle: number | null = null;
    let videoFrameCallbackSupported = false;
    let terminalState = false;

    const clearConnectTimer = () => {
      if (connectTimer !== null) {
        window.clearTimeout(connectTimer);
        connectTimer = null;
      }
    };

    const closeTransport = () => {
      if (videoWatchdogTimer !== null) {
        window.clearInterval(videoWatchdogTimer);
        videoWatchdogTimer = null;
      }
      const currentVideo = videoRef.current as
        | (HTMLVideoElement & { cancelVideoFrameCallback?: (handle: number) => void })
        | null;
      if (videoFrameCallbackHandle !== null && currentVideo?.cancelVideoFrameCallback) {
        currentVideo.cancelVideoFrameCallback(videoFrameCallbackHandle);
        videoFrameCallbackHandle = null;
      }
      if (clipboardPollRef.current !== null) {
        window.clearInterval(clipboardPollRef.current);
        clipboardPollRef.current = null;
      }
      if (pendingClickTimerRef.current !== null) {
        window.clearTimeout(pendingClickTimerRef.current);
        pendingClickTimerRef.current = null;
      }
      pointerDownRef.current = null;
      wsRef.current?.close();
      pcRef.current?.close();
      wsRef.current = null;
      pcRef.current = null;
      controlChannelRef.current = null;
      fileChannelRef.current = null;
      pendingFilesRef.current.clear();
    };

    const failConnection = (message: string, errorCode = "WEBRTC_FAILED") => {
      if (disposed || terminalState) {
        return;
      }
      terminalState = true;
      clearConnectTimer();
      try {
        wsRef.current?.send(JSON.stringify({ type: "session.error", payload: { error_code: errorCode, error: message } }));
      } catch {
        // Best-effort notification; the HTTP fail endpoint below is authoritative for audit.
      }
      closeTransport();
      setState("failed");
      setError(message);
      void failRemoteAssistSession(sessionId, { errorCode, errorMessage: message }).catch(() => undefined);
    };

    const noteVideoFrame = () => {
      lastVideoFrameAtRef.current = window.performance.now();
      lastVideoTimeRef.current = videoRef.current?.currentTime ?? 0;
      if (videoStalledRef.current) {
        videoStalledRef.current = false;
        setVideoStalled(false);
        setError(null);
      }
    };

    const scheduleVideoFrameCallback = () => {
      const video = videoRef.current as
        | (HTMLVideoElement & { requestVideoFrameCallback?: (callback: () => void) => number })
        | null;
      if (!video?.requestVideoFrameCallback) {
        videoFrameCallbackSupported = false;
        return;
      }
      videoFrameCallbackSupported = true;
      videoFrameCallbackHandle = video.requestVideoFrameCallback(() => {
        videoFrameCallbackHandle = null;
        if (disposed || terminalState) {
          return;
        }
        noteVideoFrame();
        scheduleVideoFrameCallback();
      });
    };

    const startVideoWatchdog = () => {
      noteVideoFrame();
      scheduleVideoFrameCallback();
      if (videoWatchdogTimer !== null) {
        window.clearInterval(videoWatchdogTimer);
      }
      videoWatchdogTimer = window.setInterval(() => {
        const pc = pcRef.current;
        const video = videoRef.current;
        if (!pc || !video || pc.connectionState !== "connected" || terminalState || disposed) {
          return;
        }
        const currentTime = video.currentTime;
        if (!videoFrameCallbackSupported && currentTime > lastVideoTimeRef.current + 0.05) {
          lastVideoFrameAtRef.current = window.performance.now();
          lastVideoTimeRef.current = currentTime;
          return;
        }
        if (window.performance.now() - lastVideoFrameAtRef.current > 8000 && !videoStalledRef.current) {
          videoStalledRef.current = true;
          setVideoStalled(true);
          setError("Видео временно не обновляется. Сессия не завершена, можно переподключиться.");
          wsRef.current?.send(JSON.stringify({ type: "webrtc.connection_state", payload: { state: "video_stalled" } }));
        }
      }, 2000);
    };

    async function connect() {
      setState("loading");
      setError(null);
      videoStalledRef.current = false;
      setVideoStalled(false);
      try {
        const info = await fetchRemoteAssistViewer(sessionId);
        setSessionInfo(info);
        setMode(info.mode ?? "view_only");
        if (info.media) {
          const width = info.media.max_width ?? 0;
          const height = info.media.max_height ?? 0;
          const fps = info.media.fps ?? 0;
          setMediaLabel([width && height ? `${width}x${height}` : null, fps ? `${fps} fps` : null].filter(Boolean).join(" / "));
        }
        if (!info.token || !["approved", "starting", "active"].includes(info.status)) {
          setState(info.status === "ended" ? "ended" : "failed");
          setError("Сессия пока не готова к подключению.");
          return;
        }
        const pc = new RTCPeerConnection({ iceServers: info.ice_servers ?? [] });
        pcRef.current = pc;
        pc.addTransceiver("video", { direction: "recvonly" });
        const controlChannel = pc.createDataChannel("control", { ordered: true });
        controlChannelRef.current = controlChannel;
        if (info.features?.file_transfer) {
          const fileChannel = pc.createDataChannel("file-transfer", { ordered: true });
          fileChannelRef.current = fileChannel;
          setFileTransferState("off");
          setFileTransferMaxBytes(info.features.file_transfer_max_bytes ?? 25 * 1024 * 1024);
          fileChannel.onopen = () => {
            setFileTransferState("ready");
            setFileTransferMessage("Файлы можно перетащить в окно, выбрать кнопкой или вставить через Ctrl+V.");
          };
          fileChannel.onmessage = (event) => {
            handleFileChannelMessage(event.data);
          };
          fileChannel.onclose = () => {
            setFileTransferState("off");
          };
        } else {
          setFileTransferState("off");
          setFileTransferMaxBytes(0);
        }
        controlChannel.onopen = () => {
          if (["interactive_control", "elevated_admin"].includes(info.mode ?? "view_only")) {
            controlChannel.send(JSON.stringify({ type: "control_enable" }));
            setControlEnabled(true);
            wsRef.current?.send(JSON.stringify({ type: "control.state", payload: { enabled: true } }));
          }
          if (info.features?.clipboard_auto_sync) {
            startClipboardSync(controlChannel, info.features.clipboard_max_bytes ?? 256 * 1024);
          } else {
            setClipboardState("off");
          }
        };
        controlChannel.onmessage = (event) => {
          try {
            const message = JSON.parse(String(event.data || "{}"));
            if (message.type === "control.error") {
              setError(message.payload?.error ?? message.payload?.error_code ?? "Ошибка канала управления.");
              setControlEnabled(false);
              wsRef.current?.send(JSON.stringify({ type: "control.error", payload: message.payload ?? {} }));
            }
            if (message.type === "clipboard.ready") {
              setClipboardState("syncing");
              setClipboardError(null);
              wsRef.current?.send(JSON.stringify({ type: "clipboard.state", payload: { enabled: true } }));
            }
            if (message.type === "clipboard.update") {
              void applyRemoteClipboard(message.payload);
            }
            if (message.type === "clipboard.error") {
              setClipboardState("error");
              setClipboardError(message.payload?.error ?? message.payload?.error_code ?? "Ошибка синхронизации буфера обмена.");
              wsRef.current?.send(JSON.stringify({ type: "clipboard.error", payload: { error_code: message.payload?.error_code ?? "CLIPBOARD_FAILED" } }));
            }
          } catch {
            setError("Получено некорректное сообщение канала управления.");
          }
        };
        controlChannel.onclose = () => {
          setControlEnabled(false);
          setClipboardState("off");
        };
        pc.ontrack = (event) => {
          const [stream] = event.streams;
          if (videoRef.current && stream) {
            videoRef.current.srcObject = stream;
            noteVideoFrame();
            void videoRef.current.play().catch(() => undefined);
          }
        };
        pc.onicecandidate = (event) => {
          if (event.candidate && wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(
              JSON.stringify({
                type: "webrtc.ice_candidate",
                payload: event.candidate.toJSON(),
              }),
            );
          }
        };
        pc.onconnectionstatechange = () => {
          if (pc.connectionState === "connected") {
            clearConnectTimer();
            setState("active");
            startVideoWatchdog();
          }
          if (pc.connectionState === "failed") {
            failConnection("Не удалось установить WebRTC-соединение.", "WEBRTC_FAILED");
          }
          if (pc.connectionState === "closed" && !terminalState) {
            setState("ended");
          }
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(
              JSON.stringify({
                type: "webrtc.connection_state",
                payload: { state: pc.connectionState },
              }),
            );
          }
        };

        const ws = new WebSocket(buildSignalingUrl(info.signaling_url, info.token));
        wsRef.current = ws;
        ws.onopen = async () => {
          if (disposed) {
            return;
          }
          setState("connecting");
          ws.send(JSON.stringify({ type: "session.ready", payload: { role: "operator" } }));
          const offer = await pc.createOffer();
          await pc.setLocalDescription(offer);
          await waitForIceGatheringComplete(pc);
          ws.send(JSON.stringify({ type: "webrtc.offer", payload: pc.localDescription }));
          connectTimer = window.setTimeout(() => {
            if (!disposed && pc.connectionState !== "connected") {
              failConnection("Не удалось получить видео от агента.", "SIGNALING_TIMEOUT");
            }
          }, 25000);
        };
        ws.onmessage = async (event) => {
          const message = JSON.parse(String(event.data || "{}"));
          if (message.type === "webrtc.answer") {
            await pc.setRemoteDescription(message.payload);
          }
          if (message.type === "webrtc.ice_candidate" && message.payload?.candidate) {
            await pc.addIceCandidate(message.payload);
          }
          if (message.type === "session.end") {
            terminalState = true;
            clearConnectTimer();
            setState("ended");
            setControlEnabled(false);
            onEnded?.();
            onClose();
          }
          if (message.type === "session.error") {
            failConnection(message.payload?.error ?? message.payload?.error_code ?? "Ошибка signaling.", message.payload?.error_code);
          }
        };
        ws.onerror = () => {
          failConnection("Не удалось установить signaling-соединение.", "SIGNALING_TIMEOUT");
        };
      } catch (exc) {
        setState("failed");
        setError(exc instanceof Error ? exc.message : "Не удалось открыть viewer.");
      }
    }

    void connect();
    return () => {
      disposed = true;
      clearConnectTimer();
      closeTransport();
    };
  }, [sessionId, connectNonce]);

  const startClipboardSync = (channel: RTCDataChannel, maxBytes: number) => {
    if (!browserClipboardAvailable()) {
      setClipboardState("unavailable");
      setClipboardError("Браузер не разрешил доступ к буферу обмена. Для автосинхронизации нужен HTTPS/secure context и разрешение браузера.");
      wsRef.current?.send(JSON.stringify({ type: "clipboard.error", payload: { error_code: "BROWSER_CLIPBOARD_UNAVAILABLE" } }));
      return;
    }
    setClipboardState("syncing");
    setClipboardError(null);
    channel.send(JSON.stringify({ type: "clipboard_enable" }));
    if (clipboardPollRef.current !== null) {
      window.clearInterval(clipboardPollRef.current);
    }
    let busy = false;
    clipboardPollRef.current = window.setInterval(() => {
      if (busy || clipboardApplyingRemoteRef.current || channel.readyState !== "open") {
        return;
      }
      busy = true;
      void navigator.clipboard
        .readText()
        .then(async (text) => {
          if (new TextEncoder().encode(text).length > maxBytes) {
            return;
          }
          const digest = await textHash(text);
          if (digest === clipboardHashRef.current) {
            return;
          }
          clipboardHashRef.current = digest;
          channel.send(JSON.stringify({ type: "clipboard.update", payload: { text, hash: digest, origin: "operator" } }));
        })
        .catch((exc: unknown) => {
          setClipboardState("error");
          setClipboardError(exc instanceof Error ? exc.message : "Браузер отклонил доступ к буферу обмена.");
          wsRef.current?.send(JSON.stringify({ type: "clipboard.error", payload: { error_code: "BROWSER_CLIPBOARD_READ_FAILED" } }));
        })
        .finally(() => {
          busy = false;
        });
    }, 1000);
  };

  const applyRemoteClipboard = async (payload: unknown) => {
    if (!browserClipboardAvailable() || !payload || typeof payload !== "object") {
      return;
    }
    const data = payload as { text?: unknown; hash?: unknown };
    const text = String(data.text ?? "");
    const digest = String(data.hash || (await textHash(text)));
    if (digest === clipboardHashRef.current) {
      return;
    }
    clipboardApplyingRemoteRef.current = true;
    try {
      await navigator.clipboard.writeText(text);
      clipboardHashRef.current = digest;
      setClipboardState("syncing");
      setClipboardError(null);
    } catch (exc) {
      setClipboardState("error");
      setClipboardError(exc instanceof Error ? exc.message : "Браузер не разрешил запись в буфер обмена.");
      wsRef.current?.send(JSON.stringify({ type: "clipboard.error", payload: { error_code: "BROWSER_CLIPBOARD_WRITE_FAILED" } }));
    } finally {
      window.setTimeout(() => {
        clipboardApplyingRemoteRef.current = false;
      }, 500);
    }
  };

  const handleFileChannelMessage = (rawMessage: unknown) => {
    try {
      const message = JSON.parse(String(rawMessage || "{}"));
      const payload = message.payload ?? {};
      if (message.type === "file.progress") {
        const name = String(payload.name || pendingFilesRef.current.get(String(payload.transfer_id))?.name || "файл");
        const received = Number(payload.received || 0);
        const size = Number(payload.size || 0);
        const percent = size > 0 ? Math.min(100, Math.round((received / size) * 100)) : 0;
        setFileTransferState("transferring");
        setFileTransferMessage(`${name}: ${percent}%`);
      }
      if (message.type === "file.saved") {
        const transferId = String(payload.transfer_id || "");
        const pending = pendingFilesRef.current.get(transferId);
        pendingFilesRef.current.delete(transferId);
        const name = String(payload.name || pending?.name || "файл");
        const size = Number(payload.size || pending?.size || 0);
        setFileTransferState("done");
        setFileTransferMessage(`Файл передан: ${name}`);
        wsRef.current?.send(JSON.stringify({ type: "file.transfer", payload: { status: "completed", name, size } }));
      }
      if (message.type === "file.error") {
        setFileTransferState("error");
        setFileTransferMessage(payload.error ?? payload.error_code ?? "Ошибка передачи файла.");
        wsRef.current?.send(
          JSON.stringify({ type: "file.error", payload: { error_code: payload.error_code ?? "FILE_TRANSFER_FAILED" } }),
        );
      }
    } catch {
      setFileTransferState("error");
      setFileTransferMessage("Получено некорректное сообщение канала файлов.");
    }
  };

  const waitForFileBackpressure = (channel: RTCDataChannel) => {
    if (channel.bufferedAmount < 4 * 1024 * 1024) {
      return Promise.resolve();
    }
    channel.bufferedAmountLowThreshold = 512 * 1024;
    return new Promise<void>((resolve) => {
      const finish = () => {
        channel.removeEventListener("bufferedamountlow", finish);
        resolve();
      };
      channel.addEventListener("bufferedamountlow", finish, { once: true });
    });
  };

  const sendFileToAgent = async (file: File) => {
    const channel = fileChannelRef.current;
    if (!channel || channel.readyState !== "open") {
      setFileTransferState("error");
      setFileTransferMessage("Канал передачи файлов ещё не готов.");
      return;
    }
    if (fileTransferMaxBytes > 0 && file.size > fileTransferMaxBytes) {
      setFileTransferState("error");
      setFileTransferMessage(`Файл больше лимита сессии: ${file.name}`);
      wsRef.current?.send(JSON.stringify({ type: "file.error", payload: { error_code: "FILE_TOO_LARGE", name: file.name, size: file.size } }));
      return;
    }
    const transferId = crypto.randomUUID();
    pendingFilesRef.current.set(transferId, { name: file.name, size: file.size });
    setFileTransferState("transferring");
    setFileTransferMessage(`Передача файла: ${file.name}`);
    wsRef.current?.send(JSON.stringify({ type: "file.transfer", payload: { status: "started", name: file.name, size: file.size } }));
    const buffer = await file.arrayBuffer();
    const digestBytes = await crypto.subtle.digest("SHA-256", buffer);
    const sha256 = Array.from(new Uint8Array(digestBytes))
      .map((item) => item.toString(16).padStart(2, "0"))
      .join("");
    channel.send(JSON.stringify({ type: "file.offer", payload: { transfer_id: transferId, name: file.name, size: file.size, sha256 } }));
    const bytes = new Uint8Array(buffer);
    const chunkSize = 32 * 1024;
    for (let offset = 0, seq = 0; offset < bytes.length; offset += chunkSize, seq += 1) {
      const chunk = bytes.slice(offset, offset + chunkSize);
      let binary = "";
      for (const value of chunk) {
        binary += String.fromCharCode(value);
      }
      channel.send(JSON.stringify({ type: "file.chunk", payload: { transfer_id: transferId, seq, data: btoa(binary) } }));
      await waitForFileBackpressure(channel);
    }
    channel.send(JSON.stringify({ type: "file.complete", payload: { transfer_id: transferId } }));
  };

  const sendFilesToAgent = (files: FileList | File[]) => {
    const items = Array.from(files).filter((file) => file.size >= 0);
    if (!items.length) {
      return;
    }
    void items.reduce(
      (chain, file) =>
        chain.then(async () => {
          await sendFileToAgent(file);
        }),
      Promise.resolve(),
    );
  };

  const handleFileInput = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.currentTarget.files) {
      sendFilesToAgent(event.currentTarget.files);
      event.currentTarget.value = "";
    }
  };

  const handleDrop = (event: DragEvent<HTMLElement>) => {
    if (fileTransferState === "off") {
      return;
    }
    event.preventDefault();
    if (event.dataTransfer.files.length > 0) {
      sendFilesToAgent(event.dataTransfer.files);
    }
  };

  const handlePaste = (event: ClipboardEvent<HTMLElement>) => {
    const files = extractClipboardFiles(event.clipboardData);
    if (fileTransferState === "off" || files.length === 0) {
      return;
    }
    event.preventDefault();
    sendFilesToAgent(files);
  };

  useEffect(() => {
    const onPaste = (event: globalThis.ClipboardEvent) => {
      const files = extractClipboardFiles(event.clipboardData);
      if (fileTransferState === "off" || files.length === 0) {
        return;
      }
      event.preventDefault();
      sendFilesToAgent(files);
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  });

  const sendControl = (payload: Record<string, unknown>) => {
    const channel = controlChannelRef.current;
    if (!channel || channel.readyState !== "open") {
      setError("Канал управления ещё не готов.");
      return false;
    }
    channel.send(JSON.stringify(payload));
    return true;
  };

  const setControl = (enabled: boolean) => {
    if (!["interactive_control", "elevated_admin"].includes(mode)) {
      return;
    }
    if (sendControl({ type: enabled ? "control_enable" : "control_disable" })) {
      setControlEnabled(enabled);
      setError(null);
      wsRef.current?.send(JSON.stringify({ type: "control.state", payload: { enabled } }));
    }
  };

  const pointerPayload = (event: MouseEvent<HTMLElement>) => {
    const rect = videoRef.current?.getBoundingClientRect();
    if (!rect || rect.width <= 0 || rect.height <= 0) {
      return null;
    }
    return {
      x_ratio: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
      y_ratio: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)),
    };
  };

  const handleMouseMove = (event: MouseEvent<HTMLElement>) => {
    if (!controlEnabled) {
      return;
    }
    const pointerDown = pointerDownRef.current;
    if (pointerDown) {
      const payload = pointerPayload(event);
      if (!payload) {
        return;
      }
      if (!pointerDown.dragging) {
        const moved = Math.hypot(event.clientX - pointerDown.clientX, event.clientY - pointerDown.clientY);
        if (moved < 4) {
          return;
        }
        pointerDown.dragging = true;
        sendControl({
          type: "mouse_down",
          button: pointerDown.button,
          x_ratio: pointerDown.xRatio,
          y_ratio: pointerDown.yRatio,
        });
      }
      sendControl({ type: "mouse_move", ...payload });
      return;
    }
    const now = window.performance.now();
    if (now - lastMouseMoveRef.current < 33) {
      return;
    }
    lastMouseMoveRef.current = now;
    const payload = pointerPayload(event);
    if (payload) {
      sendControl({ type: "mouse_move", ...payload });
    }
  };

  const handleMouseButton = (event: MouseEvent<HTMLElement>, type: "mouse_down" | "mouse_up") => {
    event.currentTarget.focus();
    if (!controlEnabled) {
      return;
    }
    event.preventDefault();
    const payload = pointerPayload(event);
    if (!payload) {
      pointerDownRef.current = null;
      return;
    }
    if (type === "mouse_down") {
      pointerDownRef.current = {
        button: pointerButton(event.button),
        xRatio: payload.x_ratio,
        yRatio: payload.y_ratio,
        clientX: event.clientX,
        clientY: event.clientY,
        dragging: false,
      };
      return;
    }
    const pointerDown = pointerDownRef.current;
    pointerDownRef.current = null;
    if (pointerDown?.dragging) {
      sendControl({ type: "mouse_up", button: pointerDown.button, ...payload });
      return;
    }
    if (event.button !== 0) {
      sendControl({ type: "mouse_click", button: pointerButton(event.button), click_count: 1, ...payload });
    }
  };

  const handleClick = (event: MouseEvent<HTMLElement>) => {
    if (!controlEnabled || event.button !== 0) {
      return;
    }
    event.preventDefault();
    const payload = pointerPayload(event);
    if (!payload) {
      return;
    }
    if (pendingClickTimerRef.current !== null) {
      window.clearTimeout(pendingClickTimerRef.current);
      pendingClickTimerRef.current = null;
    }
    if (event.detail > 1) {
      return;
    }
    pendingClickTimerRef.current = window.setTimeout(() => {
      pendingClickTimerRef.current = null;
      sendControl({ type: "mouse_click", button: "left", click_count: 1, ...payload });
    }, 220);
  };

  const handleDoubleClick = (event: MouseEvent<HTMLElement>) => {
    if (!controlEnabled) {
      return;
    }
    event.preventDefault();
    if (pendingClickTimerRef.current !== null) {
      window.clearTimeout(pendingClickTimerRef.current);
      pendingClickTimerRef.current = null;
    }
    const payload = pointerPayload(event);
    if (payload) {
      sendControl({ type: "mouse_click", button: "left", click_count: 2, ...payload });
    }
  };

  const handleWheel = (event: WheelEvent<HTMLElement>) => {
    if (!controlEnabled) {
      return;
    }
    event.preventDefault();
    const payload = pointerPayload(event as unknown as MouseEvent<HTMLElement>);
    if (payload) {
      sendControl({
        type: "mouse_wheel",
        delta_x: Math.round(-event.deltaX),
        delta_y: Math.round(-event.deltaY),
        ...payload,
      });
    }
  };

  const handleKey = (event: KeyboardEvent<HTMLElement>, type: "key_down" | "key_up") => {
    if (!controlEnabled) {
      return;
    }
    if (fileTransferState !== "off" && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "v") {
      return;
    }
    event.preventDefault();
    const modifiers = controlModifiers(event);
    if (type === "key_down" && modifiers.length > 0 && !isModifierKey(event.key)) {
      sendControl({ type: "key_press", key: event.key, modifiers });
      return;
    }
    if (type === "key_up" && modifiers.length > 0 && !isModifierKey(event.key)) {
      return;
    }
    sendControl({ type, key: event.key });
  };

  const endSession = async () => {
    try {
      wsRef.current?.send(JSON.stringify({ type: "session.end", payload: { reason: "operator_finished" } }));
      await endRemoteAssistSession(sessionId);
      setState("ended");
      setControlEnabled(false);
      onEnded?.();
      onClose();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Не удалось завершить сессию.");
    }
  };

  const requestElevatedAccess = async () => {
    if (!sessionInfo || mode === "elevated_admin" || elevating) {
      return;
    }
    setElevating(true);
    setError(null);
    try {
      wsRef.current?.send(JSON.stringify({ type: "session.end", payload: { reason: "elevated_requested" } }));
      await endRemoteAssistSession(sessionId, "elevated_requested");
      const nextSession = await requestRemoteAssist(sessionInfo.ticket_id, {
        deviceId: sessionInfo.device_id,
        mode: "elevated_admin",
        reason: sessionInfo.reason?.trim() || "Elevated Remote Assist request",
        durationMinutes: Math.max(1, Math.ceil((sessionInfo.max_duration_sec || 900) / 60)),
        media: sessionInfo.media,
        features: {
          clipboard_auto_sync: Boolean(sessionInfo.features?.clipboard_auto_sync ?? true),
          file_transfer: Boolean(sessionInfo.features?.file_transfer ?? true),
        },
      });
      setState("ended");
      setControlEnabled(false);
      onElevatedRequested?.(nextSession.session_id);
      onEnded?.();
      onClose();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to request elevated Remote Assist.");
      setElevating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex bg-slate-950/90 text-slate-100 backdrop-blur-sm">
      <section className="flex min-h-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-white/10 px-4">
          <div>
            <p className="text-sm font-semibold">Удалённая помощь</p>
            <p className="text-xs text-slate-400">
              {state === "active" ? "Сессия активна" : state === "connecting" ? "Подключение..." : state === "ended" ? "Сессия завершена" : "Подготовка"}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {clipboardState !== "off" ? (
              <span
                className={`rounded-lg border px-3 py-2 text-xs font-semibold ${
                  clipboardState === "syncing"
                    ? "border-emerald-300/30 bg-emerald-400/10 text-emerald-100"
                    : "border-amber-300/30 bg-amber-400/10 text-amber-100"
                }`}
                title={clipboardError ?? undefined}
              >
                Буфер: {clipboardState === "syncing" ? "авто" : "недоступен"}
              </span>
            ) : null}
            {fileTransferState !== "off" ? (
              <>
                <input className="hidden" multiple onChange={handleFileInput} ref={fileInputRef} type="file" />
                <button
                  className={`rounded-lg border px-3 py-2 text-sm font-semibold ${
                    fileTransferState === "error"
                      ? "border-rose-300/40 bg-rose-400/10 text-rose-100"
                      : "border-white/10 text-slate-300 hover:text-white"
                  }`}
                  disabled={fileTransferState === "transferring"}
                  onClick={() => fileInputRef.current?.click()}
                  title={fileTransferMessage ?? "Передать файл на устройство"}
                  type="button"
                >
                  <Upload className="mr-2 inline h-4 w-4" />
                  {fileTransferState === "transferring" ? "Передача..." : "Файл"}
                </button>
              </>
            ) : null}
            {sessionInfo && mode !== "elevated_admin" ? (
              <button
                className="rounded-lg border border-amber-300/40 bg-amber-400/10 px-3 py-2 text-sm font-semibold text-amber-100 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={elevating || !canRequestElevated}
                onClick={() => void requestElevatedAccess()}
                title={canRequestElevated ? "Запросить отдельную elevated/admin сессию" : "У оператора нет права remote_assist.elevated"}
                type="button"
              >
                <ShieldCheck className="mr-2 inline h-4 w-4" />
                {elevating ? "Повышаем..." : "Повысить права"}
              </button>
            ) : null}
            {mode === "interactive_control" || mode === "elevated_admin" ? (
              <button
                className={`rounded-lg border px-3 py-2 text-sm font-semibold ${
                  controlEnabled ? "border-amber-300/40 bg-amber-400/15 text-amber-100" : "border-white/10 text-slate-300 hover:text-white"
                }`}
                onClick={() => setControl(!controlEnabled)}
                type="button"
              >
                <MousePointer2 className="mr-2 inline h-4 w-4" />
                {controlEnabled ? "Управление включено" : "Включить управление"}
              </button>
            ) : null}
            <button
              className="rounded-lg border border-white/10 px-3 py-2 text-sm font-semibold text-slate-300 hover:text-white"
              onClick={() => setScaleMode((value) => (value === "fit" ? "actual" : "fit"))}
              title={scaleMode === "fit" ? "Показать в реальном размере" : "Вписать в окно"}
              type="button"
            >
              <Scaling className="mr-2 inline h-4 w-4" />
              {scaleMode === "fit" ? "Вписать" : "1:1"}
            </button>
            <button
              className="rounded-lg border border-white/10 p-2 text-slate-300 hover:text-white"
              onClick={() => {
                setControlEnabled(false);
                setConnectNonce((value) => value + 1);
              }}
              title="Переподключиться"
              type="button"
            >
              <RotateCcw className="h-4 w-4" />
            </button>
            <button
              className="rounded-lg border border-white/10 p-2 text-slate-300 hover:text-white"
              onClick={() => videoRef.current?.requestFullscreen()}
              title="На весь экран"
              type="button"
            >
              <Maximize2 className="h-4 w-4" />
            </button>
            <button
              className="rounded-lg border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-sm font-semibold text-rose-100"
              onClick={() => void endSession()}
              type="button"
            >
              Завершить
            </button>
            <button className="rounded-lg border border-white/10 p-2 text-slate-300 hover:text-white" onClick={onClose} type="button">
              <X className="h-4 w-4" />
            </button>
          </div>
        </header>
        <div
          className="flex min-h-0 flex-1 items-center justify-center bg-black outline-none"
          onContextMenu={(event) => event.preventDefault()}
          onClick={handleClick}
          onDoubleClick={handleDoubleClick}
          onDragOver={(event) => {
            if (fileTransferState !== "off") {
              event.preventDefault();
            }
          }}
          onDrop={handleDrop}
          onKeyDown={(event) => handleKey(event, "key_down")}
          onKeyUp={(event) => handleKey(event, "key_up")}
          onMouseDown={(event) => handleMouseButton(event, "mouse_down")}
          onMouseMove={handleMouseMove}
          onMouseUp={(event) => handleMouseButton(event, "mouse_up")}
          onPaste={handlePaste}
          onWheel={handleWheel}
          style={scaleMode === "actual" ? { overflow: "auto" } : undefined}
          tabIndex={mode === "interactive_control" || mode === "elevated_admin" || fileTransferState !== "off" ? 0 : -1}
        >
          <video
            ref={videoRef}
            autoPlay
            className={scaleMode === "fit" ? "max-h-full max-w-full" : "h-auto max-h-none max-w-none"}
            onLoadedMetadata={(event) => {
              const video = event.currentTarget;
              setVideoSize({ width: video.videoWidth, height: video.videoHeight });
            }}
            playsInline
            style={scaleMode === "actual" && videoSize ? { width: videoSize.width, height: videoSize.height } : undefined}
          />
          {state === "active" && mediaLabel ? (
            <div className="absolute bottom-4 left-4 rounded-lg border border-white/10 bg-slate-950/75 px-3 py-2 text-xs text-slate-300">
              {mediaLabel}
            </div>
          ) : null}
          {state === "active" && fileTransferMessage ? (
            <div className="absolute bottom-4 right-4 rounded-lg border border-white/10 bg-slate-950/75 px-3 py-2 text-xs text-slate-300">
              {fileTransferMessage}
            </div>
          ) : null}
          {state === "active" && videoStalled ? (
            <div className="absolute top-20 rounded-xl border border-amber-300/30 bg-amber-500/10 px-4 py-3 text-center text-sm font-semibold text-amber-100">
              Видео временно не обновляется. Управление и буфер не отключены, попробуйте переподключиться.
            </div>
          ) : null}
          {state !== "active" ? (
            <div className="absolute flex flex-col items-center gap-3 rounded-xl border border-white/10 bg-slate-950/75 px-5 py-4 text-center">
              {state === "failed" ? <MonitorX className="h-8 w-8 text-rose-200" /> : <RotateCcw className="h-8 w-8 animate-spin text-blue-200" />}
              <p className="text-sm font-semibold">{error ?? (state === "ended" ? "Сессия завершена" : "Ожидаем видео с устройства...")}</p>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
