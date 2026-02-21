import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Map as LeafletMap } from "leaflet";
import L from "leaflet";
import { Circle, MapContainer, Popup, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";

import { fetchHeatmap, type HeatmapHotspot, type HeatmapMode } from "./api/heatmap";
import { fetchEvents, type EventSummary } from "./api/events";
import "./App.css";

type RegionOption = {
  id: string;
  label: string;
  center: [number, number];
};

const REGIONS: RegionOption[] = [
  { id: "madrid", label: "Madrid", center: [40.4168, -3.7038] },
  { id: "barcelona", label: "Barcelona", center: [41.3874, 2.1686] },
  { id: "valencia", label: "Valencia", center: [39.4699, -0.3763] },
  { id: "sevilla", label: "Sevilla", center: [37.3891, -5.9845] },
  { id: "bilbao", label: "Bilbao", center: [43.263, -2.935] },
  { id: "malaga", label: "Málaga", center: [36.7213, -4.4214] },
];

const HOTSPOT_EVENT_RADIUS_M = 1500;

function App() {
  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const [selectedRegionId, setSelectedRegionId] = useState(REGIONS[0].id);
  const selectedRegion = REGIONS.find((region) => region.id === selectedRegionId) ?? REGIONS[0];
  const [date, setDate] = useState(today);
  const [hour, setHour] = useState(22);
  const [radius, setRadius] = useState(300);
  const [mode, setMode] = useState<HeatmapMode>("heuristic");
  const [refreshToken, setRefreshToken] = useState(0);

  const [hotspots, setHotspots] = useState<HeatmapHotspot[]>([]);
  const uniqueHotspots = useMemo(() => {
    const m = new Map<string, HeatmapHotspot>();
    for (const spot of hotspots) {
      const key = `${spot.lat.toFixed(5)}:${spot.lon.toFixed(5)}`;
      const prev = m.get(key);
      if (!prev || spot.score > prev.score) m.set(key, spot);
    }
    return Array.from(m.values()).sort((a, b) => b.score - a.score);
  }, [hotspots]);
  const densityCounts = useMemo(() => {
    let high = 0, medium = 0, low = 0;
    uniqueHotspots.forEach((spot) => {
      const level = classify(spot.score);
      if (level === "HIGH") high += 1;
      else if (level === "MEDIUM") medium += 1;
      else low += 1;
    });
    return { high, medium, low, all: uniqueHotspots.length };
  }, [uniqueHotspots]);

  const [densityFilter, setDensityFilter] = useState<Density>("ALL");
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [targetDisplay, setTargetDisplay] = useState<string>("Sin datos");
  const [weatherSummary, setWeatherSummary] = useState<string>("");
  const [displayHour, setDisplayHour] = useState(hour);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intensityScore = useMemo(() => {
    if (!hotspots.length) return null;
    return Math.max(...hotspots.map((spot) => spot.score));
  }, [hotspots]);
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
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [heatmap, eventsData] = await Promise.all([
          fetchHeatmap({
            date,
            hour,
            mode,
            lat: selectedRegion.center[0],
            lon: selectedRegion.center[1],
            signal: controller.signal,
          }),
          fetchEvents({ date, fromHour: hour, signal: controller.signal }).catch(() => []),
        ]);
        if (!controller.signal.aborted) {
          setHotspots(heatmap.hotspots ?? []);
          setEvents(eventsData);
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

    load();
    return () => controller.abort();
  }, [date, hour, mode, refreshToken, selectedRegion]);

  useEffect(() => {
    const map = mapRef.current;
    if (map) {
      map.flyTo(selectedRegion.center, Math.max(map.getZoom(), 11), { duration: 0.8 });
    }
  }, [selectedRegion]);

  const handleHotspotClick = useCallback((spot: HeatmapHotspot) => {
    const map = mapRef.current;
    if (!map) return;
    map.flyTo([spot.lat, spot.lon], Math.max(map.getZoom(), 14), { duration: 0.75 });
  }, []);

  const filteredHotspots = useMemo(() => {
    if (densityFilter === "ALL") return uniqueHotspots;
    return uniqueHotspots.filter((h) => classify(h.score) === densityFilter);
  }, [densityFilter, uniqueHotspots]);

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
            {REGIONS.map((region) => (
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
              center={selectedRegion.center}
              zoom={12}
              className="map"
              ref={mapRef}
            >
              <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap" />
              {filteredHotspots.map((spot, index) => {
                const level = classify(spot.score);
                const color = DENSITY_COLORS[level];
                const options = {
                  color: "#111827",
                  weight: level === "HIGH" ? 2 : 1,
                  fillColor: color,
                  fillOpacity: level === "HIGH" ? 0.55 : level === "MEDIUM" ? 0.45 : 0.35,
                  opacity: 0.9,
                };
                return (
                  <Circle
                    key={`${spot.lat}-${spot.lon}-${index}`}
                    center={[spot.lat, spot.lon]}
                    radius={spot.radius_m}
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
            <div className="side-panel__header panel__header">
              <h2>Eventos ({events.length})</h2>
            </div>
            <div className="side-panel__body">
              <ul className="list">
                {events.map((event, index) => {
                  return (
                    <li key={`event-${index}`}>
                    <button
                      type="button"
                      className="card card--flat"
                      disabled
                    >
                      <div className="event-title">{event.title}</div>
                      <div className="event-meta">
                        {event.start_dt ? new Date(event.start_dt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "Hora N/D"}
                        {event.venue_name ? ` · ${event.venue_name}` : ""}
                      </div>
                      <div className="event-meta">
                        {event.distance_m?.toFixed(0) ?? "--"} m · {normalizeSourceLabel(event.source)}
                      </div>
                      {event.url && (
                        <div className="event-meta">
                          <a href={event.url} target="_blank" rel="noopener noreferrer">Ver evento</a>
                        </div>
                      )}
                    </button>
                  </li>
                  );
                })}
              </ul>
            </div>
            <div className="side-panel__footer hotspot-strip-row">
              <DensityFilterBar value={densityFilter} onChange={setDensityFilter} counts={densityCounts} />
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

function normalizeSourceLabel(source: string | null | undefined) {
  if (!source) return "Fuente N/D";
  return source.toLowerCase() === "unknown" ? "Fuente N/D" : source;
}

type HotspotPillProps = {
  spot: HeatmapHotspot;
  active: boolean;
  onSelect: () => void;
};

function labelScore(score: number): "Baja" | "Media" | "Alta" {
  if (score < 0.8) return "Baja";
  if (score < 1.4) return "Media";
  return "Alta";
}

function getScoreColor(score: number) {
  if (score > 1.5) return "#d32f2f";
  if (score > 1.0) return "#f57c00";
  if (score > 0.5) return "#fbc02d";
  return "#1976d2";
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

function classify(score: number): DensityLevel {
  if (score >= 0.66) return "HIGH";
  if (score >= 0.33) return "MEDIUM";
  return "LOW";
}

type DensityFilterBarProps = {
  value: Density;
  onChange: (value: Density) => void;
  counts: { all: number; high: number; medium: number; low: number };
};

function DensityFilterBar({ value, onChange, counts }: DensityFilterBarProps) {
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
            onClick={() => onChange(opt.value)}
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
