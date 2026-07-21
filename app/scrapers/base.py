"""Base para scrapers: cliente HTTP com headers decentes + filtro de rock."""
from __future__ import annotations

import html
import re
import unicodedata

import httpx

from app.models import Event

_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(raw: str) -> str:
    """Remove tags e decodifica entidades de um texto rico (HTML) simples."""
    text = _TAG_RE.sub(" ", raw or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

# Palavras que indicam show de rock. Ajuste à vontade.
ROCK_KEYWORDS = [
    "rock", "metal", "punk", "hardcore", "grunge", "indie",
    "heavy", "thrash", "stoner", "post-punk", "emo", "hard rock",
    "tributo", "cover",  # tributos/covers costumam ser de rock — o filtro de banda ajuda
]

# Termos que descartam o evento mesmo que contenham keyword (ex: "rock in roda de samba")
BLOCKLIST = ["pagode", "sertanejo", "funk carioca", "axé", "forró"]


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower()


def is_rock(*fields: str) -> bool:
    blob = _norm(" ".join(f for f in fields if f))
    if any(b in blob for b in map(_norm, BLOCKLIST)):
        return False
    return any(re.search(rf"\b{re.escape(_norm(k))}\b", blob) for k in ROCK_KEYWORDS)


def get_client() -> httpx.Client:
    return httpx.Client(headers=HEADERS, timeout=20, follow_redirects=True)


class Scraper:
    """Interface: implemente fetch() retornando lista de Event."""

    name = "base"

    def fetch(self) -> list[Event]:  # pragma: no cover
        raise NotImplementedError
