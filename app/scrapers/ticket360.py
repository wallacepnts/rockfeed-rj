"""Ticket360 — plataforma nacional de ingressos, sem bloqueio anti-bot.

Tem sub-categorias próprias de gênero ("Rock" e "Rock & Roll"), então
descobre eventos automaticamente por lá em vez de precisar de filtro por
keyword — mas como é uma plataforma nacional, cada evento individual
precisa ser conferido pelo estado (`addressRegion`) pra filtrar só RJ.

Cada página de sub-categoria lista os eventos num JSON-LD ItemList (schema.org)
com a URL de cada evento; cada página de evento, por sua vez, expõe um
JSON-LD MusicEvent completo (local, endereço com estado, preço, organizador,
data) — bem mais rico que o de outras fontes, sem precisar adivinhar
seletor de HTML.

Adicione outras sub-categorias de rock que encontrar em CATEGORIES.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.models import Event
from app.scrapers.base import Scraper, get_client

CATEGORIES = [
    "https://www.ticket360.com.br/sub-categoria/7/rock",
    "https://www.ticket360.com.br/sub-categoria/258/rock-amp-roll",
]

TARGET_STATE = "RJ"

log = logging.getLogger("rockfeed")


def _find_ld_json(soup: BeautifulSoup, ld_type: str) -> dict | None:
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("@type") == ld_type:
            return data
    return None


class Ticket360Scraper(Scraper):
    name = "ticket360"

    def fetch(self) -> list[Event]:
        event_urls: set[str] = set()
        with get_client() as client:
            for category_url in CATEGORIES:
                event_urls.update(self._discover_urls(client, category_url))

            events = []
            for url in sorted(event_urls):
                event = self._fetch_event(client, url)
                if event:
                    events.append(event)
        return events

    def _discover_urls(self, client: httpx.Client, category_url: str) -> set[str]:
        try:
            resp = client.get(category_url)
            resp.raise_for_status()
        except httpx.HTTPError:
            log.warning("ticket360: falha ao buscar categoria %s, pulando", category_url)
            return set()

        soup = BeautifulSoup(resp.text, "html.parser")
        item_list = _find_ld_json(soup, "ItemList")
        if not item_list:
            return set()
        return {
            item["url"]
            for item in item_list.get("itemListElement", [])
            if item.get("url")
        }

    def _fetch_event(self, client: httpx.Client, url: str) -> Event | None:
        try:
            resp = client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError:
            log.warning("ticket360: falha ao buscar evento %s, pulando", url)
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        data = _find_ld_json(soup, "MusicEvent")
        if not data:
            return None

        location = data.get("location") or {}
        addr = location.get("address") or {}
        if addr.get("addressRegion") != TARGET_STATE:
            return None

        address = ", ".join(
            p
            for p in (
                addr.get("streetAddress"),
                addr.get("addressLocality"),
                addr.get("addressRegion"),
                addr.get("postalCode"),
            )
            if p
        )

        images = data.get("image")
        image = (images[0] if images else "") if isinstance(images, list) else (images or "")

        offer = data.get("offers") or {}
        low_price = offer.get("lowPrice")
        price = "Grátis" if low_price == 0 else (f"R$ {low_price:.2f}" if low_price else "")

        description = re.sub(r"\s+", " ", data.get("description", "")).strip()

        return Event(
            title=data.get("name", ""),
            url=data.get("url") or url,
            source=self.name,
            venue=location.get("name", ""),
            address=address,
            organizer=(data.get("organizer") or {}).get("name", ""),
            city=addr.get("addressLocality") or "Rio de Janeiro",
            date=self._parse_date(data.get("startDate")),
            end_date=self._parse_date(data.get("endDate")),
            price=price,
            image=image,
            description=description,
        )

    @staticmethod
    def _parse_date(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
