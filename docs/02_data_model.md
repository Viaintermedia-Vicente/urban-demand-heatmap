# 02 - Data Model

## 1. Introducción
El sistema necesita un modelo de datos normalizado y extensible para combinar múltiples fuentes de eventos urbanos sin inconsistencias. PostgreSQL, complementado con JSONB y capacidades geoespaciales, permite preservar el detalle original de cada fuente a la vez que expone un esquema común explotable por la capa de dominio.

## 2. Tabla principal: `events`
| Campo           | Tipo           | Descripción |
|-----------------|----------------|-------------|
| `id`            | bigserial PK   | Identificador interno. |
| `source`        | text           | Nombre de la fuente (ej. `madrid_cultura`). |
| `external_id`   | text           | ID original del evento. |
| `title`         | text           | Título legible. |
| `category`      | text           | Categoría normalizada (concierto, teatro, cine, etc.). |
| `start_datetime`| timestamptz    | Inicio normalizado a UTC. |
| `end_datetime`  | timestamptz    | Fin real o estimado. |
| `latitude`      | numeric(9,6)   | Latitud WGS84. |
| `longitude`     | numeric(9,6)   | Longitud WGS84. |
| `venue_name`    | text           | Lugar o recinto. |
| `raw_json`      | jsonb          | Payload original para trazabilidad. |
| `updated_at`    | timestamptz    | Última actualización. |

Constraint: `UNIQUE (source, external_id)` garantiza idempotencia en las importaciones.

## 3. Reglas de normalización
- Cada API externa se mapea a `events` mediante un adaptador que homogeniza nombres de campos, formatos de fecha y coordenadas.
- Las categorías se normalizan usando un catálogo interno (`concert`, `theater`, `sports`, `cinema`, etc.) que evita proliferación de taxonomías propias de cada fuente.
- Los atributos adicionales se conservan en `raw_json` para permitir mejoras futuras sin alterar el esquema principal.

## 4. Duración de eventos
Cuando una fuente no proporciona `end_datetime`, se estima aplicando una tabla de duraciones promedio por categoría:
| Categoría  | Duración estándar |
|------------|-------------------|
| concierto  | 2 horas |
| teatro     | 2.5 horas |
| cine       | 2 horas |
| feria      | 6 horas |
| manifestacion | 3 horas |
| deporte    | 3 horas |

El import job calcula `end_datetime = start_datetime + duración_estimada` y marca en `raw_json` que se trata de un valor inferido.

## 5. Tabla auxiliar opcional: `import_runs`
| Campo        | Tipo        | Descripción |
|--------------|-------------|-------------|
| `run_id`     | uuid PK     | Identificador del lote. |
| `source`     | text        | Fuente procesada. |
| `started_at` | timestamptz | Hora de inicio. |
| `finished_at`| timestamptz | Hora de fin. |
| `status`     | text        | `success`, `partial`, `failed`. |
| `inserted`   | integer     | Nuevos registros. |
| `updated`    | integer     | Registros actualizados. |
| `errors`     | jsonb       | Resumen de incidencias. |

Esta tabla permite auditar importaciones, identificar errores recurrentes y medir volumen de datos.

## 6. Ejemplos
| source         | external_id | title                              | category  | start_datetime        | end_datetime          | latitude | longitude | venue_name            |
|----------------|-------------|------------------------------------|-----------|-----------------------|-----------------------|----------|-----------|-----------------------|
| madrid_cultura | EVT-4521    | Concierto Sinfónico Auditorio      | concierto | 2026-02-10T19:00:00Z  | 2026-02-10T21:00:00Z  | 40.4404  | -3.6883   | Auditorio Nacional    |
| madrid_teatro  | TEA-1987    | Obra "La Vida Moderna"             | teatro    | 2026-02-12T20:30:00Z  | 2026-02-12T23:00:00Z  | 40.4208  | -3.7054   | Teatro Lope de Vega   |
| madrid_cine    | CINE-3110   | Estreno "Noches de Invierno"      | cine      | 2026-02-15T18:45:00Z  | 2026-02-15T20:45:00Z  | 40.4322  | -3.7010   | Cines Callao          |
