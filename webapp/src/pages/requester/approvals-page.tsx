import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeading } from "../../components/ui/page-heading";
import { Button, InlineAlert, Textarea } from "../../features/requester/ui/form-controls";
import { decideAssignedApproval, fetchAssignedApprovals, RequesterApiError, type AssignedApproval } from "../../features/requester/api";

const queryKey = ["requester-assigned-approvals"];

export function RequesterApprovalsPage() {
  const client = useQueryClient();
  const query = useQuery({ queryKey, queryFn: fetchAssignedApprovals, retry: false });
  const [notice, setNotice] = useState("");
  return <div className="mx-auto max-w-4xl space-y-4">
    <PageHeading eyebrow="Кабинет пользователя" title="Ожидают моего решения" description="Здесь только обращения, согласование которых назначено вам." actions={<Button variant="outline" onClick={() => void query.refetch()}>Обновить</Button>} />
    {query.isPending ? <p role="status">Загружаем назначенные согласования…</p> : null}
    {query.isError ? <InlineAlert role="alert" tone="danger">{query.error instanceof RequesterApiError && query.error.status === 403 ? "Право согласования не предоставлено или профиль недоступен. Обратитесь к администратору." : "Не удалось загрузить согласования. Повторите попытку."}</InlineAlert> : null}
    {notice ? <InlineAlert role="status" tone="success">{notice}</InlineAlert> : null}
    {!query.isPending && !query.isError && !query.data?.items.length ? <p className="surface-panel p-5">Нет обращений, ожидающих вашего решения</p> : null}
    {query.data?.items.map(approval => <AssignedApprovalCard key={approval.approval_id} approval={approval} onDecided={async () => {
      setNotice("Решение сохранено"); await client.invalidateQueries({ queryKey });
    }} />)}
    {query.data?.items.length === 100 ? <p className="text-sm text-slate-500">Показаны первые 100 назначений. После решения список обновится.</p> : null}
  </div>;
}

function AssignedApprovalCard({ approval, onDecided }: { approval: AssignedApproval; onDecided: () => Promise<void> }) {
  const [comment, setComment] = useState("");
  const mutation = useMutation({ mutationFn: (decision: "approved" | "rejected") => decideAssignedApproval(approval, decision, comment.trim()), onSuccess: onDecided });
  return <section className="surface-panel space-y-3 p-5" aria-label={approval.title}>
    <div><p className="text-xs text-slate-500">{approval.ticket_code || "Назначенное обращение"}</p><h2 className="text-lg font-semibold">{approval.title}</h2></div>
    <p className="whitespace-pre-wrap break-words text-sm text-slate-700">{approval.description}</p>
    {!approval.can_decide ? <p className="text-sm text-amber-800">Ожидается решение предыдущего согласующего.</p> : <>
      <label className="block text-sm font-medium">Комментарий к решению<Textarea maxLength={2000} className="mt-1" value={comment} onChange={event => setComment(event.target.value)} /></label>
      {approval.reject_requires_comment ? <p className="text-xs text-slate-500">При отклонении нужен комментарий.</p> : null}
      <div className="flex flex-wrap gap-2">
        <Button disabled={mutation.isPending} onClick={() => mutation.mutate("approved")}>Согласовать</Button>
        <Button variant="outline" disabled={mutation.isPending || approval.reject_requires_comment && !comment.trim()} onClick={() => mutation.mutate("rejected")}>Отклонить</Button>
      </div>
    </>}
    {mutation.isError ? <InlineAlert role="alert" tone="danger">{mutation.error instanceof RequesterApiError && mutation.error.status === 409 ? "Согласование уже изменилось. Обновите список перед решением." : "Не удалось сохранить решение. Обновите список и проверьте назначение."}</InlineAlert> : null}
  </section>;
}
