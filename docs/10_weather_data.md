# 10 - Weather Data Layer

## 1. Objetivo
Capturar observaciones meteorológicas históricas y previsiones horarias para enriquecer el modelo de hotspots y entrenar futuros modelos predictivos (demanda, asistencia, alertas). El almacenamiento local evita depender de la disponibilidad de terceros y permite comparar múltiples proveedores a largo plazo.

## 2. Fuente inicial: Open-Meteo
- Endpoint público gratuito (`https://api.open-meteo.com/v1/forecast`) con series horarias.
- Variables utilizadas:
  - `temperature_2m` → `temperature_c` (°C).
  - `precipitation`, `rain`, `snowfall` → milímetros por hora (la API ya devuelve mm; si un proveedor entregara cm, se convertiría multiplicando por 10).
  - `cloudcover` → `cloud_cover_pct` (0-100).
  - `windspeed_10m`, `windgusts_10m` → km/h (así se guardan).
  - `winddirection_10m` → `wind_dir_deg`.
  - `relativehumidity_2m` → `humidity_pct`.
  - `pressure_msl` → `pressure_hpa`.
  - `visibility` → metros (`visibility_m`).
  - `weathercode` → códigos numéricos ECMWF.
- Si un campo no existe o el proveedor no lo expone, se guarda `NULL`.

## 3. Tabla `weather_observations`
- Claves: `source`, `lat`, `lon`, `observed_at` para evitar duplicados.
- Se almacena `location_name` para trazabilidad (ej. "Madrid, ES").
- Observaciones en hora local convertidas a UTC antes de persistir (la API permite `timezone=UTC`).
- Campos numéricos en unidades SI: temperatura (°C), precipitaciones/nieve (mm), viento (km/h), presión (hPa), visibilidad (m).
- `snowfall_mm` representa milímetros de agua equivalente reportados por la fuente (Open-Meteo ya entrega mm).

## 4. Flujo de ingesta
1. El job `import_weather` solicita a Open-Meteo el rango horario deseado.
2. Se transforma cada hora en un diccionario acorde a `weather_observations`.
3. El repositorio persiste mediante upserts idempotentes (`source`, `lat`, `lon`, `observed_at`).
4. Los datos quedan disponibles para futuros endpoints/entrenamientos sin depender de nuevas llamadas a la API.
