from unittest.mock import MagicMock, patch

import httpx

from app.scrapers.bileto import BiletoScraper

EVENT_DATA = {
    "data": {
        "id": 121087,
        "name": "Aliança 2026",
        "venue": {
            "name": "Areninha Cultural Hermeto Pascoal",
            "locale": {
                "address": "Praça Primeiro de Maio, s/n",
                "city": {"name": "Rio de Janeiro"},
                "state": {"name": "Rio de Janeiro"},
                "postal_code": "21830-006",
            },
        },
        "next_local_date_time": "2026-08-23T15:00:00-03:00",
        "last_local_date_time": "2026-08-23T15:00:00-03:00",
        "organizer_id": 5793,
        "medias": [
            {"rel": "profile", "url": "https://assets.bileto.sympla.com.br/img.jpg"},
        ],
        "description": {"raw": "<p>Texto com <strong>tags</strong> &amp; entidades</p>"},
        "presentations": {"lowest_price": {"currency": "BRL", "value": "4000"}},
    }
}


def make_client(response):
    client = MagicMock()
    client.get.return_value = response
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    return client


def test_parses_event_with_organizer_override():
    resp = MagicMock()
    resp.raise_for_status.side_effect = None
    resp.json.return_value = EVENT_DATA

    with patch("app.scrapers.bileto.get_client") as gc, \
         patch("app.scrapers.bileto.EVENTS", [(121087, "Be Magic")]):
        gc.return_value = make_client(resp)
        events = BiletoScraper().fetch()

    assert len(events) == 1
    e = events[0]
    assert e.title == "Aliança 2026"
    assert e.url == "https://bileto.sympla.com.br/event/121087"
    assert e.venue == "Areninha Cultural Hermeto Pascoal"
    assert e.organizer == "Be Magic"
    assert e.city == "Rio de Janeiro"
    assert e.date.isoformat() == "2026-08-23T15:00:00-03:00"
    assert e.end_date is None
    assert e.price == "R$ 40.00"
    assert e.image == "https://assets.bileto.sympla.com.br/img.jpg"
    assert e.description == "Texto com tags & entidades"


def test_organizer_blank_when_no_override_given():
    resp = MagicMock()
    resp.raise_for_status.side_effect = None
    resp.json.return_value = EVENT_DATA

    with patch("app.scrapers.bileto.get_client") as gc, \
         patch("app.scrapers.bileto.EVENTS", [(121087, None)]):
        gc.return_value = make_client(resp)
        events = BiletoScraper().fetch()

    assert events[0].organizer == ""


def test_failed_event_is_skipped_not_fatal():
    resp = MagicMock()
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "boom", request=None, response=None
    )

    with patch("app.scrapers.bileto.get_client") as gc, \
         patch("app.scrapers.bileto.EVENTS", [(999999, None)]):
        gc.return_value = make_client(resp)
        events = BiletoScraper().fetch()

    assert events == []
