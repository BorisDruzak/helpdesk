import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import {
  type SupportTicketDetailPayload,
} from "../../../features/queues/api";
export function TicketRequestFormCard({
  requestForm,
}: {
  requestForm: SupportTicketDetailPayload["request_form"];
}) {
  if (!requestForm) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Данные формы</CardTitle>
        <CardDescription>{requestForm.form_title ?? requestForm.form_key ?? "структурированный ввод"}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-[1rem] bg-surface-subtle px-4 py-3">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">request_kind</p>
            <p className="mt-2 font-semibold text-slate-950">{requestForm.request_kind ?? "не указан"}</p>
          </div>
          <div className="rounded-[1rem] bg-surface-subtle px-4 py-3">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Форма</p>
            <p className="mt-2 font-semibold text-slate-950">{requestForm.form_key ?? "не указана"}</p>
          </div>
        </div>

        {requestForm.rows.length > 0 ? (
          <dl className="space-y-3">
            {requestForm.rows.map((row) => (
              <div
                className="flex items-start justify-between gap-3 rounded-[1rem] border border-slate-200/80 px-4 py-3"
                key={`${row.key}-${row.label}`}
              >
                <dt className="text-slate-500">{row.label}</dt>
                <dd className="max-w-[60%] text-right font-medium text-slate-900">{row.value}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="text-slate-500">Структурированные ответы пока не заполнены.</p>
        )}
      </CardContent>
    </Card>
  );
}