"""Modelo normalizado de evento — todos os scrapers devem retornar isso."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha1


@dataclass
class Event:
    title: str
    url: str
    source: str                      # ex: "sympla", "eventim", "articket"
    venue: str = ""
    address: str = ""
    organizer: str = ""
    city: str = "Rio de Janeiro"
    date: datetime | None = None       # início do show (se disponível)
    end_date: datetime | None = None   # encerramento do show (se disponível)
    price: str = ""
    image: str = ""
    description: str = ""
    found_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def uid(self) -> str:
        """ID estável para deduplicação entre execuções."""
        return sha1(f"{self.source}|{self.url}".encode()).hexdigest()
