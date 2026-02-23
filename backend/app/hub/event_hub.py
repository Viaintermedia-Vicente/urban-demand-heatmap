from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.engine import Engine

from app.domain.canonical import CanonicalEvent
from app.providers.events.base import EventsProvider, ExternalEvent
from app.services.event_upsert import EventUpsertService

from .provider_registry import ProviderRegistry


class EventHub:
    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry
        self.errors: list[tuple[str, Exception]] = []
        self.provider_stats: list[dict] = []

    def fetch_all(self, *, city: str, past_days: int = 0, future_days: int = 0) -> List[CanonicalEvent]:
        self.errors = []
        self.provider_stats = []
        reference = datetime.now(timezone.utc)
        combined: List[CanonicalEvent] = []
        for name in self._registry.list():
            provider = self._registry.get(name)
            provider_summary = {"provider": name, "fetched": 0, "mapped": 0, "skipped_no_coords": 0}
            try:
                events, stats = self._fetch_from_provider(
                    provider=provider,
                    city=city,
                    past_days=past_days,
                    future_days=future_days,
                    reference=reference,
                )
            except Exception as exc:  # pragma: no cover - captured in tests
                self.errors.append((name, exc))
                continue
            if stats:
                provider_summary["fetched"] += stats.get("fetched", 0)
                provider_summary["mapped"] += stats.get("mapped", len(events))
                provider_summary["skipped_no_coords"] += stats.get("skipped_no_coords", 0)
            else:
                provider_summary["fetched"] += len(events)
                provider_summary["mapped"] += len(events)
            combined.extend(self._to_canonical(events))
            self.provider_stats.append(provider_summary)
        return combined

    def sync(
        self,
        *,
        city: str,
        past_days: int,
        future_days: int,
        session,
    ) -> dict:
        events = self.fetch_all(city=city, past_days=past_days, future_days=future_days)
        engine = self._resolve_engine(session)
        upsert_service = EventUpsertService(engine)
        today = datetime.now(ZoneInfo("Europe/Madrid")).replace(hour=0, minute=0, second=0, microsecond=0)
        aggregate = {"inserted": 0, "updated": 0}
        grouped: dict[str, list[CanonicalEvent]] = defaultdict(list)
        for event in events:
            grouped[event.source].append(event)

        for source, source_events in grouped.items():
            deactivate_flag = bool(source_events) and source.lower() != "demo"
            per_stats = upsert_service.upsert_events(
                source_events,
                source=source if deactivate_flag else None,
                today=today if deactivate_flag else None,
                deactivate_missing=deactivate_flag,
            )
            aggregate["inserted"] += per_stats.get("inserted", 0)
            aggregate["updated"] += per_stats.get("updated", 0)

        return {
            "providers": self._registry.list(),
            "fetched": len(events),
            "inserted": aggregate["inserted"],
            "updated": aggregate["updated"],
            "errors": list(self.errors),
            "provider_stats": self.provider_stats,
        }

    @staticmethod
    def _fetch_from_provider(
        *, provider: EventsProvider, city: str, past_days: int, future_days: int, reference: datetime
    ) -> tuple[list[ExternalEvent], Optional[dict]]:
        aggregated: list[ExternalEvent] = []
        stats_total: Optional[dict] = None
        for direction, days in (("past", past_days), ("future", future_days)):
            if days <= 0:
                continue
            payload = provider.fetch_events(
                city=city,
                days=days,
                reference=reference,
                direction=direction,
            )
            events_batch = payload
            stats = None
            if isinstance(payload, tuple) and len(payload) == 2:
                events_batch, stats = payload  # type: ignore[assignment]
            aggregated.extend(events_batch)
            if stats:
                if stats_total is None:
                    stats_total = {"fetched": 0, "mapped": 0, "skipped_no_coords": 0}
                stats_total["fetched"] += stats.get("fetched", len(events_batch))
                stats_total["mapped"] += stats.get("mapped", len(events_batch))
                stats_total["skipped_no_coords"] += stats.get("skipped_no_coords", 0)
        if stats_total is None and aggregated:
            stats_total = {"fetched": len(aggregated), "mapped": len(aggregated), "skipped_no_coords": 0}
        return aggregated, stats_total

    @staticmethod
    def _to_canonical(events: list[ExternalEvent]) -> List[CanonicalEvent]:
        canonicals: List[CanonicalEvent] = []
        for event in events:
            canonicals.append(
                CanonicalEvent(
                    source=event.source,
                    external_id=event.external_id,
                    title=event.title,
                    start_at=event.start_at,
                    end_at=event.end_at,
                    lat=event.lat,
                    lon=event.lon,
                    venue_name=event.venue_name,
                    venue_external_id=event.venue_external_id,
                    venue_source=event.venue_source,
                    venue_city=event.venue_city,
                    venue_country=event.venue_country,
                    url=event.url,
                )
            )
        return canonicals

    @staticmethod
    def _resolve_engine(session) -> Engine:
        if isinstance(session, Engine):
            return session
        bind = getattr(session, 'bind', None)
        if bind is None:
            raise ValueError("session must be an Engine or expose 'bind'")
        return bind
