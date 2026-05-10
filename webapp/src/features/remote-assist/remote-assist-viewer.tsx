import { Maximize2, MonitorX, MousePointer2, RotateCcw, X } from "lucide-react";
import type { KeyboardEvent, MouseEvent } from "react";
import { useEffect, useRef, useState } from "react";

import { endRemoteAssistSession, fetchRemoteAssistViewer } from "./api";

type ViewerState = "loading" | "connecting" | "active" | "ended" | "failed";

type RemoteAssistViewerProps = {
  sessionId: string;
  onClose: () => void;
  onEnded?: () => void;
};

function buildSignalingUrl(baseUrl: string, token: string) {
  const url = new URL(baseUrl, window.location.href);
  url.searchParams.set("role", "operator");
  url.searchParams.set("token", token);
  return url.toString();
}

export function RemoteAssistViewer({ sessionId, onClose, onEnded }: RemoteAssistViewerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const controlChannelRef = useRef<RTCDataChannel | null>(null);
  const lastMouseMoveRef = useRef(0);
  const [state, setState] = useState<ViewerState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState("view_only");
  const [controlEnabled, setControlEnabled] = useState(false);
  const [connectNonce, setConnectNonce] = useState(0);

  useEffect(() => {
    let disposed = false;
    let connectTimer: number | null = null;

    async function connect() {
      setState("loading");
      setError(null);
      try {
        const info = await fetchRemoteAssistViewer(sessionId);
        if (!info.token || !["approved", "starting", "active"].includes(info.status)) {
          setState(info.status === "ended" ? "ended" : "failed");
          setError("Сессия пока не готова к подключению.");
          return;
        }
        setMode(info.mode ?? "view_only");
        const pc = new RTCPeerConnection({ iceServers: info.ice_servers ?? [] });
        pcRef.current = pc;
        const controlChannel = pc.createDataChannel("control", { ordered: true });
        controlChannelRef.current = controlChannel;
        controlChannel.onmessage = (event) => {
          try {
            const message = JSON.parse(String(event.data || "{}"));
            if (message.type === "control.error") {
              setError(message.payload?.error ?? message.payload?.error_code ?? "Ошибка канала управления.");
              setControlEnabled(false);
              wsRef.current?.send(JSON.stringify({ type: "control.error", payload: message.payload ?? {} }));
            }
          } catch {
            setError("Получено некорректное сообщение канала управления.");
          }
        };
        controlChannel.onclose = () => setControlEnabled(false);
        pc.ontrack = (event) => {
          const [stream] = event.streams;
          if (videoRef.current && stream) {
            videoRef.current.srcObject = stream;
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
            setState("active");
          }
          if (["failed", "closed", "disconnected"].includes(pc.connectionState)) {
            setState(pc.connectionState === "closed" ? "ended" : "failed");
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
          const offer = await pc.createOffer({ offerToReceiveVideo: true, offerToReceiveAudio: false });
          await pc.setLocalDescription(offer);
          ws.send(JSON.stringify({ type: "webrtc.offer", payload: pc.localDescription }));
          connectTimer = window.setTimeout(() => {
            void fetchRemoteAssistViewer(sessionId)
              .then((latest) => {
                if (disposed || pc.connectionState === "connected") {
                  return;
                }
                setState(latest.status === "failed" ? "failed" : latest.status === "ended" ? "ended" : "failed");
                setError(latest.error_message || latest.error_code || "Не удалось получить видео от агента.");
              })
              .catch(() => {
                if (!disposed && pc.connectionState !== "connected") {
                  setState("failed");
                  setError("Не удалось получить видео от агента.");
                }
              });
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
            setState("ended");
            setControlEnabled(false);
            onEnded?.();
            onClose();
          }
          if (message.type === "session.error") {
            setState("failed");
            setError(message.payload?.error_code ?? "Ошибка signaling.");
          }
        };
        ws.onerror = () => {
          setState("failed");
          setError("Не удалось установить signaling-соединение.");
        };
      } catch (exc) {
        setState("failed");
        setError(exc instanceof Error ? exc.message : "Не удалось открыть viewer.");
      }
    }

    void connect();
    return () => {
      disposed = true;
      wsRef.current?.close();
      pcRef.current?.close();
      if (connectTimer !== null) {
        window.clearTimeout(connectTimer);
      }
      wsRef.current = null;
      pcRef.current = null;
      controlChannelRef.current = null;
    };
  }, [sessionId, connectNonce]);

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
    if (mode !== "interactive_control") {
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

  const handleMouseClick = (event: MouseEvent<HTMLElement>) => {
    if (!controlEnabled) {
      return;
    }
    const payload = pointerPayload(event);
    if (payload) {
      sendControl({ type: "mouse_click", button: "left", ...payload });
    }
  };

  const handleKey = (event: KeyboardEvent<HTMLElement>, type: "key_down" | "key_up") => {
    if (!controlEnabled) {
      return;
    }
    event.preventDefault();
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
            {mode === "interactive_control" ? (
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
          onClick={handleMouseClick}
          onKeyDown={(event) => handleKey(event, "key_down")}
          onKeyUp={(event) => handleKey(event, "key_up")}
          onMouseMove={handleMouseMove}
          tabIndex={mode === "interactive_control" ? 0 : -1}
        >
          <video ref={videoRef} autoPlay className="max-h-full max-w-full" playsInline />
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
