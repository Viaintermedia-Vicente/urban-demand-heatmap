import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useMemo, useRef, useState } from "react";
import { Circle, MapContainer, Popup, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { fetchHeatmap } from "./api/heatmap";
import { fetchEvents } from "./api/events";
import "./App.css";
const REGIONS = [
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
    const [mode, setMode] = useState("heuristic");
    const [refreshToken, setRefreshToken] = useState(0);
    const [hotspots, setHotspots] = useState([]);
    const [events, setEvents] = useState([]);
    const [targetLabel, setTargetLabel] = useState("");
    const [weatherLabel, setWeatherLabel] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const mapRef = useRef(null);
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
                    setTargetLabel(new Date(heatmap.target).toLocaleString());
                    const w = heatmap.weather;
                    if (w) {
                        const parts = [
                            w.temperature_c != null ? `${w.temperature_c.toFixed(1)}ºC` : undefined,
                            w.precipitation_mm != null ? `${w.precipitation_mm.toFixed(1)} mm` : undefined,
                            w.wind_speed_kmh != null ? `${w.wind_speed_kmh.toFixed(0)} km/h` : undefined,
                        ].filter(Boolean);
                        setWeatherLabel(parts.join(" · "));
                    }
                    else {
                        setWeatherLabel("");
                    }
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
    useEffect(() => {
        const map = mapRef.current;
        if (map) {
            map.flyTo(selectedRegion.center, Math.max(map.getZoom(), 11), { duration: 0.8 });
        }
    }, [selectedRegion]);
    const handleSelectHotspot = (spot) => {
        const map = mapRef.current;
        if (map) {
            map.flyTo([spot.lat, spot.lon], Math.max(map.getZoom(), 14), { duration: 0.75 });
        }
    };
    return (_jsxs("div", { className: "app", children: [_jsxs("div", { className: "app__intro", children: [_jsx("h1", { children: "Heatmap TFM" }), _jsx("p", { children: "Explora hotspots urbanos y eventos estimados." })] }), _jsxs("form", { className: "controls-row", onSubmit: (e) => {
                    e.preventDefault();
                    setRefreshToken((token) => token + 1);
                }, children: [_jsxs("label", { className: "field", children: [_jsx("span", { children: "Comunidad / Provincia" }), _jsx("select", { value: selectedRegionId, onChange: (e) => setSelectedRegionId(e.target.value), "aria-label": "Selecciona la comunidad o provincia", children: REGIONS.map((region) => (_jsx("option", { value: region.id, children: region.label }, region.id))) })] }), _jsxs("label", { className: "field", children: [_jsx("span", { children: "Fecha" }), _jsx("input", { type: "date", value: date, onChange: (e) => setDate(e.target.value) })] }), _jsxs("fieldset", { className: "field mode-field", children: [_jsxs("legend", { children: ["Modo", _jsx(Tooltip, { text: _jsxs(_Fragment, { children: [_jsx("strong", { children: "Heuristic:" }), " C\u00E1lculo por reglas (sin modelo entrenado).", _jsx("br", {}), _jsx("strong", { children: "ML:" }), " C\u00E1lculo usando el modelo entrenado (ajusta llegada y asistencia seg\u00FAn condiciones)."] }) })] }), _jsxs("div", { className: "mode-toggle", role: "radiogroup", "aria-label": "Modo de scoring", children: [_jsxs("label", { children: [_jsx("input", { type: "radio", name: "mode", value: "heuristic", checked: mode === "heuristic", onChange: () => setMode("heuristic") }), "Heuristic"] }), _jsxs("label", { children: [_jsx("input", { type: "radio", name: "mode", value: "ml", checked: mode === "ml", onChange: () => setMode("ml") }), "ML"] })] })] }), _jsx("button", { type: "submit", className: "reload-btn", children: "Recargar" })] }), _jsxs("main", { className: "layout", children: [_jsxs("section", { className: "map-column", children: [_jsxs("div", { className: "map-meta", children: [_jsxs("span", { children: [targetLabel ? `Target: ${targetLabel}` : "Sin datos", mode === "ml" ? " · modo ML" : ""] }), weatherLabel && _jsx("span", { children: weatherLabel })] }), _jsxs(MapContainer, { center: selectedRegion.center, zoom: 12, className: "map", ref: mapRef, children: [_jsx(TileLayer, { url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", attribution: "\u00A9 OpenStreetMap" }), hotspots.map((spot, index) => {
                                        const color = getScoreColor(spot.score);
                                        return (_jsx(Circle, { center: [spot.lat, spot.lon], radius: spot.radius_m, pathOptions: { color, fillColor: color, fillOpacity: 0.35 }, eventHandlers: { click: () => handleSelectHotspot(spot) }, children: _jsx(Popup, { children: _jsxs("div", { className: "popup", children: [_jsx("strong", { children: "Score:" }), " ", spot.score.toFixed(3), _jsx("br", {}), _jsx("strong", { children: "Radio:" }), " ", spot.radius_m.toFixed(0), " m", spot.lead_time_min_pred != null && (_jsxs(_Fragment, { children: [_jsx("br", {}), _jsx("strong", { children: "Lead time:" }), " ", spot.lead_time_min_pred.toFixed(1), " min"] })), spot.attendance_factor_pred != null && (_jsxs(_Fragment, { children: [_jsx("br", {}), _jsx("strong", { children: "Factor asistencia:" }), " ", spot.attendance_factor_pred.toFixed(2)] }))] }) }) }, `${spot.lat}-${spot.lon}-${index}`));
                                    })] }), _jsxs("div", { className: "hour-slider", "aria-live": "polite", children: [_jsxs("label", { htmlFor: "hourRange", children: ["Hora: ", hour.toString().padStart(2, "0"), ":00"] }), _jsx("input", { id: "hourRange", type: "range", min: 0, max: 23, value: hour, onChange: (e) => setHour(Number(e.target.value)) })] })] }), _jsxs("section", { className: "sidebar", children: [loading && _jsx("div", { className: "notice", children: "Cargando datos\u2026" }), error && _jsx("div", { className: "notice notice--error", children: error }), _jsxs("div", { className: "panel", children: [_jsxs("h2", { children: ["Hotspots (", hotspots.length, ")"] }), hotspots.length === 0 && _jsx("p", { className: "muted", children: "Sin hotspots para esta hora." }), _jsx("ul", { className: "list", children: hotspots.map((spot, index) => (_jsx("li", { children: _jsxs("button", { className: "card", onClick: () => handleSelectHotspot(spot), children: [_jsxs("div", { children: [_jsx("strong", { children: "Score:" }), " ", spot.score.toFixed(3)] }), _jsxs("div", { children: [_jsx("strong", { children: "Radio:" }), " ", spot.radius_m.toFixed(0), " m"] }), mode === "ml" && (_jsxs("div", { className: "card__metrics", children: ["LT: ", spot.lead_time_min_pred?.toFixed(1) ?? "-", " min \u00B7 AF: ", spot.attendance_factor_pred?.toFixed(2) ?? "-"] }))] }) }, `spot-${index}`))) })] }), _jsxs("div", { className: "panel", children: [_jsxs("h2", { children: ["Eventos (", events.length, ")"] }), events.length === 0 && _jsx("p", { className: "muted", children: "Sin eventos disponibles." }), _jsx("ul", { className: "list", children: events.map((event, index) => (_jsxs("li", { className: "card card--flat", children: [_jsx("div", { className: "event-title", children: event.title }), _jsxs("div", { className: "event-meta", children: [new Date(event.start_dt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), event.venue_name ? ` · ${event.venue_name}` : ""] }), _jsxs("div", { className: "event-meta", children: [event.category, event.expected_attendance ? ` · Est.: ${event.expected_attendance}` : ""] })] }, `event-${index}`))) })] })] })] })] }));
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
