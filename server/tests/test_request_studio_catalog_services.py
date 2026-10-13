"""Admin grouping and entry search preserve canonical Offering identity."""
import pytest
from tickets.request_studio_catalog_projection import offering_cards

pytestmark = pytest.mark.no_db

def data():
    offering = {"full_code":"network.vpn", "service_code":"network", "public_title":"VPN", "visibility":"public", "lifecycle_status":"published", "request_template_key":"network", "metadata":{"studio_catalog":{"category_id":"remote", "synonyms":["туннель"]},"private_note":"private_signal"}}
    service = {"code":"network", "visibility":"public", "lifecycle_status":"published"}
    category = {"id":"remote", "service_code":"network", "parent_id":None, "visibility":"public", "lifecycle_status":"published"}
    scenario = {"id":"s", "offering_full_code":"network.vpn", "archived":False, "enabled":True, "published_version":1, "published_version_id":"v", "updated_at":"2026-10-13T00:00:00+00:00", "category_id":None, "status":"published", "issues":[], "published_route_available":False, "entry_points":[{"key":"paper","title":"VPN не подключается","description":"Проверим сеть", "category_id":"remote", "synonyms":["соединение пропало"]}]}
    return [offering], [scenario], [category], [service]

def test_shared_entrances_and_plain_form_synonyms_are_searchable_without_private_metadata():
    offerings, scenarios, categories, services = data()
    for query in ["подключается", "соединение пропало", "туннель"]:
        cards = offering_cards(offerings,scenarios,categories,services,query=query,selected={"remote"})
        assert len(cards)==1 and cards[0]["offering"]["full_code"]=="network.vpn"
        assert cards[0]["active_mode"]=="form"  # no public published entrance
    assert offering_cards(offerings,scenarios,categories,services,query="private_signal")==[]

def test_availability_filters_do_not_use_draft_publication_status():
    offerings, scenarios, categories, services = data()
    assert len(offering_cards(offerings,scenarios,categories,services,status="available"))==1
    offerings[0]["visibility"]="internal"
    assert offering_cards(offerings,scenarios,categories,services,status="available")==[]
    assert len(offering_cards(offerings,scenarios,categories,services,status="hidden"))==1
