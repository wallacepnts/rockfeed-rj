"""Eventim Brasil — via pyventim (https://pypi.org/project/pyventim/), uma
biblioteca de terceiros que usa a API pública de busca da Eventim.

O site www.eventim.com.br bloqueia qualquer requisição direta — httpx,
curl e até Playwright com Chromium de verdade (confirmado testando de
dentro e de fora do ambiente, inclusive com o navegador do sistema do
usuário) — no nível de rede/TLS antes de qualquer resposta chegar.
A API pública de busca (public-api.eventim.com/.../v1/attractions,
productGroups etc.) não tem esse bloqueio e devolve dados completos.

Filtramos pela própria categoria "Rock" que a Eventim atribui a cada
evento (mais confiável que keywords) e pelo estado "RJ" — o projeto cobre
o estado inteiro, não só a capital. Não buscamos preço aqui: isso exigiria
o fetcher "privado" da biblioteca (que abre um Chromium com patches
anti-detecção via patchright/scrapling — funciona, mas é pesado) para um
dado que na prática costuma vir vazio mesmo quando consultado.
"""
from __future__ import annotations

import logging
from datetime import datetime

from pyventim import EventimCategory, EventimClient, EventimMarket

from app.models import Event
from app.scrapers.base import Scraper

SEARCH_TERM = "rock"

log = logging.getLogger("rockfeed")


class EventimScraper(Scraper):
    name = "eventim"

    def fetch(self) -> list[Event]:
        client = EventimClient(market=EventimMarket.BRAZIL)
        try:
            product_groups = list(
                client.product_groups(
                    categories=[EventimCategory.CONCERTS], search_term=SEARCH_TERM
                )
            )
        except Exception:
            log.exception("eventim: falha ao buscar eventos")
            return []

        events: list[Event] = []
        for group in product_groups:
            category_names = {c.get("name") for c in (group.categories or [])}
            if "Rock" not in category_names:
                continue
            for product in group.products:
                event = self._parse_product(group, product)
                if event:
                    events.append(event)
        return events

    def _parse_product(self, group, product) -> Event | None:
        live = (product.type_attributes or {}).get("liveEntertainment") or {}
        location = live.get("location") or {}
        if location.get("state") != "RJ":
            return None

        city = location.get("city") or "Rio de Janeiro"
        state = location.get("state") or ""
        address = ", ".join(p for p in (city, state) if p)

        return Event(
            title=product.name,
            url=product.link,
            source=self.name,
            venue=location.get("name", ""),
            address=address,
            city=city,
            date=self._parse_date(live.get("startDate")),
            image=group.image_url or "",
            description=group.description or "",
        )

    @staticmethod
    def _parse_date(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
