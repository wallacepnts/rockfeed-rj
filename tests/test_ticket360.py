import json
from unittest.mock import MagicMock, patch

from app.scrapers.ticket360 import Ticket360Scraper

ITEM_LIST_HTML = """
<html><head>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"ItemList","numberOfItems":2,"itemListElement":[
    {"@type":"ListItem","position":1,"url":"https://www.ticket360.com.br/evento/1/rj-show","name":"RJ Show"},
    {"@type":"ListItem","position":2,"url":"https://www.ticket360.com.br/evento/2/sp-show","name":"SP Show"}
]}</script>
</head><body></body></html>
"""


def make_event_html(name, region, low_price=75):
    data = {
        "@context": "https://schema.org",
        "@type": "MusicEvent",
        "name": name,
        "url": f"https://www.ticket360.com.br/evento/x/{name}",
        "startDate": "2026-09-18T21:00:00-03:00",
        "endDate": "2026-09-18T23:00:00-03:00",
        "image": ["https://images.ticket360.com.br/img.webp"],
        "description": "Um baita show.\r\n\r\nLocal: Vivo Rio",
        "location": {
            "@type": "Place",
            "name": "Vivo Rio",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "Av. Infante Dom Henrique, 85",
                "addressLocality": "Rio de Janeiro" if region == "RJ" else "São Paulo",
                "addressRegion": region,
                "postalCode": "20021-140",
            },
        },
        "offers": {"@type": "AggregateOffer", "lowPrice": low_price, "priceCurrency": "BRL"},
        "organizer": {"@type": "Organization", "name": "Modernarte Espetaculos e Eventos Ltda."},
    }
    return f'<html><head><script type="application/ld+json">{json.dumps(data)}</script></head></html>'


def make_response(html_text):
    resp = MagicMock()
    resp.raise_for_status.side_effect = None
    resp.text = html_text
    return resp


def test_filters_events_by_rj_state():
    client = MagicMock()
    client.get.side_effect = [
        make_response(ITEM_LIST_HTML),
        make_response(ITEM_LIST_HTML),  # segunda categoria, mesma lista
        make_response(make_event_html("RJ Show", "RJ")),
        make_response(make_event_html("SP Show", "SP")),
    ]
    client.__enter__.return_value = client
    client.__exit__.return_value = False

    with patch("app.scrapers.ticket360.get_client") as gc:
        gc.return_value = client
        events = Ticket360Scraper().fetch()

    assert len(events) == 1
    e = events[0]
    assert e.title == "RJ Show"
    assert e.venue == "Vivo Rio"
    assert e.city == "Rio de Janeiro"
    assert e.address == "Av. Infante Dom Henrique, 85, Rio de Janeiro, RJ, 20021-140"
    assert e.organizer == "Modernarte Espetaculos e Eventos Ltda."
    assert e.date.isoformat() == "2026-09-18T21:00:00-03:00"
    assert e.end_date.isoformat() == "2026-09-18T23:00:00-03:00"
    assert e.price == "R$ 75.00"
    assert e.image == "https://images.ticket360.com.br/img.webp"
    assert e.description == "Um baita show. Local: Vivo Rio"


def test_free_event_price_is_gratis():
    client = MagicMock()
    client.get.side_effect = [
        make_response(ITEM_LIST_HTML),
        make_response(ITEM_LIST_HTML),
        make_response(make_event_html("RJ Show", "RJ", low_price=0)),
        make_response(make_event_html("SP Show", "SP")),
    ]
    client.__enter__.return_value = client
    client.__exit__.return_value = False

    with patch("app.scrapers.ticket360.get_client") as gc:
        gc.return_value = client
        events = Ticket360Scraper().fetch()

    assert events[0].price == "Grátis"


def test_event_fetch_failure_is_skipped_not_fatal():
    client = MagicMock()
    client.get.side_effect = [
        make_response(ITEM_LIST_HTML),
        make_response(ITEM_LIST_HTML),
        __import__("httpx").HTTPError("boom"),
        make_response(make_event_html("SP Show", "SP")),
    ]
    client.__enter__.return_value = client
    client.__exit__.return_value = False

    with patch("app.scrapers.ticket360.get_client") as gc:
        gc.return_value = client
        events = Ticket360Scraper().fetch()

    assert events == []
