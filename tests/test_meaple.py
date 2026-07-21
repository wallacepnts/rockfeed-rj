from unittest.mock import MagicMock, patch

from app.scrapers.meaple import MeapleScraper

CHANNEL = {
    "channel": {
        "id": "cmelsb5uf00vkqq0mdml3ziw6",
        "name": "MACACO CAOLHO ROCK PUB",
        "slug": "macacocaolhopub",
    }
}

EVENTS = {
    "events": [
        {
            "id": "evt1",
            "slug": "tributo-ozzy",
            "name": "Tributo Ozzy Osbourne",
            "description": [
                {"type": "paragraph", "children": [{"text": "Sexta - 24 de Julho"}]},
                {"type": "paragraph", "children": [{"text": "\n"}]},
                {"type": "paragraph", "children": [{"text": "Abertura: 19h"}]},
            ],
            "canceledAt": None,
            "startsAt": "2026-07-24T22:00:00.000Z",
            "endsAt": "2026-07-25T05:00:00.000Z",
            "image": {"url": "https://files.meaple.com.br/img.png"},
            "address": {
                "city": "Rio de Janeiro",
                "state": "Rio de Janeiro",
                "street": "Rua Capitão Salomão",
                "number": "57",
                "neighborhood": None,
                "zipCode": "22271-040",
            },
        },
        {
            "id": "evt2",
            "slug": "show-cancelado",
            "name": "Show Cancelado",
            "description": [],
            "canceledAt": "2026-07-01T12:00:00.000Z",
            "startsAt": "2026-08-01T22:00:00.000Z",
            "endsAt": None,
            "image": None,
            "address": {},
        },
    ]
}


def make_client():
    channel_resp = MagicMock()
    channel_resp.raise_for_status.side_effect = None
    channel_resp.json.return_value = CHANNEL

    events_resp = MagicMock()
    events_resp.raise_for_status.side_effect = None
    events_resp.json.return_value = EVENTS

    client = MagicMock()
    client.get.side_effect = [channel_resp, events_resp]
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    return client


def test_parses_event_and_skips_canceled():
    with patch("app.scrapers.meaple.get_client") as gc, \
         patch("app.scrapers.meaple.CHANNELS", ["macacocaolhopub"]):
        gc.return_value = make_client()
        events = MeapleScraper().fetch()

    assert len(events) == 1
    e = events[0]
    assert e.title == "Tributo Ozzy Osbourne"
    assert e.url == "https://meaple.com.br/macacocaolhopub/tributo-ozzy"
    assert e.venue == "MACACO CAOLHO ROCK PUB"
    assert e.organizer == "MACACO CAOLHO ROCK PUB"
    assert e.address == "Rua Capitão Salomão 57, Rio de Janeiro, Rio de Janeiro, 22271-040"
    assert e.city == "Rio de Janeiro"
    assert e.date.isoformat() == "2026-07-24T22:00:00+00:00"
    assert e.end_date.isoformat() == "2026-07-25T05:00:00+00:00"
    assert e.image == "https://files.meaple.com.br/img.png"
    assert e.description == "Sexta - 24 de Julho\nAbertura: 19h"
