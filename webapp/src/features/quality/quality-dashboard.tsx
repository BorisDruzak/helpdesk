import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCcw } from "lucide-react";
import { useState } from "react";

import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import {
  closeImprovementAction,
  completeQualityReview,
  createImprovementAction,
  fetchImprovementActions,
  fetchQualityPolicy,
  fetchQualityReviews,
  fetchQualitySummary,
  fetchServiceQuality,
} from "./api";

function metric(value: number | null | undefined, suffix = "") {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return `${value}${suffix}`;
}

export function QualityDashboard() {
  const queryClient = useQueryClient();
  const [actionTitle, setActionTitle] = useState("");
  const [actionOwner, setActionOwner] = useState("");
  const summaryQuery = useQuery({ queryKey: ["quality", "summary"], queryFn: fetchQualitySummary });
  const serviceQualityQuery = useQuery({ queryKey: ["quality", "service-quality"], queryFn: fetchServiceQuality });
  const reviewsQuery = useQuery({ queryKey: ["quality", "reviews"], queryFn: () => fetchQualityReviews() });
  const actionsQuery = useQuery({ queryKey: ["quality", "actions"], queryFn: () => fetchImprovementActions() });
  const policyQuery = useQuery({ queryKey: ["quality", "policy"], queryFn: fetchQualityPolicy });

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["quality", "summary"] }),
      queryClient.invalidateQueries({ queryKey: ["quality", "service-quality"] }),
      queryClient.invalidateQueries({ queryKey: ["quality", "reviews"] }),
      queryClient.invalidateQueries({ queryKey: ["quality", "actions"] }),
    ]);
  };

  const createActionMutation = useMutation({
    mutationFn: () =>
      createImprovementAction({
        source_kind: "manual",
        action_type: "process_review",
        title: actionTitle.trim(),
        description: actionTitle.trim(),
        priority: "medium",
        owner_actor_id: actionOwner.trim() || null,
      }),
    onSuccess: async () => {
      setActionTitle("");
      setActionOwner("");
      await invalidate();
    },
  });

  const completeReviewMutation = useMutation({
    mutationFn: (reviewId: string) => completeQualityReview(reviewId, 85),
    onSuccess: invalidate,
  });

  const closeActionMutation = useMutation({
    mutationFn: (actionId: string) => closeImprovementAction(actionId, "Closed from quality dashboard."),
    onSuccess: invalidate,
  });

  const summary = summaryQuery.data;
  const policy = policyQuery.data;

  return (
    <section className="workspace-page grid gap-5">
      <div className="workspace-page__header">
        <div>
          <p className="workspace-boot__eyebrow">Experience quality</p>
          <h1>Quality loop</h1>
          <p>CSAT, reopen reasons, QA reviews, service quality and continuous improvement actions.</p>
        </div>
        <Button leadingIcon={<RefreshCcw className="h-4 w-4" />} onClick={() => void invalidate()} type="button" variant="outline">
          Refresh
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader>
            <CardDescription>Avg CSAT</CardDescription>
            <CardTitle>{metric(summary?.avg_csat)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Feedback</CardDescription>
            <CardTitle>{metric(summary?.feedback_count)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Reopens</CardDescription>
            <CardTitle>{metric(summary?.reopen_count)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Open actions</CardDescription>
            <CardTitle>{metric(summary?.improvement_action_count)}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Service and offering quality</CardTitle>
          <CardDescription>Aggregated metrics only; requester identifiers and feedback comments are not shown here.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">Service</th>
                  <th className="px-3 py-2">Offering</th>
                  <th className="px-3 py-2">Tickets</th>
                  <th className="px-3 py-2">CSAT</th>
                  <th className="px-3 py-2">Reopen rate</th>
                  <th className="px-3 py-2">SLA breach</th>
                  <th className="px-3 py-2">KB failed</th>
                  <th className="px-3 py-2">QA failed</th>
                  <th className="px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(serviceQualityQuery.data ?? []).map((row) => (
                  <tr className="border-t border-border" key={`${row.service_code}:${row.offering_code}`}>
                    <td className="px-3 py-2">{row.service_code}</td>
                    <td className="px-3 py-2">{row.offering_code}</td>
                    <td className="px-3 py-2">{row.ticket_count}</td>
                    <td className="px-3 py-2">{metric(row.avg_csat)}</td>
                    <td className="px-3 py-2">{metric(Math.round(row.reopen_rate * 100), "%")}</td>
                    <td className="px-3 py-2">{metric(Math.round(row.sla_breach_rate * 100), "%")}</td>
                    <td className="px-3 py-2">{row.ticket_after_failed_knowledge_count}</td>
                    <td className="px-3 py-2">{row.qa_failed_count}</td>
                    <td className="px-3 py-2">{row.improvement_action_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>QA review queue</CardTitle>
            <CardDescription>Ticket-level QA work is internal to support and admins.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {(reviewsQuery.data ?? []).slice(0, 12).map((review) => (
              <div className="rounded-[0.75rem] border border-border px-3 py-3" key={review.review_id}>
                <div className="flex items-center justify-between gap-3">
                  <strong>{review.review_type}</strong>
                  <span>{review.status}</span>
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  {review.severity} / {review.service_code ?? "legacy"} / {review.ticket_id}
                </p>
                {["open", "assigned", "in_review"].includes(review.status) ? (
                  <Button className="mt-3" onClick={() => completeReviewMutation.mutate(review.review_id)} size="sm" type="button" variant="outline">
                    Complete pass
                  </Button>
                ) : null}
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Improvement actions</CardTitle>
            <CardDescription>Actions have owner, status and audit fields; they are not requester-visible.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-2 md:grid-cols-[1fr_180px_auto]">
              <input className="field-base px-3 py-2" onChange={(event) => setActionTitle(event.currentTarget.value)} placeholder="Action title" value={actionTitle} />
              <input className="field-base px-3 py-2" onChange={(event) => setActionOwner(event.currentTarget.value)} placeholder="Owner" value={actionOwner} />
              <Button disabled={!actionTitle.trim() || createActionMutation.isPending} onClick={() => createActionMutation.mutate()} type="button">
                Create
              </Button>
            </div>
            {(actionsQuery.data ?? []).slice(0, 12).map((action) => (
              <div className="rounded-[0.75rem] border border-border px-3 py-3" key={action.action_id}>
                <div className="flex items-center justify-between gap-3">
                  <strong>{action.title}</strong>
                  <span>{action.status}</span>
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  {action.priority} / {action.action_type} / owner {action.owner_actor_id ?? "unassigned"}
                </p>
                {action.status !== "done" && action.status !== "dismissed" ? (
                  <Button className="mt-3" onClick={() => closeActionMutation.mutate(action.action_id)} size="sm" type="button" variant="outline">
                    Close
                  </Button>
                ) : null}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Quality policy</CardTitle>
          <CardDescription>Effective policy preview for global scope.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm text-slate-700 md:grid-cols-4">
          <span>Low CSAT threshold: {policy?.low_csat_threshold ?? "n/a"}</span>
          <span>Reopen review: {policy?.reopen_review_enabled ? "on" : "off"}</span>
          <span>SLA review: {policy?.sla_breach_review_enabled ? "on" : "off"}</span>
          <span>QA due hours: {policy?.qa_due_hours ?? "n/a"}</span>
        </CardContent>
      </Card>
    </section>
  );
}

