from unittest.mock import MagicMock, patch

import httpx

from app.scrapers.uhuu import UhuuScraper

PAGE_HTML = """
<html><head>
<meta property="og:image" content="https://cdn.example.com/img.jpg">
</head><body>
<div class="event-container">
  <h1 class="event-title">Beatles Abbey Road</h1>
  <div class="event-details"><p><strong>13 de Agosto de 2026 </strong><br/>às 20:00</p></div>
  <div class="event-details"><p>Ingressos a partir de <strong>R$ 70,00</strong> em até 6x</p></div>
  <div class="event-details">
    <div>
      <p><strong id="pageEventLocal">Teatro Claro MAIS RJ</strong><br/>Rio de Janeiro/RJ</p>
      <a class="btn-outline">Ver localização</a>
    </div>
  </div>
</div>
</body></html>
"""


def make_client(html_text):
    resp = MagicMock()
    resp.raise_for_status.side_effect = None
    resp.text = html_text

    client = MagicMock()
    client.get.return_value = resp
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    return client


def test_parses_event_page():
    client = make_client(PAGE_HTML)
    url = "https://uhuu.com/evento/rj/rio-de-janeiro/beatles-abbey-road-16408"

    with patch("app.scrapers.uhuu.get_client") as gc, \
         patch("app.scrapers.uhuu.EVENTS", [url]):
        gc.return_value = client
        events = UhuuScraper().fetch()

    assert len(events) == 1
    e = events[0]
    assert e.title == "Beatles Abbey Road"
    assert e.url == url
    assert e.venue == "Teatro Claro MAIS RJ"
    assert e.address == "Rio de Janeiro/RJ"
    assert e.city == "Rio de Janeiro"
    assert e.date.isoformat() == "2026-08-13T20:00:00-03:00"
    assert e.price == "R$ 70.00"
    assert e.image == "https://cdn.example.com/img.jpg"


def test_page_without_expected_layout_is_skipped():
    client = make_client("<html><body>página quebrada</body></html>")

    with patch("app.scrapers.uhuu.get_client") as gc, \
         patch("app.scrapers.uhuu.EVENTS", ["https://uhuu.com/evento/rj/x/y-1"]):
        gc.return_value = client
        events = UhuuScraper().fetch()

    assert events == []


def test_page_load_failure_is_skipped_not_fatal():
    resp = MagicMock()
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "boom", request=None, response=None
    )
    client = MagicMock()
    client.get.return_value = resp
    client.__enter__.return_value = client
    client.__exit__.return_value = False

    with patch("app.scrapers.uhuu.get_client") as gc, \
         patch("app.scrapers.uhuu.EVENTS", ["https://uhuu.com/evento/rj/x/y-1"]):
        gc.return_value = client
        events = UhuuScraper().fetch()

    assert events == []
