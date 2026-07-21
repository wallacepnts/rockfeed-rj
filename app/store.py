"""Persistência em SQLite: guarda eventos já vistos para deduplicar
e manter o histórico do feed mesmo que um site fique fora do ar.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.models import Event

DB_PATH = Path(__file__).resolve().parent / "data" / "events.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    uid TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    source TEXT NOT NULL,
    venue TEXT,
    address TEXT,
    organizer TEXT,
    city TEXT,
    date TEXT,
    end_date TEXT,
    price TEXT,
    image TEXT,
    description TEXT,
    found_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


def upsert(events: list[Event]) -> int:
    """Insere só eventos novos; retorna quantos foram inseridos."""
    new = 0
    with _connect() as conn:
        for e in events:
            cur = conn.execute(
                """INSERT OR IGNORE INTO events
                   (uid, title, url, source, venue, address, organizer, city,
                    date, end_date, price, image, description, found_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    e.uid, e.title, e.url, e.source, e.venue, e.address,
                    e.organizer, e.city,
                    e.date.isoformat() if e.date else None,
                    e.end_date.isoformat() if e.end_date else None,
                    e.price, e.image, e.description,
                    e.found_at.isoformat(),
                ),
            )
            new += cur.rowcount
    return new


def latest(limit: int = 1000) -> list[dict]:
    """Eventos mais recentes (pela data em que foram encontrados)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY found_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
