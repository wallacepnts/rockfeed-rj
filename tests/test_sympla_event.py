from unittest.mock import MagicMock, patch

import httpx

from app.scrapers.sympla import SymplaEventScraper

EVENT = {
    "cancelled": False,
    "name": "Rock N Radio",
    "startDate": "2026-07-24 20:00:00",
    "endDate": "2026-07-25 02:00:00",
    "eventsAddress": {
        "name": "Tijuca Tênis Clube",
        "address": "Rua Conde de Bonfim",
        "addressNum": "451",
        "neighborhood": "Tijuca",
        "city": "Rio de Janeiro",
        "state": "RJ",
        "zipCode": "20520-051",
    },
    "eventsHost": {"name": "DJ Cidinho e Promocao de Eventos", "organizerId": 383973},
    "images": {"logoLarge": "https://images.sympla.com.br/img-lg.jpg"},
    "details": {"pt": {"text": "<p>Texto com <strong>tags</strong> &amp; entidades</p>"}},
}

TICKETS = {
    "tickets": [
        {"show": True, "salePriceMonetary": {"decimal": 18.99, "integer": 1899}},
        {"show": True, "salePriceMonetary": {"decimal": 25.0, "integer": 2500}},
        {"show": False, "salePriceMonetary": {"decimal": 5.0, "integer": 500}},
    ]
}


def make_json_response(payload):
    resp = MagicMock()
    resp.raise_for_status.side_effect = None
    resp.json.return_value = payload
    return resp


def make_client(*responses):
    client = MagicMock()
    client.get.side_effect = list(responses)
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    return client


def test_parses_event_strips_query_and_takes_lowest_visible_price():
    client = make_client(make_json_response(EVENT), make_json_response(TICKETS))
    url = "https://www.sympla.com.br/evento/rock-n-radio/3464520?share_id=copiarlink"

    with patch("app.scrapers.sympla.get_client") as gc, \
         patch("app.scrapers.sympla.EVENTS", [(url, None)]):
        gc.return_value = client
        events = SymplaEventScraper().fetch()

    assert len(events) == 1
    e = events[0]
    assert e.title == "Rock N Radio"
    assert e.url == "https://www.sympla.com.br/evento/rock-n-radio/3464520"
    assert e.venue == "Tijuca Tênis Clube"
    assert e.address == "Rua Conde de Bonfim 451, Tijuca, Rio de Janeiro, RJ, 20520-051"
    assert e.organizer == "DJ Cidinho e Promocao de Eventos"
    assert e.city == "Rio de Janeiro"
    assert e.date.isoformat() == "2026-07-24T20:00:00-03:00"
    assert e.end_date.isoformat() == "2026-07-25T02:00:00-03:00"
    assert e.image == "https://images.sympla.com.br/img-lg.jpg"
    assert e.description == "Texto com tags & entidades"
    # menor preço entre os visíveis (18.99), ignora o de show=False (5.00)
    assert e.price == "R$ 18.99"


def test_free_ticket_shows_gratis():
    tickets = {"tickets": [{"show": True, "salePriceMonetary": {"decimal": 0, "integer": 0}}]}
    client = make_client(make_json_response(EVENT), make_json_response(tickets))

    with patch("app.scrapers.sympla.get_client") as gc, \
         patch("app.scrapers.sympla.EVENTS", [("https://www.sympla.com.br/evento/x/1", None)]):
        gc.return_value = client
        events = SymplaEventScraper().fetch()

    assert events[0].price == "Grátis"


def test_organizer_override_replaces_events_host_name():
    client = make_client(make_json_response(EVENT), make_json_response(TICKETS))

    with patch("app.scrapers.sympla.get_client") as gc, \
         patch("app.scrapers.sympla.EVENTS", [("https://www.sympla.com.br/evento/x/1", "LET'S ROCK")]):
        gc.return_value = client
        events = SymplaEventScraper().fetch()

    assert events[0].organizer == "LET'S ROCK"


def test_cancelled_event_is_skipped_without_fetching_price():
    cancelled = dict(EVENT, cancelled=True)
    client = make_client(make_json_response(cancelled))

    with patch("app.scrapers.sympla.get_client") as gc, \
         patch("app.scrapers.sympla.EVENTS", [("https://www.sympla.com.br/evento/x/1", None)]):
        gc.return_value = client
        events = SymplaEventScraper().fetch()

    assert events == []
    assert client.get.call_count == 1


def test_failed_fetch_is_skipped_not_fatal():
    resp = MagicMock()
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "boom", request=None, response=None
    )
    client = MagicMock()
    client.get.return_value = resp
    client.__enter__.return_value = client
    client.__exit__.return_value = False

    with patch("app.scrapers.sympla.get_client") as gc, \
         patch("app.scrapers.sympla.EVENTS", [("https://www.sympla.com.br/evento/x/1", None)]):
        gc.return_value = client
        events = SymplaEventScraper().fetch()

    assert events == []


def test_no_event_id_in_url_is_skipped():
    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    with patch("app.scrapers.sympla.get_client") as gc, \
         patch("app.scrapers.sympla.EVENTS", [("https://www.sympla.com.br/evento/sem-id-no-final", None)]):
        gc.return_value = client
        events = SymplaEventScraper().fetch()

    assert events == []
    client.get.assert_not_called()
