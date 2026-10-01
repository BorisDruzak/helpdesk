import {
  Button,
} from "../../../components/ui/button";
import {
  cn,
} from "../../../shared/ui/cn";
import {
  formatDateTime,
} from '../detail-formatting';
import {
  useTicketDetailController,
} from "../hooks/use-ticket-detail-controller";
export function TicketDialogTabComposer({ controller }: { controller: ReturnType<typeof useTicketDetailController> }) {
  const { activeTab, messageMode, setMessageMode, messageDraft, setMessageDraft, sendMessageMutation, publicCommentAccess, messageAccess, canSendInternal, latestTimelineEntry } = controller;
  return (activeTab === "dialog" ? (
    <div className="border-t border-border bg-white px-6 py-5">
      <div className="space-y-4">
        <div className="flex gap-6 border-b border-border pb-3">
          <button
            className={cn(
              "text-sm font-semibold",
              messageMode === "public" ? "text-brand-700" : "text-slate-500",
            )}
            disabled={!publicCommentAccess.allowed}
            onClick={() => setMessageMode("public")}
            type="button"
          >
            Ответить
          </button>
          {canSendInternal ? (
            <button
              className={cn(
                "text-sm font-semibold",
                messageMode === "internal" ? "text-brand-700" : "text-slate-500",
              )}
              onClick={() => setMessageMode("internal")}
              type="button"
            >
              Внутренний комментарий
            </button>
          ) : null}
        </div>

        <textarea
          aria-label="Ответ оператору"
          className="field-base min-h-[140px] w-full resize-none px-4 py-4 text-sm text-slate-800"
          onChange={(event) => setMessageDraft(event.target.value)}
          placeholder={
            messageMode === "public"
              ? "Напишите сообщение пользователю..."
              : "Добавьте внутренний комментарий для команды..."
          }
          disabled={!messageAccess.allowed}
          value={messageDraft}
        />

        {!messageAccess.allowed ? (
          <p className="rounded-[0.8rem] border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            {messageAccess.reason}
          </p>
        ) : null}

        {sendMessageMutation.isError ? (
          <p className="text-sm text-rose-700">
            {sendMessageMutation.error instanceof Error
              ? sendMessageMutation.error.message
              : "Не удалось отправить сообщение."}
          </p>
        ) : null}

        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-slate-500">
            Последнее событие: {formatDateTime(latestTimelineEntry?.ts)}
          </p>
          <Button
            disabled={!messageAccess.allowed || !messageDraft.trim() || sendMessageMutation.isPending}
            onClick={() => {
              void sendMessageMutation.mutateAsync();
            }}
          >
            {sendMessageMutation.isPending ? "Отправляем..." : "Отправить"}
          </Button>
        </div>
      </div>
    </div>
  ) : null);
}