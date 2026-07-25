from unittest.mock import MagicMock, patch

import httpx

from app.scrapers.bileto import BiletoScraper

ROCK_EVENT_DATA = {
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
        "description": {"raw": "<p>Metal extremo nacional com <strong>tags</strong> &amp; entidades</p>"},
        "presentations": {"lowest_price": {"currency": "BRL", "value": "4000"}},
    }
}

NON_ROCK_EVENT_DATA = {
    "data": {
        "id": 999001,
        "name": "Setembro em Dança",
        "venue": {"name": "Areninha Cultural Hermeto Pascoal", "locale": {}},
        "next_local_date_time": "2026-09-20T09:00:00-03:00",
        "medias": [],
        "description": {"raw": "<p>Espetáculo de dança com bailarinos da região</p>"},
        "presentations": {},
    }
}


def make_response(data_or_text, is_json=True):
    resp = MagicMock()
    resp.raise_for_status.side_effect = None
    if is_json:
        resp.json.return_value = data_or_text
    else:
        resp.text = data_or_text
    return resp


def make_client(responses):
    client = MagicMock()
    client.get.side_effect = responses
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    return client


def test_parses_event_with_organizer_override():
    with patch("app.scrapers.bileto.get_client") as gc, \
         patch("app.scrapers.bileto.VENUES", []), \
         patch("app.scrapers.bileto.EVENTS", [(121087, "Be Magic")]):
        gc.return_value = make_client([make_response(ROCK_EVENT_DATA)])
        events = BiletoScraper().fetch()

    assert len(events) == 1
    e = events[0]
    assert e.title == "Aliança 2026"
    assert e.url == "https://bileto.sympla.com.br/event/121087"
    assert e.source == "bileto"
    assert e.venue == "Areninha Cultural Hermeto Pascoal"
    assert e.organizer == "Be Magic"
    assert e.city == "Rio de Janeiro"
    assert e.date.isoformat() == "2026-08-23T15:00:00-03:00"
    assert e.end_date is None
    assert e.price == "R$ 40.00"
    assert e.image == "https://assets.bileto.sympla.com.br/img.jpg"
    assert e.description == "Metal extremo nacional com tags & entidades"


def test_organizer_blank_when_no_override_given():
    with patch("app.scrapers.bileto.get_client") as gc, \
         patch("app.scrapers.bileto.VENUES", []), \
         patch("app.scrapers.bileto.EVENTS", [(121087, None)]):
        gc.return_value = make_client([make_response(ROCK_EVENT_DATA)])
        events = BiletoScraper().fetch()

    assert events[0].organizer == ""


def test_failed_event_is_skipped_not_fatal():
    fail_resp = MagicMock()
    fail_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "boom", request=None, response=None
    )

    with patch("app.scrapers.bileto.get_client") as gc, \
         patch("app.scrapers.bileto.VENUES", []), \
         patch("app.scrapers.bileto.EVENTS", [(999999, None)]):
        gc.return_value = make_client([fail_resp])
        events = BiletoScraper().fetch()

    assert events == []


def test_discovers_and_filters_rock_events_from_venue_agenda():
    agenda_html = """
    <a href="https://bileto.sympla.com.br/event/121087">Aliança</a>
    <a href="https://bileto.sympla.com.br/event/999001">Dança</a>
    """
    with patch("app.scrapers.bileto.get_client") as gc, \
         patch("app.scrapers.bileto.VENUES", [("areninha", "https://sympla.com.br/agenda/x")]), \
         patch("app.scrapers.bileto.EVENTS", []):
        gc.return_value = make_client([
            make_response(agenda_html, is_json=False),
            make_response(ROCK_EVENT_DATA),
            make_response(NON_ROCK_EVENT_DATA),
        ])
        events = BiletoScraper().fetch()

    assert len(events) == 1
    assert events[0].title == "Aliança 2026"
    assert events[0].source == "bileto:areninha"


def test_organizer_override_applies_to_venue_discovered_event():
    agenda_html = '<a href="https://bileto.sympla.com.br/event/121087">Aliança</a>'
    with patch("app.scrapers.bileto.get_client") as gc, \
         patch("app.scrapers.bileto.VENUES", [("areninha", "https://sympla.com.br/agenda/x")]), \
         patch("app.scrapers.bileto.EVENTS", []), \
         patch("app.scrapers.bileto.ORGANIZER_OVERRIDES", {121087: "Be Magic"}):
        gc.return_value = make_client([
            make_response(agenda_html, is_json=False),
            make_response(ROCK_EVENT_DATA),
        ])
        events = BiletoScraper().fetch()

    assert events[0].organizer == "Be Magic"


def test_venue_agenda_fetch_failure_is_skipped_not_fatal():
    fail_resp = MagicMock()
    fail_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "boom", request=None, response=None
    )
    with patch("app.scrapers.bileto.get_client") as gc, \
         patch("app.scrapers.bileto.VENUES", [("areninha", "https://sympla.com.br/agenda/x")]), \
         patch("app.scrapers.bileto.EVENTS", []):
        gc.return_value = make_client([fail_resp])
        events = BiletoScraper().fetch()

    assert events == []


def test_event_in_both_venue_and_events_list_is_not_fetched_twice():
    agenda_html = '<a href="https://bileto.sympla.com.br/event/121087">Aliança</a>'
    with patch("app.scrapers.bileto.get_client") as gc, \
         patch("app.scrapers.bileto.VENUES", [("areninha", "https://sympla.com.br/agenda/x")]), \
         patch("app.scrapers.bileto.EVENTS", [(121087, None)]):
        client = make_client([
            make_response(agenda_html, is_json=False),
            make_response(ROCK_EVENT_DATA),
        ])
        gc.return_value = client
        events = BiletoScraper().fetch()

    assert len(events) == 1
    assert client.get.call_count == 2


def test_excluded_ids_are_skipped_even_if_rock_matches():
    agenda_html = '<a href="https://bileto.sympla.com.br/event/121087">Aliança</a>'
    with patch("app.scrapers.bileto.get_client") as gc, \
         patch("app.scrapers.bileto.VENUES", [("areninha", "https://sympla.com.br/agenda/x")]), \
         patch("app.scrapers.bileto.EVENTS", []), \
         patch("app.scrapers.bileto.EXCLUDED_IDS", {121087}):
        gc.return_value = make_client([make_response(agenda_html, is_json=False)])
        events = BiletoScraper().fetch()

    assert events == []
