"""Envia os eventos raspados pro Revel (ingestão externa), pra virarem
rascunho lá pra revisão manual — não confundir com o feed RSS (/feed.xml)
nem com /events.json (que é passivo, só serve quando alguém consulta).

Configuração via variáveis de ambiente:
    REVEL_INGEST_URL      ex: https://revel.exemplo.com.br/api/external/events
    REVEL_INGEST_API_KEY  o mesmo valor configurado no Revel (EXTERNAL_INGEST_API_KEY)

Se qualquer uma faltar, o push fica desabilitado silenciosamente (útil pra
rodar localmente sem Revel configurado).
"""
from __future__ import annotations

import logging
import os

import httpx

from app.events_json import build_events_json

log = logging.getLogger("rockfeed")

REVEL_INGEST_URL = os.environ.get("REVEL_INGEST_URL", "")
REVEL_INGEST_API_KEY = os.environ.get("REVEL_INGEST_API_KEY", "")
REVEL_PUSH_TIMEOUT = 30  # segundos


def push_to_revel() -> None:
    """Envia o snapshot atual de eventos pro Revel.

    Nunca levanta exceção: o Revel pode estar fora do ar (roda intermitente),
    e uma falha aqui não pode derrubar o refresh dos scrapers. Sem retry —
    a próxima varredura (60 min) tenta de novo com os dados atualizados.
    """
    if not REVEL_INGEST_URL or not REVEL_INGEST_API_KEY:
        return

    events = build_events_json()
    if not events:
        return

    try:
        response = httpx.post(
            REVEL_INGEST_URL,
            json=events,
            headers={"Authorization": f"Bearer {REVEL_INGEST_API_KEY}"},
            timeout=REVEL_PUSH_TIMEOUT,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        log.exception("falha ao enviar eventos pro Revel")
        return

    _log_summary(response.json())


def _log_summary(payload: dict) -> None:
    results = payload.get("results", [])
    counts: dict[str, int] = {}
    for r in results:
        counts[r["action"]] = counts.get(r["action"], 0) + 1
    log.info("Revel: %s (%d eventos no envio)", counts, len(results))
