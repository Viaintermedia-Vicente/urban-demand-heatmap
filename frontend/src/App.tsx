import { useEffect, useMemo, useRef, useState } from "react";
import type { Map as LeafletMap } from "leaflet";
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

function App() {
  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const [selectedRegionId, setSelectedRegionId] = useState(REGIONS[0].id);
  const selectedRegion = REGIONS.find((region) => region.id === selectedRegionId) ?? REGIONS[0];
  const [date, setDate] = useState(today);
  const [hour, setHour] = useState(22);
  const [mode, setMode] = useState<HeatmapMode>("heuristic");
  const [refreshToken, setRefreshToken] = useState(0);

  const [hotspots, setHotspots] = useState<HeatmapHotspot[]>([]);
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [targetDisplay, setTargetDisplay] = useState<string>("Sin datos");
  const [weatherSummary, setWeatherSummary] = useState<string>("");
  const [displayHour, setDisplayHour] = useState(hour);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
          setEvents(eventsData);
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

  const handleSelectHotspot = (spot: HeatmapHotspot) => {
    const map = mapRef.current;
    if (map) {
      map.flyTo([spot.lat, spot.lon], Math.max(map.getZoom(), 14), { duration: 0.75 });
    }
  };

  return (
    <div className="app">
      <div className="app__intro">
        <h1>Heatmap TFM</h1>
        <p>Explora hotspots urbanos y eventos estimados.</p>
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
          <MapContainer
            center={selectedRegion.center}
            zoom={12}
            className="map"
            ref={mapRef}
          >
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap" />
            {hotspots.map((spot, index) => {
              const color = getScoreColor(spot.score);
              return (
                <Circle
                  key={`${spot.lat}-${spot.lon}-${index}`}
                  center={[spot.lat, spot.lon]}
                  radius={spot.radius_m}
                  pathOptions={{ color, fillColor: color, fillOpacity: 0.35 }}
                  eventHandlers={{ click: () => handleSelectHotspot(spot) }}
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
          <div className="hour-slider" aria-live="polite">
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
        </section>

        <section className="sidebar">
          {loading && <div className="notice">Cargando datos…</div>}
          {error && <div className="notice notice--error">{error}</div>}

          <div className="panel">
            <h2>Hotspots ({hotspots.length})</h2>
            {hotspots.length === 0 && <p className="muted">Sin hotspots para esta hora.</p>}
            <ul className="list">
              {hotspots.map((spot, index) => (
                <li key={`spot-${index}`}>
                  <button className="card" onClick={() => handleSelectHotspot(spot)}>
                    <div>
                      <strong>Score:</strong> {spot.score.toFixed(3)}
                    </div>
                    <div>
                      <strong>Radio:</strong> {spot.radius_m.toFixed(0)} m
                    </div>
                    {mode === "ml" && (
                      <div className="card__metrics">
                        LT: {spot.lead_time_min_pred?.toFixed(1) ?? "-"} min · AF: {spot.attendance_factor_pred?.toFixed(2) ?? "-"}
                      </div>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="panel">
            <h2>Eventos ({events.length})</h2>
            {events.length === 0 && <p className="muted">Sin eventos disponibles.</p>}
            <ul className="list">
              {events.map((event, index) => (
                <li key={`event-${index}`} className="card card--flat">
                  <div className="event-title">{event.title}</div>
                  <div className="event-meta">
                    {new Date(event.start_dt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    {event.venue_name ? ` · ${event.venue_name}` : ""}
                  </div>
                  <div className="event-meta">
                    {event.category}
                    {event.expected_attendance ? ` · Est.: ${event.expected_attendance}` : ""}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </main>
    </div>
  );
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
