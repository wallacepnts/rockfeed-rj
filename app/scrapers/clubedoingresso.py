"""Clube do Ingresso — site tradicional renderizado no servidor (sem SPA e
sem bloqueio anti-bot). Cada página de evento já traz nome, data, local,
endereço, organizador e preços diretamente no HTML — não existe uma
página dedicada de produtor, só a de cada evento.

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
    "https://www.clubedoingresso.com/evento/thewallomusical-riodejaneiro",
    "https://www.clubedoingresso.com/evento/kingdiamondsymphonictribute-rj",
    "https://www.clubedoingresso.com/evento/rammsteinsymphonictribute-riodejaneiro",
    "https://www.clubedoingresso.com/evento/fabiolioneeorquestra-riodejaneiro-07-10",
    "https://www.clubedoingresso.com/evento/anette-olzon-riodejaneiro",
    "https://www.clubedoingresso.com/evento/hybridtheory2026-riodejaneiro",
    "https://www.clubedoingresso.com/evento/blacklabelsociety-riodejaneiro",
    "https://www.clubedoingresso.com/evento/rodoxrj-teatrocitta",
    "https://www.clubedoingresso.com/evento/bride-riodejaneiro",
    "https://www.clubedoingresso.com/evento/testament-riodejaneiro",
    "https://www.clubedoingresso.com/evento/meetandgreet-angra-riodejaneiro",
]

log = logging.getLogger("rockfeed")

# horário local do Rio é UTC-3 o ano todo desde o fim do horário de verão em 2019
_BR_TZ = timezone(timedelta(hours=-3))

_MONTHS = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5,
    "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}
_DATE_RE = re.compile(r"(\d{1,2}) de (\w+) de (\d{4})(?:.*?(\d{1,2}):(\d{2}))?")
_CITY_RE = re.compile(r"-\s*([^-,]+),\s*[A-Z]{2}$")


def _strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


class ClubeDoIngressoScraper(Scraper):
    name = "clubedoingresso"

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
            log.warning("clubedoingresso: falha ao buscar %s, pulando", url)
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        name_el = soup.select_one(".PageEvent__nameEvent .nome")
        if not name_el:
            log.warning("clubedoingresso: layout inesperado em %s, pulando", url)
            return None
        title = name_el.get_text(strip=True)

        date_el = soup.select_one(".PageEvent__select .PageEvent__desc")
        date = self._parse_date(date_el.get_text(strip=True)) if date_el else None

        local_el = soup.select_one(".PageEvent__local")
        venue = ""
        address = ""
        if local_el:
            subtitle = local_el.select_one(".PageEvent__subTitle")
            desc = local_el.select_one(".PageEvent__desc")
            venue = subtitle.get_text(strip=True) if subtitle else ""
            address = desc.get_text(strip=True) if desc else ""

        city_match = _CITY_RE.search(address)
        city = city_match.group(1).strip() if city_match else "Rio de Janeiro"

        org_el = soup.select_one(".PageEvent__organizer .PageEvent__desc")
        organizer = org_el.get_text(strip=True) if org_el else ""

        img_el = soup.select_one(".PageEvent__img")
        image = img_el.get("src", "") if img_el else ""

        prices = [
            float(m["content"])
            for m in soup.select('meta[property="product:price:amount"]')
            if m.get("content")
        ]
        price = f"R$ {min(prices):.2f}" if prices else ""

        return Event(
            title=title,
            url=url,
            source=self.name,
            venue=venue,
            address=address,
            organizer=organizer,
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
                int(year), month, int(day),
                int(hour) if hour else 0, int(minute) if minute else 0,
                tzinfo=_BR_TZ,
            )
        except ValueError:
            return None
