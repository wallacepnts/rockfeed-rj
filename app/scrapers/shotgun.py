"""Shotgun — plataforma de ingressos protegida por um desafio anti-bot da
Vercel que bloqueia qualquer requisição HTTP simples, mesmo com os cookies
certos (testado com curl de duas redes diferentes, sempre 429). A única
forma de acessar é com um navegador de verdade executando JS — por isso
esse scraper usa Playwright (Chromium headless) em vez de httpx, via
app.scrapers.browser.

A página de cada local (venue) já lista os próximos eventos renderizados
no HTML — não precisamos visitar cada evento individualmente, só a página
do local.

Adicione outros locais de rock que você acompanha em VENUES.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime

from bs4 import BeautifulSoup

from app.models import Event
from app.scrapers.base import Scraper
from app.scrapers.browser import browser_page

BASE_URL = "https://shotgun.live/pt-br"

VENUES = [
    "espaco-cultural-redoma",
    "gentalha",
    "nina-brea-sa",
    "carolina-de-oliveira-silva",
    "causa-mortis",
]

log = logging.getLogger("rockfeed")

_PRICE_RE = re.compile(r"R\$\s*([\d.,]+)")


class ShotgunScraper(Scraper):
    name = "shotgun"

    def fetch(self) -> list[Event]:
        events: list[Event] = []
        for slug in VENUES:
            events.extend(self._fetch_venue(slug))
        return events

    def _fetch_venue(self, slug: str) -> list[Event]:
        url = f"{BASE_URL}/venues/{slug}"
        try:
            with browser_page() as page:
                page.goto(url, wait_until="networkidle", timeout=30000)
                html = page.content()
        except Exception:
            log.warning("shotgun: falha ao carregar local '%s', pulando", slug)
            return []

        soup = BeautifulSoup(html, "html.parser")
        h1 = soup.select_one("h1")
        venue_name = h1.get_text(strip=True) if h1 else slug

        events: list[Event] = []
        seen_urls = set()
        for card in soup.select('a[href^="/pt-br/events/"]'):
            event = self._parse_card(card, venue_name, slug)
            if event and event.url not in seen_urls:
                seen_urls.add(event.url)
                events.append(event)
        return events

    def _parse_card(self, card, venue_name: str, slug: str) -> Event | None:
        title_el = card.select_one("p")
        time_el = card.select_one("time[datetime]")
        if not title_el or not time_el:
            return None

        img = card.select_one("img")
        image = img.get("src", "") if img else ""

        price_match = _PRICE_RE.search(card.get_text(" ", strip=True))
        price = f"R$ {price_match.group(1).replace(',', '.')}" if price_match else ""

        href = card.get("href", "")
        url = f"https://shotgun.live{href}" if href.startswith("/") else href

        return Event(
            title=title_el.get_text(strip=True),
            url=url,
            source=f"{self.name}:{slug}",
            venue=venue_name,
            organizer=venue_name,
            city="Rio de Janeiro",
            date=self._parse_date(time_el.get("datetime")),
            price=price,
            image=image,
        )

    @staticmethod
    def _parse_date(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
