"""Bounded interchange of the existing scenario definition, never another store."""
import json
import yaml
from yaml.events import AliasEvent, CollectionStartEvent, CollectionEndEvent
from web_api.dto.request_scenario import ScenarioDraftDefinition, ScenarioDefinition
from tickets.request_scenario_validation import validate_scenario


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if not isinstance(key, str) or key in result:
            raise ValueError("Document keys must be unique strings")
        result[key] = value
    return result


class DocumentLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node):
    return _unique_pairs([(loader.construct_object(key), loader.construct_object(value)) for key, value in node.value])


DocumentLoader.add_constructor("tag:yaml.org,2002:map", _mapping)
# YAML timestamps must retain the string representation used by JSON and the DTO.
DocumentLoader.yaml_implicit_resolvers = {key: [item for item in values if item[0] != "tag:yaml.org,2002:timestamp"]
                                         for key, values in DocumentLoader.yaml_implicit_resolvers.items()}


def parse_scenario_document(content, format):
    if not isinstance(content, str) or len(content.encode("utf-8")) > 1048576:
        raise ValueError("Document exceeds byte limit")
    try:
        if format == "json":
            raw = json.loads(content, object_pairs_hook=_unique_pairs,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite number")))
        elif format == "yaml":
            depth = count = 0
            for event in yaml.parse(content, Loader=DocumentLoader):
                count += 1
                if isinstance(event, AliasEvent) or getattr(event, "anchor", None):
                    raise ValueError("Aliases and anchors are not supported")
                if isinstance(event, CollectionStartEvent):
                    depth += 1
                if isinstance(event, CollectionEndEvent):
                    depth -= 1
                if depth > 32 or count > 40000:
                    raise ValueError("Document exceeds structure limit")
            raw = yaml.load(content, Loader=DocumentLoader)
        else:
            raise ValueError("Unsupported document format")
        return ScenarioDraftDefinition.model_validate(raw)
    except (yaml.YAMLError, RecursionError, TypeError) as exc:
        raise ValueError("Invalid scenario document") from exc


def document_issues(definition):
    try:
        return validate_scenario(ScenarioDefinition.model_validate(definition.model_dump(mode="json")))
    except ValueError:
        from tickets.request_scenario_validation import ScenarioIssue
        return [ScenarioIssue("incomplete_graph", "blocks", "Добавьте входы, вопросы и завершение маршрута.")]


async def document_reference_issues(session, definition):
    """Read-only import checks share the publication reference validator."""
    if definition.schema_version != 3 or definition.processing is None:
        return []
    from sqlalchemy import select
    from app.db.models import TicketQueue, TicketBusinessCalendar
    from tickets.request_scenario_processing import validate_map_processing_references
    queues = [{"code": row.code, "is_active": row.is_active}
              for row in await session.scalars(select(TicketQueue))]
    calendars = [{key: getattr(row, key) for key in ("id", "is_active", "timezone", "weekly_hours_json", "holidays_json")}
                 for row in await session.scalars(select(TicketBusinessCalendar))]
    return validate_map_processing_references(definition, queues, calendars)


def export_scenario_document(definition, format):
    raw = ScenarioDraftDefinition.model_validate(definition.model_dump(mode="json") if hasattr(definition, "model_dump") else definition).model_dump(mode="json")
    if format == "json":
        return json.dumps(raw, ensure_ascii=False, indent=2, allow_nan=False)
    if format == "yaml":
        return yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    raise ValueError("Unsupported document format")
