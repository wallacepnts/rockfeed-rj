"""Articket — raspa páginas de produtoras/organizadores (ex: Tomarock Produções).

O site não tem mais uma página fixa por produtora em /<slug>; a URL atual é
/o/<id>/<slug> e lista os eventos futuros da produtora. Cada evento, por sua
vez, expõe dados estruturados (schema.org/Event) num <script type=
"application/ld+json">, então em vez de adivinhar seletores CSS lemos esse
JSON diretamente — muito mais estável a mudanças de layout.

Adicione outras produtoras que você acompanha em PAGES.
"""
from __future__ import annotations

import html
import json
import logging
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.models import Event
from app.scrapers.base import Scraper, get_client

PAGES = [
    # (rótulo, url da página da produtora)
    ("tomarock", "https://articket.com.br/o/133/tomarock-producoes"),
    ("autoral-em-foco", "https://articket.com.br/o/1266/autoral-em-foco"),
    ("tribus", "https://articket.com.br/o/997/tribus"),
    ("rock-n-beer", "https://articket.com.br/o/596/rock-n-beer"),
    ("rotten-place", "https://articket.com.br/o/1245/rotten-place"),
]

EVENT_URL_RE = re.compile(r"^https://articket\.com\.br/e/\d+/")

log = logging.getLogger("rockfeed")


class ArticketScraper(Scraper):
    name = "articket"

    def fetch(self) -> list[Event]:
        events: list[Event] = []
        with get_client() as client:
            for label, org_url in PAGES:
                try:
                    resp = client.get(org_url)
                    resp.raise_for_status()
                except httpx.HTTPError:
                    log.warning("articket: falha ao buscar página '%s', pulando", label)
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                event_urls = sorted(
                    {
                        a["href"]
                        for a in soup.select("a[href]")
                        if EVENT_URL_RE.match(a["href"])
                    }
                )
                for event_url in event_urls:
                    event = self._fetch_event(client, label, event_url)
                    if event:
                        events.append(event)
        return events

    def _fetch_event(self, client: httpx.Client, label: str, event_url: str) -> Event | None:
        try:
            resp = client.get(event_url)
            resp.raise_for_status()
        except httpx.HTTPError:
            log.warning("articket: falha ao buscar evento %s, pulando", event_url)
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        script = soup.find("script", type="application/ld+json")
        if not script or not script.string:
            return None
        try:
            data = json.loads(script.string)
        except ValueError:
            return None

        title = html.unescape(data.get("name", ""))
        if not title:
            return None

        # A descrição vem do CMS da Articket já com entidades HTML (ex: &quot;)
        # em vez de texto puro; decodificamos antes de re-escapar pro XML do feed.
        description = html.unescape(data.get("description", ""))
        # PAGES é uma lista curada de produtoras/organizadores de rock — aceita
        # tudo que vier de lá, sem passar pelo filtro genérico de keywords.

        location = data.get("location") or {}
        venue = location.get("name", "")
        addr = location.get("address") or {}
        city = addr.get("addressLocality") or "Rio de Janeiro"
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
        organizer = (data.get("organizer") or {}).get("name", "")

        date = None
        if data.get("startDate"):
            try:
                date = datetime.fromisoformat(data["startDate"])
            except ValueError:
                pass

        end_date = None
        if data.get("endDate"):
            try:
                end_date = datetime.fromisoformat(data["endDate"])
            except ValueError:
                pass

        images = data.get("image")
        if isinstance(images, list):
            image = images[0] if images else ""
        else:
            image = images or ""

        offer = data.get("offers") or {}
        price = f"R$ {offer['price']}" if offer.get("price") else ""

        return Event(
            title=title,
            url=offer.get("url") or event_url,
            source=f"{self.name}:{label}",
            venue=venue,
            address=address,
            organizer=organizer,
            city=city,
            date=date,
            end_date=end_date,
            price=price,
            image=image,
            description=description,
        )
