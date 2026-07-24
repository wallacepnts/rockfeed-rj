"""Bileto — plataforma de ticketing legada que a Sympla mantém à parte
(bileto.sympla.com.br), usada por casas como a Areninha Cultural Hermeto
Pascoal.

A API é https://bff-sales-api-cdn.bileto.sympla.com.br/api/v1/events/{id}
(precisa do header x-api-key visto na própria página do evento). Não existe
— ou pelo menos não achamos — um endpoint que liste todos os eventos de um
produtor: o "organizer_id" que a API retorna costuma ser a conta de
ticketing do próprio local, não o produtor real do show, e a API nunca
expõe um nome legível de organizador.

Por isso essa fonte funciona por lista curada de eventos, não por produtor:
pegue o link bileto.sympla.com.br/event/<id> de cada show de rock que
achar e adicione em EVENTS. Se você souber quem é o produtor de verdade
(a API não sabe), informe em organizer_override; senão deixe None.
"""
from __future__ import annotations

import logging
from datetime import datetime

import httpx

from app.models import Event
from app.scrapers.base import Scraper, get_client, strip_html

API_BASE = "https://bff-sales-api-cdn.bileto.sympla.com.br/api/v1"
API_KEY = "cQkazy2Wc"

EVENTS = [
    # (event_id, organizer_override — None se você não souber quem produz)
    (121087, None),
    (119374, "Be Magic"),
    (122061, None),
    (124028, None),
    (124027, None),
    (123463, None),
    (109416, None),
    (120951, None),
    (123596, None),
]

log = logging.getLogger("rockfeed")


class BiletoScraper(Scraper):
    name = "bileto"

    def fetch(self) -> list[Event]:
        events: list[Event] = []
        with get_client() as client:
            for event_id, organizer_override in EVENTS:
                event = self._fetch_event(client, event_id, organizer_override)
                if event:
                    events.append(event)
        return events

    def _fetch_event(
        self, client: httpx.Client, event_id: int, organizer_override: str | None
    ) -> Event | None:
        try:
            resp = client.get(
                f"{API_BASE}/events/{event_id}",
                headers={"x-api-key": API_KEY, "accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()["data"]
        except httpx.HTTPError:
            log.warning("bileto: falha ao buscar evento %d, pulando", event_id)
            return None

        venue = data.get("venue") or {}
        locale = venue.get("locale") or {}
        city = (locale.get("city") or {}).get("name") or "Rio de Janeiro"
        address = ", ".join(
            p
            for p in (
                locale.get("address"),
                city,
                (locale.get("state") or {}).get("name"),
                locale.get("postal_code"),
            )
            if p
        )

        images = data.get("medias") or []
        image = next((m["url"] for m in images if m.get("rel") == "profile"), "")

        return Event(
            title=data.get("name", ""),
            url=f"https://bileto.sympla.com.br/event/{event_id}",
            source=self.name,
            venue=venue.get("name", ""),
            address=address,
            organizer=organizer_override or "",
            city=city,
            date=self._parse_date(data.get("next_local_date_time")),
            # a API não expõe um horário de encerramento de verdade (só a
            # data da próxima/última sessão, geralmente igual à de início)
            end_date=None,
            price=self._format_price(data),
            image=image,
            description=strip_html((data.get("description") or {}).get("raw", "")),
        )

    @staticmethod
    def _format_price(data: dict) -> str:
        lowest = (data.get("presentations") or {}).get("lowest_price") or {}
        value = lowest.get("value")
        if not value:
            return ""
        try:
            return f"R$ {int(value) / 100:.2f}"
        except (TypeError, ValueError):
            return ""

    @staticmethod
    def _parse_date(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
