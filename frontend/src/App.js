import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import { Circle, MapContainer, Marker, Popup, TileLayer, useMapEvents } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { fetchHeatmap } from "./api/heatmap";
import { fetchEvents } from "./api/events";
import { fetchHotspotEvents } from "./api/hotspotEvents";
import "./App.css";
const REGIONS = [
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
    const [mode, setMode] = useState("heuristic");
    const [refreshToken, setRefreshToken] = useState(0);
    const [hotspots, setHotspots] = useState([]);
    const [selectedHotspot, setSelectedHotspot] = useState(null);
    const [selectedHotspotKey, setSelectedHotspotKey] = useState(null);
    const isSpotSelected = (spot) => selectedHotspotKey === makeHotspotKey(spot);
    const [hotspotEvents, setHotspotEvents] = useState([]);
    const [selectedPoint, setSelectedPoint] = useState(null);
    const [hotspotEventsLoading, setHotspotEventsLoading] = useState(false);
    const [hotspotEventsError, setHotspotEventsError] = useState(null);
    const [events, setEvents] = useState([]);
    const [targetDisplay, setTargetDisplay] = useState("Sin datos");
    const [weatherSummary, setWeatherSummary] = useState("");
    const [displayHour, setDisplayHour] = useState(hour);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const intensityScore = useMemo(() => {
        if (!hotspots.length)
            return null;
        return Math.max(...hotspots.map((spot) => spot.score));
    }, [hotspots]);
    const intensityLabel = intensityScore != null ? labelScore(intensityScore) : "Sin datos";
    const mapRef = useRef(null);
    const pointIcon = useMemo(() => L.divIcon({ className: "map-point-marker", iconSize: [12, 12], iconAnchor: [6, 6] }), []);
    const madridFormatter = useMemo(() => new Intl.DateTimeFormat("es-ES", {
        weekday: "long",
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "numeric",
        hour12: false,
        timeZone: "Europe/Madrid",
    }), []);
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
                    }
                    else {
                        setTargetDisplay("Sin datos");
                        setDisplayHour(hour);
                    }
                    const w = heatmap.weather;
                    setWeatherSummary(buildWeatherSummary(w, targetInfo?.hour ?? hour));
                    setEvents(eventsData);
                }
            }
            catch (err) {
                if (!controller.signal.aborted) {
                    const message = err instanceof Error ? err.message : "Error desconocido";
                    setError(message);
                }
            }
            finally {
                if (!controller.signal.aborted) {
                    setLoading(false);
                }
            }
        }
        load();
        return () => controller.abort();
    }, [date, hour, mode, refreshToken, selectedRegion]);
    const loadHotspotEvents = useCallback(async (lat, lon) => {
        setHotspotEventsLoading(true);
        setHotspotEventsError(null);
        try {
            const data = await fetchHotspotEvents({ lat, lon, date, hour, radius_m: radius, limit: 20 });
            setHotspotEvents(data);
        }
        catch (err) {
            setHotspotEventsError(err instanceof Error ? err.message : "Error desconocido");
            setHotspotEvents([]);
        }
        finally {
            setHotspotEventsLoading(false);
        }
    }, [date, hour, radius]);
    useEffect(() => {
        if (selectedHotspot) {
            loadHotspotEvents(selectedHotspot.lat, selectedHotspot.lon);
        }
        else if (!selectedPoint) {
            setHotspotEvents([]);
            setHotspotEventsError(null);
        }
    }, [selectedHotspot, selectedPoint, loadHotspotEvents]);
    useEffect(() => {
        if (selectedPoint) {
            loadHotspotEvents(selectedPoint.lat, selectedPoint.lon);
        }
    }, [selectedPoint, loadHotspotEvents]);
    useEffect(() => {
        const map = mapRef.current;
        if (map) {
            map.flyTo(selectedRegion.center, Math.max(map.getZoom(), 11), { duration: 0.8 });
        }
    }, [selectedRegion]);
    const handleSelectHotspot = useCallback((spot) => {
        const key = makeHotspotKey(spot);
        if (selectedHotspotKey === key) {
            setSelectedHotspot(null);
            setSelectedHotspotKey(null);
            setSelectedPoint(null);
            setHotspotEvents([]);
            return;
        }
        setSelectedHotspot(spot);
        setSelectedHotspotKey(key);
        setSelectedPoint(null);
        loadHotspotEvents(spot.lat, spot.lon);
        const map = mapRef.current;
        if (map) {
            map.flyTo([spot.lat, spot.lon], Math.max(map.getZoom(), 14), { duration: 0.75 });
        }
    }, [selectedHotspotKey, loadHotspotEvents]);
    const handleStripHotspot = useCallback((spot) => {
        handleSelectHotspot(spot);
    }, [handleSelectHotspot]);
    const clearHotspotSelection = useCallback(() => {
        setSelectedHotspot(null);
        setSelectedHotspotKey(null);
        setSelectedPoint(null);
        setHotspotEvents([]);
    }, []);
    const handleMapClick = useCallback((lat, lon) => {
        setSelectedHotspot(null);
        setSelectedHotspotKey(null);
        setSelectedPoint({ lat, lon });
        loadHotspotEvents(lat, lon);
        const map = mapRef.current;
        if (map) {
            map.flyTo([lat, lon], Math.max(map.getZoom(), 13), { duration: 0.6 });
        }
    }, [loadHotspotEvents]);
    const handleNearbyEventClick = useCallback((event) => {
        const map = mapRef.current;
        if (!map)
            return;
        map.flyTo([event.lat, event.lon], Math.max(map.getZoom(), 15), { duration: 0.8 });
        const content = [
            `<strong>${event.title}</strong>`,
            event.start_dt ? new Date(event.start_dt).toLocaleString("es-ES", { hour: "2-digit", minute: "2-digit" }) : "Hora N/D",
            event.venue_name || "Sin venue",
            `${Math.round(event.distance_m)} m`,
            event.url ? `<a href="${event.url}" target="_blank" rel="noopener noreferrer">Ver más</a>` : null,
        ]
            .filter(Boolean)
            .join("<br />");
        L.popup().setLatLng([event.lat, event.lon]).setContent(content).openOn(map);
    }, []);
    return (_jsxs("div", { className: "app", children: [_jsxs("div", { className: "app__intro", children: [_jsx("h1", { children: "Heatmap TFM" }), _jsx("p", { children: "Explora hotspots urbanos y eventos estimados \u00B7 vista TS." })] }), _jsxs("form", { className: "controls-row", onSubmit: (e) => {
                    e.preventDefault();
                    setRefreshToken((token) => token + 1);
                }, children: [_jsxs("label", { className: "field", children: [_jsx("span", { children: "Comunidad / Provincia" }), _jsx("select", { value: selectedRegionId, onChange: (e) => setSelectedRegionId(e.target.value), "aria-label": "Selecciona la comunidad o provincia", children: REGIONS.map((region) => (_jsx("option", { value: region.id, children: region.label }, region.id))) })] }), _jsxs("label", { className: "field", children: [_jsx("span", { children: "Fecha" }), _jsx("input", { type: "date", value: date, onChange: (e) => setDate(e.target.value) })] }), _jsxs("fieldset", { className: "field mode-field", children: [_jsxs("legend", { children: ["Modo", _jsx(Tooltip, { text: _jsxs(_Fragment, { children: [_jsx("strong", { children: "Heuristic:" }), " C\u00E1lculo por reglas (sin modelo entrenado).", _jsx("br", {}), _jsx("strong", { children: "ML:" }), " C\u00E1lculo usando el modelo entrenado (ajusta llegada y asistencia seg\u00FAn condiciones)."] }) })] }), _jsxs("div", { className: "mode-toggle", role: "radiogroup", "aria-label": "Modo de scoring", children: [_jsxs("label", { children: [_jsx("input", { type: "radio", name: "mode", value: "heuristic", checked: mode === "heuristic", onChange: () => setMode("heuristic") }), "Heuristic"] }), _jsxs("label", { children: [_jsx("input", { type: "radio", name: "mode", value: "ml", checked: mode === "ml", onChange: () => setMode("ml") }), "ML"] })] })] }), _jsx("button", { type: "submit", className: "reload-btn", children: "Recargar" })] }), _jsxs("main", { className: "layout", children: [_jsxs("section", { className: "map-column", children: [_jsxs("div", { className: "map-meta", children: [_jsxs("span", { className: "map-meta__target", children: [targetDisplay, mode === "ml" && _jsx("span", { className: "map-meta__badge", children: "Modo ML" })] }), weatherSummary && _jsx("span", { className: "map-meta__weather", children: weatherSummary })] }), _jsxs(MapContainer, { center: selectedRegion.center, zoom: 12, className: "map", ref: mapRef, children: [_jsx(TileLayer, { url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", attribution: "\u00A9 OpenStreetMap" }), _jsx(MapClickCapture, { onMapClick: handleMapClick }), hotspots.map((spot, index) => {
                                        const color = getScoreColor(spot.score);
                                        const isSelected = isSpotSelected(spot);
                                        const options = {
                                            color: isSelected ? "#2e7d32" : color,
                                            fillColor: color,
                                            fillOpacity: isSelected ? 0.5 : 0.35,
                                            weight: isSelected ? 4 : 2,
                                        };
                                        return (_jsx(Circle, { center: [spot.lat, spot.lon], radius: spot.radius_m, pathOptions: options, eventHandlers: {
                                                click: (leafletEvent) => {
                                                    leafletEvent.originalEvent?.stopPropagation?.();
                                                    handleSelectHotspot(spot);
                                                },
                                            }, children: _jsx(Popup, { children: _jsxs("div", { className: "popup", children: [_jsx("strong", { children: "Score:" }), " ", spot.score.toFixed(3), _jsx("br", {}), _jsx("strong", { children: "Radio:" }), " ", spot.radius_m.toFixed(0), " m", spot.lead_time_min_pred != null && (_jsxs(_Fragment, { children: [_jsx("br", {}), _jsx("strong", { children: "Lead time:" }), " ", spot.lead_time_min_pred.toFixed(1), " min"] })), spot.attendance_factor_pred != null && (_jsxs(_Fragment, { children: [_jsx("br", {}), _jsx("strong", { children: "Factor asistencia:" }), " ", spot.attendance_factor_pred.toFixed(2)] }))] }) }) }, `${spot.lat}-${spot.lon}-${index}`));
                                    }), selectedPoint && (_jsx(Marker, { position: [selectedPoint.lat, selectedPoint.lon], icon: pointIcon, children: _jsx(Popup, { children: _jsx("div", { className: "popup", children: "Punto seleccionado" }) }) }))] }), _jsxs("div", { className: "hour-row", "aria-live": "polite", children: [_jsxs("div", { className: "hour-slider", children: [_jsxs("label", { htmlFor: "hourRange", children: ["Hora: ", displayHour.toString().padStart(2, "0"), "h"] }), _jsx("input", { id: "hourRange", type: "range", min: 0, max: 23, value: hour, onChange: (e) => {
                                                    const value = Number(e.target.value);
                                                    setHour(value);
                                                    setDisplayHour(value);
                                                } })] }), _jsxs("div", { className: "hour-score", title: "\u00CDndice relativo (no es n\u00BA de asistentes)", children: [_jsx("span", { className: "hour-score__label", children: intensityLabel }), _jsx("small", { className: "hour-score__value", children: intensityScore != null ? intensityScore.toFixed(2) : "--" })] })] })] }), _jsxs("section", { className: "sidebar", children: [loading && _jsx("div", { className: "notice", children: "Cargando datos\u2026" }), error && _jsx("div", { className: "notice notice--error", children: error }), _jsxs("div", { className: "side-panel", children: [_jsxs("div", { className: "side-panel__header panel__header", children: [_jsxs("h2", { children: [selectedHotspot || selectedPoint ? "Eventos cercanos" : "Eventos", " (", selectedHotspot || selectedPoint ? hotspotEvents.length : events.length, ")"] }), (selectedHotspot || selectedPoint) && (_jsx("button", { type: "button", className: "link-btn", onClick: clearHotspotSelection, children: "Limpiar selecci\u00F3n" }))] }), _jsxs("div", { className: "side-panel__body", children: [!selectedHotspot && !selectedPoint && _jsx("p", { className: "muted", children: "Haz click en un hotspot o en el mapa para ver eventos cercanos." }), hotspotEventsLoading && _jsx("p", { className: "muted", children: "Buscando eventos\u2026" }), hotspotEventsError && _jsx("p", { className: "notice notice--error", children: hotspotEventsError }), (selectedHotspot || selectedPoint) && !hotspotEventsLoading && hotspotEvents.length === 0 && !hotspotEventsError && (_jsx("p", { className: "muted", children: "No hay eventos dentro de este radio." })), _jsx("ul", { className: "list", children: (selectedHotspot || selectedPoint ? hotspotEvents : events).map((event, index) => (_jsx("li", { children: _jsxs("button", { type: "button", className: "card card--flat", onClick: () => handleNearbyEventClick(event), children: [_jsx("div", { className: "event-title", children: event.title }), _jsxs("div", { className: "event-meta", children: [event.start_dt ? new Date(event.start_dt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "Hora N/D", event.venue_name ? ` · ${event.venue_name}` : ""] }), _jsxs("div", { className: "event-meta", children: [(event.distance_m ?? 0).toFixed(0), " m \u00B7 ", normalizeSourceLabel(event.source)] }), event.url && (_jsx("div", { className: "event-meta", children: _jsx("a", { href: event.url, target: "_blank", rel: "noopener noreferrer", children: "Ver evento" }) }))] }) }, `hotspot-event-${index}`))) }), _jsxs("div", { className: "hotspot-strip-row", children: [_jsxs("div", { className: "hotspot-strip", role: "list", children: [_jsxs("button", { type: "button", className: `hotspot-pill${!selectedHotspotKey && !selectedPoint ? " hotspot-pill--active" : ""}`, onClick: clearHotspotSelection, children: [_jsx("span", { className: "hotspot-pill__dot" }), _jsx("span", { className: "hotspot-pill__text", children: "Todos" })] }), hotspots.length === 0 && _jsx("span", { className: "muted", children: "Sin hotspots para esta hora." }), hotspots.map((spot, index) => (_jsx(HotspotPill, { spot: spot, active: selectedHotspotKey === makeHotspotKey(spot), onSelect: () => handleStripHotspot(spot) }, `spot-${index}`)))] }), _jsx(RadiusSelector, { value: radius, onChange: setRadius })] })] })] })] })] })] }));
}
function normalizeSourceLabel(source) {
    if (!source)
        return "Fuente N/D";
    return source.toLowerCase() === "unknown" ? "Fuente N/D" : source;
}
function HotspotPill({ spot, active, onSelect }) {
    const label = labelScore(spot.score);
    const color = getScoreColor(spot.score);
    return (_jsxs("button", { type: "button", className: `hotspot-pill${active ? " hotspot-pill--active" : ""}`, onClick: onSelect, children: [_jsx("span", { className: "hotspot-pill__dot", style: { backgroundColor: color } }), _jsxs("span", { className: "hotspot-pill__text", children: [label, " ", spot.score.toFixed(2)] })] }));
}
function RadiusSelector({ value, onChange }) {
    const options = [
        { label: "200 m", value: 200, color: "#4caf50" },
        { label: "300 m", value: 300, color: "#1976d2" },
        { label: "500 m", value: 500, color: "#f57c00" },
    ];
    return (_jsx("div", { className: "radius-selector", children: options.map((option) => {
            const active = option.value === value;
            return (_jsxs("button", { type: "button", className: `radius-selector__btn${active ? " radius-selector__btn--active" : ""}`, onClick: () => onChange(option.value), style: { borderColor: active ? option.color : "transparent" }, children: [_jsx("span", { className: "radius-selector__dot", style: { backgroundColor: option.color } }), option.label] }, option.value));
        }) }));
}
function labelScore(score) {
    if (score < 0.8)
        return "Baja";
    if (score < 1.4)
        return "Media";
    return "Alta";
}
function getScoreColor(score) {
    if (score > 1.5)
        return "#d32f2f";
    if (score > 1.0)
        return "#f57c00";
    if (score > 0.5)
        return "#fbc02d";
    return "#1976d2";
}
function Tooltip({ text }) {
    const tooltipId = "mode-info-tooltip";
    return (_jsxs("span", { className: "tooltip", children: [_jsx("button", { type: "button", className: "tooltip__trigger", "aria-describedby": tooltipId, "aria-label": "Informaci\u00F3n sobre los modos", children: "?" }), _jsx("span", { className: "tooltip__content", role: "tooltip", id: tooltipId, children: text })] }));
}
export default App;
function MapClickCapture({ onMapClick }) {
    useMapEvents({
        click(event) {
            onMapClick(event.latlng.lat, event.latlng.lng);
        },
    });
    return null;
}
function formatTargetMetadata(targetIso, formatter) {
    if (!targetIso)
        return null;
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
function capitalize(value) {
    if (!value)
        return value;
    return value.charAt(0).toUpperCase() + value.slice(1);
}
function makeHotspotKey(spot) {
    return `${spot.lat.toFixed(5)}:${spot.lon.toFixed(5)}`;
}
function buildWeatherSummary(weather, localHour) {
    if (!weather)
        return "";
    const icon = getWeatherIcon(weather, localHour);
    const temp = weather.temperature_c != null ? `${weather.temperature_c.toFixed(1)}ºC` : "N/D";
    const rainAmount = weather.precipitation_mm != null ? weather.precipitation_mm.toFixed(1) : "0.0";
    const wind = weather.wind_speed_kmh != null ? `${weather.wind_speed_kmh.toFixed(0)} km/h` : "N/D";
    return `${icon} ${temp}   🌧 ${rainAmount} mm   💨 ${wind}`;
}
function getWeatherIcon(weather, localHour) {
    if (weather?.precipitation_mm != null && weather.precipitation_mm > 0) {
        return "🌧";
    }
    if (localHour >= 7 && localHour <= 19) {
        return "☀";
    }
    return "🌙";
}
