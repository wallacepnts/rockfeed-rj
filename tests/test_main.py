import pytest
from fastapi import HTTPException
from starlette.requests import Request

import app.main as m


def make_request(headers=None):
    headers = headers or {}
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    scope = {"type": "http", "headers": raw_headers, "method": "GET"}
    return Request(scope)


@pytest.fixture(autouse=True)
def no_real_store(monkeypatch):
    monkeypatch.setattr(m.store, "latest", lambda limit=100: [])


@pytest.fixture(autouse=True)
def reset_refresh_throttle(monkeypatch):
    monkeypatch.setattr(m, "_last_manual_refresh", None)


def test_feed_returns_etag():
    resp = m.feed(make_request())
    assert resp.status_code == 200
    assert resp.headers.get("etag")


def test_feed_returns_304_when_etag_matches():
    first = m.feed(make_request())
    etag = first.headers["etag"]
    second = m.feed(make_request({"If-None-Match": etag}))
    assert second.status_code == 304
    assert second.body == b""


def test_feed_returns_200_when_etag_stale():
    m.feed(make_request())
    resp = m.feed(make_request({"If-None-Match": "stale-value"}))
    assert resp.status_code == 200


def test_refresh_blocks_repeated_calls(monkeypatch):
    monkeypatch.setattr(m, "run_scrapers", lambda: {"ok": True})
    m.refresh()
    with pytest.raises(HTTPException) as exc_info:
        m.refresh()
    assert exc_info.value.status_code == 429


def test_refresh_allows_call_after_interval_elapses(monkeypatch):
    from datetime import datetime, timezone

    monkeypatch.setattr(m, "run_scrapers", lambda: {"ok": True})
    m.refresh()
    monkeypatch.setattr(
        m, "_last_manual_refresh", datetime.now(timezone.utc) - m.MIN_MANUAL_REFRESH_INTERVAL
    )
    assert m.refresh() == {"ok": True}
