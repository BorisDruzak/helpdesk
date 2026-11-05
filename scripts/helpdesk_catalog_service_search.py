"""Plan/apply two requester services through canonical audited Studio publication.

No standalone CLI or credentials. Caller owns staging host, release and verified
backup guards. Existing draft/version/ticket history is not rewritten.
"""
from copy import deepcopy

from sqlalchemy import or_, select, text

from scripts.helpdesk_phase1_catalog import OTHER_KEY, fingerprint, read_catalog, require_target

NEW_KEYS = ('requester_electronic_budget_20261105', 'requester_eis_20261105')


def build_definitions(source, service_code):
    if source.get('scenario_key') != 'phase1_business_system' or source.get('schema_version') != 3:
        raise ValueError('The current published information-system intake is required')
    definitions = []
    specs = [
        (NEW_KEYS[0], 'Электронный бюджет', 'Электронный бюджет', ['электронный бюджет', 'ЭБ', 'бюджет']),
        (NEW_KEYS[1], 'ЕИС — Единая информационная система в сфере закупок', 'ЕИС', ['ЕИС', 'закупки', 'единая информационная система', 'еис закупки']),
    ]
    for key, title, short, aliases in specs:
        d = deepcopy(source)
        d.update(scenario_key=key, title=title, description=f'Помощь с входом, электронной подписью и ошибками работы: {short}.',
            service_code=service_code, offering_full_code='', category_id=None, publish_offering=False)
        d['process_binding']['request_template_key'] = ''
        request = next(block for block in d['blocks'] if block['id'] == 'request')
        request['title'] = f'Опишите проблему: {short}'
        request['fields'] = [
            {'key': 'request_details', 'type': 'textarea', 'label': 'Что произошло и какая помощь нужна?', 'required': True,
             'help_text': 'Укажите раздел системы, ваши действия и текст ошибки. Не сообщайте пароли, PIN, коды входа, ключи подписи или содержимое служебных документов.'},
            {'key': 'error_text', 'type': 'textarea', 'label': 'Текст или код ошибки', 'required': False},
            {'key': 'first_seen', 'type': 'text', 'label': 'Когда появилась проблема?', 'required': False},
        ]
        d['entry_points'] = [
            {'key': 'login', 'title': f'{short}: не удаётся войти', 'synonyms': aliases + [f'вход {short}', f'доступ {short}'], 'reported_symptom': f'Не удаётся войти: {short}'},
            {'key': 'signature', 'title': f'{short}: ошибка электронной подписи', 'synonyms': [f'подпись {short}', f'сертификат {short}', f'не подписывается {short}'], 'reported_symptom': f'Ошибка электронной подписи: {short}'},
            {'key': 'error', 'title': f'{short}: ошибка работы системы', 'synonyms': [f'ошибка {short}', f'не работает {short}'], 'reported_symptom': f'Ошибка работы системы: {short}'},
        ]
        for entry in d['entry_points']:
            entry.update(enabled=True, visibility='public', category_id=None, target_block_id='request', description='Опишите проблему — специалист поддержки проверит её и поможет с дальнейшими действиями.')
        definitions.append(d)
    return definitions


