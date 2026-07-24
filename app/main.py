"""Microserviço: serve /feed.xml e atualiza os scrapers em background.

Rodar:  uvicorn app.main:app --host 0.0.0.0 --port 8765
Feed:   http://localhost:8765/feed.xml
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Request, Response

from app import store
from app.events_json import build_events_json
from app.feed import build_rss
from app.revel_push import push_to_revel
from app.scrapers.articket import ArticketScraper
from app.scrapers.bileto import BiletoScraper
from app.scrapers.clubedoingresso import ClubeDoIngressoScraper
from app.scrapers.eventim import EventimScraper
from app.scrapers.leveingresso import LeveIngressoScraper
from app.scrapers.meaple import MeapleScraper
from app.scrapers.shotgun import ShotgunScraper
from app.scrapers.sympla import SymplaEventScraper, SymplaScraper
from app.scrapers.uhuu import UhuuScraper
from app.scrapers.uticket import UticketScraper

REFRESH_MINUTES = 60  # intervalo entre varreduras
MIN_MANUAL_REFRESH_INTERVAL = timedelta(minutes=5)  # limite p/ /refresh manual

SCRAPERS = [
    SymplaScraper(),
    SymplaEventScraper(),
    EventimScraper(),
    ArticketScraper(),
    MeapleScraper(),
    BiletoScraper(),
    ShotgunScraper(),
    UticketScraper(),
    ClubeDoIngressoScraper(),
    UhuuScraper(),
    LeveIngressoScraper(),
]
_last_manual_refresh: datetime | None = None

log = logging.getLogger("rockfeed")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")


def run_scrapers() -> dict[str, int]:
    """Executa todos os scrapers; falha em um não derruba os outros."""
    report: dict[str, int] = {}
    for scraper in SCRAPERS:
        try:
            events = scraper.fetch()
            new = store.upsert(events)
            report[scraper.name] = new
            log.info("%s: %d eventos, %d novos", scraper.name, len(events), new)
        except Exception:
            log.exception("scraper %s falhou", scraper.name)
            report[scraper.name] = -1
    push_to_revel()
    return report


async def refresh_loop() -> None:
    while True:
        await asyncio.to_thread(run_scrapers)
        await asyncio.sleep(REFRESH_MINUTES * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(refresh_loop())
    yield
    task.cancel()


app = FastAPI(title="RockFeed RJ", lifespan=lifespan)


@app.get("/feed.xml")
def feed(request: Request) -> Response:
    content = build_rss()
    etag = hashlib.md5(content.encode()).hexdigest()
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    return Response(
        content=content,
        media_type="application/rss+xml",
        headers={"ETag": etag},
    )


@app.get("/events.json")
def events_json() -> list[dict]:
    """Exportação estruturada dos eventos, pra importação por sistemas
    externos (ex: Revel) — não é o feed de leitura (ver /feed.xml)."""
    return build_events_json()


@app.get("/refresh")
def refresh() -> dict:
    """Força uma varredura manual (útil pra testar). Limitado a 1 a cada
    MIN_MANUAL_REFRESH_INTERVAL pra não martelar os sites raspados se o
    endpoint ficar exposto fora de localhost."""
    global _last_manual_refresh
    now = datetime.now(timezone.utc)
    if _last_manual_refresh is not None:
        elapsed = now - _last_manual_refresh
        if elapsed < MIN_MANUAL_REFRESH_INTERVAL:
            wait = int((MIN_MANUAL_REFRESH_INTERVAL - elapsed).total_seconds())
            raise HTTPException(
                status_code=429,
                detail=f"Aguarde {wait}s antes de forçar outra varredura.",
            )
    _last_manual_refresh = now
    return run_scrapers()


@app.get("/health")
def health() -> dict:
    return {"ok": True, "events": len(store.latest())}
