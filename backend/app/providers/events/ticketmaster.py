from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx

from .base import EventsProvider, ExternalEvent


class TicketmasterEventsProvider(EventsProvider):
    BASE_URL = "https://app.ticketmaster.com/discovery/v2/events.json"

    def __init__(self, api_key: Optional[str] = None, timeout: float = 10.0):
        self.api_key = api_key or os.getenv("TICKETMASTER_API_KEY")
        if not self.api_key:
            raise RuntimeError("TICKETMASTER_API_KEY is required for TicketmasterEventsProvider")
        self.timeout = timeout

    def fetch_events(
        self,
        *,
        city: str,
        days: int,
        reference: Optional[datetime] = None,
        direction: str = "future",
    ) -> List[ExternalEvent]:
        reference = reference or datetime.now(timezone.utc)
        if direction == "future":
            start = reference
            end = reference + timedelta(days=max(1, days))
        else:
            start = reference - timedelta(days=max(1, days))
            end = reference
        params = {
            "apikey": self.api_key,
            "locale": "*",
            "city": city,
            "startDateTime": self._format_ts(start),
            "endDateTime": self._format_ts(end),
            "size": min(200, max(50, days * 50)),
            "sort": "date,asc",
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(self.BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        embedded = data.get("_embedded", {})
        events = embedded.get("events", [])
        return self._process_events(events)

    def _process_events(self, events: list[dict]) -> tuple[list[ExternalEvent], dict]:
        mapped: List[ExternalEvent] = []
        stats = {"fetched": len(events), "mapped": 0, "skipped_no_coords": 0}
        for item in events:
            try:
                event = self._map_event(item)
            except Exception:
                continue
            if event is None:
                stats["skipped_no_coords"] += 1
                continue
            mapped.append(event)
        stats["mapped"] = len(mapped)
        return mapped, stats

    def _map_event(self, payload: dict) -> ExternalEvent:
        dates = payload.get("dates", {})
        start = self._parse_ts(dates.get("start", {}).get("dateTime"))
        end = self._parse_ts(dates.get("end", {}).get("dateTime")) if dates.get("end") else None
        venue = None
        venues = payload.get("_embedded", {}).get("venues", [])
        if venues:
            venue = venues[0]
        location = (venue or {}).get("location", {})
        if location:
            try:
                lat = float(location.get("latitude"))
                lon = float(location.get("longitude"))
            except (TypeError, ValueError):
                return None
        else:
            return None
        classification = (payload.get("classifications") or [{}])[0]
        segment = (classification.get("segment") or {}).get("name")
        genre = (classification.get("genre") or {}).get("name")
        popularity = payload.get("score")
        if popularity is not None:
            try:
                popularity = float(popularity)
            except (TypeError, ValueError):
                popularity = None
        return ExternalEvent(
            source="ticketmaster",
            external_id=payload.get("id", ""),
            title=payload.get("name", ""),
            category=(segment or genre or "unknown").lower(),
            subcategory=genre,
            start_at=start,
            end_at=end,
            status=payload.get("dates", {}).get("status", {}).get("code"),
            url=payload.get("url"),
            venue_name=(venue or {}).get("name"),
            venue_external_id=(venue or {}).get("id"),
            venue_city=(venue or {}).get("city", {}).get("name"),
            venue_country=(venue or {}).get("country", {}).get("countryCode"),
            lat=lat,
            lon=lon,
            timezone=(venue or {}).get("timezone") or (start.tzinfo.tzname(None) if start.tzinfo else "UTC"),
            popularity_score=popularity,
        )

    @staticmethod
    def _parse_ts(value: Optional[str]) -> datetime:
        if value is None:
            raise ValueError("Missing datetime")
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        if len(value) == 19:
            value += "+00:00"
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    @staticmethod
    def _format_ts(value: datetime) -> str:
        value = value.astimezone(timezone.utc).replace(microsecond=0)
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
