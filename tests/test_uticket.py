from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from app.scrapers.uticket import UticketScraper

ORG_INFO = {"userId": 240767, "name": "GARAGE GRINDHOUSE"}

EVENT_LIST = [
    {"id": "01M89SS401PU7B", "name": "TRIBUTO AO IRON MAIDEN", "startDate": "2026-07-25T23:00:00Z"},
]

EVENT_INFO = {
    "id": "01M89SS401PU7B",
    "userId": 240767,
    "userImgUrl": "https://img.uticket.com.br/user/240767",
    "UserName": "GARAGE GRINDHOUSE",
    "name": "TRIBUTO AO IRON MAIDEN COM A SHE BEAST!",
    "description": '"<p>Texto com <strong>tags</strong> &amp; entidades</p>"',
    "place": {
        "name": "GARAGE GRINDHOUSE",
        "address": "Rua Ceara, 154 - Rio de Janeiro-RJ",
    },
    "schedules": [{"start": "2026-07-25T23:00:00Z", "end": "2026-07-26T07:20:00Z"}],
    "hidden": False,
}

TICKET_TYPES = {"ticketTypes": [{"price": 1500}, {"price": 2000}]}


def make_page(responses_by_url):
    page = MagicMock()

    def evaluate(script, url):
        for key, value in responses_by_url.items():
            if key in url:
                if isinstance(value, Exception):
                    raise value
                return value
        raise AssertionError(f"URL não esperada: {url}")

    page.evaluate.side_effect = evaluate
    page.goto.return_value = None
    return page


@contextmanager
def fake_browser_page(page):
    yield page


def test_parses_organizer_events_and_standalone_events():
    page = make_page({
        "organizerpage/?slug=garagegrindhouse": ORG_INFO,
        "event/user/240767": EVENT_LIST,
        "eventinfo/01M89SS401PU7B": EVENT_INFO,
        "tickettype?eventId=01M89SS401PU7B": TICKET_TYPES,
    })

    with patch("app.scrapers.uticket.browser_page", lambda: fake_browser_page(page)), \
         patch("app.scrapers.uticket.ORGANIZERS", ["garagegrindhouse"]), \
         patch("app.scrapers.uticket.EVENTS", []):
        events = UticketScraper().fetch()

    assert len(events) == 1
    e = events[0]
    assert e.title == "TRIBUTO AO IRON MAIDEN COM A SHE BEAST!"
    assert e.url == "https://uticket.com.br/evento/tributo-ao-iron-maiden-com-a-she-beast/01M89SS401PU7B"
    assert e.venue == "GARAGE GRINDHOUSE"
    assert e.organizer == "GARAGE GRINDHOUSE"
    assert e.city == "Rio de Janeiro"
    assert e.address == "Rua Ceara, 154 - Rio de Janeiro-RJ"
    assert e.date.isoformat() == "2026-07-25T23:00:00+00:00"
    assert e.end_date.isoformat() == "2026-07-26T07:20:00+00:00"
    assert e.price == "R$ 15.00"
    assert e.image == "https://img.uticket.com.br/event/01M89SS401PU7B/l"
    assert e.description == "Texto com tags & entidades"
    assert e.source == "uticket:garagegrindhouse"


def test_standalone_event_uses_bare_source():
    page = make_page({
        "eventinfo/01M6Z9W7XDG0M9": dict(EVENT_INFO, id="01M6Z9W7XDG0M9"),
        "tickettype?eventId=01M6Z9W7XDG0M9": TICKET_TYPES,
    })

    with patch("app.scrapers.uticket.browser_page", lambda: fake_browser_page(page)), \
         patch("app.scrapers.uticket.ORGANIZERS", []), \
         patch("app.scrapers.uticket.EVENTS", [
             "https://uticket.com.br/evento/x/01M6Z9W7XDG0M9?utm_source=ig",
         ]):
        events = UticketScraper().fetch()

    assert len(events) == 1
    assert events[0].source == "uticket"


def test_hidden_event_is_skipped():
    page = make_page({
        "eventinfo/01M6Z9W7XDG0M9": dict(EVENT_INFO, hidden=True),
    })

    with patch("app.scrapers.uticket.browser_page", lambda: fake_browser_page(page)), \
         patch("app.scrapers.uticket.ORGANIZERS", []), \
         patch("app.scrapers.uticket.EVENTS", ["https://uticket.com.br/evento/x/01M6Z9W7XDG0M9"]):
        events = UticketScraper().fetch()

    assert events == []


def test_organizer_failure_is_skipped_not_fatal():
    page = make_page({
        "organizerpage/?slug=bad": RuntimeError("boom"),
    })

    with patch("app.scrapers.uticket.browser_page", lambda: fake_browser_page(page)), \
         patch("app.scrapers.uticket.ORGANIZERS", ["bad"]), \
         patch("app.scrapers.uticket.EVENTS", []):
        events = UticketScraper().fetch()

    assert events == []


def test_site_unreachable_returns_empty():
    page = MagicMock()
    page.goto.side_effect = RuntimeError("boom")

    with patch("app.scrapers.uticket.browser_page", lambda: fake_browser_page(page)):
        events = UticketScraper().fetch()

    assert events == []
