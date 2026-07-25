"""Sesc Cultura RJ — API pública de programação cultural (endpoint próprio
em WordPress, por trás do site https://cultura.sescrio.org.br).

GET https://apicultura.sescrio.org.br/wp-json/sesc-cultura/v1/eventos/filter
    ?categoria_eventos=show&per_page=100&page=N

Filtra pela categoria "Show" (musical) automaticamente, mas o site não tem
taxonomia de gênero musical — a programação é majoritariamente
forró/pagode/samba/MPB/sertanejo. Por isso, diferente da maioria das fontes
daqui, usa o filtro genérico de rock (is_rock(), base.py) sobre
título+sinopse pra selecionar só os shows de rock dentro da programação
geral.

Cada evento pode ter várias sessões (datas/locais diferentes,
ex: turnê passando por várias unidades do Sesc pelo estado) — cada
sessão vira um Event à parte.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.models import Event
from app.scrapers.base import Scraper, get_client, is_rock, strip_html

API_URL = "https://apicultura.sescrio.org.br/wp-json/sesc-cultura/v1/eventos/filter"
PROGRAMACAO_BASE = "https://cultura.sescrio.org.br/programacao"

# Sesc RJ tem uma rede fixa de unidades pelo estado — mapeamento manual do
# nome do local (como vem na API) pra cidade, já que a API não expõe endereço.
VENUE_CITY = {
    "Arte Sesc": "Rio de Janeiro",
    "Casa Sesc na Flip": "Paraty",
    "Centro Cultural Sesc Quitandinha": "Petrópolis",
    "Itaipava": "Petrópolis",
    "Nova Friburgo": "Nova Friburgo",
    "Penedo (Itatiaia)": "Itatiaia",
    "Petrópolis": "Petrópolis",
    "Porciúncula": "Porciúncula",
    "Sesc Barra Mansa": "Barra Mansa",
    "Sesc Botafogo - Biblioteca Machado de Assis": "Rio de Janeiro",
    "Sesc Campos": "Campos dos Goytacazes",
    "Sesc Cocotá - Biblioteca Euclides da Cunha": "Rio de Janeiro",
    "Sesc Copacabana": "Rio de Janeiro",
    "Sesc Duque de Caxias": "Duque de Caxias",
    "Sesc Ginástico": "Rio de Janeiro",
    "Sesc Grussaí": "São João da Barra",
    "Sesc Madureira": "Rio de Janeiro",
    "Sesc Niterói": "Niterói",
    "Sesc Nogueira": "Rio das Ostras",
    "Sesc Nova Friburgo": "Nova Friburgo",
    "Sesc Nova Iguaçu": "Nova Iguaçu",
    "Sesc Ramos": "Rio de Janeiro",
    "Sesc São Gonçalo": "São Gonçalo",
    "Sesc São João de Meriti": "São João de Meriti",
    "Sesc Teresópolis": "Teresópolis",
    "Sesc Tijuca": "Rio de Janeiro",
    "Sesc Três Rios": "Três Rios",
    "Tanguá": "Tanguá",
    "Teatro Sesc Rosinha de Valença": "Valença",
    "Teresópolis": "Teresópolis",
}

_BR_TZ = timezone(timedelta(hours=-3))

# Falsos positivos conhecidos do is_rock() nessa fonte: a keyword "tributo"
# pega homenagens de outros gêneros (samba, choro), e alguns repertórios
# multi-gênero só citam "rock" de passagem entre vários outros ritmos.
EXCLUDED_SLUGS = {
    "irmao-cafe-wilson-moreira-90-anos",  # tributo a Wilson Moreira (samba/jongo)
    "silverio-pontes",  # tributo a Zé da Velha (choro)
    "capivaras-molhadas",  # repertório de carnaval/MPB/nordestino, rock só citado de passagem
    "giu",  # MPB/pop/samba/reggae/rock — rock é uma entre várias influências
    "dida-nascimento",  # "reggae, rock, MPB" — descrição curta demais pra ser conclusiva
}

log = logging.getLogger("rockfeed")


class SescCulturaScraper(Scraper):
    name = "sesccultura"

    def fetch(self) -> list[Event]:
        events: list[Event] = []
        with get_client() as client:
            page = 1
            while True:
                try:
                    resp = client.get(
                        API_URL,
                        params={"categoria_eventos": "show", "per_page": 100, "page": page},
                    )
                    resp.raise_for_status()
                    payload = resp.json()
                except httpx.HTTPError:
                    log.warning("sesccultura: falha ao buscar página %d, parando", page)
                    break

                eventos = (payload.get("data") or {}).get("eventos") or []
                if not eventos:
                    break

                for item in eventos:
                    events.extend(self._parse_item(item))

                if len(eventos) < 100:
                    break
                page += 1
        return events

    def _parse_item(self, item: dict) -> list[Event]:
        title = item.get("title", "")
        if item.get("slug") in EXCLUDED_SLUGS:
            return []
        meta = item.get("event_meta") or {}
        sinopse = meta.get("sinopse_markdown", "")
        if not is_rock(title, sinopse):
            return []

        url = f"{PROGRAMACAO_BASE}/{item.get('slug', '')}"
        image = (item.get("featured_image") or {}).get("large", "")
        description = strip_html(sinopse)

        events = []
        for session in meta.get("sessoes") or []:
            venue = session.get("local", "")
            date, end_date = self._parse_session_dates(session)
            price = self._lowest_price(session.get("ingressos") or [])
            session_key = session.get("data_intervalo_iso8601", "")
            ticket_url = session.get("url_ingresso") or f"{url}?sessao={session_key}"
            events.append(
                Event(
                    title=title,
                    url=ticket_url,
                    source=self.name,
                    venue=venue,
                    organizer="Sesc Rio",
                    city=VENUE_CITY.get(venue, "Rio de Janeiro"),
                    date=date,
                    end_date=end_date,
                    price=price,
                    image=image,
                    description=description,
                )
            )
        return events

    @staticmethod
    def _parse_session_dates(session: dict) -> tuple[datetime | None, datetime | None]:
        date_parts = (session.get("data_intervalo_iso8601") or "").split("/")
        time_parts = (session.get("hora_intervalo_iso8601") or "").split("/")
        if not date_parts or not date_parts[0]:
            return None, None
        start_date = date_parts[0]
        end_date_str = date_parts[1] if len(date_parts) > 1 else start_date
        start_time = time_parts[0] if time_parts and time_parts[0] else "00:00:00"
        end_time = time_parts[1] if len(time_parts) > 1 and time_parts[1] else start_time
        try:
            start = datetime.fromisoformat(f"{start_date}T{start_time}").replace(tzinfo=_BR_TZ)
            end = datetime.fromisoformat(f"{end_date_str}T{end_time}").replace(tzinfo=_BR_TZ)
        except ValueError:
            return None, None
        return start, end

    @staticmethod
    def _lowest_price(ingressos: list[dict]) -> str:
        prices = []
        for t in ingressos:
            try:
                prices.append(float(t.get("preco", "")))
            except (TypeError, ValueError):
                continue
        if not prices:
            return ""
        lowest = min(prices)
        return "Grátis" if lowest <= 0 else f"R$ {lowest:.2f}"
