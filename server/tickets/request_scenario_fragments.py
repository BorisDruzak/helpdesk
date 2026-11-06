"""Bounded fragment extraction and safe insertion into an author-owned draft."""
from copy import deepcopy
from uuid import uuid4

from web_api.dto.request_scenario import ScenarioDraftDefinition


class FragmentDependencyError(ValueError):
    def __init__(self, dependencies):
        self.dependencies = dependencies
        super().__init__('Fragment dependencies require explicit mappings')


def _conditions(value):
    if isinstance(value, dict):
        if value.get('source') == 'answer' and isinstance(value.get('field'), str):
            yield value
        for child in value.values():
            yield from _conditions(child)
    elif isinstance(value, list):
        for child in value:
            yield from _conditions(child)


def _validate_field_identities(blocks):
    fields = [field for block in blocks for field in block.get("fields", [])]
    keys = [field["key"] for field in fields]
    facts = [(field.get("process_mapping") or {}).get("fact_key") or field["key"] for field in fields]
    aliases = [alias for field in fields for alias in field.get("aliases", [])]
    if len(keys) != len(set(keys)) or len(facts) != len(set(facts)) or len(aliases) != len(set(aliases)) or set(aliases) & (set(keys) | set(facts)) or any(fact in set(keys) - {field["key"]} for field, fact in zip(fields, facts)):
        raise ValueError("Ambiguous field, fact or alias identifiers")
    return fields


def extract_fragment(definition, block_ids):
    source = ScenarioDraftDefinition.model_validate(deepcopy(definition)).model_dump(mode='json')
    ids = set(block_ids)
    blocks = [block for block in source['blocks'] if block['id'] in ids]
    if not ids or len(ids) != len(block_ids) or len(blocks) != len(ids):
        raise ValueError('Select existing unique blocks')
    selected_fields = _validate_field_identities(blocks)
    fields = {field['key'] for field in selected_fields}
    fact_labels = {(field.get('process_mapping') or {}).get('fact_key') or field['key']: field['label'] for field in selected_fields}
    deps = {('fact', key) for key in fact_labels}
    for block in blocks:
        for edge in block['transitions']:
            if edge['to'] not in ids:
                deps.add(('block', edge['to']))
        block['transitions'] = [edge for edge in block['transitions'] if edge['to'] in ids]
        for condition in _conditions(block):
            if condition['field'] not in fields:
                deps.add(('field', condition['field']))
        for edge in block['transitions']:
            processing = edge.get('processing') or {}
            for kind in ('route', 'sla_profile'):
                if processing.get(kind):
                    deps.add((kind, processing[kind]))
        if block['kind'] in {'sla', 'submit_ticket'}:
            for kind in ('sla_profile', 'policy_ref'):
                if block.get(kind):
                    deps.add((kind, block[kind]))
    source_profiles = (source.get('processing') or {}).get('sla_profiles', {})
    for kind, key in list(deps):
        if kind == 'sla_profile':
            calendar = source_profiles.get(key, {}).get('calendar_id')
            if calendar is not None:
                deps.add(('calendar', str(calendar)))
    source['blocks'] = blocks
    source['entry_block_id'] = None
    source['entry_points'] = []
    source['editor_layout']['positions'] = {key: val for key, val in source['editor_layout']['positions'].items() if key in ids}
    return source, [{'kind': kind, 'key': key, 'label': fact_labels.get(key, key) if kind == 'fact' else key} for kind, key in sorted(deps)]


def _new_key(prefix):
    return prefix + '_' + uuid4().hex


