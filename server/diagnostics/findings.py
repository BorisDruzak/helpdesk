from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DiagnosticEvidence, DiagnosticFinding
from app.repos.diagnostics_repo import DiagnosticRepo


def _has(evidence: list[DiagnosticEvidence], *, kind: str, perspective: str | None = None, status: str | None = None) -> list[DiagnosticEvidence]:
    result = []
    for item in evidence:
        if item.kind != kind:
            continue
        if perspective is not None and item.perspective != perspective:
            continue
        if status is not None and item.status != status:
            continue
        result.append(item)
    return result


class DiagnosticFindingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DiagnosticRepo(session)

    async def evaluate_ticket(self, ticket_id: str, session_id: str | None = None) -> list[DiagnosticFinding]:
        evidence = await self.repo.list_evidence(ticket_id, session_id=session_id)
        created: list[DiagnosticFinding] = []

        endpoint_http_error = _has(evidence, kind="network.http", perspective="endpoint", status="error")
        server_http_error = _has(evidence, kind="network.http", perspective="server", status="error")
        server_http_ok = _has(evidence, kind="network.http", perspective="server", status="ok")
        monitoring_problem = _has(evidence, kind="monitoring.problem", status="error") or _has(
            evidence, kind="monitoring.problem", status="warning"
        )
        logs = _has(evidence, kind="logs.bundle")

        if endpoint_http_error and server_http_error:
            created.append(
                await self.repo.upsert_finding(
                    ticket_id=ticket_id,
                    session_id=session_id,
                    root_cause_code="server_side_problem",
                    title="Probable server-side problem",
                    description="Endpoint and server-side HTTP checks both failed.",
                    confidence=0.8,
                    status="suspected",
                    evidence_ids=[endpoint_http_error[0].id, server_http_error[0].id],
                    recommended_actions=["check_backend", "review_monitoring", "collect_logs"],
                    created_by="system",
                )
            )

        if endpoint_http_error and server_http_ok:
            created.append(
                await self.repo.upsert_finding(
                    ticket_id=ticket_id,
                    session_id=session_id,
                    root_cause_code="endpoint_network_or_proxy_problem",
                    title="Probable endpoint network or proxy problem",
                    description="Endpoint HTTP check failed while server-side check succeeded.",
                    confidence=0.75,
                    status="suspected",
                    evidence_ids=[endpoint_http_error[0].id, server_http_ok[0].id],
                    recommended_actions=["check_proxy", "check_endpoint_network", "request_remote_assist"],
                    created_by="system",
                )
            )

        if (endpoint_http_error or server_http_error) and monitoring_problem:
            source = endpoint_http_error[0] if endpoint_http_error else server_http_error[0]
            created.append(
                await self.repo.upsert_finding(
                    ticket_id=ticket_id,
                    session_id=session_id,
                    root_cause_code="monitoring_confirmed_service_problem",
                    title="Monitoring confirms a service problem",
                    description="HTTP failure is backed by monitoring evidence.",
                    confidence=0.9,
                    status="suspected",
                    evidence_ids=[source.id, monitoring_problem[0].id],
                    recommended_actions=["open_problem_record", "notify_service_owner"],
                    created_by="system",
                )
            )

        if logs:
            created.append(
                await self.repo.upsert_finding(
                    ticket_id=ticket_id,
                    session_id=session_id,
                    root_cause_code="logs_available_for_l2",
                    title="Diagnostic logs are available",
                    description="Collected endpoint logs can be used for second-line analysis.",
                    confidence=0.5,
                    status="suspected",
                    evidence_ids=[logs[0].id],
                    recommended_actions=["attach_logs_to_passport"],
                    created_by="system",
                )
            )

        return created

    async def list_findings(self, ticket_id: str, session_id: str | None = None) -> list[DiagnosticFinding]:
        return await self.repo.list_findings(ticket_id, session_id=session_id)
