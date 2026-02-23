import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Map as LeafletMap } from "leaflet";
import L from "leaflet";
import { Circle, MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";

import { fetchHeatmap, type HeatmapEvent, type HeatmapHotspot, type HeatmapMode } from "./api/heatmap";
import { fetchEvents, type EventSummary } from "./api/events";
import { fetchRegions } from "./api/regions";
import "./App.css";

type RegionOption = {
  id: string;
  label: string;
  lat: number;
  lon: number;
};

const DEFAULT_SELECTION_RADIUS_M = 500;
const EVENT_MERGE_RADIUS_M = 250;

function App() {
  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const fallbackRegion: RegionOption = { id: "madrid", label: "Madrid", lat: 40.4168, lon: -3.7038 };
  const [regions, setRegions] = useState<RegionOption[]>([]);
  const [selectedRegionId, setSelectedRegionId] = useState<string>(fallbackRegion.id);
  const selectedRegion = regions.find((region) => region.id === selectedRegionId) ?? fallbackRegion;
  const [date, setDate] = useState(today);
  const [hour, setHour] = useState(22);
  const [mode, setMode] = useState<HeatmapMode>("heuristic");
  const [refreshToken, setRefreshToken] = useState(0);

  const [hotspots, setHotspots] = useState<HeatmapHotspot[]>([]);
  const mergedHotspots = useMemo(() => mergeCloseHotspots(hotspots, 250), [hotspots]);
  const [densityFilter, setDensityFilter] = useState<Density>("ALL");
  const [events, setEvents] = useState<HeatmapEvent[]>([]);
  const [selectedHotspot, setSelectedHotspot] = useState<HeatmapHotspot | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<HeatmapEvent | null>(null);
  const [activeTab, setActiveTab] = useState<"predictive" | "events">("predictive");
  const [targetDisplay, setTargetDisplay] = useState<string>("Sin datos");
  const [weatherSummary, setWeatherSummary] = useState<string>("");
  const [displayHour, setDisplayHour] = useState(hour);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);
  const intensityScore = useMemo(() => {
    if (!mergedHotspots.length) return null;
    return Math.max(...mergedHotspots.map((spot) => spot.score));
  }, [mergedHotspots]);
  const intensityLabel = intensityScore != null ? labelScore(intensityScore) : "Sin datos";

  const mapRef = useRef<LeafletMap | null>(null);
  const madridFormatter = useMemo(
    () =>
      new Intl.DateTimeFormat("es-ES", {
        weekday: "long",
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "numeric",
        hour12: false,
        timeZone: "Europe/Madrid",
      }),
    []
  );

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    async function loadRegions() {
      try {
        const loaded = await fetchRegions();
        if (cancelled) return;
        setRegions(loaded);
        if (loaded.length > 0) {
          setSelectedRegionId((prev) => prev || loaded[0].id);
        }
      } catch {
        if (cancelled) return;
        setRegions([fallbackRegion]);
        setSelectedRegionId((prev) => prev || fallbackRegion.id);
      }
    }

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [heatmap, eventsFallback] = await Promise.all([
          fetchHeatmap({
            date,
            hour,
            mode,
            lat: selectedRegion.lat,
            lon: selectedRegion.lon,
            signal: controller.signal,
          }),
          fetchEvents({ date, fromHour: hour, signal: controller.signal }).catch(() => [] as EventSummary[]),
        ]);
        if (!controller.signal.aborted) {
          setHotspots(heatmap.hotspots ?? []);
          const eventsFromHeatmap = (heatmap.events as HeatmapEvent[] | undefined) ?? [];
          const mergedEventsSource =
            eventsFromHeatmap.length > 0
              ? eventsFromHeatmap
              : eventsFallback.map(adaptEventSummary);
          const eventsWithScore = enrichEventsWithHotspotScore(mergedEventsSource, heatmap.hotspots ?? []);
          setEvents(eventsWithScore);
          const targetInfo = formatTargetMetadata(heatmap.target, madridFormatter);
          if (targetInfo) {
            setTargetDisplay(targetInfo.label);
            setDisplayHour(targetInfo.hour);
          } else {
            setTargetDisplay("Sin datos");
            setDisplayHour(hour);
          }
          const w = heatmap.weather;
          setWeatherSummary(buildWeatherSummary(w, targetInfo?.hour ?? hour));
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          const message = err instanceof Error ? err.message : "Error desconocido";
          setError(message);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadRegions().then(load);
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [date, hour, mode, refreshToken, selectedRegion, fallbackRegion, madridFormatter]);

  useEffect(() => {
    setSelectedHotspot(null);
    setSelectedEvent(null);
    setExpandedEventId(null);
  }, [selectedRegion, date, hour, mode]);

  useEffect(() => {
    const map = mapRef.current;
    if (map) {
      map.flyTo([selectedRegion.lat, selectedRegion.lon], Math.max(map.getZoom(), 11), { duration: 0.8 });
    }
  }, [selectedRegion]);

  const handleHotspotClick = useCallback((spot: HeatmapHotspot) => {
    const nextKey = makeHotspotKey(spot);
    setExpandedEventId(null);
    setSelectedHotspot((prev) => {
      const same = prev && makeHotspotKey(prev) === nextKey;
      if (same) return null;
      return spot;
    });
    setSelectedEvent(null);
    const map = mapRef.current;
    if (!map) return;
    map.flyTo([spot.lat, spot.lon], Math.max(map.getZoom(), 14), { duration: 0.75 });
  }, []);

  const handleEventClick = useCallback((event: HeatmapEvent, key: string) => {
    setExpandedEventId((prev) => (prev === key ? null : key));
    setSelectedEvent(event);
    setSelectedHotspot(null);
    if (event.lat != null && event.lon != null) {
      const map = mapRef.current;
      if (map) map.flyTo([event.lat, event.lon], Math.max(map.getZoom(), 14), { duration: 0.75 });
    }
  }, []);

  const resetAllFilters = useCallback(() => {
    setDensityFilter("ALL");
    setExpandedEventId(null);
    setSelectedHotspot(null);
    setSelectedEvent(null);
  }, []);

  const handleDensityChange = useCallback(
    (value: Density) => {
      setDensityFilter(value);
      setSelectedHotspot(null);
      setSelectedEvent(null);
      setExpandedEventId(null);
    },
    []
  );

  const densityCounts = useMemo(() => {
    let high = 0, medium = 0, low = 0;
    mergedHotspots.forEach((spot) => {
      const level = classify(spot.score);
      if (level === "HIGH") high += 1;
      else if (level === "MEDIUM") medium += 1;
      else low += 1;
    });
    return { high, medium, low, all: mergedHotspots.length };
  }, [mergedHotspots]);

  const mapHotspots = useMemo(() => {
    if (densityFilter === "ALL") return mergedHotspots;
    return mergedHotspots.filter((h) => classify(h.score) === densityFilter);
  }, [densityFilter, mergedHotspots]);

  const visibleEvents = useMemo(() => {
    return [...events].sort((a, b) => (a.start_dt ?? "").localeCompare(b.start_dt ?? ""));
  }, [events]);

  const makeEventIcon = useCallback((category: string | null | undefined, selected: boolean) => {
    const color = getEventColor(category);
    const size = selected ? 16 : 14;
    const className = selected ? "event-marker event-marker--selected" : "event-marker";
    return L.divIcon({
      className,
      html: `<div class="event-marker__dot" style="background:${color}"></div>`,
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
    });
  }, []);

  return (
    <div className="app">
      <div className="app__intro">
        <h1>Heatmap TFM</h1>
        <p>Explora hotspots urbanos y eventos estimados · vista TS.</p>
      </div>
      <form
        className="controls-row"
        onSubmit={(e) => {
          e.preventDefault();
          setRefreshToken((token) => token + 1);
        }}
      >
        <label className="field">
          <span>Comunidad / Provincia</span>
          <select
            value={selectedRegionId}
            onChange={(e) => setSelectedRegionId(e.target.value)}
            aria-label="Selecciona la comunidad o provincia"
          >
            {(regions.length ? regions : [fallbackRegion]).map((region) => (
              <option key={region.id} value={region.id}>
                {region.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Fecha</span>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <fieldset className="field mode-field">
          <legend>
            Modo
            <Tooltip
              text={
                <>
                  <strong>Heuristic:</strong> Cálculo por reglas (sin modelo entrenado).<br />
                  <strong>ML:</strong> Cálculo usando el modelo entrenado (ajusta llegada y asistencia según condiciones).
                </>
              }
            />
          </legend>
          <div className="mode-toggle" role="radiogroup" aria-label="Modo de scoring">
            <label>
              <input
                type="radio"
                name="mode"
                value="heuristic"
                checked={mode === "heuristic"}
                onChange={() => setMode("heuristic")}
              />
              Heuristic
            </label>
            <label>
              <input
                type="radio"
                name="mode"
                value="ml"
                checked={mode === "ml"}
                onChange={() => setMode("ml")}
              />
              ML
            </label>
          </div>
        </fieldset>
        <button type="submit" className="reload-btn">
          Recargar
        </button>
      </form>

      <main className="layout">
        <section className="map-column">
          <div className="map-meta">
            <span className="map-meta__target">
              {targetDisplay}
              {mode === "ml" && <span className="map-meta__badge">Modo ML</span>}
            </span>
            {weatherSummary && <span className="map-meta__weather">{weatherSummary}</span>}
          </div>
          <div className="map-wrapper">
            <MapContainer
              center={[selectedRegion.lat, selectedRegion.lon]}
              zoom={12}
              className="map"
              ref={mapRef}
            >
              <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap" />
              {activeTab === "predictive" &&
                mapHotspots.map((spot, index) => {
                  const level = classify(spot.score);
                  const color = DENSITY_COLORS[level];
                  const isSelected = selectedHotspot && makeHotspotKey(selectedHotspot) === makeHotspotKey(spot);
                  const options = {
                    color: isSelected ? "#111827" : "#111827",
                    weight: isSelected ? 3 : level === "HIGH" ? 2 : 1,
                    fillColor: color,
                    fillOpacity: isSelected ? 0.6 : level === "HIGH" ? 0.55 : level === "MEDIUM" ? 0.45 : 0.35,
                    opacity: 0.9,
                  };
                  return (
                    <Circle
                      key={`${spot.lat}-${spot.lon}-${index}`}
                      center={[spot.lat, spot.lon]}
                      radius={spot.radius_m ?? 150}
                      pathOptions={options}
                      eventHandlers={{
                        click: (leafletEvent) => {
                          leafletEvent.originalEvent?.stopPropagation?.();
                          handleHotspotClick(spot);
                        },
                      }}
                    >
                      <Popup>
                        <div className="popup">
                          <strong>Score:</strong> {spot.score.toFixed(3)}
                          <br />
                          <strong>Radio:</strong> {spot.radius_m.toFixed(0)} m
                          {spot.lead_time_min_pred != null && (
                            <>
                              <br />
                              <strong>Lead time:</strong> {spot.lead_time_min_pred.toFixed(1)} min
                            </>
                          )}
                          {spot.attendance_factor_pred != null && (
                            <>
                              <br />
                              <strong>Factor asistencia:</strong> {spot.attendance_factor_pred.toFixed(2)}
                            </>
                          )}
                        </div>
                      </Popup>
                    </Circle>
                  );
                })}
              {activeTab === "events" &&
                visibleEvents
                  .filter((evt) => evt.lat != null && evt.lon != null)
                  .map((evt, index) => {
                    const isSelected = selectedEvent && makeEventKey(selectedEvent) === makeEventKey(evt);
                    const icon = makeEventIcon(evt.category ?? null, isSelected);
                    return (
                      <Marker
                        key={`evt-marker-${index}`}
                        position={[evt.lat as number, evt.lon as number]}
                        icon={icon}
                        eventHandlers={{
                          click: () => handleEventClick(evt, makeEventKey(evt, index)),
                        }}
                      >
                        <Popup>
                          <div className="popup">
                            <strong>{evt.title}</strong>
                            <br />
                            {evt.start_dt ? new Date(evt.start_dt).toLocaleString("es-ES", { hour: "2-digit", minute: "2-digit" }) : "Hora N/D"}
                            {evt.venue_name && (
                              <>
                                <br />
                                {evt.venue_name}
                              </>
                            )}
                            {evt.url && (
                              <>
                                <br />
                                <a href={evt.url} target="_blank" rel="noopener noreferrer">Ver evento</a>
                              </>
                            )}
                          </div>
                        </Popup>
                      </Marker>
                    );
                  })}
            </MapContainer>
            <div className="map-legend" title="Clasificación por score relativo">
              <div><span className="legend-dot legend-dot--high" /> Alta</div>
              <div><span className="legend-dot legend-dot--medium" /> Media</div>
              <div><span className="legend-dot legend-dot--low" /> Baja</div>
            </div>
          </div>
            <div className="map-controls">
              <div className="hour-row" aria-live="polite">
                <div className="hour-slider">
                  <label htmlFor="hourRange">Hora: {displayHour.toString().padStart(2, "0")}h</label>
                  <input
                    id="hourRange"
                    type="range"
                    min={0}
                    max={23}
                    value={hour}
                    onChange={(e) => {
                      const value = Number(e.target.value);
                      setHour(value);
                      setDisplayHour(value);
                    }}
                  />
                </div>
              </div>
            </div>
          </section>

        <section className="sidebar">
          {loading && <div className="notice">Cargando datos…</div>}
          {error && <div className="notice notice--error">{error}</div>}

          <div className="side-panel">
            <div className="mode-toggle">
              <button
                type="button"
                className={`mode-toggle__btn${activeTab === "predictive" ? " mode-toggle__btn--active" : ""}`}
                onClick={() => { setActiveTab("predictive"); setExpandedEventId(null); setSelectedEvent(null); }}
              >
                🔮 Predictivo
              </button>
              <button
                type="button"
                className={`mode-toggle__btn${activeTab === "events" ? " mode-toggle__btn--active" : ""}`}
                onClick={() => { setActiveTab("events"); setExpandedEventId(null); setSelectedHotspot(null); }}
              >
                📍 Eventos actuales
              </button>
            </div>

            {activeTab === "predictive" && (
              <>
                <div className="side-panel__header panel__header">
                  <h2>Zonas ({mapHotspots.length})</h2>
                </div>
                <div className="side-panel__body">
                  <ul className="list">
                    {mapHotspots.map((spot, index) => {
                      const isExpanded = expandedEventId === makeHotspotKey(spot);
                      const level = classify(spot.score);
                      return (
                        <li key={`zone-${index}`}>
                        <button
                          type="button"
                          className="card card--flat"
                          onClick={() => {
                            setExpandedEventId((prev) => (prev === makeHotspotKey(spot) ? null : makeHotspotKey(spot)));
                            handleHotspotClick(spot);
                          }}
                        >
                          <div className="event-title">{`${level === "HIGH" ? "Alta" : level === "MEDIUM" ? "Media" : "Baja"} · ${spot.score.toFixed(2)}`}</div>
                          <div className="event-meta">{`Lat ${spot.lat.toFixed(5)}, Lon ${spot.lon.toFixed(5)}`}</div>
                          {isExpanded && (
                            <div className="event-detail">
                              <div className="event-detail__grid">
                                <span><strong>Score:</strong> {spot.score.toFixed(3)}</span>
                                <span><strong>Radio:</strong> {spot.radius_m.toFixed(0)} m</span>
                              </div>
                            </div>
                          )}
                        </button>
                      </li>
                      );
                    })}
                  </ul>
                </div>
                <div className="side-panel__footer hotspot-strip-row">
                  <DensityFilterBar value={densityFilter} onChange={handleDensityChange} onReset={resetAllFilters} counts={densityCounts} />
                </div>
              </>
            )}

            {activeTab === "events" && (
              <>
                <div className="side-panel__header panel__header">
                  <h2>Eventos actuales ({visibleEvents.length})</h2>
                </div>
                <div className="side-panel__body">
                  {visibleEvents.length === 0 && <p className="muted">No hay eventos.</p>}
                  <ul className="list">
                    {visibleEvents.map((event, index) => {
                  const eventKey = makeEventKey(event, index);
                  const sourceLabel = normalizeSourceLabel(event.source);
                  const categoryLabel = (event.category ?? "").trim();
                  const showCategory = !!categoryLabel && categoryLabel.toLowerCase() !== "unknown";
                  const isExpanded = expandedEventId === eventKey;
                  return (
                    <li key={`event-${index}`}>
                      <button
                        type="button"
                        className="card card--flat"
                        onClick={() => handleEventClick(event, eventKey)}
                      >
                        <div className="event-title">{event.title}</div>
                        <div className="event-meta">{event.venue_name ?? "Sin venue"}</div>
                        <div className="event-meta row-space">
                          {showCategory && renderCategoryBadge(categoryLabel)}
                          {event.url && (
                            <a
                              href={event.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="event-link__anchor"
                            >
                              Ver evento
                            </a>
                          )}
                        </div>
                        <div className="event-detail">
                          <div className="event-detail__grid">
                            {event.start_dt && (
                              <span>
                                <strong>Inicio:</strong>{" "}
                                {new Date(event.start_dt).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}
                              </span>
                            )}
                            {event.end_dt && (
                              <span>
                                <strong>Fin:</strong>{" "}
                                {new Date(event.end_dt).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}
                              </span>
                            )}
                          </div>
                          {event.description && <p className="event-desc">{event.description}</p>}
                        </div>
                      </button>
                    </li>
                  );
                })}
                  </ul>
                </div>
              </>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

function normalizeSourceLabel(source: string | null | undefined) {
  if (!source) return "";
  const cleaned = source.trim().toLowerCase();
  if (cleaned === "unknown" || cleaned === "none" || cleaned === "n/d" || cleaned === "nd") return "";
  return source;
}

function labelScore(score: number): "Baja" | "Media" | "Alta" {
  if (score < 0.8) return "Baja";
  if (score < 1.4) return "Media";
  return "Alta";
}

type TooltipProps = {
  text: React.ReactNode;
};

function Tooltip({ text }: TooltipProps) {
  const tooltipId = "mode-info-tooltip";
  return (
    <span className="tooltip">
      <button type="button" className="tooltip__trigger" aria-describedby={tooltipId} aria-label="Información sobre los modos">
        ?
      </button>
      <span className="tooltip__content" role="tooltip" id={tooltipId}>
        {text}
      </span>
    </span>
  );
}

export default App;

type MapClickCaptureProps = {
  onMapClick: (lat: number, lon: number) => void;
};

function formatTargetMetadata(targetIso: string | undefined, formatter: Intl.DateTimeFormat) {
  if (!targetIso) return null;
  const date = new Date(targetIso);
  const parts = formatter.formatToParts(date);
  const partsMap = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  const weekday = capitalize(partsMap.weekday ?? "");
  const day = partsMap.day ?? "";
  const month = capitalize(partsMap.month ?? "");
  const year = partsMap.year ?? "";
  const hour = Number(partsMap.hour ?? "0");
  const label = `${weekday} · ${day} ${month} ${year} · ${hour}h`;
  return { label, hour };
}

function capitalize(value: string) {
  if (!value) return value;
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function makeHotspotKey(spot: HeatmapHotspot) {
  return `${spot.lat.toFixed(5)}:${spot.lon.toFixed(5)}`;
}

function buildWeatherSummary(weather: any, localHour: number) {
  if (!weather) return "";
  const icon = getWeatherIcon(weather, localHour);
  const temp = weather.temperature_c != null ? `${weather.temperature_c.toFixed(1)}ºC` : "N/D";
  const rainAmount = weather.precipitation_mm != null ? weather.precipitation_mm.toFixed(1) : "0.0";
  const wind = weather.wind_speed_kmh != null ? `${weather.wind_speed_kmh.toFixed(0)} km/h` : "N/D";
  return `${icon} ${temp}   🌧 ${rainAmount} mm   💨 ${wind}`;
}

function getWeatherIcon(weather: any, localHour: number) {
  if (weather?.precipitation_mm != null && weather.precipitation_mm > 0) {
    return "🌧";
  }
  if (localHour >= 7 && localHour <= 19) {
    return "☀";
  }
  return "🌙";
}

type DensityLevel = "HIGH" | "MEDIUM" | "LOW";
type Density = "ALL" | DensityLevel;

const DENSITY_COLORS: Record<DensityLevel, string> = {
  HIGH: "#ef4444",
  MEDIUM: "#f59e0b",
  LOW: "#22c55e",
} as const;

function getEventColor(category: string | null | undefined) {
  const cat = (category ?? "").toLowerCase();
  if (cat.includes("music") || cat.includes("música") || cat.includes("concert") || cat.includes("festival")) return "#8b5cf6";
  if (cat.includes("theatre") || cat.includes("teatro")) return "#2563eb";
  if (cat.includes("comedy") || cat.includes("comedia")) return "#10b981";
  if (cat.includes("sport") || cat.includes("deporte") || cat.includes("match")) return "#f59e0b";
  return "#0ea5e9";
}

function normalizeCategory(category: string | null | undefined) {
  if (!category) return null;
  const cat = category.toLowerCase().trim();
  if (!cat || cat === "unknown") return null;
  return category;
}

function renderCategoryBadge(category: string | null | undefined) {
  const label = normalizeCategory(category);
  if (!label) return null;
  return <span className="event-badge">{label}</span>;
}

function classify(score: number): DensityLevel {
  if (score >= 0.66) return "HIGH";
  if (score >= 0.33) return "MEDIUM";
  return "LOW";
}

function classifyEvent(event: HeatmapEvent): DensityLevel {
  const scoreVal = event.score != null && !Number.isNaN(Number(event.score)) ? Number(event.score) : 0;
  return classify(scoreVal);
}

function adaptEventSummary(event: EventSummary): HeatmapEvent {
  const categoryLabel = normalizeCategory((event as any).category);
  return {
    id: (event as any).id ?? `${event.title}-${event.start_dt ?? ""}`,
    title: event.title,
    category: categoryLabel,
    start_dt: (event as any).start_dt ?? null,
    end_dt: (event as any).end_dt ?? null,
    venue_name: (event as any).venue_name ?? null,
    lat: (event as any).lat ?? null,
    lon: (event as any).lon ?? null,
    url: (event as any).url ?? null,
    source: (event as any).source ?? null,
    expected_attendance: (event as any).expected_attendance ?? null,
    city: (event as any).city ?? null,
    address: (event as any).address ?? null,
    organizer: (event as any).organizer ?? null,
    price: (event as any).price ?? null,
    description: (event as any).description ?? null,
    score: (event as any).score ?? null,
  };
}

function enrichEventsWithHotspotScore(events: HeatmapEvent[], hotspots: HeatmapHotspot[]) {
  if (!hotspots.length) return events;
  const radiusByHotspot = (spot: HeatmapHotspot) => spot.radius_m ?? DEFAULT_SELECTION_RADIUS_M;
  return events.map((evt) => {
    if (evt.score != null && !Number.isNaN(Number(evt.score))) {
      return evt;
    }
    if (evt.lat == null || evt.lon == null) {
      return { ...evt, score: null };
    }
    let bestScore: number | null = null;
    for (const hs of hotspots) {
      const distance = haversineMeters(evt.lat, evt.lon, hs.lat, hs.lon);
      if (distance <= radiusByHotspot(hs)) {
        bestScore = bestScore == null ? hs.score : Math.max(bestScore, hs.score);
      }
    }
    return { ...evt, score: bestScore };
  });
}

function makeEventKey(event: HeatmapEvent, fallbackIndex?: number) {
  const key = event.id ?? (event.title ? `${event.title}-${event.start_dt ?? ""}` : null);
  return key != null ? String(key) : `evt-${fallbackIndex ?? 0}`;
}

function haversineMeters(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371000;
  const phi1 = (lat1 * Math.PI) / 180;
  const phi2 = (lat2 * Math.PI) / 180;
  const dPhi = ((lat2 - lat1) * Math.PI) / 180;
  const dLambda = ((lon2 - lon1) * Math.PI) / 180;
  const a = Math.sin(dPhi / 2) ** 2 + Math.cos(phi1) * Math.cos(phi2) * Math.sin(dLambda / 2) ** 2;
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

function mergeCloseHotspots(hotspots: HeatmapHotspot[], thresholdMeters: number): HeatmapHotspot[] {
  if (!hotspots.length) return [];
  const sorted = [...hotspots].sort((a, b) => b.score - a.score);
  const clusters: { latSum: number; lonSum: number; count: number; score: number; radius: number }[] = [];

  sorted.forEach((spot) => {
    let merged = false;
    for (const cluster of clusters) {
      const distance = haversineMeters(
        cluster.latSum / cluster.count,
        cluster.lonSum / cluster.count,
        spot.lat,
        spot.lon
      );
      if (distance < thresholdMeters) {
        cluster.latSum += spot.lat;
        cluster.lonSum += spot.lon;
        cluster.count += 1;
        cluster.score = Math.max(cluster.score, spot.score);
        cluster.radius = Math.max(cluster.radius, spot.radius_m ?? DEFAULT_SELECTION_RADIUS_M);
        merged = true;
        break;
      }
    }
    if (!merged) {
      clusters.push({
        latSum: spot.lat,
        lonSum: spot.lon,
        count: 1,
        score: spot.score,
        radius: spot.radius_m ?? DEFAULT_SELECTION_RADIUS_M,
      });
    }
  });

  return clusters.map((c) => ({
    lat: c.latSum / c.count,
    lon: c.lonSum / c.count,
    score: c.score,
    radius_m: c.radius,
    lead_time_min_pred: null,
    attendance_factor_pred: null,
  }));
}

type DensityFilterBarProps = {
  value: Density;
  onChange: (value: Density) => void;
  onReset: () => void;
  counts: { all: number; high: number; medium: number; low: number };
};

function DensityFilterBar({ value, onChange, onReset, counts }: DensityFilterBarProps) {
  const options: Array<{ label: string; value: Density; color: string; emoji: string; count: number }> = [
    { label: "Todas", value: "ALL", color: "#0f172a", emoji: "⚪", count: counts.all },
    { label: "Alta", value: "HIGH", color: "#ef4444", emoji: "🔴", count: counts.high },
    { label: "Media", value: "MEDIUM", color: "#f59e0b", emoji: "🟡", count: counts.medium },
    { label: "Baja", value: "LOW", color: "#22c55e", emoji: "🟢", count: counts.low },
  ];
  return (
    <div className="density-filter">
      {options.map((opt) => {
        const active = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            className={`density-filter__btn${active ? " density-filter__btn--active" : ""}`}
            onClick={() => (opt.value === "ALL" ? onReset() : onChange(opt.value))}
            style={{ borderColor: active ? opt.color : "transparent" }}
          >
            <span className="density-filter__emoji">{opt.emoji}</span>
            {opt.label} ({opt.count})
          </button>
        );
      })}
    </div>
  );
}
