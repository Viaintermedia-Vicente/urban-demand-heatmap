from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol


@dataclass
class ExternalEvent:
    source: str
    external_id: str
    title: str
    start_at: datetime
    end_at: Optional[datetime] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    status: Optional[str] = None
    url: Optional[str] = None
    venue_name: Optional[str] = None
    venue_external_id: Optional[str] = None
    venue_source: Optional[str] = None
    venue_city: Optional[str] = None
    venue_country: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    timezone: Optional[str] = None
    popularity_score: Optional[float] = None


class EventsProvider(Protocol):
    """Contract for external event providers."""

    def fetch_events(
        self,
        *,
        city: str,
        days: int,
        reference: Optional[datetime] = None,
        direction: str = "future",
    ) -> list[ExternalEvent]:
        """Fetch events for ``city`` relative to ``reference`` within ``days``.

        ``direction`` should be either "future" or "past". Providers may ignore
        the hint if unsupported but the job layer relies on it for backfill.
        """
        raise NotImplementedError
