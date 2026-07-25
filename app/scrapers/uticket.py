"""uTicket — plataforma de ingressos atrás de proteção Cloudflare que
bloqueia requisições HTTP simples (confirmado: 403 "Attention Required"
mesmo com headers de navegador). Só passa com um navegador de verdade —
por isso usa Playwright (via app.scrapers.browser), igual à Shotgun.

Diferente da Shotgun, não precisamos renderizar uma página por evento:
depois de uma única navegação inicial (que resolve o desafio do
Cloudflare), toda chamada seguinte usa fetch() dentro da própria página —
o cookie de sessão já resolvido continua valendo — direto pra API
(api.uticket.com.br), bem mais rápido que abrir página por página.

Fluxo:
- organizerpage/?slug=<slug>  -> resolve pro userId do produtor
- event/user/<userId>         -> lista os próximos eventos do produtor
- eventinfo/<id>              -> detalhes completos de qualquer evento
- tickettype?eventId=<id>     -> preços dos ingressos

Produtores curados em ORGANIZERS (por slug — a maioria); eventos avulsos
(quando não tem página de produtor) em EVENTS — só precisa do link do
evento. Às vezes o userId que aparece no eventinfo de um show avulso é
diferente do userId da página pública do produtor (ex: conta operacional
vs. conta "vitrine" do produtor) — nesse caso o event/user/<userId> da
página pública pode não listar o show. Se acontecer, adicione o userId
numérico visto no eventinfo (campo "userId") direto em ORGANIZER_IDS, sem
precisar de slug.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime

from app.models import Event
from app.scrapers.base import Scraper, strip_html
from app.scrapers.browser import browser_page

API_BASE = "https://api.uticket.com.br"
IMAGE_BASE = "https://img.uticket.com.br/event"

ORGANIZERS = [
    "garagegrindhouse",
    "bulldogrockbar",
    "lordpub",
    "saturnaliaproducoes",
]

# (rótulo, userId) — quando já se sabe o userId de verdade (visto no
# eventinfo de um show avulso) e não faz sentido resolver por slug (ver
# docstring do módulo).
ORGANIZER_IDS = [
    ("ariesproducoes", 544805),
]

EVENTS = [
    "https://uticket.com.br/evento/rua-crew-apresenta-ermos-arigo-e-hell-in-paradise/01M6Z9W7XDG0M9",
    "https://uticket.com.br/evento/autoral-rockfest/01M3084K8YZDES",
    "https://uticket.com.br/evento/tributo-ao-rappa-com-a-banda-assalto-rj/01M7C3XALFTJM3",
]

log = logging.getLogger("rockfeed")

_EVENT_ID_RE = re.compile(r"/([0-9A-Za-z]+)$")
_CITY_RE = re.compile(r"-\s*([A-Za-zÀ-ÿ\s]+?)\s*-\s*[A-Z]{2}$")


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "evento"


class UticketScraper(Scraper):
    name = "uticket"

    # depois de ~11 fetches seguidos pela mesma sessão, a Cloudflare passa a
    # recusar tudo ("Failed to fetch") até a página ser recarregada de novo —
    # renavegar a cada N alvos evita que isso derrube o resto da varredura.
    _RENAVIGATE_EVERY = 5

    def fetch(self) -> list[Event]:
        events: list[Event] = []
        with browser_page() as page:
            if not self._navigate(page):
                return []

            targets: list[tuple[str, str]] = []  # (event_id, rótulo de origem)
            for slug in ORGANIZERS:
                targets.extend(self._discover_organizer_events(page, slug))
            for label, user_id in ORGANIZER_IDS:
                targets.extend(self._discover_organizer_events_by_id(page, label, user_id))

            self._navigate(page)  # renova a sessão antes da rodada de detalhes

            for url in EVENTS:
                m = _EVENT_ID_RE.search(url.split("?")[0])
                if m:
                    targets.append((m.group(1), self.name))
                else:
                    log.warning("uticket: não achei o ID do evento em %s, pulando", url)

            for i, (event_id, label) in enumerate(targets):
                if i and i % self._RENAVIGATE_EVERY == 0:
                    self._navigate(page)
                event = self._fetch_event(page, event_id, label)
                if event:
                    events.append(event)
                page.wait_for_timeout(200)
        return events

    @staticmethod
    def _navigate(page) -> bool:
        try:
            page.goto("https://uticket.com.br/", wait_until="networkidle", timeout=30000)
            return True
        except Exception:
            log.warning("uticket: falha ao (re)carregar o site")
            return False

    def _discover_organizer_events(self, page, slug: str) -> list[tuple[str, str]]:
        try:
            org = self._fetch_json(page, f"{API_BASE}/organizerpage/?slug={slug}")
            listing = self._fetch_json(page, f"{API_BASE}/event/user/{org['userId']}")
        except Exception:
            log.warning("uticket: falha ao buscar produtor '%s', pulando", slug)
            return []
        return [(item["id"], f"{self.name}:{slug}") for item in listing]

    def _discover_organizer_events_by_id(
        self, page, label: str, user_id: int
    ) -> list[tuple[str, str]]:
        try:
            listing = self._fetch_json(page, f"{API_BASE}/event/user/{user_id}")
        except Exception:
            log.warning("uticket: falha ao buscar produtor '%s' (userId %d), pulando", label, user_id)
            return []
        return [(item["id"], f"{self.name}:{label}") for item in (listing or [])]

    def _fetch_event(self, page, event_id: str, label: str) -> Event | None:
        try:
            info = self._fetch_json(page, f"{API_BASE}/eventinfo/{event_id}")
        except Exception:
            log.warning("uticket: falha ao buscar evento %s, pulando", event_id)
            return None

        if info.get("hidden"):
            return None

        place = info.get("place") or {}
        address = place.get("address", "")
        city_match = _CITY_RE.search(address)
        city = city_match.group(1).strip() if city_match else "Rio de Janeiro"

        schedules = info.get("schedules") or []
        date = self._parse_date(schedules[0].get("start")) if schedules else None
        end_date = self._parse_date(schedules[0].get("end")) if schedules else None

        title = info.get("name", "")
        url = f"https://uticket.com.br/evento/{_slugify(title)}/{event_id}"
        description = strip_html((info.get("description") or "").strip('"'))

        return Event(
            title=title,
            url=url,
            source=label,
            venue=place.get("name", ""),
            address=address,
            organizer=info.get("UserName", ""),
            city=city,
            date=date,
            end_date=end_date,
            price=self._fetch_lowest_price(page, event_id),
            image=f"{IMAGE_BASE}/{event_id}/l",
            description=description,
        )

    def _fetch_lowest_price(self, page, event_id: str) -> str:
        try:
            data = self._fetch_json(page, f"{API_BASE}/tickettype?eventId={event_id}")
            tickets = data.get("ticketTypes") or []
        except Exception:
            return ""
        prices = [t["price"] for t in tickets if t.get("price") is not None]
        if not prices:
            return ""
        lowest = min(prices) / 100
        return "Grátis" if lowest <= 0 else f"R$ {lowest:.2f}"

    @staticmethod
    def _fetch_json(page, url: str):
        return page.evaluate(
            """async (url) => {
                const r = await fetch(url);
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return await r.json();
            }""",
            url,
        )

    @staticmethod
    def _parse_date(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
