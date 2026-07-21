"""Helper compartilhado pra scrapers que precisam de um navegador de verdade
(Playwright) em vez de HTTP puro — usado só quando o site tem proteção
anti-bot que bloqueia requisições simples mesmo com headers/cookies corretos
(ex: Shotgun, atrás de um "Vercel Security Checkpoint").

É bem mais pesado que os scrapers baseados em httpx (baixa um Chromium,
cada página demora segundos pra carregar em vez de milissegundos), então só
vale usar quando não há alternativa mais leve.
"""
from __future__ import annotations

from contextlib import contextmanager

from playwright.sync_api import sync_playwright

from app.scrapers.base import HEADERS


@contextmanager
def browser_page():
    """Abre uma página de Chromium headless com um user-agent de navegador real."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(user_agent=HEADERS["User-Agent"])
            yield page
        finally:
            browser.close()
