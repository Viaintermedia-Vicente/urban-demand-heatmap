# 03 - API Contract

## 1. Introducción
La API REST JSON de `tfm-hotspots` está diseñada para que el frontend web consuma datos de heatmaps y eventos de forma consistente. Todos los endpoints devuelven JSON, usan HTTPS en entornos productivos y añaden un `request_id` para trazabilidad.

## 2. GET /api/heatmap
**Descripción**: devuelve hotspots predictivos (modo heuristic o ml) para una fecha/hora y posición de referencia.

**Parámetros**
- `date` (YYYY-MM-DD, requerido)
- `hour` (0-23, requerido)
- `lat` (opcional, por defecto 40.4168)
- `lon` (opcional, por defecto -3.7038)
- `mode` (`heuristic` | `ml`, por defecto `heuristic`)

**Ejemplo de response**
```json
{
  "mode": "heuristic",
  "target": "2026-02-22T22:00:00Z",
  "weather": {...},
  "hotspots": [
    {"lat": 40.4203, "lon": -3.7044, "score": 0.87, "radius_m": 220}
  ],
  "events": [
    {
      "id": 123,
      "title": "Concierto en Retiro",
      "category": "music",
      "start_dt": "2026-02-22T20:30:00Z",
      "lat": 40.4208,
      "lon": -3.7054,
      "url": "https://...",
      "score": 0.42
    }
  ]
}
```
Nota: si no hay eventos en base de datos para esa franja, `events` puede venir vacío o incluir entradas sintéticas derivadas de los hotspots para que el frontend no quede sin datos.

## 3. GET /api/events
**Descripción**: lista eventos activos a partir de `from_hour` para la fecha dada.

**Parámetros**
- `date` (YYYY-MM-DD, requerido)
- `from_hour` (0-23, requerido)

**Ejemplo de response**
```json
[
  {
    "id": 123,
    "title": "Concierto en Retiro",
    "category": "music",
    "subcategory": null,
    "start_dt": "2026-02-22T20:30:00Z",
    "end_dt": "2026-02-22T23:00:00Z",
    "venue_name": "Auditorio Retiro",
    "lat": 40.4208,
    "lon": -3.7054,
    "url": "https://...",
    "expected_attendance": 1200,
    "source": "ticketmaster"
  }
]
```
Categoría puede venir `null` o `"unknown"` si la fuente no aporta dato; `lat/lon` usan coordenadas del evento o, en su defecto, las del venue (pueden ser `null` si tampoco existen).

## 4. GET /api/hotspot_events
**Descripción**: eventos cercanos a un punto/fecha/hora dentro de un radio dado.

Parámetros: `date`, `hour`, `lat`, `lon`, `radius_m` (default 300), `limit` (default 20).

## 5. Gestión de errores
- `400 Bad Request`: parámetros inválidos o formatos incorrectos.
  ```json
  {"error": {"code": "BAD_REQUEST", "message": "hour must be between 0 and 23"}}
  ```
- `404 Not Found`: ciudad no soportada o recurso inexistente.
- `500 Internal Server Error`: fallo inesperado en backend o base de datos; se registra `request_id` para diagnóstico.
Mensajes claros ayudan al usuario y al equipo técnico a entender la causa.

## 6. Notas de diseño
- Los endpoints están pensados para ampliaciones futuras (nuevas métricas, filtros adicionales) sin romper compatibilidad.
- La API REST sirve tanto al frontend React como a integraciones externas, por ejemplo un conector hacia Odoo que pueda consumir `events` para planificar recursos.
