"""Leve Ingresso — plataforma de ticketing tradicional (HTML server-side,
sem proteção anti-bot), usada por casas menores.

Não achamos endpoint nem página de listagem por produtor/local — cada
evento só existe na própria página de compra (/comprar/<id>/<slug>), sem
API pública nem organizador exposto. Por isso funciona por lista curada de
eventos (EVENTS), igual Bileto/Clube do Ingresso/Uhuu: pegue o link de cada
show de rock que achar e adicione aqui; informe organizer_override quando
souber quem produz (a página não expõe isso).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

import httpx
from bs4 import BeautifulSoup

from app.models import Event
from app.scrapers.base import Scraper, get_client, strip_html

EVENTS = [
    # (url, organizer_override — None se você não souber quem produz)
    ("https://leveingresso.com/comprar/518/12-09-rodox-sao-goncalo-rj", None),
    ("https://leveingresso.com/comprar/510/17-09-mateus-asato-world-tour-rio-de-janeiro", None),
]

# Horário local do Rio/SP é UTC-3 o ano todo desde o fim do horário de
# verão em 2019 — a página não traz offset.
_BR_TZ = timezone(timedelta(hours=-3))

_MONTHS = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}
_DATE_RE = re.compile(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", re.IGNORECASE)
_TIME_RE = re.compile(r"(\d{1,2})h(\d{2})")
_CITY_RE = re.compile(r"-\s*([A-Za-zÀ-ÿ\s]+?)\s*-\s*[A-Z]{2}$")
_PRICE_RE = re.compile(r'value="([\d.]+)"\s+name="valor(\d+)"')

log = logging.getLogger("rockfeed")


class LeveIngressoScraper(Scraper):
    name = "leveingresso"

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
        try:
            resp = client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError:
            log.warning("leveingresso: falha ao buscar %s, pulando", url)
            return None

        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        title_tag = soup.find("meta", attrs={"property": "og:title"})
        title = (title_tag.get("content") or "").strip() if title_tag else ""

        image_tag = soup.find("meta", attrs={"property": "og:image"})
        image = (image_tag.get("content") or "") if image_tag else ""

        info_box = soup.find("div", class_="dado-event")
        venue = ""
        address = ""
        day_text = ""
        time_text = ""
        if info_box:
            h3 = info_box.find("h3")
            day_text = h3.get_text(strip=True) if h3 else ""
            for li in info_box.find_all("li"):
                text = li.get_text(strip=True)
                if text.startswith("Endereço:"):
                    address = text.split(":", 1)[1].strip()
                elif text.startswith("Local:"):
                    venue = text.split(":", 1)[1].strip()
                elif text.startswith("Início do Evento:"):
                    time_text = text.split(":", 1)[1].strip()

        return Event(
            title=title,
            url=url,
            source=self.name,
            venue=venue,
            address=address,
            organizer=organizer_override or "",
            city=self._parse_city(address),
            date=self._parse_datetime(day_text, time_text),
            end_date=None,
            price=self._lowest_price(html),
            image=image,
            description=self._extract_description(soup),
        )

    @staticmethod
    def _parse_city(address: str) -> str:
        m = _CITY_RE.search(address)
        return m.group(1).strip() if m else "Rio de Janeiro"

    @staticmethod
    def _parse_datetime(day_text: str, time_text: str) -> datetime | None:
        m = _DATE_RE.search(day_text)
        if not m:
            return None
        day, month_name, year = m.groups()
        month = _MONTHS.get(month_name.lower())
        if not month:
            return None
        hour, minute = 0, 0
        tm = _TIME_RE.search(time_text)
        if tm:
            hour, minute = int(tm.group(1)), int(tm.group(2))
        return datetime(int(year), month, int(day), hour, minute, tzinfo=_BR_TZ)

    @staticmethod
    def _lowest_price(html: str) -> str:
        prices = [float(v) for v, _ in _PRICE_RE.findall(html)]
        if not prices:
            return ""
        lowest = min(prices)
        return "Grátis" if lowest <= 0 else f"R$ {lowest:.2f}"

    @staticmethod
    def _extract_description(soup: BeautifulSoup) -> str:
        # A descrição (release do evento) fica na aba "Release" (id="menu1");
        # a classe do wrapper interno se repete em outras abas (valores,
        # mapa de setores), então precisa mirar no id certo primeiro.
        tab = soup.find("div", id="menu1")
        if not tab:
            return ""
        box = tab.find("div", class_="prs_es_tabs_event_sche_img_cont_wrapper")
        return strip_html(str(box)) if box else ""
