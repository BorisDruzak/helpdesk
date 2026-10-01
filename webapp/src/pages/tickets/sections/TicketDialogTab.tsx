import {
  Avatar,
} from "../../../components/ui/avatar";
import {
  Badge,
} from "../../../components/ui/badge";
import {
  cn,
} from "../../../shared/ui/cn";
import {
  formatDateTime,
  getRoleTone,
  getRoleLabel,
  getRoleBadgeTone,
  normalizeAttachment,
} from '../detail-formatting';
import {
  ArtifactPreview,
} from './ArtifactPreview';
import {
  useTicketDetailController,
} from "../hooks/use-ticket-detail-controller";
export function TicketDialogTab({ controller }: { controller: ReturnType<typeof useTicketDetailController> }) {
  if (!controller.ticketId) return null;
  const { ticketId, activeTab, detail, attachments } = controller;
  return (detail && activeTab === "dialog" ? (
    <div className="space-y-4">
      {detail.timeline.map((entry, entryIndex) => {
        const entryAttachments = entry.attachments.map((attachment, attachmentIndex) =>
          normalizeAttachment(
            attachment,
            ticketId,
            `${entry.event_id ?? entry.message_id ?? entryIndex}-${attachmentIndex}`,
            entry.sender_display_name ?? getRoleLabel(entry),
            entry.ts,
          ),
        );

        return (
          <div
            key={`${entry.event_id ?? entry.message_id ?? entry.ts ?? entryIndex}`}
            className={cn(
              "rounded-[1.3rem] border px-5 py-5 shadow-soft",
              entry.from_role === "support" || entry.from_role === "agent"
                ? "border-blue-100 bg-blue-50/60"
                : entry.visibility === "internal"
                  ? "border-amber-100 bg-amber-50/70"
                  : "border-border bg-white",
            )}
          >
            <div className="flex items-start gap-4">
              <Avatar name={entry.sender_display_name ?? getRoleLabel(entry)} tone={getRoleTone(entry)} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-semibold text-slate-950">
                    {entry.sender_display_name ?? getRoleLabel(entry)}
                  </p>
                  <span className="text-sm text-slate-400">{formatDateTime(entry.ts)}</span>
                  <Badge className="ml-auto" tone={getRoleBadgeTone(entry)}>
                    {getRoleLabel(entry)}
                  </Badge>
                </div>

                {entry.reply_to?.preview ? (
                  <div className="mt-3 rounded-panel border border-border bg-white/70 px-4 py-3 text-sm text-slate-500">
                    <p className="font-medium text-slate-700">
                      {entry.reply_to.sender_display_name ?? entry.reply_to.sender_role ?? "Сообщение"}
                    </p>
                    <p className="mt-1 line-clamp-2">{entry.reply_to.preview}</p>
                  </div>
                ) : null}

                <p className="mt-3 whitespace-pre-line text-[15px] leading-7 text-slate-700">
                  {entry.text}
                </p>

                {entry.result_summary ? (
                  <div className="mt-3 rounded-panel border border-border bg-white/80 px-4 py-3 text-sm text-slate-600">
                    <p className="font-medium text-slate-800">Результат</p>
                    <p className="mt-1">{entry.result_summary}</p>
                    {entry.result_preview ? (
                      <pre className="mt-3 overflow-x-auto rounded-panel bg-slate-950 px-4 py-3 text-xs text-slate-100">
                        {entry.result_preview}
                      </pre>
                    ) : null}
                  </div>
                ) : null}

                {entryAttachments.length ? (
                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    {entryAttachments.map((attachment) => (
                      <ArtifactPreview key={attachment.id} attachment={attachment} />
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  ) : null);
}