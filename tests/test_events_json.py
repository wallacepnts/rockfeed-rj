from datetime import datetime, timedelta, timezone

from app.events_json import build_events_json


def _row(**overrides):
    row = {
        "title": "Show",
        "url": "http://x/1",
        "source": "sympla",
        "venue": "",
        "address": "",
        "organizer": "",
        "city": "",
        "date": None,
        "end_date": None,
        "price": "",
        "image": "",
        "description": "",
        "found_at": datetime.now(timezone.utc).isoformat(),
        "uid": "uid-1",
    }
    row.update(overrides)
    return row


def test_build_events_json_excludes_past_events(monkeypatch):
    past = _row(
        title="Show Passado",
        uid="past",
        date=(datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
    )
    future = _row(
        title="Show Futuro",
        uid="future",
        date=(datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
    )
    no_date = _row(title="Sem Data", uid="nodate", date=None)

    monkeypatch.setattr(
        "app.events_json.store.latest", lambda limit: [past, future, no_date]
    )
    events = build_events_json()

    titles = {e["title"] for e in events}
    assert "Show Passado" not in titles
    assert "Show Futuro" in titles
    assert "Sem Data" in titles


def test_build_events_json_returns_structured_fields(monkeypatch):
    row = _row(
        title="Show Estruturado",
        venue="Circo Voador",
        address="Rio de Janeiro/RJ",
        organizer="Produtora X",
        city="Rio de Janeiro",
        price="R$ 50",
        image="http://x/img.jpg",
        description="Descrição do show",
    )
    monkeypatch.setattr("app.events_json.store.latest", lambda limit: [row])
    events = build_events_json()

    assert events == [
        {
            "uid": "uid-1",
            "title": "Show Estruturado",
            "url": "http://x/1",
            "source": "sympla",
            "venue": "Circo Voador",
            "address": "Rio de Janeiro/RJ",
            "organizer": "Produtora X",
            "city": "Rio de Janeiro",
            "date": None,
            "end_date": None,
            "price": "R$ 50",
            "image": "http://x/img.jpg",
            "description": "Descrição do show",
        }
    ]
