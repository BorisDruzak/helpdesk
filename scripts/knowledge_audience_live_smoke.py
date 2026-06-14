from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import ssl
import sys
from types import SimpleNamespace
from typing import Any
from urllib import error, request
import uuid

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / "server"
for path in (str(REPO_ROOT), str(SERVER_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.db import get_session, init_db, shutdown_db
from app.db.models import (
    KnowledgeAudienceRule,
    RegistryAudienceGroup,
    RegistryAudienceGroupMember,
    RegistryDepartment,
    RegistryPerson,
    RegistryPersonIdentity,
    Ticket,
    TicketQueue,
    TicketQueueMember,
    UiUser,
)
from app.repos.knowledge_repo import KnowledgeRepo
from auth.service import AuthService
from config import DATABASE_URL
from knowledge.ask_service import KnowledgeAskService
from knowledge.search_service import KnowledgeSearchService
from knowledge.suggestion_service import KnowledgeSuggestionService
from registry.effective_identity_service import EffectiveIdentityService


class SmokeFailure(RuntimeError):
    pass


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def _json_response(response: Any) -> dict[str, Any]:
    raw = response.read()
    text = raw.decode("utf-8", errors="replace")
    try:
        payload = json.loads(text) if text else {}
    except json.JSONDecodeError as exc:
        raise SmokeFailure(f"non-JSON response from {response.geturl()}: {text[:500]}") from exc
    return payload


class ApiClient:
    def __init__(self, *, base_url: str, insecure_tls: bool) -> None:
        self.base_url = base_url.rstrip("/")
        context = ssl._create_unverified_context() if insecure_tls else ssl.create_default_context()
        self.opener = request.build_opener(request.HTTPSHandler(context=context))

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, headers=headers, method=method.upper())
        try:
            with self.opener.open(req, timeout=45) as response:
                return _json_response(response)
        except error.HTTPError as exc:
            body = _json_response(exc)
            raise SmokeFailure(f"{method} {path} failed with HTTP {exc.code}: {body}") from exc
        except error.URLError as exc:
            raise SmokeFailure(f"{method} {path} failed: {exc}") from exc

    def get(self, path: str, *, token: str) -> dict[str, Any]:
        return self.request("GET", path, token=token)

    def post(self, path: str, *, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", path, token=token, payload=payload)


class KnowledgeAudienceLiveSmoke:
    def __init__(self, *, base_url: str, run_id: str, insecure_tls: bool) -> None:
        self.base_url = base_url
        self.run_id = run_id
        self.marker = f"phase5 knowledge audience {run_id}"
        self.api = ApiClient(base_url=base_url, insecure_tls=insecure_tls)
        self.tokens: dict[str, str] = {}
        self.ids: dict[str, str] = {}
        self.report: dict[str, Any] = {
            "run_id": run_id,
            "base_url": base_url,
            "commit": None,
            "marker": self.marker,
            "checks": {},
            "created": {},
        }

    async def setup(self) -> None:
        await init_db(DATABASE_URL)
        auth = AuthService(SimpleNamespace(users={}))
        admin_login = f"phase5-admin-{self.run_id}"
        support_login = f"phase5-support-{self.run_id}"
        requester_it_login = f"phase5-it-{self.run_id}"
        requester_finance_login = f"phase5-finance-{self.run_id}"
        self.tokens = {
            "admin": await auth.generate_ui_token(admin_login, "admin", expires_hours=2),
            "support": await auth.generate_ui_token(support_login, "support", expires_hours=2),
            "it": await auth.generate_ui_token(requester_it_login, "user", expires_hours=2),
            "finance": await auth.generate_ui_token(requester_finance_login, "user", expires_hours=2),
        }
        await self._seed_data(
            admin_login=admin_login,
            support_login=support_login,
            requester_it_login=requester_it_login,
            requester_finance_login=requester_finance_login,
        )
        self.report["created"] = {
            key: value
            for key, value in self.ids.items()
            if key.endswith("_slug") or key in {"ticket_id", "ticket_code"}
        }

    async def close(self) -> None:
        await shutdown_db()

    async def _seed_data(
        self,
        *,
        admin_login: str,
        support_login: str,
        requester_it_login: str,
        requester_finance_login: str,
    ) -> None:
        async with get_session() as session:
            suffix = self.run_id
            session.add_all(
                [
                    UiUser(user_login=admin_login, password_hash="live-smoke", actor_role="admin", is_active=True),
                    UiUser(user_login=support_login, password_hash="live-smoke", actor_role="support", is_active=True),
                    UiUser(user_login=requester_it_login, password_hash="live-smoke", actor_role="user", is_active=True),
                    UiUser(user_login=requester_finance_login, password_hash="live-smoke", actor_role="user", is_active=True),
                ]
            )
            it_department = RegistryDepartment(
                department_id=str(uuid.uuid4()),
                code=f"phase5-it-{suffix}",
                name=f"Phase 5 IT {suffix}",
                status="active",
                source="live_smoke",
            )
            finance_department = RegistryDepartment(
                department_id=str(uuid.uuid4()),
                code=f"phase5-finance-{suffix}",
                name=f"Phase 5 Finance {suffix}",
                status="active",
                source="live_smoke",
            )
            it_person = RegistryPerson(
                person_id=str(uuid.uuid4()),
                display_name=f"Phase 5 IT Requester {suffix}",
                email=f"{requester_it_login}@live-smoke.test",
                department_id=it_department.department_id,
                source="live_smoke",
                status="active",
            )
            finance_person = RegistryPerson(
                person_id=str(uuid.uuid4()),
                display_name=f"Phase 5 Finance Requester {suffix}",
                email=f"{requester_finance_login}@live-smoke.test",
                department_id=finance_department.department_id,
                source="live_smoke",
                status="active",
            )
            session.add_all(
                [
                    it_department,
                    finance_department,
                    it_person,
                    finance_person,
                    RegistryPersonIdentity(
                        person_id=it_person.person_id,
                        provider="ui_login",
                        identifier=requester_it_login,
                        normalized_identifier=requester_it_login,
                        verified=True,
                        source="live_smoke",
                    ),
                    RegistryPersonIdentity(
                        person_id=finance_person.person_id,
                        provider="ui_login",
                        identifier=requester_finance_login,
                        normalized_identifier=requester_finance_login,
                        verified=True,
                        source="live_smoke",
                    ),
                ]
            )
            queue = TicketQueue(
                code=f"phase5-knowledge-{suffix}",
                name=f"Phase 5 Knowledge {suffix}",
                is_active=True,
            )
            session.add(queue)
            await session.flush()
            session.add(TicketQueueMember(queue_id=queue.id, actor_id=support_login, role_in_queue="operator"))

            repo = KnowledgeRepo(session)
            space_code = f"phase5-knowledge-{suffix}"
            await repo.upsert_space(
                {
                    "code": space_code,
                    "title": f"Phase 5 Knowledge {suffix}",
                    "visibility": "requester",
                    "lifecycle_status": "active",
                },
                actor_id=admin_login,
            )
            public = await self._published_item(
                repo,
                space_code=space_code,
                slug=f"phase5-public-{suffix}",
                title=f"{self.marker} public visible",
                body=f"{self.marker} public body",
                visibility="requester",
                actor_id=admin_login,
            )
            it_item = await self._published_item(
                repo,
                space_code=space_code,
                slug=f"phase5-it-{suffix}",
                title=f"{self.marker} IT visible",
                body=f"{self.marker} IT body",
                visibility="requester",
                actor_id=admin_login,
            )
            finance_item = await self._published_item(
                repo,
                space_code=space_code,
                slug=f"phase5-finance-{suffix}",
                title=f"{self.marker} Finance scoped",
                body=f"{self.marker} finance hidden body",
                visibility="requester",
                actor_id=admin_login,
            )
            audience_group_item = await self._published_item(
                repo,
                space_code=space_code,
                slug=f"phase5-audience-group-{suffix}",
                title=f"{self.marker} audience group visible",
                body=f"{self.marker} audience group body",
                visibility="requester",
                actor_id=admin_login,
            )
            internal = await self._published_item(
                repo,
                space_code=space_code,
                slug=f"phase5-support-internal-{suffix}",
                title=f"{self.marker} support internal runbook",
                body=f"{self.marker} internal body",
                visibility="support_internal",
                item_type="runbook",
                actor_id=admin_login,
            )
            audience_group = RegistryAudienceGroup(
                audience_group_id=str(uuid.uuid4()),
                code=f"phase5_ag_{suffix}",
                name=f"Phase 5 Audience Group {suffix}",
                status="active",
                source="manual",
            )
            session.add(audience_group)
            await session.flush()
            session.add_all(
                [
                    RegistryAudienceGroupMember(
                        audience_group_id=audience_group.audience_group_id,
                        member_type="person",
                        member_id=it_person.person_id,
                        source="manual",
                    ),
                    KnowledgeAudienceRule(
                        rule_id=str(uuid.uuid4()),
                        subject_type="item",
                        subject_id=it_item["item_id"],
                        target_type="department",
                        target_id=it_department.department_id,
                        effect="allow",
                        status="active",
                    ),
                    KnowledgeAudienceRule(
                        rule_id=str(uuid.uuid4()),
                        subject_type="item",
                        subject_id=finance_item["item_id"],
                        target_type="department",
                        target_id=finance_department.department_id,
                        effect="allow",
                        status="active",
                    ),
                    KnowledgeAudienceRule(
                        rule_id=str(uuid.uuid4()),
                        subject_type="item",
                        subject_id=audience_group_item["item_id"],
                        target_type="audience_group",
                        target_id=audience_group.audience_group_id,
                        effect="allow",
                        status="active",
                    ),
                ]
            )
            ticket = Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id=f"phase5-device-{suffix}",
                title=self.marker,
                description="",
                status="in_progress",
                requester_id=requester_it_login,
                requester_person_id=it_person.person_id,
                queue_id=queue.id,
                assignee_id=support_login,
                priority="P2",
            )
            session.add(ticket)
            await session.commit()
            self.ids = {
                "public_slug": public["slug"],
                "it_slug": it_item["slug"],
                "finance_slug": finance_item["slug"],
                "audience_group_slug": audience_group_item["slug"],
                "audience_group_id": audience_group.audience_group_id,
                "audience_group_item_id": audience_group_item["item_id"],
                "internal_slug": internal["slug"],
                "finance_item_id": finance_item["item_id"],
                "ticket_id": ticket.ticket_id,
                "ticket_code": str(getattr(ticket, "ticket_code", "") or ""),
            }

    async def _published_item(
        self,
        repo: KnowledgeRepo,
        *,
        space_code: str,
        slug: str,
        title: str,
        body: str,
        visibility: str,
        actor_id: str,
        item_type: str = "article",
    ) -> dict[str, Any]:
        item = await repo.create_item_draft(
            {
                "space_code": space_code,
                "slug": slug,
                "item_type": item_type,
                "title": title,
                "summary": title,
                "visibility": visibility,
                "owner_actor_id": actor_id,
                "reviewer_actor_id": actor_id,
            },
            actor_id=actor_id,
            actor_role="admin",
        )
        version = await repo.create_version(
            item["item_id"],
            {"title": title, "body_format": "markdown", "body": body},
            actor_id=actor_id,
            actor_role="admin",
        )
        return await repo.publish_item(item["item_id"], version["version_id"], actor_id=actor_id, actor_role="admin")

    async def run_checks(self) -> dict[str, Any]:
        it_payload = {"query": f"{self.marker} IT visible", "limit": 10, "surface": "live_phase5"}
        finance_payload = {"query": f"{self.marker} Finance scoped", "limit": 10, "surface": "live_phase5"}
        self.report["checks"]["service_requester_it_search"] = await self._check_service_search("it", it_payload)
        self.report["checks"]["service_requester_finance_search"] = await self._check_service_search("finance", finance_payload)
        self.report["checks"]["service_requester_it_hidden_search"] = await self._check_hidden_service_search("it", finance_payload)
        self.report["checks"]["service_requester_it_audience_group_search"] = (
            await self._check_audience_group_service_search("it")
        )
        self.report["checks"]["service_requester_finance_audience_group_hidden_search"] = (
            await self._check_audience_group_service_search("finance")
        )
        self.report["checks"]["service_requester_it_suggest"] = await self._check_service_suggest("it", it_payload)
        self.report["checks"]["service_requester_it_hidden_suggest"] = await self._check_hidden_service_suggest("it", finance_payload)
        self.report["checks"]["service_requester_it_ask"] = await self._check_service_ask("it", it_payload)
        self.report["checks"]["service_requester_it_hidden_ask"] = await self._check_hidden_service_ask("it", finance_payload)
        self.report["checks"]["support_ticket_suggestions"] = self._check_support_ticket_suggestions()
        self.report["checks"]["admin_explain_denied"] = self._check_admin_explain_denied()
        self.report["status"] = "passed"
        return self.report

    def _assert_payload_excludes_finance(self, payload: dict[str, Any]) -> None:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        _require(self.ids["finance_slug"] not in text, "finance slug leaked into requester-scoped payload")
        _require(f"{self.marker} Finance scoped" not in text, "finance title leaked into requester-scoped payload")
        _require("finance hidden body" not in text, "finance body leaked into requester-scoped payload")

    def _assert_payload_excludes_audience_group_article(self, payload: dict[str, Any]) -> None:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        _require(self.ids["audience_group_slug"] not in text, "audience-group slug leaked to non-member")
        _require(f"{self.marker} audience group visible" not in text, "audience-group title leaked to non-member")
        _require("audience group body" not in text, "audience-group body leaked to non-member")

    async def _requester_audience(self, session, token_key: str):
        actor_id = f"phase5-{token_key}-{self.run_id}"
        return await EffectiveIdentityService(session).resolve_person_audience(
            person_id=None,
            actor_id=actor_id,
            actor_role="requester",
        )

    async def _check_service_search(self, token_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with get_session() as session:
            audience = await self._requester_audience(session, token_key)
            results = await KnowledgeSearchService(session).search(
                query=payload.get("query"),
                actor_role="requester",
                limit=10,
                surface=str(payload.get("surface") or "live_phase5"),
                effective_audience=audience,
            )
            await session.commit()
        slugs = {str(item.get("slug") or "") for item in results if isinstance(item, dict)}
        if token_key == "it":
            _require(self.ids["it_slug"] in slugs, "IT requester does not see IT article")
            _require(self.ids["finance_slug"] not in slugs, "IT requester sees finance article")
            _require(self.ids["internal_slug"] not in slugs, "IT requester sees support internal runbook")
            self._assert_payload_excludes_finance({"results": results})
        else:
            _require(self.ids["finance_slug"] in slugs, "finance requester does not see finance article")
            _require(self.ids["it_slug"] not in slugs, "finance requester sees IT article")
        return {"status": "passed", "slugs": sorted(slugs)}

    async def _check_hidden_service_search(self, token_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with get_session() as session:
            audience = await self._requester_audience(session, token_key)
            results = await KnowledgeSearchService(session).search(
                query=payload.get("query"),
                actor_role="requester",
                limit=10,
                surface=str(payload.get("surface") or "live_phase5"),
                effective_audience=audience,
            )
            await session.commit()
        slugs = {str(item.get("slug") or "") for item in results if isinstance(item, dict)}
        _require(self.ids["finance_slug"] not in slugs, "hidden search returned finance article")
        self._assert_payload_excludes_finance({"results": results})
        return {"status": "passed", "slugs": sorted(slugs)}

    async def _check_audience_group_service_search(self, token_key: str) -> dict[str, Any]:
        async with get_session() as session:
            audience = await self._requester_audience(session, token_key)
            results = await KnowledgeSearchService(session).search(
                query=f"{self.marker} audience group visible",
                actor_role="requester",
                limit=10,
                surface="live_phase5",
                effective_audience=audience,
            )
            await session.commit()
        slugs = {str(item.get("slug") or "") for item in results if isinstance(item, dict)}
        audience_groups = (audience.to_dict()).get("audience_groups") or []
        if token_key == "it":
            _require(self.ids["audience_group_slug"] in slugs, "audience-group member cannot see scoped article")
            _require(
                any(
                    isinstance(item, dict) and item.get("audience_group_id") == self.ids["audience_group_id"]
                    for item in audience_groups
                ),
                "audience-group member effective audience does not include the registry audience group",
            )
        else:
            _require(self.ids["audience_group_slug"] not in slugs, "audience-group non-member sees scoped article")
            _require(
                not any(
                    isinstance(item, dict) and item.get("audience_group_id") == self.ids["audience_group_id"]
                    for item in audience_groups
                ),
                "audience-group non-member effective audience includes the registry audience group",
            )
            self._assert_payload_excludes_audience_group_article({"results": results})
        return {"status": "passed", "slugs": sorted(slugs), "audience_groups": audience_groups}

    async def _check_service_suggest(self, token_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with get_session() as session:
            audience = await self._requester_audience(session, token_key)
            response = await KnowledgeSuggestionService(session).suggest(
                payload,
                actor_role="requester",
                effective_audience=audience,
            )
        slugs = {str(item.get("slug") or "") for item in response.get("suggestions") or [] if isinstance(item, dict)}
        _require(self.ids["it_slug"] in slugs, "IT requester suggest missing IT article")
        _require(self.ids["finance_slug"] not in slugs, "IT requester suggest sees finance article")
        _require(self.ids["internal_slug"] not in slugs, "IT requester suggest sees support internal runbook")
        self._assert_payload_excludes_finance(response)
        return {"status": "passed", "slugs": sorted(slugs)}

    async def _check_hidden_service_suggest(self, token_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with get_session() as session:
            audience = await self._requester_audience(session, token_key)
            response = await KnowledgeSuggestionService(session).suggest(
                payload,
                actor_role="requester",
                effective_audience=audience,
            )
        slugs = {str(item.get("slug") or "") for item in response.get("suggestions") or [] if isinstance(item, dict)}
        _require(self.ids["finance_slug"] not in slugs, "hidden suggest returned finance article")
        self._assert_payload_excludes_finance(response)
        return {"status": "passed", "slugs": sorted(slugs)}

    async def _check_service_ask(self, token_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with get_session() as session:
            audience = await self._requester_audience(session, token_key)
            response = await KnowledgeAskService(session).ask(
                query=payload.get("query"),
                actor_role="requester",
                effective_audience=audience,
            )
        slugs = {
            str(((item.get("item") or {}) if isinstance(item, dict) else {}).get("slug") or "")
            for item in response.get("retrieval_results") or []
            if isinstance(item, dict)
        }
        _require(self.ids["it_slug"] in slugs, "IT requester ask missing IT article")
        _require(self.ids["finance_slug"] not in slugs, "IT requester ask sees finance article")
        _require(self.ids["internal_slug"] not in slugs, "IT requester ask sees support internal runbook")
        self._assert_payload_excludes_finance(response)
        return {"status": "passed", "slugs": sorted(slugs)}

    async def _check_hidden_service_ask(self, token_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with get_session() as session:
            audience = await self._requester_audience(session, token_key)
            response = await KnowledgeAskService(session).ask(
                query=payload.get("query"),
                actor_role="requester",
                effective_audience=audience,
            )
        slugs = {
            str(((item.get("item") or {}) if isinstance(item, dict) else {}).get("slug") or "")
            for item in response.get("retrieval_results") or []
            if isinstance(item, dict)
        }
        _require(self.ids["finance_slug"] not in slugs, "hidden ask returned finance article")
        self._assert_payload_excludes_finance(response)
        return {"status": "passed", "slugs": sorted(slugs)}

    def _check_support_ticket_suggestions(self) -> dict[str, Any]:
        path = f"/api/web/support/tickets/{self.ids['ticket_id']}/knowledge-suggestions"
        response = self.api.get(path, token=self.tokens["support"])
        _require(response.get("status") == "success", f"support suggestions returned status={response.get('status')}")
        data = response.get("data") or {}
        article_ids = {str(item.get("id") or "") for item in data.get("articles") or [] if isinstance(item, dict)}
        _require(self.ids["public_slug"] in article_ids, "support ticket suggestions missing public article")
        _require(self.ids["it_slug"] in article_ids, "support ticket suggestions missing IT article")
        _require(self.ids["internal_slug"] in article_ids, "support ticket suggestions missing support internal runbook")
        _require(self.ids["finance_slug"] not in article_ids, "support ticket suggestions sees finance article")
        self._assert_payload_excludes_finance(response)
        return {"status": "passed", "article_ids": sorted(article_ids)}

    def _check_admin_explain_denied(self) -> dict[str, Any]:
        path = (
            f"/api/web/admin/knowledge/access/explain"
            f"?actor_id=phase5-it-{self.run_id}&actor_role=user&item_id={self.ids['finance_item_id']}"
        )
        response = self.api.get(path, token=self.tokens["admin"])
        _require(response.get("status") == "success", f"admin explain returned status={response.get('status')}")
        explain = (response.get("data") or {}).get("explain") or {}
        decision = explain.get("decision") or {}
        _require(decision.get("allowed") is False, f"admin explain expected denied decision, got {decision}")
        return {
            "status": "passed",
            "allowed": decision.get("allowed"),
            "reason_code": decision.get("reason_code"),
        }


def write_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


async def async_main(args: argparse.Namespace) -> int:
    smoke = KnowledgeAudienceLiveSmoke(base_url=args.base_url, run_id=args.run_id, insecure_tls=args.insecure_tls)
    try:
        await smoke.setup()
        report = await smoke.run_checks()
        if args.output:
            write_report(report, Path(args.output))
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        smoke.report["status"] = "failed"
        smoke.report["error"] = str(exc)
        if args.output:
            write_report(smoke.report, Path(args.output))
        print(json.dumps(smoke.report, ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    finally:
        await smoke.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live smoke for Knowledge audience-rule anti-leak behavior.")
    parser.add_argument("--base-url", default="https://192.168.100.17:9443")
    parser.add_argument("--run-id", default=_run_id())
    parser.add_argument("--output", default="")
    parser.add_argument("--insecure-tls", action="store_true")
    return parser.parse_args()


def main() -> int:
    return asyncio.run(async_main(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
