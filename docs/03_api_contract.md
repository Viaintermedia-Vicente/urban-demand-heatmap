# 03 - API Contract

## 1. Introducción
La API REST JSON de `tfm-hotspots` está diseñada para que el frontend web consuma datos de heatmaps y eventos de forma consistente. Todos los endpoints devuelven JSON, usan HTTPS en entornos productivos y añaden un `request_id` para trazabilidad.

## 2. GET /api/heatmap
**Descripción**: devuelve los hotspots calculados para una ciudad, fecha y hora específicas.

**Parámetros**
- `city` (string, requerido)
- `date` (formato YYYY-MM-DD, requerido)
- `hour` (entero 0-23, requerido)
- `categories` (string, lista separada por comas, opcional)
- `bbox` (string `minLon,minLat,maxLon,maxLat`, opcional)

**Ejemplo de request**
```
GET /api/heatmap?city=madrid&date=2026-02-12&hour=18&categories=concierto,teatro
```

**Ejemplo de response**
```json
{
  "meta": {"request_id": "abc-123"},
  "data": [
    {"lat": 40.4203, "lon": -3.7044, "score": 0.87, "radius_m": 220},
    {"lat": 40.4404, "lon": -3.6883, "score": 0.72, "radius_m": 180}
  ]
}
```
Los puntos se devuelven ordenados por `score` descendente; si se incluye `bbox`, se filtran los resultados dentro de ese rectángulo.

## 3. GET /api/events
**Descripción**: lista los eventos a partir de una hora determinada, filtrados por ciudad y fecha.

**Parámetros**
- `city` (string, requerido)
- `date` (YYYY-MM-DD, requerido)
- `from_hour` (0-23, requerido)
- `categories` (lista separada por comas, opcional)
- `bbox` (opcional)
- `limit` (opcional, por defecto 50, máximo 200)

**Ejemplo de request**
```
GET /api/events?city=madrid&date=2026-02-12&from_hour=17&categories=teatro
```

**Ejemplo de response**
```json
{
  "meta": {"request_id": "abc-124", "paging": {"limit": 50, "has_more": false}},
  "data": [
    {"event_id": "TEA-1987", "title": "Obra La Vida Moderna", "category": "teatro", "start_dt": "2026-02-12T20:30:00Z", "end_dt": "2026-02-12T23:00:00Z", "lat": 40.4208, "lon": -3.7054, "venue": "Teatro Lope de Vega"}
  ]
}
```
Los eventos siempre se devuelven en orden cronológico ascendente a partir de `from_hour`.

## 4. POST /api/admin/import-events
**Descripción**: endpoint administrativo para lanzar imports manuales (testing, reproducibilidad).

**Body mínimo**
```json
{
  "source": "madrid_cultura",
  "date_range": {"from": "2026-02-10", "to": "2026-02-12"}
}
```

**Response**
```json
{
  "meta": {"request_id": "adm-001"},
  "data": {"source": "madrid_cultura", "inserted": 120, "updated": 45, "run_id": "c0f7..."}
}
```

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
