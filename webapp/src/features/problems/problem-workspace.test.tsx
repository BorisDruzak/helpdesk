import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  convertProblemCandidate,
  approveProblemRca,
  createKnownErrorDraft,
  createProblemRca,
  fetchProblemCandidates,
  fetchProblems,
  fetchProblemSummary,
  linkProblemTicket,
  scanProblemCandidates,
} from "./api";
import { ProblemWorkspace } from "./problem-workspace";

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return {
    ...actual,
    approveProblemRca: vi.fn(),
    convertProblemCandidate: vi.fn(),
    createKnownErrorDraft: vi.fn(),
    createProblemRca: vi.fn(),
    fetchProblemCandidates: vi.fn(),
    fetchProblems: vi.fn(),
    fetchProblemSummary: vi.fn(),
    linkProblemTicket: vi.fn(),
    scanProblemCandidates: vi.fn(),
  };
});

const fetchProblemSummaryMock = vi.mocked(fetchProblemSummary);
const fetchProblemsMock = vi.mocked(fetchProblems);
const fetchProblemCandidatesMock = vi.mocked(fetchProblemCandidates);
const approveProblemRcaMock = vi.mocked(approveProblemRca);
const scanProblemCandidatesMock = vi.mocked(scanProblemCandidates);
const convertProblemCandidateMock = vi.mocked(convertProblemCandidate);
const createProblemRcaMock = vi.mocked(createProblemRca);
const createKnownErrorDraftMock = vi.mocked(createKnownErrorDraft);
const linkProblemTicketMock = vi.mocked(linkProblemTicket);

function renderWorkspace() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ProblemWorkspace />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("ProblemWorkspace", () => {
  it("shows problem metrics, candidates and problem RCA actions", async () => {
    fetchProblemSummaryMock.mockResolvedValue({
      open_problem_count: 1,
      candidate_count: 1,
      linked_ticket_count: 2,
      unresolved_known_errors: 1,
      problems_without_rca: 1,
      problems_by_status: { investigating: 1 },
      problems_by_severity: { high: 1 },
      problems_by_service: { network: 1 },
    });
    fetchProblemsMock.mockResolvedValue([
      {
        problem_id: "p1",
        problem_key: "PRB-000001",
        title: "Repeated VPN outage",
        description: "Repeated VPN outage",
        status: "investigating",
        severity: "high",
        priority: "high",
        service_code: "network",
        offering_code: "network.vpn_issue",
      },
    ]);
    fetchProblemCandidatesMock.mockResolvedValue([
      {
        candidate_id: "c1",
        status: "open",
        signal_type: "low_csat_pattern",
        title: "VPN low CSAT",
        summary: "Low CSAT cluster",
        service_code: "network",
        offering_code: "network.vpn_issue",
        ticket_count: 3,
        reopen_count: 1,
        low_csat_count: 2,
        sla_breach_count: 0,
        failed_kb_count: 0,
      },
    ]);
    scanProblemCandidatesMock.mockResolvedValue({ created: 0, updated: 1, candidates: [] });
    convertProblemCandidateMock.mockResolvedValue({
      problem: {
        problem_id: "p1",
        problem_key: "PRB-000001",
        title: "Repeated VPN outage",
        description: "Repeated VPN outage",
        status: "candidate",
        severity: "high",
        priority: "high",
      },
    });
    approveProblemRcaMock.mockResolvedValue({
      rca_id: "r1",
      problem_id: "p1",
      version_number: 1,
      status: "approved",
      methodology: "five_whys",
      problem_statement: "Repeated VPN outage",
      root_cause: "Gateway route expired",
    });
    createProblemRcaMock.mockResolvedValue({
      rca_id: "r1",
      problem_id: "p1",
      version_number: 1,
      status: "draft",
      methodology: "five_whys",
      problem_statement: "Repeated VPN outage",
      root_cause: "Gateway route expired",
    });
    createKnownErrorDraftMock.mockResolvedValue({ link_id: "k1" });
    linkProblemTicketMock.mockResolvedValue({
      link_id: "l1",
      problem_id: "p1",
      ticket_id: "t1",
      link_type: "confirmed",
      evidence_summary: "Same VPN outage",
    });

    renderWorkspace();

    expect(await screen.findByRole("heading", { name: "Problem workspace" })).toBeInTheDocument();
    expect((await screen.findAllByText("PRB-000001")).length).toBeGreaterThan(0);
    expect(await screen.findByText("VPN low CSAT")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Scan" }));
    await waitFor(() => expect(scanProblemCandidatesMock).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("button", { name: "Convert" }));
    await waitFor(() => expect(convertProblemCandidateMock).toHaveBeenCalled());
    expect(convertProblemCandidateMock.mock.calls[0]?.[0]).toBe("c1");

    fireEvent.change(screen.getByPlaceholderText("Root cause summary"), { target: { value: "Gateway route expired" } });
    fireEvent.click(screen.getByRole("button", { name: "Create and approve RCA" }));
    await waitFor(() => expect(createProblemRcaMock).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: "Known error draft" }));
    await waitFor(() => expect(createKnownErrorDraftMock).toHaveBeenCalled());
    expect(createKnownErrorDraftMock.mock.calls[0]?.[0]).toBe("p1");

    fireEvent.change(screen.getByPlaceholderText("ticket_id"), { target: { value: "t1" } });
    fireEvent.change(screen.getByPlaceholderText("Evidence summary"), { target: { value: "Same VPN outage" } });
    fireEvent.click(screen.getByRole("button", { name: "Link ticket" }));
    await waitFor(() => expect(linkProblemTicketMock).toHaveBeenCalled());
    expect(linkProblemTicketMock).toHaveBeenCalledWith("p1", "t1", "Same VPN outage");
  });
});
