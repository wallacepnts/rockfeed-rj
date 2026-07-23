from unittest.mock import MagicMock, patch

import httpx

from app.scrapers.sympla import SymplaScraper

EVENT_ITEM = {
    "id": 3484588,
    "name": "KRUGER - TRIBUTO SYSTEM OF A DOWN",
    "url": "https://www.sympla.com.br/evento/kruger/3484588",
    "start_date": "2026-07-25T01:00:00+00:00",
    "end_date": "2026-07-25T05:00:00+00:00",
    "images": {
        "original": "https://images.sympla.com.br/img.jpg",
        "lg": "https://images.sympla.com.br/img-lg.jpg",
    },
    "location": {
        "name": "DRUNKS PUB",
        "address": "Estrada Rio do A",
        "address_num": "695",
        "neighborhood": "Campo Grande",
        "city": "Rio de Janeiro",
        "state": "RJ",
        "zip_code": "23080-300",
    },
    "organizer": {"id": "14627486", "name": "FABRICIO MOTTA"},
}


def make_response(data, total):
    resp = MagicMock()
    resp.raise_for_status.side_effect = None
    resp.json.return_value = {"data": data, "total": total, "limit": 24, "page": 1}
    return resp


def make_tickets_response(price=18.99):
    resp = MagicMock()
    resp.raise_for_status.side_effect = None
    resp.json.return_value = {
        "tickets": [{"show": True, "salePriceMonetary": {"decimal": price}}]
    }
    return resp


def make_client(pages):
    client = MagicMock()
    client.post.side_effect = pages
    client.get.return_value = make_tickets_response()
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    return client


def test_parses_single_page_of_events():
    client = make_client([make_response([EVENT_ITEM], total=1)])
    with patch("app.scrapers.sympla.get_client") as gc, \
         patch("app.scrapers.sympla.ORGANIZERS", [("drunkspubcg", 14627486)]):
        gc.return_value = client
        events = SymplaScraper().fetch()

    assert len(events) == 1
    e = events[0]
    assert e.title == "KRUGER - TRIBUTO SYSTEM OF A DOWN"
    assert e.url == "https://www.sympla.com.br/evento/kruger/3484588"
    assert e.source == "sympla:drunkspubcg"
    assert e.venue == "DRUNKS PUB"
    assert e.address == "Estrada Rio do A 695, Campo Grande, Rio de Janeiro, RJ, 23080-300"
    assert e.organizer == "FABRICIO MOTTA"
    assert e.city == "Rio de Janeiro"
    assert e.date.isoformat() == "2026-07-25T01:00:00+00:00"
    assert e.end_date.isoformat() == "2026-07-25T05:00:00+00:00"
    assert e.image == "https://images.sympla.com.br/img-lg.jpg"
    assert e.price == "R$ 18.99"
    assert client.post.call_count == 1


def test_falls_back_to_original_image_when_lg_missing():
    item = {**EVENT_ITEM, "images": {"original": "https://images.sympla.com.br/img.jpg"}}
    client = make_client([make_response([item], total=1)])
    with patch("app.scrapers.sympla.get_client") as gc, \
         patch("app.scrapers.sympla.ORGANIZERS", [("drunkspubcg", 14627486)]):
        gc.return_value = client
        events = SymplaScraper().fetch()

    assert events[0].image == "https://images.sympla.com.br/img.jpg"


def test_price_fetch_failure_leaves_price_blank():
    client = make_client([make_response([EVENT_ITEM], total=1)])
    fail_resp = MagicMock()
    fail_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "boom", request=None, response=None
    )
    client.get.return_value = fail_resp

    with patch("app.scrapers.sympla.get_client") as gc, \
         patch("app.scrapers.sympla.ORGANIZERS", [("drunkspubcg", 14627486)]):
        gc.return_value = client
        events = SymplaScraper().fetch()

    assert events[0].price == ""


def test_stops_pagination_once_total_is_reached():
    page1 = [dict(EVENT_ITEM, id=i, url=f"https://x/{i}") for i in range(24)]
    page2 = [dict(EVENT_ITEM, id=24, url="https://x/24")]
    client = make_client(
        [make_response(page1, total=25), make_response(page2, total=25)]
    )
    with patch("app.scrapers.sympla.get_client") as gc, \
         patch("app.scrapers.sympla.ORGANIZERS", [("drunkspubcg", 14627486)]):
        gc.return_value = client
        events = SymplaScraper().fetch()

    assert len(events) == 25
    assert client.post.call_count == 2


def test_page_failure_preserves_events_already_collected():
    page1 = [dict(EVENT_ITEM, id=i, url=f"https://x/{i}") for i in range(24)]
    ok_resp = make_response(page1, total=50)

    fail_resp = MagicMock()
    fail_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "boom", request=None, response=None
    )

    client = make_client([ok_resp, fail_resp])
    with patch("app.scrapers.sympla.get_client") as gc, \
         patch("app.scrapers.sympla.ORGANIZERS", [("drunkspubcg", 14627486)]):
        gc.return_value = client
        events = SymplaScraper().fetch()

    assert len(events) == 24
