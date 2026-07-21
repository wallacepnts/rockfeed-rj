"""Exportação JSON estruturada dos eventos, para importação por sistemas
externos (ex: Revel) — diferente do feed.xml, que é formatado pra leitores RSS.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app import store


def build_events_json(limit: int = 1000) -> list[dict]:
    today = datetime.now(timezone.utc).date().isoformat()
    events = []
    for e in store.latest(limit):
        if e.get("date") and e["date"][:10] < today:
            continue  # show já aconteceu
        events.append(
            {
                "uid": e["uid"],
                "title": e["title"],
                "url": e["url"],
                "source": e["source"],
                "venue": e.get("venue") or "",
                "address": e.get("address") or "",
                "organizer": e.get("organizer") or "",
                "city": e.get("city") or "",
                "date": e.get("date"),
                "end_date": e.get("end_date"),
                "price": e.get("price") or "",
                "image": e.get("image") or "",
                "description": e.get("description") or "",
            }
        )
    return events
