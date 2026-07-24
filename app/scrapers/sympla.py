"""Sympla — busca eventos de produtores específicos via API de busca do site.

A API pública usada pelo próprio site é um proxy em
POST https://www.sympla.com.br/api/v1/search, com payload
{"service": "/v5/search", "params": {...}}. O parâmetro relevante pra listar
os eventos de um produtor é organizer_id — o ID numérico interno do
produtor, não o slug que aparece na URL /produtor/<slug>.

Não existe um jeito estático de descobrir esse organizer_id a partir do
slug: a página /produtor/<slug> não expõe isso nem no HTML nem nos bundles
JS (o resto do site é uma SPA client-rendered sem API estática visível).
Pra adicionar um novo produtor, capture o organizer_id abrindo o DevTools
(aba Network, filtro Fetch/XHR) na página do produtor, achando a
requisição "search" feita pelo site e olhando o campo organizer_id no
payload — depois é só somar (rótulo, organizer_id) em ORGANIZERS.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

import httpx

from app.models import Event
from app.scrapers.base import Scraper, get_client, strip_html

SEARCH_URL = "https://www.sympla.com.br/api/v1/search"
EVENT_API_BASE = "https://event-page.svc.sympla.com.br/api/event-bff/purchase/event"

ONLY_FIELDS = (
    "name,start_date,end_date,images,event_type,duration_type,location,"
    "id,global_score,start_date_formats,end_date_formats,url,company,type,organizer"
)

ORGANIZERS = [
    # (rótulo, organizer_id)
    ("drunkspubcg", 14627486),
    ("ttgarage", 15611642),
    ("raoni", 1075269),
    ("corporateeventsbrasil", 4467917),
    ("retrobar1141", 15731574),
    ("heavybeerbar", 12444208),
    ("djcidinho", 11635758),
    ("moonlitreverie", 319322218),
    ("rodrigofelippe", 10009916),
    ("rocknewyork", 18932139),
    ("hallted", 307272757),
    ("erreifestival4", 12357135),
    ("roxxmusicbar", 22560506),
    ("festemorj", 165690),
    ("oclapub", 7745786),
    ("studiosuburbia", 315545187),
    ("gabrielmezzalira", 13209059),
]

PAGE_SIZE = 24

log = logging.getLogger("rockfeed")


def _fetch_lowest_price(client: httpx.Client, event_id) -> str:
    """Menor preço de ingresso visível pro evento (endpoint .../tickets/grouped)."""
    try:
        resp = client.get(f"{EVENT_API_BASE}/{event_id}/tickets/grouped")
        resp.raise_for_status()
        tickets = resp.json().get("tickets", [])
    except httpx.HTTPError:
        return ""

    prices = [
        t["salePriceMonetary"]["decimal"]
        for t in tickets
        if t.get("show") and t.get("salePriceMonetary")
    ]
    if not prices:
        return ""
    lowest = min(prices)
    return "Grátis" if lowest <= 0 else f"R$ {lowest:.2f}"


class SymplaScraper(Scraper):
    name = "sympla"

    def fetch(self) -> list[Event]:
        events: list[Event] = []
        with get_client() as client:
            for label, organizer_id in ORGANIZERS:
                events.extend(self._fetch_organizer(client, label, organizer_id))
        return events

    def _fetch_organizer(
        self, client: httpx.Client, label: str, organizer_id: int
    ) -> list[Event]:
        events: list[Event] = []
        page = 1
        while True:
            body = {
                "service": "/v5/search",
                "params": {
                    "only": ONLY_FIELDS,
                    "organizer_id": organizer_id,
                    "sort": "date",
                    "limit": str(PAGE_SIZE),
                    "page": page,
                },
                "ignoreLocation": True,
            }
            try:
                resp = client.post(
                    SEARCH_URL, json=body, headers={"content-type": "application/json"}
                )
                resp.raise_for_status()
                payload = resp.json()
            except httpx.HTTPError:
                log.warning(
                    "sympla: falha ao buscar produtor '%s' (página %d), mantendo eventos já coletados",
                    label,
                    page,
                )
                break

            items = payload.get("data", [])
            if not items:
                break
            events.extend(self._parse_event(client, label, item) for item in items)

            if len(events) >= payload.get("total", 0) or len(items) < PAGE_SIZE:
                break
            page += 1
        return events

    def _parse_event(self, client: httpx.Client, label: str, item: dict) -> Event:
        images = item.get("images") or {}
        location = item.get("location") or {}
        street_line = " ".join(
            p for p in (location.get("address"), location.get("address_num")) if p
        ).strip()
        address = ", ".join(
            p
            for p in (
                street_line,
                location.get("neighborhood"),
                location.get("city"),
                location.get("state"),
                location.get("zip_code"),
            )
            if p
        )
        organizer = (item.get("organizer") or {}).get("name", "")

        return Event(
            title=item.get("name", ""),
            url=item.get("url", ""),
            source=f"{self.name}:{label}",
            venue=location.get("name", ""),
            address=address,
            organizer=organizer,
            city=location.get("city") or "Rio de Janeiro",
            date=self._parse_date(item.get("start_date")),
            end_date=self._parse_date(item.get("end_date")),
            price=_fetch_lowest_price(client, item.get("id")),
            image=images.get("lg") or images.get("original", ""),
        )

    @staticmethod
    def _parse_date(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None


# Horário local do Rio/SP é UTC-3 o ano todo desde o fim do horário de
# verão em 2019 — os campos de data das páginas de evento não trazem offset.
_BR_TZ = timezone(timedelta(hours=-3))

_EVENT_ID_RE = re.compile(r"/(\d+)$")


class SymplaEventScraper(Scraper):
    """Eventos avulsos da Sympla — quando você não sabe (ou não consegue
    achar) a página do produtor, mas tem o link de um show específico.

    Usa a mesma API que a página do evento chama por trás (event-page.svc),
    identificando o evento pelo ID no final da URL — sem precisar descobrir
    organizer_id nem raspar HTML. Traz nome do produtor (eventsHost) e o
    menor preço de ingresso disponível (endpoint .../tickets/grouped).

    eventsHost costuma ser só a conta pessoal de quem cadastrou o evento na
    Sympla, não o produtor/marca de verdade — quando você souber quem
    realmente organiza, informe em organizer_override; senão deixe None.

    Adicione os links dos shows que achar em EVENTS.
    """

    name = "sympla_eventos"

    def fetch(self) -> list[Event]:
        events: list[Event] = []
        with get_client() as client:
            for url, organizer_override in EVENTS:
                event = self._fetch_event(client, url, organizer_override)
                if event:
                    events.append(event)
        return events

    def _fetch_event(
        self, client: httpx.Client, url: str, organizer_override: str | None
    ) -> Event | None:
        clean_url = url.split("?")[0]
        m = _EVENT_ID_RE.search(clean_url)
        if not m:
            log.warning("sympla: não achei o ID do evento em %s, pulando", clean_url)
            return None
        event_id = m.group(1)

        try:
            resp = client.get(f"{EVENT_API_BASE}/{event_id}")
            resp.raise_for_status()
            event = resp.json()
        except httpx.HTTPError:
            log.warning("sympla: falha ao buscar evento %s, pulando", clean_url)
            return None

        if event.get("cancelled"):
            return None

        address_info = event.get("eventsAddress") or {}
        street_line = " ".join(
            p for p in (address_info.get("address"), address_info.get("addressNum")) if p
        ).strip()
        address = ", ".join(
            p
            for p in (
                street_line,
                address_info.get("neighborhood"),
                address_info.get("city"),
                address_info.get("state"),
                address_info.get("zipCode"),
            )
            if p
        )

        host = event.get("eventsHost") or {}
        images = event.get("images") or {}
        details = ((event.get("details") or {}).get("pt") or {}).get("text", "")

        return Event(
            title=event.get("name", ""),
            url=clean_url,
            source=self.name,
            venue=address_info.get("name", ""),
            address=address,
            organizer=organizer_override or host.get("name", ""),
            city=address_info.get("city") or "Rio de Janeiro",
            date=self._parse_local_date(event.get("startDate")),
            end_date=self._parse_local_date(event.get("endDate")),
            price=_fetch_lowest_price(client, event_id),
            image=images.get("logoLarge") or images.get("logoUrl", ""),
            description=strip_html(details),
        )

    @staticmethod
    def _parse_local_date(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_BR_TZ)
        except ValueError:
            return None


EVENTS = [
    # (url, organizer_override — None se o eventsHost já for o produtor real)
    # os 6 links originais (Victims of a Down, Rock N Radio, Moonlit Reverie
    # Fest, The Jekylls, Rock New York, Hallted) viraram entradas em
    # ORGANIZERS acima — removidos daqui pra não duplicar no feed.
    ("https://www.sympla.com.br/evento/dr-chud-misfitis-rio-de-janeiro/3373200", None),
    ("https://www.sympla.com.br/evento/animals-lab-24-de-julho-heavy-beer/3462550", "LET'S ROCK"),
    ("https://www.sympla.com.br/evento/show-the-docs/3512510", None),
    ("https://www.sympla.com.br/evento/vinx-no-garage/3509641", None),
    ("https://www.sympla.com.br/evento/anti-climax/3496669", None),
    ("https://www.sympla.com.br/evento/backthothe90-s-show-case-elvm-2026/3514709", None),
    ("https://www.sympla.com.br/evento/teto-preto-mokambo-e-coyote-valvulado/3490755", None),
    ("https://www.sympla.com.br/evento/stay-negative-aniversario-dessa-pazinatto/3506149", None),
    ("https://www.sympla.com.br/evento/glamslam-party-rio-de-janeiro-tuff-nite-stinger-facing-fear/3510825", None),
    ("https://www.sympla.com.br/evento/e-eu-que-era-emo-anarriemo-no-rock-n-beer/3475035", None),
    ("https://www.sympla.com.br/evento/the-rocks-festival/3422473", None),
    ("https://www.sympla.com.br/evento/festa-tape-25-07-2026-18h/3486144", None),
    ("https://www.sympla.com.br/evento/arraia-do-rock/3515234", None),
    ("https://www.sympla.com.br/evento/rock-no-olimpo-faces-da-deusa/3499885", None),
    ("https://www.sympla.com.br/evento/rock-in-virgo-rio-de-janeiro/3468280", None),
]
