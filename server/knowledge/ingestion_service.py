from __future__ import annotations

import html
import base64
import binascii
from dataclasses import dataclass
import io
import ipaddress
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any
from urllib import error as url_error
from urllib import request as url_request
from urllib.parse import urlsplit
import uuid
import zipfile

from sqlalchemy.ext.asyncio import AsyncSession

import config
from app.db.models import KnowledgeIngestionJob
from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.ai_proposal_service import KnowledgeAiProposalService
from knowledge.contracts import KNOWLEDGE_BODY_FORMATS, KNOWLEDGE_INGESTION_SOURCE_KINDS, KnowledgeValidationError
from knowledge.embedding_service import KnowledgeEmbeddingService, Transport
from knowledge.segmentation_service import KnowledgeSegmentationService

MAX_IMPORT_UPLOAD_BYTES = 5 * 1024 * 1024
REMOTE_IMPORT_SOURCE_KINDS = {"url", "git"}
LOCAL_IMPORT_SOURCE_KINDS = {"text", "markdown", "html", "docx", "pdf"}
REMOTE_IMPORT_TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".html", ".htm"}


def _new_id() -> str:
    return str(uuid.uuid4())


def _slug_from_title(title: str) -> str:
    ascii_title = re.sub(r"[^a-zA-Z0-9_-]+", "-", title.lower()).strip("-")
    return ascii_title or f"import-{uuid.uuid4().hex[:8]}"


def _redact_error(error: BaseException) -> str:
    text = str(error)
    text = re.sub(r"(?i)(token|password|secret)=\S+", r"\1=<redacted>", text)
    return text[:500]


class KnowledgeRemoteImportBlockedError(KnowledgeValidationError):
    """Raised when a remote import source is blocked by the safe fetch policy."""

    def __init__(self, reason: str = "remote import fetch is disabled by safe import policy") -> None:
        super().__init__(reason)


@dataclass(frozen=True)
class RemoteImportContent:
    source_kind: str
    source_name: str
    body: str
    body_format: str
    remote_source: dict[str, Any]


