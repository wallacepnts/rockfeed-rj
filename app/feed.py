"""Gera o RSS 2.0 a partir dos eventos armazenados."""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime

from app import store

CHANNEL_TITLE = "Shows de Rock no Rio de Janeiro"
CHANNEL_LINK = "https://rockfeed.anaconda-amberjack.ts.net/feed.xml"
CHANNEL_DESC = "Agregador de shows de rock em sites de ingressos do RJ"


def _esc(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_rss(limit: int = 1000) -> str:
    today = datetime.now(timezone.utc).date().isoformat()
    items = []
    for e in store.latest(limit):
        if e.get("date") and e["date"][:10] < today:
            continue  # show já aconteceu

        desc_parts = []
        if e.get("date"):
            desc_parts.append(f"Início: {e['date'][:16].replace('T', ' ')}")
        if e.get("end_date"):
            desc_parts.append(f"Encerramento: {e['end_date'][:16].replace('T', ' ')}")
        if e.get("venue"):
            desc_parts.append(f"Local: {e['venue']}")
        if e.get("address"):
            desc_parts.append(f"Endereço: {e['address']}")
        if e.get("organizer"):
            desc_parts.append(f"Organizado por: {e['organizer']}")
        if e.get("description"):
            desc_parts.append(f"Descrição: {e['description']}")
        if e.get("price"):
            desc_parts.append(f"Preço: {e['price']}")
        desc_parts.append(f"Fonte: {e['source']}")
        description = " | ".join(desc_parts)

        found = datetime.fromisoformat(e["found_at"]).replace(tzinfo=timezone.utc)
        enclosure = (
            f'<enclosure url="{_esc(e["image"])}" type="image/jpeg" length="0"/>'
            if e.get("image")
            else ""
        )
        items.append(
            f"""    <item>
      <title>{_esc(e['title'])}</title>
      <link>{_esc(e['url'])}</link>
      <guid isPermaLink="false">{e['uid']}</guid>
      <pubDate>{format_datetime(found)}</pubDate>
      <description>{_esc(description)}</description>
      {enclosure}
    </item>"""
        )

    now = format_datetime(datetime.now(timezone.utc))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{CHANNEL_TITLE}</title>
    <link>{CHANNEL_LINK}</link>
    <description>{CHANNEL_DESC}</description>
    <language>pt-br</language>
    <lastBuildDate>{now}</lastBuildDate>
{chr(10).join(items)}
  </channel>
</rss>
"""
