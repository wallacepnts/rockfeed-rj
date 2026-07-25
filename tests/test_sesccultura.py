from unittest.mock import MagicMock, patch

from app.scrapers.sesccultura import SescCulturaScraper

ROCK_EVENT = {
    "id": 1,
    "title": "Banda Trisônica",
    "slug": "banda-trisonica",
    "featured_image": {"large": "https://cdn.example.com/img.jpg"},
    "event_meta": {
        "sinopse_markdown": "<p>O repertório da banda é baseado no Rock nacional, "
        "como Barão Vermelho, Cazuza, Legião Urbana.</p>",
        "sessoes": [
            {
                "local": "Sesc Nogueira",
                "data_intervalo_iso8601": "2026-04-18/2026-04-18",
                "hora_intervalo_iso8601": "20:00:00/21:30:00",
                "url_ingresso": "",
                "ingressos": [{"tipo": "Grátis", "preco": "0"}],
            }
        ],
    },
}

NON_ROCK_EVENT = {
    "id": 2,
    "title": "Dudu Nobre",
    "slug": "dudu-nobre",
    "featured_image": {"large": ""},
    "event_meta": {
        "sinopse_markdown": "<p>Show de samba e pagode com Dudu Nobre.</p>",
        "sessoes": [
            {
                "local": "Sesc Copacabana",
                "data_intervalo_iso8601": "2026-08-01/2026-08-01",
                "hora_intervalo_iso8601": "20:00:00/21:00:00",
                "url_ingresso": "",
                "ingressos": [{"tipo": "Inteira", "preco": "20"}],
            }
        ],
    },
}

EXCLUDED_EVENT = {
    "id": 3,
    "title": "Silvério Pontes",
    "slug": "silverio-pontes",
    "featured_image": {"large": ""},
    "event_meta": {
        "sinopse_markdown": "<p>Tributo ao Zé da Velha, mestre do choro.</p>",
        "sessoes": [
            {
                "local": "Sesc Ramos",
                "data_intervalo_iso8601": "2026-04-09/2026-04-09",
                "hora_intervalo_iso8601": "19:00:00/20:00:00",
                "url_ingresso": "",
                "ingressos": [{"tipo": "Inteira", "preco": "7.5"}],
            }
        ],
    },
}


def make_response(eventos):
    resp = MagicMock()
    resp.raise_for_status.side_effect = None
    resp.json.return_value = {"data": {"eventos": eventos}}
    return resp


def make_client(pages):
    client = MagicMock()
    client.get.side_effect = pages
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    return client


def test_filters_rock_and_skips_others():
    client = make_client([make_response([ROCK_EVENT, NON_ROCK_EVENT, EXCLUDED_EVENT])])
    with patch("app.scrapers.sesccultura.get_client") as gc:
        gc.return_value = client
        events = SescCulturaScraper().fetch()

    assert len(events) == 1
    e = events[0]
    assert e.title == "Banda Trisônica"
    assert e.url == "https://cultura.sescrio.org.br/programacao/banda-trisonica?sessao=2026-04-18/2026-04-18"
    assert e.venue == "Sesc Nogueira"
    assert e.city == "Rio das Ostras"
    assert e.organizer == "Sesc Rio"
    assert e.date.isoformat() == "2026-04-18T20:00:00-03:00"
    assert e.end_date.isoformat() == "2026-04-18T21:30:00-03:00"
    assert e.price == "Grátis"
    assert e.image == "https://cdn.example.com/img.jpg"
    assert "Barão Vermelho" in e.description


def test_prefers_real_ticket_url_when_present():
    event = {
        **ROCK_EVENT,
        "event_meta": {
            **ROCK_EVENT["event_meta"],
            "sessoes": [
                {
                    **ROCK_EVENT["event_meta"]["sessoes"][0],
                    "url_ingresso": "https://www.ingresso.com/evento/banda-trisonica-ccsq",
                }
            ],
        },
    }
    client = make_client([make_response([event])])
    with patch("app.scrapers.sesccultura.get_client") as gc:
        gc.return_value = client
        events = SescCulturaScraper().fetch()

    assert events[0].url == "https://www.ingresso.com/evento/banda-trisonica-ccsq"


def test_multiple_sessions_become_separate_events():
    event = {
        **ROCK_EVENT,
        "event_meta": {
            **ROCK_EVENT["event_meta"],
            "sessoes": [
                ROCK_EVENT["event_meta"]["sessoes"][0],
                {
                    "local": "Sesc Tijuca",
                    "data_intervalo_iso8601": "2026-06-09/2026-06-09",
                    "hora_intervalo_iso8601": "19:00:00/20:10:00",
                    "url_ingresso": "",
                    "ingressos": [{"tipo": "Inteira", "preco": "15"}],
                },
            ],
        },
    }
    client = make_client([make_response([event])])
    with patch("app.scrapers.sesccultura.get_client") as gc:
        gc.return_value = client
        events = SescCulturaScraper().fetch()

    assert len(events) == 2
    assert {e.venue for e in events} == {"Sesc Nogueira", "Sesc Tijuca"}


def test_stops_pagination_when_page_returns_fewer_than_page_size():
    client = make_client([make_response([ROCK_EVENT])])
    with patch("app.scrapers.sesccultura.get_client") as gc:
        gc.return_value = client
        events = SescCulturaScraper().fetch()

    assert len(events) == 1
    assert client.get.call_count == 1
