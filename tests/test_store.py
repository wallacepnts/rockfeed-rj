import pytest

from app import store
from app.models import Event


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "events.db")


def make_event(url="http://x/1", source="sympla", title="Show"):
    return Event(title=title, url=url, source=source)


def test_upsert_inserts_new_events():
    inserted = store.upsert([make_event()])
    assert inserted == 1
    assert len(store.latest(10)) == 1


def test_upsert_deduplicates_by_uid():
    store.upsert([make_event()])
    inserted_again = store.upsert([make_event()])
    assert inserted_again == 0
    assert len(store.latest(10)) == 1


def test_same_url_different_source_is_not_a_duplicate():
    store.upsert([make_event(source="sympla")])
    inserted = store.upsert([make_event(source="eventim")])
    assert inserted == 1
    assert len(store.latest(10)) == 2


def test_latest_respects_limit():
    store.upsert([make_event(url=f"http://x/{i}") for i in range(5)])
    assert len(store.latest(2)) == 2


def test_upsert_refreshes_fields_of_existing_event():
    event = make_event()
    event.organizer = "Coordenadas Bar"
    store.upsert([event])

    updated = make_event()
    updated.organizer = "Mr. Trip Produções"
    inserted = store.upsert([updated])

    assert inserted == 0
    rows = store.latest(10)
    assert len(rows) == 1
    assert rows[0]["organizer"] == "Mr. Trip Produções"


def test_upsert_preserves_found_at_on_update():
    store.upsert([make_event()])
    first_found_at = store.latest(10)[0]["found_at"]

    updated = make_event()
    updated.found_at = updated.found_at.replace(year=updated.found_at.year + 1)
    store.upsert([updated])

    assert store.latest(10)[0]["found_at"] == first_found_at
