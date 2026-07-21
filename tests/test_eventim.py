from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.scrapers.eventim import EventimScraper

RJ_PRODUCT = SimpleNamespace(
    name="EDU FALASCHI NO CIRCO VOADOR",
    link="https://www.eventim.com.br/en/event/edu-falaschi-no-circo-voador-21443773/",
    type_attributes={
        "liveEntertainment": {
            "location": {"name": "Circo Voador", "city": "Rio de Janeiro", "state": "RJ"},
            "startDate": "2026-08-07T20:00:00-03:00",
        }
    },
)

SP_PRODUCT = SimpleNamespace(
    name="SOME SHOW IN SAO PAULO",
    link="https://www.eventim.com.br/en/event/some-show-sp/",
    type_attributes={
        "liveEntertainment": {
            "location": {"name": "Some Venue", "city": "São Paulo", "state": "SP"},
            "startDate": "2026-08-07T20:00:00-03:00",
        }
    },
)


def make_group(products, categories):
    return SimpleNamespace(
        image_url="https://cdn.example.com/img.png",
        description="Descrição do show",
        categories=[{"name": c} for c in categories],
        products=products,
    )


def test_parses_rj_rock_event_and_skips_other_states():
    rock_group = make_group([RJ_PRODUCT, SP_PRODUCT], ["Shows & Music", "Rock"])

    fake_client = MagicMock()
    fake_client.product_groups.return_value = [rock_group]

    with patch("app.scrapers.eventim.EventimClient", return_value=fake_client):
        events = EventimScraper().fetch()

    assert len(events) == 1
    e = events[0]
    assert e.title == "EDU FALASCHI NO CIRCO VOADOR"
    assert e.url == "https://www.eventim.com.br/en/event/edu-falaschi-no-circo-voador-21443773/"
    assert e.venue == "Circo Voador"
    assert e.city == "Rio de Janeiro"
    assert e.address == "Rio de Janeiro, RJ"
    assert e.date.isoformat() == "2026-08-07T20:00:00-03:00"
    assert e.image == "https://cdn.example.com/img.png"
    assert e.description == "Descrição do show"
    assert e.source == "eventim"


def test_non_rock_category_group_is_skipped():
    non_rock_group = make_group([RJ_PRODUCT], ["Shows & Music", "Pop"])

    fake_client = MagicMock()
    fake_client.product_groups.return_value = [non_rock_group]

    with patch("app.scrapers.eventim.EventimClient", return_value=fake_client):
        events = EventimScraper().fetch()

    assert events == []


def test_client_failure_returns_empty_not_fatal():
    fake_client = MagicMock()
    fake_client.product_groups.side_effect = RuntimeError("boom")

    with patch("app.scrapers.eventim.EventimClient", return_value=fake_client):
        events = EventimScraper().fetch()

    assert events == []