class _NoRedirectHandler(url_request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise KnowledgeRemoteImportBlockedError("remote import redirects are blocked by safe import policy")


def _configured_allowed_hosts() -> tuple[str, ...]:
    raw = getattr(config, "KNOWLEDGE_REMOTE_IMPORT_ALLOWED_HOSTS", ())
    if isinstance(raw, str):
        return tuple(host.strip().lower() for host in raw.split(",") if host.strip())
    return tuple(str(host).strip().lower() for host in raw if str(host).strip())


def _host_matches_allowlist(host: str, allowed_hosts: tuple[str, ...]) -> bool:
    normalized = host.lower().strip(".")
    for allowed in allowed_hosts:
        allowed = allowed.lower().strip(".")
        if not allowed:
            continue
        if allowed == normalized:
            return True
        if allowed.startswith("*.") and normalized.endswith(allowed[1:]) and normalized != allowed[2:]:
            return True
    return False


def _is_blocked_ip_literal(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return any(
        (
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_multicast,
            address.is_reserved,
            address.is_unspecified,
        )
    )


def _safe_remote_url(payload: dict[str, Any], *, field_name: str) -> tuple[str, Any]:
    raw_url = str(payload.get(field_name) or "").strip()
    if not raw_url:
        raise KnowledgeValidationError(f"{field_name} is required for remote import")
    parsed = urlsplit(raw_url)
    if parsed.scheme.lower() != "https":
        raise KnowledgeRemoteImportBlockedError("remote import requires https URL")
    if parsed.username or parsed.password:
        raise KnowledgeRemoteImportBlockedError("remote import URL credentials are blocked")
    if not parsed.hostname or _is_blocked_ip_literal(parsed.hostname):
        raise KnowledgeRemoteImportBlockedError("remote import host is blocked")
    if not _host_matches_allowlist(parsed.hostname, _configured_allowed_hosts()):
        raise KnowledgeRemoteImportBlockedError("remote import host is not allowlisted")
    return raw_url, parsed


def _remote_body_format(source_kind: str, source_path: str, content_type: str = "") -> str:
    content_type = content_type.lower()
    suffix = Path(source_path).suffix.lower()
    if "markdown" in content_type or suffix in {".md", ".markdown"}:
        return "markdown"
    if "html" in content_type or suffix in {".html", ".htm"}:
        return "html"
    return "plain_text"


class KnowledgeRemoteImportFetcher:
    def fetch(self, payload: dict[str, Any]) -> RemoteImportContent:
        if not bool(getattr(config, "KNOWLEDGE_REMOTE_IMPORT_ENABLED", False)):
            raise KnowledgeRemoteImportBlockedError()
        source_kind = str(payload.get("source_kind") or "").lower()
        if source_kind == "url":
            return self._fetch_url(payload)
        if source_kind == "git":
            return self._fetch_git(payload)
        raise KnowledgeValidationError(f"unsupported remote import source_kind: {source_kind}")

    def _fetch_url(self, payload: dict[str, Any]) -> RemoteImportContent:
        raw_url, parsed = _safe_remote_url(payload, field_name="url")
        max_bytes = max(1, int(getattr(config, "KNOWLEDGE_REMOTE_IMPORT_MAX_BYTES", 1024 * 1024)))
        timeout = max(1, int(getattr(config, "KNOWLEDGE_REMOTE_IMPORT_TIMEOUT_SECONDS", 10)))
        opener = url_request.build_opener(_NoRedirectHandler())
        request = url_request.Request(raw_url, headers={"User-Agent": "pc-client-knowledge-import/1.0"})
        try:
            with opener.open(request, timeout=timeout) as response:
                content_type = str(response.headers.get("content-type") or "")
                raw = response.read(max_bytes + 1)
        except (OSError, url_error.URLError) as exc:
            raise KnowledgeValidationError("unable to fetch allowlisted remote URL") from exc
        if len(raw) > max_bytes:
            raise KnowledgeValidationError("remote URL import exceeds safe size limit")
        body = raw.decode("utf-8", errors="replace").strip()
        if not body:
            raise KnowledgeValidationError("remote URL import returned empty content")
        body_format = _remote_body_format("url", parsed.path, content_type)
        path = parsed.path or "/"
        return RemoteImportContent(
            source_kind="url",
            source_name=parsed.hostname or "remote-url",
            body=body,
            body_format=body_format,
            remote_source={"source_kind": "url", "host": parsed.hostname, "path": path[:240], "bytes": len(raw)},
        )

    def _fetch_git(self, payload: dict[str, Any]) -> RemoteImportContent:
        repo_url, parsed = _safe_remote_url(payload, field_name="repo_url")
        ref = str(payload.get("ref") or "").strip()
        if ref and not re.fullmatch(r"[A-Za-z0-9._/-]{1,128}", ref):
            raise KnowledgeRemoteImportBlockedError("remote git ref is blocked")
        max_bytes = max(1, int(getattr(config, "KNOWLEDGE_REMOTE_IMPORT_MAX_BYTES", 1024 * 1024)))
        timeout = max(1, int(getattr(config, "KNOWLEDGE_REMOTE_IMPORT_TIMEOUT_SECONDS", 10)))
        max_files = max(1, int(getattr(config, "KNOWLEDGE_REMOTE_IMPORT_MAX_GIT_FILES", 50)))
        with tempfile.TemporaryDirectory(prefix="knowledge-import-git-") as tmp_dir:
            repo_dir = Path(tmp_dir) / "repo"
            command = ["git", "clone", "--depth", "1", "--filter=blob:none", "--no-tags"]
            if ref:
                command.extend(["--branch", ref])
            command.extend([repo_url, str(repo_dir)])
            try:
                subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout)
            except (OSError, subprocess.SubprocessError) as exc:
                raise KnowledgeValidationError("unable to fetch allowlisted git repository") from exc
            parts: list[str] = []
            total_bytes = 0
            file_count = 0
            for path in sorted(repo_dir.rglob("*")):
                if file_count >= max_files:
                    break
                if not path.is_file() or ".git" in path.parts or path.suffix.lower() not in REMOTE_IMPORT_TEXT_SUFFIXES:
                    continue
                raw = path.read_bytes()
                total_bytes += len(raw)
                if total_bytes > max_bytes:
                    raise KnowledgeValidationError("remote git import exceeds safe size limit")
                relative_path = path.relative_to(repo_dir).as_posix()
                parts.append(f"# {relative_path}\n\n{raw.decode('utf-8', errors='replace').strip()}")
                file_count += 1
        if not parts:
            raise KnowledgeValidationError("remote git import found no supported text files")
        repo_name = f"{parsed.hostname}{parsed.path}".removesuffix(".git").strip("/")
        return RemoteImportContent(
            source_kind="git",
            source_name=repo_name or (parsed.hostname or "remote-git"),
            body="\n\n".join(parts),
            body_format="markdown",
            remote_source={
                "source_kind": "git",
                "host": parsed.hostname,
                "repo": repo_name,
                "ref": ref or "default",
                "file_count": file_count,
                "bytes": total_bytes,
            },
        )


def _strip_html(value: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|li|h[1-6])>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(re.sub(r"[ \t]+", " ", text)).strip()


def _uploaded_bytes(payload: dict[str, Any], *, source_kind: str) -> bytes:
    encoded = payload.get("file_content_base64")
    if not isinstance(encoded, str) or not encoded.strip():
        raise KnowledgeValidationError(f"{source_kind} import requires file_content_base64 upload")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise KnowledgeValidationError(f"invalid {source_kind} upload encoding") from exc
    if not raw:
        raise KnowledgeValidationError(f"{source_kind} upload is empty")
    if len(raw) > MAX_IMPORT_UPLOAD_BYTES:
        raise KnowledgeValidationError(f"{source_kind} upload exceeds safe size limit")
    return raw


def _parse_docx_upload(payload: dict[str, Any]) -> str:
    raw = _uploaded_bytes(payload, source_kind="docx")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8", errors="replace")
    except (KeyError, zipfile.BadZipFile, OSError, UnicodeDecodeError) as exc:
        raise KnowledgeValidationError("unable to parse uploaded DOCX") from exc
    text_runs = re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", document_xml, flags=re.DOTALL)
    text = "\n".join(html.unescape(re.sub(r"\s+", " ", run)).strip() for run in text_runs if run.strip())
    if not text.strip():
        raise KnowledgeValidationError("uploaded DOCX contains no extractable text")
    return text.strip()


def _unescape_pdf_literal(value: str) -> str:
    return (
        value.replace(r"\(", "(")
        .replace(r"\)", ")")
        .replace(r"\\", "\\")
        .replace(r"\n", "\n")
        .replace(r"\r", "\r")
        .replace(r"\t", "\t")
    )


def _parse_pdf_upload(payload: dict[str, Any]) -> str:
    raw = _uploaded_bytes(payload, source_kind="pdf")
    if not raw.lstrip().startswith(b"%PDF"):
        raise KnowledgeValidationError("uploaded PDF has invalid header")
    decoded = raw.decode("latin-1", errors="ignore")
    literals = [_unescape_pdf_literal(match) for match in re.findall(r"\(((?:\\.|[^\\)])*)\)", decoded)]
    text = " ".join(re.sub(r"\s+", " ", literal).strip() for literal in literals if literal.strip())
    if not text.strip():
        raise KnowledgeValidationError("uploaded PDF contains no extractable text")
    return text.strip()


def _first_non_empty_line(body: str) -> str:
    for line in body.splitlines():
        cleaned = line.strip().strip("#").strip()
        if cleaned:
            return cleaned[:120]
    return "Imported knowledge"


def _markdown_sections(body: str) -> list[dict[str, Any]]:
    headings: list[tuple[str, int]] = []
    for match in re.finditer(r"(?m)^(#{2,6})\s+(.+?)\s*$", body):
        headings.append((match.group(2).strip(), match.end()))
    sections: list[dict[str, Any]] = []
    for index, (heading, start) in enumerate(headings):
        end = headings[index + 1][1] if index + 1 < len(headings) else len(body)
        preview = re.sub(r"\s+", " ", body[start:end].strip())[:240]
        sections.append({"heading": heading, "preview": preview})
    return sections


def _text_sections(body: str) -> list[dict[str, Any]]:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", body) if paragraph.strip()]
    return [{"heading": f"Section {index + 1}", "preview": re.sub(r"\s+", " ", paragraph)[:240]} for index, paragraph in enumerate(paragraphs[:12])]


def _safe_keywords(*values: str) -> list[str]:
    words: list[str] = []
    for value in values:
        for match in re.finditer(r"[A-Za-zА-Яа-я0-9_-]{3,40}", value):
            word = match.group(0).lower()
            if word not in words:
                words.append(word)
            if len(words) >= 8:
                return words
    return words


def _parse_import_payload(payload: dict[str, Any], remote_fetcher: KnowledgeRemoteImportFetcher | None = None) -> tuple[dict[str, Any], str]:
    source_kind = str(payload.get("source_kind") or "text").lower()
    remote_source: dict[str, Any] | None = None
    remote_body_format: str | None = None
    if source_kind in REMOTE_IMPORT_SOURCE_KINDS:
        content = (remote_fetcher or KnowledgeRemoteImportFetcher()).fetch(payload)
        source_name = content.source_name
        raw_body = content.body
        remote_source = content.remote_source
        remote_body_format = content.body_format
    elif source_kind not in LOCAL_IMPORT_SOURCE_KINDS:
        raise KnowledgeValidationError(f"unsupported import source_kind: {source_kind}")
    else:
        source_name = str(payload.get("source_name") or payload.get("title") or "manual text")
        raw_body = str(payload.get("body") or "")
    if source_kind == "html":
        parsed_body = _strip_html(raw_body)
    elif source_kind == "docx":
        parsed_body = _parse_docx_upload(payload)
    elif source_kind == "pdf":
        parsed_body = _parse_pdf_upload(payload)
    elif remote_body_format == "html":
        parsed_body = _strip_html(raw_body)
    else:
        parsed_body = raw_body.strip()
    if not parsed_body:
        raise KnowledgeValidationError("import body is required")
    body_format = (
        remote_body_format
        if remote_body_format in KNOWLEDGE_BODY_FORMATS
        else ("markdown" if source_kind == "markdown" else ("html" if source_kind == "html" else "plain_text"))
    )
    title_match = re.search(r"(?m)^#\s+(.+?)\s*$", parsed_body) if body_format == "markdown" else None
    detected_title = str(payload.get("title") or (title_match.group(1).strip() if title_match else "") or _first_non_empty_line(parsed_body))
    sections = _markdown_sections(parsed_body) if body_format == "markdown" else _text_sections(parsed_body)
    ai_requested = bool(payload.get("ai_enrichment_enabled"))
    preview = {
        "source_kind": source_kind,
        "source_name": source_name,
        "body_format": body_format,
        "detected_title": detected_title,
        "word_count": len(re.findall(r"\S+", parsed_body)),
        "section_count": len(sections),
        "sections": sections,
        "ai_enrichment": {
            "enabled": ai_requested,
            "status": "blocked_pending_policy" if ai_requested else "disabled",
            "proposals": [],
        },
    }
    if remote_source is not None:
        preview["remote_source"] = remote_source
    return preview, parsed_body


class KnowledgeIngestionService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        embedding_transport: Transport | None = None,
        remote_fetcher: KnowledgeRemoteImportFetcher | None = None,
    ):
        self.session = session
        self.embedding_transport = embedding_transport
        self.remote_fetcher = remote_fetcher

    def preview_import(self, payload: dict[str, Any]) -> dict[str, Any]:
        preview, _parsed_body = _parse_import_payload(payload, self.remote_fetcher)
        return preview

    async def create_drafts_from_import(self, payload: dict[str, Any], *, actor_id: str | None, actor_role: str = "admin") -> dict[str, Any]:
        preview, parsed_body = _parse_import_payload(payload, self.remote_fetcher)
        ingestion_source_kind = {
            "url": "external_url",
            "git": "git_repo",
        }.get(str(preview["source_kind"]), preview["source_kind"])
        result = await self.ingest_text(
            {
                **payload,
                "source_kind": ingestion_source_kind,
                "source_name": preview["source_name"],
                "title": payload.get("title") or preview["detected_title"],
                "body_format": preview["body_format"],
                "body": parsed_body,
            },
            actor_id=actor_id,
            actor_role=actor_role,
        )
        segmentation: dict[str, Any] = {
            "enabled": False,
            "status": "disabled",
            "profile_code": str(payload.get("segmentation_profile_code") or "default-auto"),
        }
        if bool(payload.get("auto_segment_after_import")):
            segment_result = await KnowledgeSegmentationService(self.session).auto_segment(
                result["item"]["item_id"],
                {
                    "version_id": result["version"]["version_id"],
                    "profile_code": segmentation["profile_code"],
                },
                actor_id=actor_id,
                actor_role=actor_role,
            )
            segmentation = {
                "enabled": True,
                "status": "completed",
                "profile_code": segmentation["profile_code"],
                **segment_result,
            }
        ai_enrichment = dict(preview["ai_enrichment"])
        if ai_enrichment["enabled"]:
            proposals = await self._create_ai_enrichment_proposals(preview, result, actor_id=actor_id, actor_role=actor_role)
            ai_enrichment = {**ai_enrichment, "status": "review_required", "proposals": proposals}
        indexing = await self._index_after_import_if_enabled(result, actor_id=actor_id, actor_role=actor_role)
        return {"preview": preview, "ai_enrichment": ai_enrichment, "segmentation": segmentation, "indexing": indexing, **result}

    async def _create_ai_enrichment_proposals(
        self,
        preview: dict[str, Any],
        result: dict[str, Any],
        *,
        actor_id: str | None,
        actor_role: str,
    ) -> list[dict[str, Any]]:
        item = result["item"]
        version = result["version"]
        job = result["job"]
        title = str(item.get("title") or preview.get("detected_title") or item.get("slug") or "Imported knowledge")
        sections = preview.get("sections") if isinstance(preview.get("sections"), list) else []
        section_headings = [str(section.get("heading") or "") for section in sections if isinstance(section, dict)]
        keywords = _safe_keywords(title, " ".join(section_headings))
        source_ref = str(job.get("job_id") or item["item_id"])
        graph_key = f"concept:import-{_slug_from_title(str(item.get('slug') or title))}"
        service = KnowledgeAiProposalService(self.session)
        proposal_payloads = [
            {
                "proposal_type": "summary",
                "target_kind": "item",
                "target_ref": item["item_id"],
                "title": f"Summary proposal for {title}",
                "rationale": "Imported draft can be enriched with a reviewed summary before publication.",
                "proposed_payload": {
                    "summary": f"Imported draft for {title}",
                    "version_id": version["version_id"],
                    "source": "import_enrichment_seed",
                },
                "confidence_score": 0.45,
            },
            {
                "proposal_type": "tags",
                "target_kind": "item",
                "target_ref": item["item_id"],
                "title": f"Tag proposal for {title}",
                "rationale": "Imported headings suggest candidate tags for reviewer approval.",
                "proposed_payload": {"tags": keywords, "version_id": version["version_id"], "source": "import_enrichment_seed"},
                "confidence_score": 0.4,
            },
            {
                "proposal_type": "glossary_term",
                "target_kind": "item",
                "target_ref": item["item_id"],
                "title": f"Glossary proposal for {title}",
                "rationale": "The imported title can seed a glossary term for governed review.",
                "proposed_payload": {
                    "term": title,
                    "definition": f"Review glossary definition for {title}",
                    "version_id": version["version_id"],
                    "source": "import_enrichment_seed",
                },
                "confidence_score": 0.35,
            },
            {
                "proposal_type": "graph_node",
                "target_kind": "graph",
                "target_ref": item["item_id"],
                "title": f"Graph node proposal for {title}",
                "rationale": "Imported draft can be linked into the knowledge graph after review.",
                "proposed_payload": {
                    "graph": {
                        "nodes": [
                            {
                                "stable_key": graph_key,
                                "node_type": "concept",
                                "label": title,
                                "linked_item_id": item["item_id"],
                                "visibility": item.get("visibility") or "support_internal",
                            }
                        ],
                        "edges": [],
                    },
                    "version_id": version["version_id"],
                    "source": "import_enrichment_seed",
                },
                "confidence_score": 0.5,
            },
            {
                "proposal_type": "duplicate",
                "target_kind": "item",
                "target_ref": item["item_id"],
                "title": f"Duplicate review proposal for {title}",
                "rationale": "Imported draft should be checked for duplicate knowledge before publication.",
                "proposed_payload": {
                    "duplicate_review": {
                        "item_id": item["item_id"],
                        "candidate_count": 0,
                        "signals": ["title_similarity_review_required"],
                    },
                    "version_id": version["version_id"],
                    "source": "import_enrichment_seed",
                },
                "confidence_score": 0.3,
            },
        ]
        proposals: list[dict[str, Any]] = []
        for proposal_payload in proposal_payloads:
            proposals.append(
                await service.create(
                    {
                        **proposal_payload,
                        "visibility": item.get("visibility") or "support_internal",
                        "source_kind": "knowledge_import",
                        "source_ref": source_ref,
                    },
                    actor_id=actor_id,
                    actor_role=actor_role,
                )
            )
        return proposals

    async def _index_after_import_if_enabled(self, result: dict[str, Any], *, actor_id: str | None, actor_role: str) -> dict[str, Any]:
        service = KnowledgeEmbeddingService(self.session, transport=self.embedding_transport)
        status = await service.status()
        if not bool(status.get("vector_enabled")):
            return {"enabled": False, "status": "disabled", "reason": "vector_indexing_disabled"}
        index_result = await service.reindex_item(
            str(result["item"]["item_id"]),
            {"version_id": result["version"]["version_id"]},
            actor_id=actor_id,
            actor_role=actor_role,
        )
        return {"enabled": True, "status": index_result["job"]["status"], **index_result}

    async def ingest_text(self, payload: dict[str, Any], *, actor_id: str | None, actor_role: str = "admin") -> dict[str, Any]:
        repo = KnowledgeRepo(self.session)
        space = await repo.get_space_by_code(str(payload.get("space_code") or ""))
        if space is None:
            raise ValueError("knowledge space not found")
        source_kind = str(payload.get("source_kind") or "text")
        if source_kind not in KNOWLEDGE_INGESTION_SOURCE_KINDS:
            raise KnowledgeValidationError(f"unsupported ingestion source_kind: {source_kind}")
        job = KnowledgeIngestionJob(
            job_id=_new_id(),
            space_id=space.space_id,
            source_kind=source_kind,
            source_name=str(payload.get("source_name") or payload.get("title") or "manual text"),
            status="queued",
            created_by=actor_id,
        )
        self.session.add(job)
        await self.session.flush()
        item = await repo.create_item_draft(
            {
                "space_code": space.code,
                "slug": payload.get("slug") or _slug_from_title(str(payload.get("title") or payload.get("source_name") or "knowledge")),
                "item_type": payload.get("item_type") or "document",
                "title": payload.get("title") or payload.get("source_name") or "Imported knowledge",
                "summary": payload.get("summary"),
                "visibility": payload.get("visibility") or "support_internal",
                "source_kind": "imported_document",
                "source_ref": payload.get("source_name"),
                "owner_actor_id": payload.get("owner_actor_id") or actor_id,
                "reviewer_actor_id": payload.get("reviewer_actor_id") or actor_id,
            },
            actor_id=actor_id,
            actor_role=actor_role,
        )
        version = await repo.create_version(
            item["item_id"],
            {
                "title": item["title"],
                "summary": item.get("summary"),
                "body_format": str(payload.get("body_format") or ("markdown" if str(payload.get("source_kind") or "").lower() == "markdown" else "plain_text")),
                "body": str(payload.get("body") or ""),
                "change_summary": "Imported draft",
            },
            actor_id=actor_id,
            actor_role=actor_role,
        )
        job.status = "review_required"
        job.created_item_id = item["item_id"]
        job.created_version_id = version["version_id"]
        job.stats_json = {"chunk_count": len((payload.get("body") or "").split("\n\n"))}
        await self.session.flush()
        return {"job": {"job_id": job.job_id, "status": job.status}, "item": item, "version": version, "chunk_count": max(1, job.stats_json["chunk_count"])}

    async def fail_job_redacted(self, *, space_code: str, source_name: str, error: BaseException, actor_id: str | None) -> dict[str, Any]:
        return {"job_id": None, "status": "failed", "source_name": source_name, "error_message_redacted": _redact_error(error)}
