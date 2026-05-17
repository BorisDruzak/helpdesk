import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpenCheck, CheckCircle2, Clock3, FileSearch, GitMerge, GitPullRequestDraft, Link2, RefreshCcw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import {
  approveProblemRca,
  convertProblemCandidate,
  createKnownErrorDraft,
  createProblem,
  createProblemRca,
  createWorkaroundDraft,
  fetchProblemScannerStatus,
  fetchProblemCandidates,
  fetchProblems,
  fetchProblemSummary,
  linkProblemTicket,
  mergeProblemCandidate,
  runProblemScanner,
  scanProblemCandidates,
  transitionProblem,
  type ProblemRecord,
} from "./api";

function valueLabel(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  return String(value);
}

function statusTone(status: string) {
  if (["resolved", "closed"].includes(status)) {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if (["known_error", "workaround_available"].includes(status)) {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  return "border-slate-200 bg-slate-50 text-slate-700";
}

export function ProblemWorkspace() {
  const queryClient = useQueryClient();
  const [selectedProblemId, setSelectedProblemId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [serviceCode, setServiceCode] = useState("");
  const [offeringCode, setOfferingCode] = useState("");
  const [rcaRootCause, setRcaRootCause] = useState("");
  const [linkTicketId, setLinkTicketId] = useState("");
  const [linkEvidence, setLinkEvidence] = useState("");
  const [mergeTargets, setMergeTargets] = useState<Record<string, string>>({});
  const summaryQuery = useQuery({ queryKey: ["problems", "summary"], queryFn: fetchProblemSummary });
  const problemsQuery = useQuery({ queryKey: ["problems", "list"], queryFn: () => fetchProblems() });
  const candidatesQuery = useQuery({ queryKey: ["problems", "candidates"], queryFn: fetchProblemCandidates });
  const scannerStatusQuery = useQuery({ queryKey: ["problems", "scanner-status"], queryFn: fetchProblemScannerStatus });

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["problems", "summary"] }),
      queryClient.invalidateQueries({ queryKey: ["problems", "list"] }),
      queryClient.invalidateQueries({ queryKey: ["problems", "candidates"] }),
      queryClient.invalidateQueries({ queryKey: ["problems", "scanner-status"] }),
    ]);
  };

  const problems = problemsQuery.data ?? [];
  const selectedProblem = useMemo<ProblemRecord | null>(
    () => problems.find((problem) => problem.problem_id === selectedProblemId) ?? problems[0] ?? null,
    [problems, selectedProblemId],
  );

  useEffect(() => {
    if (!selectedProblemId && problems[0]) {
      setSelectedProblemId(problems[0].problem_id);
    }
  }, [problems, selectedProblemId]);

  const createProblemMutation = useMutation({
    mutationFn: () =>
      createProblem({
        title: title.trim(),
        description: title.trim(),
        severity: "medium",
        priority: "medium",
        service_code: serviceCode.trim() || null,
        offering_code: offeringCode.trim() || null,
      }),
    onSuccess: async (problem) => {
      setTitle("");
      setServiceCode("");
      setOfferingCode("");
      setSelectedProblemId(problem.problem_id);
      await invalidate();
    },
  });

  const scanMutation = useMutation({ mutationFn: scanProblemCandidates, onSuccess: invalidate });
  const scannerRunMutation = useMutation({ mutationFn: () => runProblemScanner(), onSuccess: invalidate });
  const dryRunMutation = useMutation({ mutationFn: () => runProblemScanner({ dry_run: true }), onSuccess: invalidate });
  const mergeCandidateMutation = useMutation({
    mutationFn: (payload: { candidateId: string; targetCandidateId: string }) =>
      mergeProblemCandidate(payload.candidateId, payload.targetCandidateId, "same root pattern"),
    onSuccess: invalidate,
  });
  const convertMutation = useMutation({
    mutationFn: convertProblemCandidate,
    onSuccess: async (result) => {
      setSelectedProblemId(result.problem.problem_id);
      await invalidate();
    },
  });
  const transitionMutation = useMutation({
    mutationFn: (payload: { problemId: string; status: string }) =>
      transitionProblem(payload.problemId, {
        status: payload.status,
        root_cause_summary: selectedProblem?.root_cause_summary ?? rcaRootCause.trim(),
        workaround_summary: selectedProblem?.workaround_summary ?? "Support workaround is documented.",
        permanent_fix_summary: selectedProblem?.permanent_fix_summary ?? "Permanent fix candidate is tracked through improvement/change work.",
      }),
    onSuccess: invalidate,
  });
  const rcaMutation = useMutation({
    mutationFn: async (problem: ProblemRecord) => {
      const rca = await createProblemRca(problem.problem_id, {
        methodology: "five_whys",
        problem_statement: problem.title,
        root_cause: rcaRootCause.trim(),
      });
      await approveProblemRca(problem.problem_id, rca.rca_id);
      return rca;
    },
    onSuccess: async () => {
      setRcaRootCause("");
      await invalidate();
    },
  });
  const knownErrorMutation = useMutation({ mutationFn: createKnownErrorDraft, onSuccess: invalidate });
  const workaroundMutation = useMutation({ mutationFn: createWorkaroundDraft, onSuccess: invalidate });
  const linkTicketMutation = useMutation({
    mutationFn: (problem: ProblemRecord) => linkProblemTicket(problem.problem_id, linkTicketId.trim(), linkEvidence.trim()),
    onSuccess: async () => {
      setLinkTicketId("");
      setLinkEvidence("");
      await invalidate();
    },
  });

  const summary = summaryQuery.data;
  const scanner = scannerStatusQuery.data;

  return (
    <section className="workspace-page grid gap-5">
      <div className="workspace-page__header">
        <div>
          <p className="workspace-boot__eyebrow">Problem management</p>
          <h1>Problem workspace</h1>
          <p>Problem candidates, RCA, known errors, workarounds and permanent-fix tracking.</p>
        </div>
        <Button leadingIcon={<RefreshCcw className="h-4 w-4" />} onClick={() => void invalidate()} type="button" variant="outline">
          Refresh
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader>
            <CardDescription>Open problems</CardDescription>
            <CardTitle>{valueLabel(summary?.open_problem_count)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Candidates</CardDescription>
            <CardTitle>{valueLabel(summary?.candidate_count)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Linked tickets</CardDescription>
            <CardTitle>{valueLabel(summary?.linked_ticket_count)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Without RCA</CardDescription>
            <CardTitle>{valueLabel(summary?.problems_without_rca)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Overdue problems</CardDescription>
            <CardTitle>{valueLabel(summary?.overdue_problem_count ?? 0)}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>Scanner operations</CardTitle>
              <CardDescription>Scheduled and manual problem candidate detection with run history state.</CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button disabled={scannerRunMutation.isPending} leadingIcon={<RefreshCcw className="h-4 w-4" />} onClick={() => scannerRunMutation.mutate()} type="button" variant="outline">
                Run scanner
              </Button>
              <Button disabled={dryRunMutation.isPending} leadingIcon={<FileSearch className="h-4 w-4" />} onClick={() => dryRunMutation.mutate()} type="button" variant="outline">
                Dry run
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-5">
            <div>
              <p className="text-xs uppercase text-slate-500">State</p>
              <p className="font-semibold">{scanner?.enabled ? "enabled" : "disabled"}</p>
            </div>
            <div>
              <p className="text-xs uppercase text-slate-500">Last status</p>
              <p className="font-semibold">{scanner?.last_run?.status ?? "n/a"}</p>
            </div>
            <div>
              <p className="text-xs uppercase text-slate-500">Created</p>
              <p className="font-semibold">{valueLabel(scanner?.last_run?.candidates_created)}</p>
            </div>
            <div>
              <p className="text-xs uppercase text-slate-500">Updated</p>
              <p className="font-semibold">{valueLabel(scanner?.last_run?.candidates_updated)}</p>
            </div>
            <div>
              <p className="text-xs uppercase text-slate-500">Duration</p>
              <p className="font-semibold">{scanner?.last_run?.duration_ms ? `${scanner.last_run.duration_ms} ms` : "n/a"}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Problem list</CardTitle>
            <CardDescription>First-class problem records, separate from tickets and requester-visible workflow.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-2 md:grid-cols-[1fr_150px_180px_auto]">
              <input className="field-base px-3 py-2" onChange={(event) => setTitle(event.currentTarget.value)} placeholder="Problem title" value={title} />
              <input className="field-base px-3 py-2" onChange={(event) => setServiceCode(event.currentTarget.value)} placeholder="service_code" value={serviceCode} />
              <input className="field-base px-3 py-2" onChange={(event) => setOfferingCode(event.currentTarget.value)} placeholder="offering_code" value={offeringCode} />
              <Button disabled={!title.trim() || createProblemMutation.isPending} onClick={() => createProblemMutation.mutate()} type="button">
                Create
              </Button>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Key</th>
                    <th className="px-3 py-2">Title</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2">Severity</th>
                    <th className="px-3 py-2">Service</th>
                    <th className="px-3 py-2">Offering</th>
                    <th className="px-3 py-2">Next due</th>
                  </tr>
                </thead>
                <tbody>
                  {problems.map((problem) => (
                    <tr
                      className={`cursor-pointer border-t border-border ${selectedProblem?.problem_id === problem.problem_id ? "bg-slate-50" : ""}`}
                      key={problem.problem_id}
                      onClick={() => setSelectedProblemId(problem.problem_id)}
                    >
                      <td className="px-3 py-2 font-semibold">{problem.problem_key}</td>
                      <td className="px-3 py-2">{problem.title}</td>
                      <td className="px-3 py-2">
                        <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${statusTone(problem.status)}`}>{problem.status}</span>
                      </td>
                      <td className="px-3 py-2">{problem.severity}</td>
                      <td className="px-3 py-2">{problem.service_code ?? "legacy"}</td>
                      <td className="px-3 py-2">{problem.offering_code ?? "uncategorized"}</td>
                      <td className="px-3 py-2">
                        <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${problem.is_overdue ? "border-red-200 bg-red-50 text-red-800" : "border-slate-200 bg-slate-50 text-slate-700"}`}>
                          {problem.next_due_milestone ?? "n/a"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>RCA and known error</CardTitle>
            <CardDescription>RCA stays internal; known error/workaround drafts start as support_internal knowledge.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {selectedProblem ? (
              <>
                <div className="rounded-[0.75rem] border border-border px-3 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <strong>{selectedProblem.problem_key}</strong>
                    <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${statusTone(selectedProblem.status)}`}>{selectedProblem.status}</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-600">{selectedProblem.title}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {selectedProblem.service_code ?? "legacy"} / {selectedProblem.offering_code ?? "uncategorized"}
                  </p>
                </div>
                <div className="rounded-[0.75rem] border border-border px-3 py-3">
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                    <Clock3 className="h-4 w-4" />
                    SLO milestones
                  </div>
                  <div className="mt-3 grid gap-2 text-xs text-slate-600 md:grid-cols-2">
                    <span>Investigation: {selectedProblem.investigation_due_at ?? "n/a"}</span>
                    <span>Known error: {selectedProblem.known_error_due_at ?? "n/a"}</span>
                    <span>Workaround: {selectedProblem.workaround_due_at ?? "n/a"}</span>
                    <span>RCA: {selectedProblem.rca_due_at ?? "n/a"}</span>
                    <span>Resolution: {selectedProblem.resolution_due_at ?? "n/a"}</span>
                    <span>Closure: {selectedProblem.closure_due_at ?? "n/a"}</span>
                  </div>
                </div>
                <textarea
                  className="field-base min-h-24 px-3 py-2"
                  onChange={(event) => setRcaRootCause(event.currentTarget.value)}
                  placeholder="Root cause summary"
                  value={rcaRootCause}
                />
                <div className="rounded-[0.75rem] border border-border px-3 py-3">
                  <p className="text-sm font-semibold text-slate-800">Link affected ticket</p>
                  <div className="mt-3 grid gap-2 md:grid-cols-[minmax(0,0.7fr)_minmax(0,1fr)_auto]">
                    <input
                      className="field-base px-3 py-2"
                      onChange={(event) => setLinkTicketId(event.currentTarget.value)}
                      placeholder="ticket_id"
                      value={linkTicketId}
                    />
                    <input
                      className="field-base px-3 py-2"
                      onChange={(event) => setLinkEvidence(event.currentTarget.value)}
                      placeholder="Evidence summary"
                      value={linkEvidence}
                    />
                    <Button
                      disabled={!linkTicketId.trim() || linkTicketMutation.isPending}
                      leadingIcon={<Link2 className="h-4 w-4" />}
                      onClick={() => linkTicketMutation.mutate(selectedProblem)}
                      type="button"
                      variant="outline"
                    >
                      Link ticket
                    </Button>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    disabled={transitionMutation.isPending}
                    leadingIcon={<FileSearch className="h-4 w-4" />}
                    onClick={() => transitionMutation.mutate({ problemId: selectedProblem.problem_id, status: "investigating" })}
                    type="button"
                    variant="outline"
                  >
                    Investigate
                  </Button>
                  <Button
                    disabled={!rcaRootCause.trim() || rcaMutation.isPending}
                    leadingIcon={<CheckCircle2 className="h-4 w-4" />}
                    onClick={() => rcaMutation.mutate(selectedProblem)}
                    type="button"
                    variant="outline"
                  >
                    Create and approve RCA
                  </Button>
                  <Button
                    disabled={knownErrorMutation.isPending}
                    leadingIcon={<BookOpenCheck className="h-4 w-4" />}
                    onClick={() => knownErrorMutation.mutate(selectedProblem.problem_id)}
                    type="button"
                    variant="outline"
                  >
                    Known error draft
                  </Button>
                  <Button
                    disabled={workaroundMutation.isPending}
                    leadingIcon={<GitPullRequestDraft className="h-4 w-4" />}
                    onClick={() => workaroundMutation.mutate(selectedProblem.problem_id)}
                    type="button"
                    variant="outline"
                  >
                    Workaround draft
                  </Button>
                </div>
              </>
            ) : (
              <p className="text-sm text-slate-500">No problem selected.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-3">
            <div>
              <CardTitle>Problem candidates</CardTitle>
              <CardDescription>Scanner groups repeated incidents, low CSAT, reopens, SLA breaches and failed knowledge attempts.</CardDescription>
            </div>
            <Button disabled={scanMutation.isPending} leadingIcon={<RefreshCcw className="h-4 w-4" />} onClick={() => scanMutation.mutate()} type="button" variant="outline">
              Scan
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 lg:grid-cols-2">
            {(candidatesQuery.data ?? []).map((candidate) => (
              <div className="rounded-[0.75rem] border border-border px-3 py-3" key={candidate.candidate_id}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <strong>{candidate.title}</strong>
                    <p className="mt-1 text-xs text-slate-500">
                      {candidate.signal_type} / {candidate.service_code ?? "legacy"} / {candidate.offering_code ?? "uncategorized"}
                    </p>
                  </div>
                  <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-semibold text-slate-700">{candidate.status}</span>
                </div>
                <div className="mt-3 grid grid-cols-5 gap-2 text-xs text-slate-600">
                  <span>Tickets {candidate.ticket_count}</span>
                  <span>Reopen {candidate.reopen_count}</span>
                  <span>CSAT {candidate.low_csat_count}</span>
                  <span>SLA {candidate.sla_breach_count}</span>
                  <span>KB {candidate.failed_kb_count}</span>
                </div>
                <div className="mt-3 grid gap-2 text-xs text-slate-600 md:grid-cols-3">
                  <span>Duplicates {candidate.duplicate_count ?? 0}</span>
                  <span>First seen {candidate.first_seen_at ?? "n/a"}</span>
                  <span>Last seen {candidate.last_seen_at ?? "n/a"}</span>
                </div>
                {candidate.status === "open" ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      disabled={convertMutation.isPending}
                      leadingIcon={<Link2 className="h-4 w-4" />}
                      onClick={() => convertMutation.mutate(candidate.candidate_id)}
                      size="sm"
                      type="button"
                      variant="outline"
                    >
                      Convert
                    </Button>
                    <input
                      className="field-base min-w-48 px-3 py-2 text-xs"
                      onChange={(event) => setMergeTargets((current) => ({ ...current, [candidate.candidate_id]: event.currentTarget.value }))}
                      placeholder="target candidate_id"
                      value={mergeTargets[candidate.candidate_id] ?? ""}
                    />
                    <Button
                      disabled={!mergeTargets[candidate.candidate_id]?.trim() || mergeCandidateMutation.isPending}
                      leadingIcon={<GitMerge className="h-4 w-4" />}
                      onClick={() => mergeCandidateMutation.mutate({ candidateId: candidate.candidate_id, targetCandidateId: mergeTargets[candidate.candidate_id].trim() })}
                      size="sm"
                      type="button"
                      variant="outline"
                    >
                      Merge
                    </Button>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
