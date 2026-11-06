"""Transactional shared fragment library backed by retained author assets."""
from copy import deepcopy
from sqlalchemy import select, func
from app.db.request_scenario_models import RequestStudioFragment, RequestStudioFragmentAsset, RequestStudioAsset
from app.repos.request_scenario_repo import ScenarioAdminError, serialize
from tickets.request_scenario_assets import copy_material_sources, clone_material_assets, material_references, asset_metadata
from tickets.request_scenario_fragments import extract_fragment, insert_fragment, FragmentDependencyError
from web_api.dto.request_scenario import ScenarioDraftDefinition
from web_api.dto.request_scenario_admin import ScenarioSave


def summary(row):
    return {'id': row.id, 'title': row.title, 'revision': row.revision,
            'block_count': len(row.definition['blocks']), 'source_title': row.source_title, 'archived': row.archived}


async def list_fragments(repo):
    rows = (await repo.session.scalars(select(RequestStudioFragment).where(RequestStudioFragment.archived.is_(False))
            .order_by(RequestStudioFragment.title, RequestStudioFragment.id).limit(500))).all()
    total = await repo.session.scalar(select(func.count()).select_from(RequestStudioFragment).where(RequestStudioFragment.archived.is_(False)))
    return {'items': [summary(row) for row in rows], 'total': total}


async def get_fragment(repo, identifier, *, lock=False):
    stmt = select(RequestStudioFragment).where(RequestStudioFragment.id == identifier)
    if lock:
        stmt = stmt.with_for_update()
    row = await repo.session.scalar(stmt)
    if not row:
        raise ScenarioAdminError('FRAGMENT_NOT_FOUND', 404)
    return row


def detail(row):
    return {'fragment': summary(row), 'definition': deepcopy(row.definition),
            'external_dependencies': deepcopy(row.external_dependencies)}


async def create_fragment(repo, payload):
    current, _ = await repo.detail(payload.source_scenario_id)
    await repo._service_lock(current.service_code)
    source, draft = await repo.detail(payload.source_scenario_id, lock=True)
    if source.archived or draft.revision != payload.source_revision:
        raise ScenarioAdminError('REVISION_CONFLICT', 409)
    raw, dependencies = extract_fragment(draft.definition, payload.block_ids)
    sources = await copy_material_sources(repo.session, source.id, raw)
    fragment = RequestStudioFragment(title=payload.title, source_scenario_id=source.id,
        source_title=source.title, source_revision=draft.revision, revision=1, definition=raw,
        external_dependencies=dependencies, archived=False, created_by=repo.auth.actor_id)
    repo.session.add(fragment)
    await repo.session.flush()
    raw, rebinding = await clone_material_assets(repo.session, source.id, raw, sources, repo.auth.actor_id)
    fragment.definition = raw
    for metadata in rebinding.values():
        repo.session.add(RequestStudioFragmentAsset(fragment_id=fragment.id, asset_id=metadata['asset_id']))
    await repo.session.flush()
    await repo._audit('scenario_fragment', fragment.id, 'create', None, summary(fragment))
    return detail(fragment)


async def archive_fragment(repo, identifier, revision):
    fragment = await get_fragment(repo, identifier, lock=True)
    if fragment.archived or fragment.revision != revision:
        raise ScenarioAdminError('REVISION_CONFLICT', 409)
    before = summary(fragment)
    fragment.archived = True
    fragment.revision += 1
    await repo.session.flush()
    await repo._audit('scenario_fragment', fragment.id, 'archive', before, summary(fragment))
    return detail(fragment)


async def insert_saved_fragment(repo, identifier, fragment_id, payload):
    fragment = await get_fragment(repo, fragment_id, lock=True)
    if fragment.archived or fragment.revision != payload.fragment_revision:
        raise ScenarioAdminError('FRAGMENT_REVISION_CONFLICT', 409)
    current, _ = await repo.detail(identifier)
    await repo._service_lock(current.service_code)
    row, draft = await repo.detail(identifier, lock=True)
    if row.archived or draft.revision != payload.revision:
        raise ScenarioAdminError('REVISION_CONFLICT', 409)
    if draft.definition.get('schema_version', 1) < 4:
        raise ScenarioAdminError('UPGRADE_REQUIRED', 409)
    mapping = payload.mappings.model_dump()
    # Resolve mappings and validate before writing or cloning anything.
    candidate, candidate_ids = insert_fragment(draft.definition, fragment.definition, position=payload.position, mappings=mapping)
    refs = list(material_references(fragment.definition))
    ids = {ref['asset_id'] for ref in refs}
    links = set((await repo.session.scalars(select(RequestStudioFragmentAsset.asset_id).where(
        RequestStudioFragmentAsset.fragment_id == fragment.id))).all())
    if ids != links:
        raise ScenarioAdminError('ATTACHMENT_REFERENCE_INVALID', 409)
    sources = {}
    for identifier_ in ids:
        asset = await repo.session.get(RequestStudioAsset, identifier_)
        if not asset or asset.removed_at or asset.scenario_id != fragment.source_scenario_id or any(asset_metadata(asset) != ref for ref in refs if ref['asset_id'] == identifier_):
            raise ScenarioAdminError('ATTACHMENT_REFERENCE_INVALID', 409)
        sources[identifier_] = asset
    # A policy mapping retains its actual kind, including final route overrides.
    from tickets.request_scenario_processing import scenario_sla_reference_issues
    selected = ScenarioDraftDefinition.model_validate(candidate)
    selected = selected.model_copy(update={'blocks': [block for block in selected.blocks if block.id in candidate_ids]})
    issues = await scenario_sla_reference_issues(repo.session, selected)
    if issues:
        raise ValueError({issue['path']: issue['message'] for issue in issues})
    fragment_copy, _ = await clone_material_assets(repo.session, row.id, fragment.definition, sources, repo.auth.actor_id)
    updated, inserted = insert_fragment(draft.definition, fragment_copy, position=payload.position, mappings=mapping)
    result = await repo.save(row.id, ScenarioSave(revision=draft.revision,
        definition=ScenarioDraftDefinition.model_validate(updated)))
    await repo._audit('scenario_fragment', fragment.id, 'insert', None,
                      {'scenario_id': row.id, 'fragment_revision': fragment.revision, 'block_ids': inserted})
    return {**result, 'inserted_block_ids': inserted}