async def publish_additions(session_factory, auth, *, apply=False, expected_fingerprint=None):
    from app.db.request_scenario_models import RequestStudioScenario, RequestStudioScenarioVersion
    from app.repos.request_scenario_repo import RequestScenarioRepo
    from app.repos.service_catalog_repo import ServiceCatalogRepo
    from tickets.request_scenario_publication import ScenarioPublicationService
    from tickets.service_catalog_runtime import ServiceCatalogRuntimeResolver
    from web_api.dto.request_scenario_admin import ScenarioPublish

    if not auth.is_admin() or not auth.actor_id:
        raise ValueError('A trusted authenticated admin context is required')
    async with session_factory() as session:
        async with session.begin():
            require_target(await session.scalar(text('SELECT current_database()')))
            if apply:
                # Same canonical source-freeze order as the existing reviewed publisher.
                await session.execute(text('SELECT pg_advisory_xact_lock(20261105, 11)'))
                locked_codes = set((await session.scalars(select(RequestStudioScenario.service_code).where(or_(
                    RequestStudioScenario.scenario_key.in_(['phase1_business_system', OTHER_KEY]), RequestStudioScenario.title == 'ФРГУ 3.0')))).all())
                lock_repo = RequestScenarioRepo(session, auth)
                for code in sorted(locked_codes):
                    await lock_repo._service_lock(code)
                await ScenarioPublicationService(lock_repo)._freeze_sources(write_offering=True)
                await session.execute(text('LOCK TABLE request_studio_scenarios, request_studio_drafts, request_studio_scenario_versions IN SHARE ROW EXCLUSIVE MODE'))
            snapshot = await read_catalog(session)
            scenarios = snapshot[RequestStudioScenario.__tablename__]
            versions = {row['id']: row for row in snapshot[RequestStudioScenarioVersion.__tablename__]}
            source = next(row for row in scenarios if row['scenario_key'] == 'phase1_business_system' and row['enabled'] and not row['archived'])
            system = next(row for row in scenarios if row['title'] == 'ФРГУ 3.0' and row['enabled'] and not row['archived'])
            other = next(row for row in scenarios if row['scenario_key'] == OTHER_KEY and row['enabled'] and not row['archived'])
            if apply and not {source['service_code'], system['service_code'], other['service_code']}.issubset(locked_codes):
                raise ValueError('Service bindings changed while locking; obtain a fresh plan')
            definitions = build_definitions(versions[source['published_version_id']]['definition'], system['service_code'])
            current_hash = fingerprint(snapshot)
            if not apply:
                return {'fingerprint': current_hash, 'definitions': definitions, 'fallback_offering': other['offering_full_code'], 'applied': False}
            if not expected_fingerprint or current_hash != expected_fingerprint:
                raise ValueError('Publication inputs changed; obtain a fresh plan')
            repo = RequestScenarioRepo(session, auth)
            publisher = ScenarioPublicationService(repo)
            published = []
            for raw in definitions:
                created = await repo.create_service(raw)
                row, draft = created['scenario'], created['draft']
                if row['archived']:
                    raise ValueError('An existing new-service map is archived')
                if row['published_version_id']:
                    existing = await session.get(RequestStudioScenarioVersion, row['published_version_id'])
                    if not row['enabled'] or existing.definition != draft['definition']:
                        raise ValueError('Existing publication differs from the prepared map')
                    published.append({'title': raw['title'], 'changed': False})
                    continue
                preview = await publisher.preview(row['id'], draft['revision'])
                if not preview['readiness']['can_publish']:
                    raise ValueError('The new service did not pass canonical publication readiness')
                await publisher.publish(row['id'], ScenarioPublish(revision=draft['revision'], confirm=True, confirmation_token=preview['confirmation_token']))
                published.append({'title': raw['title'], 'changed': True})
            catalog = ServiceCatalogRepo(session)
            fallback = await catalog.get_offering_by_full_code(other['offering_full_code'])
            metadata = deepcopy(fallback.get('metadata') or {})
            wanted = {'entry_point_key': 'not_found'}
            changed = metadata.get('requester_fallback') != wanted
            if changed:
                metadata['requester_fallback'] = wanted
                await catalog.upsert_offering_draft({**fallback, 'metadata': metadata}, actor_id=auth.actor_id, actor_role=auth.actor_role)
                await catalog.publish_offering(fallback['full_code'], actor_id=auth.actor_id, actor_role=auth.actor_role)
            public = await ServiceCatalogRuntimeResolver(session).current_catalog_for_requester()
            if public['fallback']['full_code'] != fallback['full_code'] or public['fallback'].get('entry_point_key') != 'not_found':
                raise ValueError('Fallback is not currently publicly executable')
            return {'applied': True, 'scenarios': published, 'fallback_changed': changed, 'fallback': public['fallback']['full_code']}
