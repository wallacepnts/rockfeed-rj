"""Meaple — plataforma de eventos usada por bares/casas de show independentes
(ex: Macaco Caolho Rock Pub).

API pública: https://api.meaple.com.br/v1
- GET /channels/{slug}            -> resolve o slug pro id interno (cuid)
- GET /channels/{id}/events?type=FUTURE -> lista os próximos eventos do canal

Cada canal é um bar/produtor que você já sabe que é de rock — os eventos são
aceitos sem passar pelo filtro genérico de keywords, igual às páginas
curadas da Articket.

Adicione outros canais de rock que você acompanha em CHANNELS.
"""
from __future__ import annotations

import logging
from datetime import datetime

import httpx

from app.models import Event
from app.scrapers.base import Scraper, get_client

API_BASE = "https://api.meaple.com.br/v1"

CHANNELS = [
    "macacocaolhopub",
    "calaboucorockbar",
    "coordenadasbar",
    "orockvive",
    "tributando-emocoes",
    "meltonsello",
    "bar-do-chico",
    "brookspubrecreio",
    "brookspubmeier",
]

log = logging.getLogger("rockfeed")


def _flatten_description(nodes: list | None) -> str:
    """A descrição vem em rich-text (lista de parágrafos com 'children'); vira texto puro."""
    lines = []
    for node in nodes or []:
        text = "".join(child.get("text", "") for child in node.get("children", []))
        if text.strip():
            lines.append(text.strip())
    return "\n".join(lines)


class MeapleScraper(Scraper):
    name = "meaple"

    def fetch(self) -> list[Event]:
        events: list[Event] = []
        with get_client() as client:
            for slug in CHANNELS:
                try:
                    resp = client.get(f"{API_BASE}/channels/{slug}")
                    resp.raise_for_status()
                    channel = resp.json()["channel"]
                except httpx.HTTPError:
                    log.warning("meaple: falha ao resolver canal '%s', pulando", slug)
                    continue

                try:
                    resp = client.get(
                        f"{API_BASE}/channels/{channel['id']}/events",
                        params={"type": "FUTURE"},
                    )
                    resp.raise_for_status()
                    raw_events = resp.json()["events"]
                except httpx.HTTPError:
                    log.warning("meaple: falha ao buscar eventos de '%s', pulando", slug)
                    continue

                for raw in raw_events:
                    if raw.get("canceledAt"):
                        continue
                    events.append(self._parse_event(slug, channel, raw))
        return events

    def _parse_event(self, slug: str, channel: dict, raw: dict) -> Event:
        addr = raw.get("address") or {}
        street_line = " ".join(
            p for p in (addr.get("street") or "", addr.get("number") or "") if p
        ).strip()
        address = ", ".join(
            p
            for p in (
                street_line,
                addr.get("neighborhood"),
                addr.get("city"),
                addr.get("state"),
                addr.get("zipCode"),
            )
            if p
        )

        date = self._parse_date(raw.get("startsAt"))
        end_date = self._parse_date(raw.get("endsAt"))

        return Event(
            title=(raw.get("name") or "").strip(),
            url=f"https://meaple.com.br/{slug}/{raw.get('slug', '')}",
            source=f"{self.name}:{slug}",
            venue=channel.get("name", ""),
            address=address,
            organizer=channel.get("name", ""),
            city=addr.get("city") or "Rio de Janeiro",
            date=date,
            end_date=end_date,
            image=(raw.get("image") or {}).get("url", ""),
            description=_flatten_description(raw.get("description")),
        )

    @staticmethod
    def _parse_date(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
