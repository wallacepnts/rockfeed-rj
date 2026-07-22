from unittest.mock import MagicMock, patch

import httpx

import app.revel_push as revel_push


def configure(monkeypatch, url="https://revel.example/api/external/events", key="secret-key"):
    monkeypatch.setattr(revel_push, "REVEL_INGEST_URL", url)
    monkeypatch.setattr(revel_push, "REVEL_INGEST_API_KEY", key)


def make_response(results):
    resp = MagicMock()
    resp.raise_for_status.side_effect = None
    resp.json.return_value = {"results": results}
    return resp


def test_does_nothing_when_url_not_configured(monkeypatch):
    configure(monkeypatch, url="")
    with patch("app.revel_push.httpx.post") as post:
        revel_push.push_to_revel()
    post.assert_not_called()


def test_does_nothing_when_api_key_not_configured(monkeypatch):
    configure(monkeypatch, key="")
    with patch("app.revel_push.httpx.post") as post:
        revel_push.push_to_revel()
    post.assert_not_called()


def test_does_nothing_when_there_are_no_events(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(revel_push, "build_events_json", lambda: [])
    with patch("app.revel_push.httpx.post") as post:
        revel_push.push_to_revel()
    post.assert_not_called()


def test_posts_events_with_bearer_auth(monkeypatch):
    configure(monkeypatch, url="https://revel.example/api/external/events", key="secret-key")
    events = [{"uid": "abc", "title": "Show"}]
    monkeypatch.setattr(revel_push, "build_events_json", lambda: events)

    with patch("app.revel_push.httpx.post") as post:
        post.return_value = make_response([{"uid": "abc", "action": "created"}])
        revel_push.push_to_revel()

    post.assert_called_once_with(
        "https://revel.example/api/external/events",
        json=events,
        headers={"Authorization": "Bearer secret-key"},
        timeout=revel_push.REVEL_PUSH_TIMEOUT,
    )


def test_swallows_connection_errors(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(revel_push, "build_events_json", lambda: [{"uid": "abc"}])

    with patch("app.revel_push.httpx.post") as post:
        post.side_effect = httpx.ConnectError("boom")
        revel_push.push_to_revel()  # não deve levantar


def test_swallows_http_status_errors(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(revel_push, "build_events_json", lambda: [{"uid": "abc"}])

    fail_resp = MagicMock()
    fail_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "boom", request=None, response=None
    )

    with patch("app.revel_push.httpx.post") as post:
        post.return_value = fail_resp
        revel_push.push_to_revel()  # não deve levantar
