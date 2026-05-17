import { afterEach, describe, expect, it, vi } from "vitest";

import {
  approveProblemRca,
  convertProblemCandidate,
  createKnownErrorDraft,
  createProblem,
  createProblemRca,
  createWorkaroundDraft,
  fetchProblemCandidates,
  fetchProblemScannerStatus,
  fetchProblemSummary,
  fetchProblems,
  fetchTicketProblemLinks,
  mergeProblemCandidate,
  runProblemScanner,
  scanProblemCandidates,
  transitionProblem,
} from "./api";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("problem api", () => {
  it("loads problem summary, list, candidates and ticket links", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/web/problems/metrics/summary") {
        return jsonResponse({
          status: "ok",
          summary: {
            open_problem_count: 1,
            candidate_count: 1,
            linked_ticket_count: 2,
            unresolved_known_errors: 1,
            problems_without_rca: 1,
            problems_by_status: { investigating: 1 },
            problems_by_severity: { high: 1 },
            problems_by_service: { network: 1 },
          },
        });
      }
      if (url === "/api/web/problems") {
        return jsonResponse({
          status: "ok",
          problems: [{ problem_id: "p1", problem_key: "PRB-000001", title: "VPN", description: "VPN", status: "investigating", severity: "high", priority: "high" }],
        });
      }
      if (url === "/api/web/problem-candidates") {
        return jsonResponse({
          status: "ok",
          candidates: [{ candidate_id: "c1", status: "open", signal_type: "low_csat_pattern", title: "VPN CSAT", summary: "CSAT", ticket_count: 2, reopen_count: 0, low_csat_count: 2, sla_breach_count: 0, failed_kb_count: 0 }],
        });
      }
      if (url === "/api/web/problem-scanner/status") {
        return jsonResponse({
          status: "ok",
          scanner: { enabled: false, running: false, interval_seconds: 86400, lookback_hours: 168, dry_run: false, last_run: null },
        });
      }
      if (url === "/api/web/problems?ticket_id=ticket-1") {
        return jsonResponse({
          status: "ok",
          items: [
            {
              problem: { problem_id: "p1", problem_key: "PRB-000001", title: "VPN", description: "VPN", status: "investigating", severity: "high", priority: "high" },
              link: { link_id: "l1", problem_id: "p1", ticket_id: "ticket-1", link_type: "confirmed" },
            },
          ],
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    expect((await fetchProblemSummary()).open_problem_count).toBe(1);
    expect((await fetchProblems())[0]?.problem_key).toBe("PRB-000001");
    expect((await fetchProblemCandidates())[0]?.signal_type).toBe("low_csat_pattern");
    expect((await fetchProblemScannerStatus()).enabled).toBe(false);
    expect((await fetchTicketProblemLinks("ticket-1"))[0]?.link.link_type).toBe("confirmed");
  });

  it("mutates problem lifecycle, candidates, RCA and knowledge drafts", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/problems" && init?.method === "POST") {
        return jsonResponse({ status: "ok", problem: { problem_id: "p1", problem_key: "PRB-000001", title: "VPN", description: "VPN", status: "new", severity: "medium", priority: "medium" } });
      }
      if (url === "/api/web/problems/p1/transition") {
        return jsonResponse({ status: "ok", problem: { problem_id: "p1", problem_key: "PRB-000001", title: "VPN", description: "VPN", status: "investigating", severity: "medium", priority: "medium" } });
      }
      if (url === "/api/web/problem-candidates/scan") {
        return jsonResponse({ status: "ok", scan: { created: 1, updated: 0, candidates: [] } });
      }
      if (url === "/api/web/problem-candidates/c1/convert") {
        return jsonResponse({ status: "ok", problem: { problem_id: "p1", problem_key: "PRB-000001", title: "VPN", description: "VPN", status: "candidate", severity: "medium", priority: "medium" } });
      }
      if (url === "/api/web/problem-scanner/run") {
        return jsonResponse({ status: "ok", run: { run_id: "run-1", status: "completed", triggered_by: "api", lookback_hours: 168, candidates_created: 1, candidates_updated: 0, candidates_skipped: 0 } });
      }
      if (url === "/api/web/problem-candidates/c1/merge") {
        return jsonResponse({
          status: "ok",
          source: { candidate_id: "c1", status: "merged", signal_type: "low_csat_pattern", title: "A", summary: "A", ticket_count: 1, reopen_count: 0, low_csat_count: 1, sla_breach_count: 0, failed_kb_count: 0 },
          target: { candidate_id: "c2", status: "open", signal_type: "reopen_pattern", title: "B", summary: "B", ticket_count: 2, reopen_count: 2, low_csat_count: 0, sla_breach_count: 0, failed_kb_count: 0 },
        });
      }
      if (url === "/api/web/problems/p1/rca") {
        return jsonResponse({ status: "ok", rca: { rca_id: "r1", problem_id: "p1", version_number: 1, status: "draft", methodology: "five_whys", problem_statement: "VPN", root_cause: "Gateway route" } });
      }
      if (url === "/api/web/problems/p1/rca/r1/approve") {
        return jsonResponse({ status: "ok", rca: { rca_id: "r1", problem_id: "p1", version_number: 1, status: "approved", methodology: "five_whys", problem_statement: "VPN", root_cause: "Gateway route" } });
      }
      if (url === "/api/web/problems/p1/known-error-draft" || url === "/api/web/problems/p1/workaround-draft") {
        return jsonResponse({ status: "ok", link: { link_id: "k1" } });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    await createProblem({ title: "VPN", description: "VPN", severity: "medium", priority: "medium" });
    await transitionProblem("p1", { status: "investigating" });
    await scanProblemCandidates();
    await runProblemScanner();
    await convertProblemCandidate("c1");
    await mergeProblemCandidate("c1", "c2", "same root pattern");
    const rca = await createProblemRca("p1", { methodology: "five_whys", problem_statement: "VPN", root_cause: "Gateway route" });
    await approveProblemRca("p1", rca.rca_id);
    await createKnownErrorDraft("p1");
    await createWorkaroundDraft("p1");

    expect(fetchMock).toHaveBeenCalledTimes(10);
  });
});
