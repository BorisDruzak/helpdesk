"""Admin-only fragment APIs, sharing Studio auth and transaction handling."""
from pydantic import TypeAdapter
from aiohttp import web
from auth.middleware import require_auth
from web_api.dto.request_scenario_admin import Identifier, RevisionInput
from web_api.dto.request_scenario_fragments import FragmentCreate, FragmentInsert
from web_api.request_scenario_admin_handlers import _run, _payload, _id
from tickets.request_scenario_fragment_library import list_fragments, create_fragment, get_fragment, detail, archive_fragment, insert_saved_fragment


def _fragment_id(request):
    return TypeAdapter(Identifier).validate_python(request.match_info['fragment_id'])


@require_auth('admin', 'auditor')
async def handle_fragment_list(request):
    return await _run(request, lambda repo: list_fragments(repo))


@require_auth('admin')
async def handle_fragment_create(request):
    async def operation(repo):
        return await create_fragment(repo, await _payload(request, FragmentCreate))
    return await _run(request, operation, write=True)


@require_auth('admin', 'auditor')
async def handle_fragment_detail(request):
    async def operation(repo):
        return detail(await get_fragment(repo, _fragment_id(request)))
    return await _run(request, operation)


@require_auth('admin')
async def handle_fragment_archive(request):
    async def operation(repo):
        payload = await _payload(request, RevisionInput)
        return await archive_fragment(repo, _fragment_id(request), payload.revision)
    return await _run(request, operation, write=True)


@require_auth('admin')
async def handle_fragment_insert(request):
    async def operation(repo):
        return await insert_saved_fragment(repo, _id(request), _fragment_id(request), await _payload(request, FragmentInsert))
    return await _run(request, operation, write=True)
