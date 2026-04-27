import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, Send } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import {
  authorizePublicTicket,
  closePublicTicket,
  fetchPublicTicket,
  sendPublicTicketMessage,
} from "../../features/requester/api";
import type { PublicTicketMessage } from "../../features/requester/types";

function tokenStorageKey(ticketId: string): string {
  return `public_ticket_token:${ticketId}`;
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "";
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

function messageAuthor(message: PublicTicketMessage): string {
  const role = message.from_role ?? message.sender_role ?? "user";
  if (role === "support" || role === "agent" || role === "admin") {
    return "Поддержка";
  }
  return "Вы";
}

export function RequesterTicketPage() {
  const params = useParams();
  const [searchParams] = useSearchParams();
  const ticketId = params.ticketId ?? searchParams.get("ticket_id") ?? "";
  const codeFromUrl = searchParams.get("code") ?? "";
  const [token, setToken] = useState(() => (ticketId ? sessionStorage.getItem(tokenStorageKey(ticketId)) ?? "" : ""));
  const [code, setCode] = useState(codeFromUrl);
  const [message, setMessage] = useState("");
  const [feedback, setFeedback] = useState<{ tone: "error" | "success"; text: string } | null>(null);

  useEffect(() => {
    if (ticketId) {
      setToken(sessionStorage.getItem(tokenStorageKey(ticketId)) ?? "");
    }
  }, [ticketId]);

  const authorizeMutation = useMutation({
    mutationFn: (accessCode: string) => authorizePublicTicket(ticketId, accessCode),
    onSuccess: (result) => {
      sessionStorage.setItem(tokenStorageKey(ticketId), result.public_token);
      setToken(result.public_token);
      setFeedback({ tone: "success", text: "Доступ к тикету открыт." });
    },
    onError: (error) => {
      setFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось проверить код доступа.",
      });
    },
  });

  useEffect(() => {
    if (ticketId && codeFromUrl && !token && !authorizeMutation.isPending) {
      authorizeMutation.mutate(codeFromUrl);
    }
  }, [authorizeMutation, codeFromUrl, ticketId, token]);

  const ticketQuery = useQuery({
    queryKey: ["requester-ticket", ticketId, token],
    queryFn: () => fetchPublicTicket(ticketId, token),
    enabled: Boolean(ticketId && token),
    retry: false,
  });

  const sendMutation = useMutation({
    mutationFn: () => sendPublicTicketMessage(ticketId, token, message.trim()),
    onSuccess: async () => {
      setMessage("");
      setFeedback({ tone: "success", text: "Сообщение отправлено." });
      await ticketQuery.refetch();
    },
    onError: (error) => {
      setFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось отправить сообщение.",
      });
    },
  });

  const closeMutation = useMutation({
    mutationFn: () => closePublicTicket(ticketId, token),
    onSuccess: async () => {
      setFeedback({ tone: "success", text: "Решение подтверждено." });
      await ticketQuery.refetch();
    },
    onError: (error) => {
      setFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось подтвердить решение.",
      });
    },
  });

  const ticket = ticketQuery.data?.ticket;
  const messages = useMemo(() => ticketQuery.data?.messages ?? [], [ticketQuery.data?.messages]);

  if (!ticketId) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-app px-4">
        <Card className="max-w-lg">
          <CardHeader>
            <CardTitle>Тикет не выбран</CardTitle>
            <CardDescription>Откройте ссылку из заявки или создайте новое обращение.</CardDescription>
          </CardHeader>
          <CardContent>
            <Link
              className="inline-flex h-11 items-center justify-center rounded-pill bg-brand-600 px-4 text-sm font-semibold text-white"
              to="/app/help"
            >
              Создать заявку
            </Link>
          </CardContent>
        </Card>
      </main>
    );
  }

  if (!token) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-app px-4 py-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Вход в тикет</CardTitle>
            <CardDescription>Введите код доступа, который был показан после создания заявки.</CardDescription>
          </CardHeader>
          <CardContent>
            <form
              className="grid gap-4"
              onSubmit={(event) => {
                event.preventDefault();
                if (!code.trim()) {
                  setFeedback({ tone: "error", text: "Введите код доступа." });
                  return;
                }
                authorizeMutation.mutate(code.trim());
              }}
            >
              <label className="grid gap-2 text-sm font-medium text-slate-700">
                <span>Код доступа</span>
                <Input onChange={(event) => setCode(event.currentTarget.value)} value={code} />
              </label>
              {feedback ? (
                <div className="rounded-[1rem] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                  {feedback.text}
                </div>
              ) : null}
              <Button disabled={authorizeMutation.isPending} type="submit">
                Открыть тикет
              </Button>
            </form>
          </CardContent>
        </Card>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-app px-4 py-6 md:px-8">
      <section className="mx-auto grid max-w-6xl gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Card className="overflow-hidden">
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle>{ticket?.ticket_code || ticket?.ticket_id || ticketId}</CardTitle>
                <CardDescription>{ticket?.title || "Чат по заявке"}</CardDescription>
              </div>
              <Badge tone={ticket?.status === "resolved" ? "success" : "neutral"} withDot>
                {ticket?.status ?? "загрузка"}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {ticketQuery.isLoading ? (
              <div className="rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                Загружаем тикет...
              </div>
            ) : null}

            {ticketQuery.isError ? (
              <div className="rounded-[1rem] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                {ticketQuery.error instanceof Error ? ticketQuery.error.message : "Не удалось загрузить тикет."}
              </div>
            ) : null}

            <div className="max-h-[58vh] space-y-3 overflow-y-auto pr-2">
              {messages.length ? (
                messages.map((item, index) => (
                  <article key={item.message_id ?? item.event_id ?? index} className="rounded-[1rem] border border-border bg-white px-4 py-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-semibold text-slate-950">{messageAuthor(item)}</p>
                      <p className="text-xs text-slate-400">{formatDateTime(item.ts ?? item.created_at)}</p>
                    </div>
                    <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-700">{item.text}</p>
                  </article>
                ))
              ) : (
                <div className="rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-sm text-slate-500">
                  Сообщений пока нет.
                </div>
              )}
            </div>

            <form
              className="grid gap-3"
              onSubmit={(event) => {
                event.preventDefault();
                if (!message.trim()) {
                  return;
                }
                sendMutation.mutate();
              }}
            >
              <label className="grid gap-2 text-sm font-medium text-slate-700">
                <span>Сообщение в поддержку</span>
                <textarea
                  className="field-base min-h-24 px-4 py-3 text-sm text-slate-900 placeholder:text-slate-400"
                  onChange={(event) => setMessage(event.currentTarget.value)}
                  value={message}
                />
              </label>
              {feedback ? (
                <div
                  className={
                    feedback.tone === "error"
                      ? "rounded-[1rem] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
                      : "rounded-[1rem] border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700"
                  }
                >
                  {feedback.text}
                </div>
              ) : null}
              <Button disabled={sendMutation.isPending} leadingIcon={<Send className="h-4 w-4" />} type="submit">
                Отправить
              </Button>
            </form>
          </CardContent>
        </Card>

        <aside className="grid content-start gap-5">
          <Card>
            <CardHeader>
              <CardTitle>Статус обращения</CardTitle>
              <CardDescription>Здесь виден текущий этап обработки заявки.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-slate-600">
              <p>Тикет: {ticket?.ticket_code || ticketId}</p>
              <p>Статус: {ticket?.status ?? "загрузка"}</p>
              {ticket?.status === "resolved" ? (
                <Button
                  disabled={closeMutation.isPending}
                  leadingIcon={<CheckCircle2 className="h-4 w-4" />}
                  onClick={() => closeMutation.mutate()}
                  variant="outline"
                >
                  Подтвердить решение
                </Button>
              ) : null}
              <Link className="text-sm font-semibold text-brand-700 hover:text-brand-900" to="/app/help">
                Создать новую заявку
              </Link>
            </CardContent>
          </Card>
        </aside>
      </section>
    </main>
  );
}
