"""Uhuu — site tradicional renderizado no servidor (sem SPA e sem bloqueio
anti-bot). Cada página de evento já traz nome, data, local e preço
diretamente no HTML — não expõe organizador/produtor em lugar nenhum da
página (diferente da Clube do Ingresso).

Adicione os links dos shows que achar em EVENTS.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timedelta, timezone

import httpx
from bs4 import BeautifulSoup

from app.models import Event
from app.scrapers.base import Scraper, get_client

EVENTS = [
    "https://uhuu.com/evento/rj/rio-de-janeiro/beatles-abbey-road-16408",
    "https://uhuu.com/evento/rj/rio-de-janeiro/elvis-revival-16411",
    "https://uhuu.com/evento/rj/rio-de-janeiro/tributo-elis-regina-16463",
    "https://uhuu.com/evento/rj/sao-joao-de-meriti/nando-reis-16546",
    "https://uhuu.com/evento/rj/rio-de-janeiro/guilherme-de-sa-16556",
    "https://uhuu.com/evento/rj/rio-de-janeiro/elton-john-session-16179",
    "https://uhuu.com/evento/rj/rio-de-janeiro/metallica-the-ultimate-experience-16647",
    "https://uhuu.com/evento/rj/rio-de-janeiro/toca-raul-o-espetaculo-do-maluco-beleza-16641",
    "https://uhuu.com/evento/rj/rio-de-janeiro/phil-collins-in-concert-tributo-16646",
]

log = logging.getLogger("rockfeed")

# horário local do Rio é UTC-3 o ano todo desde o fim do horário de verão em 2019
_BR_TZ = timezone(timedelta(hours=-3))

_MONTHS = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5,
    "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}
_DATE_RE = re.compile(r"(\d{1,2}) de (\w+) de (\d{4}).*?(\d{1,2}):(\d{2})")
_PRICE_RE = re.compile(r"R\$\s*([\d.,]+)")


def _strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


class UhuuScraper(Scraper):
    name = "uhuu"

    def fetch(self) -> list[Event]:
        events: list[Event] = []
        with get_client() as client:
            for url in EVENTS:
                event = self._fetch_event(client, url)
                if event:
                    events.append(event)
        return events

    def _fetch_event(self, client: httpx.Client, url: str) -> Event | None:
        try:
            resp = client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError:
            log.warning("uhuu: falha ao buscar %s, pulando", url)
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one(".event-title")
        details = soup.select(".event-details")
        if not title_el or len(details) < 3:
            log.warning("uhuu: layout inesperado em %s, pulando", url)
            return None

        title = title_el.get_text(strip=True)
        date = self._parse_date(details[0].get_text(" ", strip=True))
        price = self._parse_price(details[1].get_text(" ", strip=True))

        local_el = soup.select_one("#pageEventLocal")
        venue = local_el.get_text(strip=True) if local_el else ""
        location_text = details[2].get_text(" ", strip=True)
        address = location_text.replace(venue, "", 1).replace("Ver localização", "").strip()
        city = address.split("/")[0].strip() or "Rio de Janeiro"

        img_el = soup.select_one('meta[property="og:image"]')
        image = img_el.get("content", "") if img_el else ""

        return Event(
            title=title,
            url=url,
            source=self.name,
            venue=venue,
            address=address,
            city=city,
            date=date,
            price=price,
            image=image,
        )

    @staticmethod
    def _parse_date(text: str) -> datetime | None:
        m = _DATE_RE.search(_strip_accents(text).lower())
        if not m:
            return None
        day, month_name, year, hour, minute = m.groups()
        month = _MONTHS.get(month_name)
        if not month:
            return None
        try:
            return datetime(
                int(year), month, int(day), int(hour), int(minute), tzinfo=_BR_TZ
            )
        except ValueError:
            return None

    @staticmethod
    def _parse_price(text: str) -> str:
        m = _PRICE_RE.search(text)
        if not m:
            return ""
        return f"R$ {m.group(1).replace(',', '.')}"
