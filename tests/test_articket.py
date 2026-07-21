import json
from unittest.mock import MagicMock, patch

from app.scrapers.articket import ArticketScraper

EVENT_HTML = """<html><head>
<script type="application/ld+json">{json_ld}</script>
</head><body></body></html>"""

JSON_LD = {
    "name": "TOMAROCK EM CAXIAS",
    "startDate": "2026-07-26T15:00:00-03:00",
    "endDate": "2026-07-26T22:00:00-03:00",
    "location": {
        "name": "Espaço Retrô",
        "address": {
            "streetAddress": "Rua Coronel João Teles 225",
            "addressLocality": "Rio de Janeiro",
            "addressRegion": "Rio de Janeiro",
            "postalCode": "25020-180",
        },
    },
    "image": ["https://cdn.articket.com.br/img.webp"],
    "description": 'Show especial &quot;Dia do Rock&quot;',
    "offers": {"price": "20.00", "url": "https://articket.com.br/e/1/tomarock-em-caxias"},
    "organizer": {"name": "Tomarock Produções"},
}


def make_client(org_html, event_html):
    org_resp = MagicMock()
    org_resp.raise_for_status.side_effect = None
    org_resp.text = org_html

    event_resp = MagicMock()
    event_resp.raise_for_status.side_effect = None
    event_resp.text = event_html

    client = MagicMock()
    client.get.side_effect = [org_resp, event_resp]
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    return client


def test_parses_all_expected_fields_from_json_ld():
    org_html = '<a href="https://articket.com.br/e/1/tomarock-em-caxias">TOMAROCK EM CAXIAS</a>'
    event_html = EVENT_HTML.format(json_ld=json.dumps(JSON_LD))

    with patch("app.scrapers.articket.get_client") as gc, \
         patch("app.scrapers.articket.PAGES", [("tomarock", "http://org")]):
        gc.return_value = make_client(org_html, event_html)
        events = ArticketScraper().fetch()

    assert len(events) == 1
    e = events[0]
    assert e.title == "TOMAROCK EM CAXIAS"
    assert e.venue == "Espaço Retrô"
    assert e.address == "Rua Coronel João Teles 225, Rio de Janeiro, Rio de Janeiro, 25020-180"
    assert e.organizer == "Tomarock Produções"
    assert e.city == "Rio de Janeiro"
    assert e.date.isoformat() == "2026-07-26T15:00:00-03:00"
    assert e.end_date.isoformat() == "2026-07-26T22:00:00-03:00"
    assert e.price == "R$ 20.00"
    assert e.image == "https://cdn.articket.com.br/img.webp"
    # entidades HTML do CMS de origem devem ser decodificadas, não repassadas cruas
    assert e.description == 'Show especial "Dia do Rock"'
    assert e.url == "https://articket.com.br/e/1/tomarock-em-caxias"
