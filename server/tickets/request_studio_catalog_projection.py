"""Admin offering cards: requester mode is separate from editing history."""

from tickets.request_scenario_catalog import category_path_is_public
from tickets.service_catalog_contract import REQUEST_TYPE_LABELS_RU
from datetime import datetime


def offering_type_search_text(offering):
    metadata = offering.get("metadata") or {}
    profile = metadata.get("studio_profile") if isinstance(metadata, dict) else None
    profile = profile if isinstance(profile, str) else ""
    request_type = offering.get("request_type") or ""
    # The purpose editor uses these labels in addition to canonical catalog labels.
    purpose_labels = {"request": "Общий запрос", "access": "Запрос доступа", "software_install": "Установка ПО"}
    return " ".join(str(value or "") for value in (
        request_type, REQUEST_TYPE_LABELS_RU.get(request_type), purpose_labels.get(request_type),
        profile, REQUEST_TYPE_LABELS_RU.get(profile), purpose_labels.get(profile)))



def offering_cards(offerings, scenarios, categories, services, *, query="", status="all", service_code=None, offering_code=None, selected=None):
    by_category = {item["id"]: item for item in categories}
    by_service = {item["code"]: item for item in services}
    cards = []
    for offering in offerings:
        if offering_code and offering["full_code"] != offering_code:
            continue
        if service_code and offering.get("service_code") != service_code:
            continue
        history = [item for item in scenarios if item["offering_full_code"] == offering["full_code"]]
        history.sort(key=lambda item: (bool(item["archived"]), not bool(item["enabled"] and item["published_version"]),
            -datetime.fromisoformat(item["updated_at"]).timestamp(), item["id"]))
        current = [item for item in history if not item["archived"]]
        category_ids = {item["category_id"] for item in (current or history) if item["category_id"]}
        for item in current:
            category_ids.update(entry.get("category_id") for entry in item.get("entry_points", []) + item.get("published_entry_points", []) if isinstance(entry, dict) and entry.get("category_id"))
        catalog_metadata = (offering.get("metadata") or {}).get("studio_catalog", {}) if isinstance(offering.get("metadata") or {}, dict) else {}
        catalog_metadata = catalog_metadata if isinstance(catalog_metadata, dict) else {}
        folder = catalog_metadata.get("category_id")
        if isinstance(folder, str) and folder in by_category and by_category[folder].get("service_code") == offering.get("service_code") and by_category[folder].get("lifecycle_status") != "archived":
            category_ids.add(folder)
        if selected is not None and not category_ids.intersection(selected):
            continue
        active = next((item for item in current if item["enabled"] and item["published_version"] and item.get("published_route_available", True)
            and category_path_is_public(item["category_id"], by_category)), None)
        service = by_service.get(offering.get("service_code"), {})
        available = all(item.get("visibility") == "public" and item.get("lifecycle_status") == "published"
            for item in (service, offering)) and bool(offering.get("request_template_key"))
        matches = status == "all" or status == "available" and available or status == "hidden" and not available or status == "form_only" and available and active is None or status == "guided" and available and active is not None or any(
            item["status"] == status or status == "errors" and item["issues"] and not item["archived"]
            or status == "draft" and not item["archived"] and not item["published_version_id"] for item in history)
        if not matches:
            continue
        # Search only public catalog fields and the existing canonical type labels.
        text = " ".join(str(offering.get(key) or "") for key in ("public_title", "short_description", "full_code", "service_code"))
        text += " " + offering_type_search_text(offering)
        text += " " + " ".join(str(item.get(key) or "") for item in history for key in ("title", "description", "category_title"))
        text += " " + " ".join(str(entry.get(key) or "") for item in current for entry in item.get("entry_points", []) + item.get("published_entry_points", []) if isinstance(entry, dict) for key in ("title", "description", "synonyms"))
        text += " " + str(catalog_metadata.get("synonyms") or "")
        if query and query.casefold() not in text.casefold():
            continue
        cards.append({"offering": offering, "scenarios": history, "active_mode": "scenario" if active else "form",
            "requester_available": available, "active_scenario_id": active["id"] if active else None, "category_ids": sorted(category_ids)})
    cards.sort(key=lambda item: (item["offering"]["public_title"].casefold(), item["offering"]["full_code"]))
    return cards
