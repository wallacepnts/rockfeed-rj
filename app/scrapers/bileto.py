"""Bileto — plataforma de ticketing legada que a Sympla mantém à parte
(bileto.sympla.com.br), usada por casas como a Areninha Cultural Hermeto
Pascoal.

A API de cada evento é
https://bff-sales-api-cdn.bileto.sympla.com.br/api/v1/events/{id}
(precisa do header x-api-key visto na própria página do evento). O
"organizer_id" que ela retorna costuma ser a conta de ticketing do próprio
local, não o produtor real do show, e a API nunca expõe um nome legível de
organizador.

Descoberta automática por local: a página do produtor
(site.bileto.sympla.com.br/<slug>/) incorpora um widget "agenda de
eventos" hospedado em sympla.com.br/agenda-eventos/<hash> que lista todos
os eventos futuros da casa — capture essa URL abrindo a página do local
com o DevTools (aba Network) e procurando o iframe/link pra
"agenda-eventos", e adicione em VENUES. Diferente da Sympla/Meaple, esses
locais costumam ser centros culturais gerais (teatro, dança, biblioteca
etc.), não bares de rock dedicados — por isso a descoberta por VENUES
passa pelo filtro genérico de keywords (is_rock(), base.py) em vez de
aceitar tudo.

Locais sem esse widget (ou eventos avulsos sem local mapeado) entram em
EVENTS por link direto; informe organizer_override quando souber quem
produz de verdade (a API não sabe), senão deixe None.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime

import httpx

from app.models import Event
from app.scrapers.base import Scraper, get_client, is_rock, strip_html

API_BASE = "https://bff-sales-api-cdn.bileto.sympla.com.br/api/v1"
API_KEY = "cQkazy2Wc"

VENUES = [
    # (rótulo, URL do widget "agenda-eventos" embutido na página do local)
    (
        "areninhaculturalhermetopascoal",
        "https://www.sympla.com.br/agenda-eventos/m-lkysRaP5jPcLaW3iVa0lFyZpw2xH45R4EWhBITmbAoohbI2W6VZd-aK0oBIVSTI_e-UEVd_iUOL5W6yxTDQg",
    ),
]

# organizer_override por event_id, pra casos em que se sabe quem produz de
# verdade mesmo vindo da descoberta automática por local (a API não sabe).
ORGANIZER_OVERRIDES: dict[int, str] = {
    119374: "Be Magic",
}

EVENTS = [
    # (event_id, organizer_override — None se você não souber quem produz)
    (122061, None),
    (124028, None),
    (124027, None),
    (109416, None),
    (120951, None),
    (123596, None),
    (124526, None),
    (123300, None),
    (123089, None),
    (103244, None),
    (95883, None),
    (124279, None),
]

_EVENT_ID_RE = re.compile(r"bileto\.sympla\.com\.br/event/(\d+)")

log = logging.getLogger("rockfeed")


class BiletoScraper(Scraper):
    name = "bileto"

    def fetch(self) -> list[Event]:
        events: list[Event] = []
        seen_ids: set[int] = set()
        with get_client() as client:
            for label, agenda_url in VENUES:
                for event_id in self._discover_venue_events(client, agenda_url):
                    if event_id in seen_ids:
                        continue
                    seen_ids.add(event_id)
                    event = self._fetch_event(
                        client,
                        event_id,
                        ORGANIZER_OVERRIDES.get(event_id),
                        source=f"{self.name}:{label}",
                        require_rock=True,
                    )
                    if event:
                        events.append(event)

            for event_id, organizer_override in EVENTS:
                if event_id in seen_ids:
                    continue
                seen_ids.add(event_id)
                event = self._fetch_event(client, event_id, organizer_override, source=self.name)
                if event:
                    events.append(event)
        return events

    def _discover_venue_events(self, client: httpx.Client, agenda_url: str) -> list[int]:
        try:
            resp = client.get(agenda_url)
            resp.raise_for_status()
        except httpx.HTTPError:
            log.warning("bileto: falha ao buscar agenda %s, pulando", agenda_url)
            return []
        return sorted({int(m) for m in _EVENT_ID_RE.findall(resp.text)})

    def _fetch_event(
        self,
        client: httpx.Client,
        event_id: int,
        organizer_override: str | None,
        source: str,
        require_rock: bool = False,
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

        title = data.get("name", "")
        description = strip_html((data.get("description") or {}).get("raw", ""))
        if require_rock and not is_rock(title, description):
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
            title=title,
            url=f"https://bileto.sympla.com.br/event/{event_id}",
            source=source,
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
            description=description,
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