def insert_fragment(destination, fragment, *, position, mappings):
    target = ScenarioDraftDefinition.model_validate(deepcopy(destination)).model_dump(mode='json')
    if target['schema_version'] < 4:
        raise ValueError('UPGRADE_REQUIRED')
    _validate_field_identities(target['blocks'])
    source, dependencies = extract_fragment(fragment, [block['id'] for block in fragment['blocks']])
    available_fields = {field['key'] for block in target['blocks'] for field in block.get('fields', [])}
    processing = target.get('processing') or {}
    targets = {'field': available_fields, 'route': set(processing.get('routes', {})),
               'sla_profile': set(processing.get('sla_profiles', {}))}
    names = {'field': 'fields', 'route': 'routes', 'sla_profile': 'sla_profiles', 'policy_ref': 'policy_refs', 'calendar': 'calendars', 'fact': 'facts'}
    resolved, missing = {}, []
    for dep in dependencies:
        kind, key = dep['kind'], dep['key']
        if kind == 'block':
            continue
        value = mappings.get(names[kind], {}).get(key)
        if not value or kind in targets and value not in targets[kind]:
            missing.append(dep)
        else:
            resolved[(kind, key)] = value
    target_fields = _validate_field_identities(target['blocks'])
    occupied = {field['key'] for field in target_fields} | {alias for field in target_fields for alias in field.get('aliases', [])}
    occupied |= {(field.get('process_mapping') or {}).get('fact_key') or field['key'] for field in target_fields}
    fact_values = [value for (kind, _), value in resolved.items() if kind == 'fact']
    duplicates = {value for value in fact_values if fact_values.count(value) > 1}
    for dep in dependencies:
        if dep['kind'] == 'fact' and (resolved.get(('fact', dep['key'])) in occupied or resolved.get(('fact', dep['key'])) in duplicates):
            missing.append(dep)
    for kind, key in list(resolved):
        if kind == 'sla_profile':
            source_profile = (source.get('processing') or {}).get('sla_profiles', {}).get(key, {})
            source_calendar = source_profile.get('calendar_id')
            if source_calendar is not None:
                actual = processing.get('sla_profiles', {}).get(resolved[(kind, key)], {}).get('calendar_id')
                mapped = resolved.get(('calendar', str(source_calendar)))
                if mapped is not None and mapped != actual:
                    missing.append({'kind': 'calendar', 'key': str(source_calendar), 'label': str(source_calendar)})
    if missing:
        raise FragmentDependencyError(missing)
    block_keys = {block['id']: _new_key('block') for block in source['blocks']}
    field_keys = {field['key']: _new_key('field') for block in source['blocks'] for field in block.get('fields', [])}
    points = source.get('editor_layout', {}).get('positions', {})
    min_x = min((point['x'] for point in points.values()), default=0)
    min_y = min((point['y'] for point in points.values()), default=0)
    layout = target.setdefault('editor_layout', {}).setdefault('positions', {})
    for block in source['blocks']:
        old_id = block['id']
        block['id'] = block_keys[old_id]
        point = points.get(old_id, {'x': min_x, 'y': min_y})
        layout[block['id']] = {'x': max(-100000, min(100000, position['x'] + point['x'] - min_x)),
                               'y': max(-100000, min(100000, position['y'] + point['y'] - min_y))}
        for field in block.get('fields', []):
            old_key = field['key']
            field['key'] = field_keys[old_key]
            mapping = field.get('process_mapping') or {}
            old_fact = mapping.get('fact_key') or old_key
            mapping['fact_key'] = resolved[('fact', old_fact)]
            field['process_mapping'] = mapping
            field['aliases'] = [_new_key('alias') for _ in field.get('aliases', [])]
        for condition in _conditions(block):
            key = condition['field']
            condition['field'] = field_keys.get(key) or resolved[('field', key)]
        for edge in block['transitions']:
            edge['to'] = block_keys[edge['to']]
            if edge.get('button'):
                edge['button']['key'] = _new_key('action')
            settings = edge.get('processing') or {}
            for kind in ('route', 'sla_profile'):
                if settings.get(kind):
                    settings[kind] = resolved[(kind, settings[kind])]
        if block['kind'] in {'sla', 'submit_ticket'}:
            for kind in ('sla_profile', 'policy_ref'):
                if block.get(kind):
                    block[kind] = resolved[(kind, block[kind])]
    target['blocks'].extend(source['blocks'])
    _validate_field_identities(target['blocks'])
    definition = ScenarioDraftDefinition.model_validate(target)
    from tickets.request_scenario_validation import validate_scenario
    inserted = list(block_keys.values())
    invalid = [issue for issue in validate_scenario(definition) if issue.code in {'incompatible_condition', 'unknown_field'}
               and any(issue.path.startswith(f'blocks.{key}.') for key in inserted)]
    if invalid:
        raise FragmentDependencyError([dep for dep in dependencies if dep['kind'] == 'field'])
    return definition.model_dump(mode='json'), inserted
