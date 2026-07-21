from datetime import datetime, timedelta, timezone

from app.feed import _esc, build_rss


def _row(**overrides):
    row = {
        "title": "Show",
        "url": "http://x/1",
        "source": "sympla",
        "venue": "",
        "city": "",
        "date": None,
        "price": "",
        "image": "",
        "description": "",
        "found_at": datetime.now(timezone.utc).isoformat(),
        "uid": "uid-1",
    }
    row.update(overrides)
    return row


def test_esc_escapes_quotes_for_xml_attributes():
    escaped = _esc('Show "Especial" & Cia <ao vivo>')
    assert '"' not in escaped
    assert "&quot;" in escaped
    assert "&amp;" in escaped
    assert "&lt;" in escaped and "&gt;" in escaped


def test_build_rss_excludes_past_events(monkeypatch):
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

    monkeypatch.setattr("app.feed.store.latest", lambda limit: [past, future, no_date])
    xml = build_rss()

    assert "Show Passado" not in xml
    assert "Show Futuro" in xml
    assert "Sem Data" in xml


def test_build_rss_escapes_image_url_quotes(monkeypatch):
    row = _row(image='http://x/img.jpg?a=1"onerror=alert(1)')
    monkeypatch.setattr("app.feed.store.latest", lambda limit: [row])
    xml = build_rss()
    # a aspa não escapada fecharia o atributo url="" prematuramente
    assert '1"onerror' not in xml
    assert "1&quot;onerror" in xml
