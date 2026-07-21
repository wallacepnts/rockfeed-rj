from unittest.mock import MagicMock, patch

import httpx

from app.scrapers.clubedoingresso import ClubeDoIngressoScraper

PAGE_HTML = """
<html><body>
<div class="PageEvent__details">
  <div class="PageEvent__nameEvent">
    <div class="nome" data-nome="Testament no Rio de Janeiro">Testament no Rio de Janeiro</div>
  </div>
  <div class="PageEvent__select">
    <div class="PageEvent__desc">Domingo, 13 de Dezembro de 2026 - Abertura: 18:00</div>
  </div>
  <div class="PageEvent__local">
    <div class="PageEvent__subTitle">Sacadura 154</div>
    <div class="PageEvent__desc">Rua Sacadura Cabral, 154 - Centro - Rio de Janeiro, RJ</div>
  </div>
  <div class="PageEvent__organizer">
    <div class="PageEvent__subTitle">Organizado por:</div>
    <div class="PageEvent__desc">Liberation MC</div>
  </div>
</div>
<img class="PageEvent__img" src="https://cdn.example.com/img.jpg">
<meta property="product:price:amount" content="300">
<meta property="product:price:amount" content="600">
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
    url = "https://www.clubedoingresso.com/evento/testament-riodejaneiro"

    with patch("app.scrapers.clubedoingresso.get_client") as gc, \
         patch("app.scrapers.clubedoingresso.EVENTS", [url]):
        gc.return_value = client
        events = ClubeDoIngressoScraper().fetch()

    assert len(events) == 1
    e = events[0]
    assert e.title == "Testament no Rio de Janeiro"
    assert e.url == url
    assert e.venue == "Sacadura 154"
    assert e.address == "Rua Sacadura Cabral, 154 - Centro - Rio de Janeiro, RJ"
    assert e.city == "Rio de Janeiro"
    assert e.organizer == "Liberation MC"
    assert e.date.isoformat() == "2026-12-13T18:00:00-03:00"
    assert e.price == "R$ 300.00"
    assert e.image == "https://cdn.example.com/img.jpg"


def test_page_without_expected_layout_is_skipped():
    client = make_client("<html><body>página quebrada</body></html>")

    with patch("app.scrapers.clubedoingresso.get_client") as gc, \
         patch("app.scrapers.clubedoingresso.EVENTS", ["https://x/evento/y"]):
        gc.return_value = client
        events = ClubeDoIngressoScraper().fetch()

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

    with patch("app.scrapers.clubedoingresso.get_client") as gc, \
         patch("app.scrapers.clubedoingresso.EVENTS", ["https://x/evento/y"]):
        gc.return_value = client
        events = ClubeDoIngressoScraper().fetch()

    assert events == []
