from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from app.scrapers.shotgun import ShotgunScraper

PAGE_HTML = """
<html><body>
<h1>Espaço Cultural Redoma</h1>
<a href="/pt-br/events/stela-none-left">
  <div>
    <img alt="capa" src="https://res.cloudinary.com/img.png">
    <p>08/08 - Stela + None Left No Redoma</p>
    <div>Espaço Redoma</div>
    <time datetime="2026-08-08T22:00:00.000Z">sáb., 8 de ago.</time>
    <span>R$ 25,00</span>
  </div>
</a>
<a href="/pt-br/events/sem-data">
  <div>
    <p>Evento sem time tag</p>
  </div>
</a>
</body></html>
"""


def make_browser_page(html_text):
    page = MagicMock()
    page.content.return_value = html_text

    @contextmanager
    def fake_browser_page():
        yield page

    return fake_browser_page, page


def test_parses_events_from_venue_page():
    fake_ctx, page = make_browser_page(PAGE_HTML)
    with patch("app.scrapers.shotgun.browser_page", fake_ctx), \
         patch("app.scrapers.shotgun.VENUES", ["espaco-cultural-redoma"]):
        events = ShotgunScraper().fetch()

    assert len(events) == 1
    e = events[0]
    assert e.title == "08/08 - Stela + None Left No Redoma"
    assert e.url == "https://shotgun.live/pt-br/events/stela-none-left"
    assert e.venue == "Espaço Cultural Redoma"
    assert e.organizer == "Espaço Cultural Redoma"
    assert e.source == "shotgun:espaco-cultural-redoma"
    assert e.city == "Rio de Janeiro"
    assert e.date.isoformat() == "2026-08-08T22:00:00+00:00"
    assert e.price == "R$ 25.00"
    assert e.image == "https://res.cloudinary.com/img.png"


def test_card_without_time_tag_is_skipped():
    fake_ctx, page = make_browser_page(PAGE_HTML)
    with patch("app.scrapers.shotgun.browser_page", fake_ctx), \
         patch("app.scrapers.shotgun.VENUES", ["espaco-cultural-redoma"]):
        events = ShotgunScraper().fetch()

    urls = [e.url for e in events]
    assert "https://shotgun.live/pt-br/events/sem-data" not in urls


def test_page_load_failure_returns_empty_not_fatal():
    @contextmanager
    def failing_browser_page():
        raise RuntimeError("boom")
        yield  # pragma: no cover

    with patch("app.scrapers.shotgun.browser_page", failing_browser_page), \
         patch("app.scrapers.shotgun.VENUES", ["espaco-cultural-redoma"]):
        events = ShotgunScraper().fetch()

    assert events == []
