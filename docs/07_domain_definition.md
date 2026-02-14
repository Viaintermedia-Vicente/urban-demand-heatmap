# 07 - Definición de dominio

## Eventos
- Un evento representa una manifestación de actividad urbana (concierto, teatro, cine, feria, manifestación, deporte, etc.).
- Propiedades mínimas: identificador, título, categoría, horario de inicio/fin y localización geográfica.
- Los eventos pueden tener origen en distintas fuentes; la normalización ocurre antes de llegar al dominio.

## Influencia temporal
- La contribución de un evento depende de la relación entre la hora consultada y su ventana temporal.
- Se distinguen tres fases: **pre** (anticipación), **pico** (durante) y **post** (resaca). Fuera de ese intervalo la influencia es cero.
- Las duraciones de cada fase pueden variar por categoría (ej. conciertos tienen pre más corto que ferias).

## Influencia espacial
- Cada evento afecta principalmente a un radio cercano a su localización.
- La influencia decrece al alejarse; a partir de cierta distancia (radio de corte) se considera nula.
- Radios diferentes según tipo de evento o aforo estimado.

## Score
- El score combina influencias temporal y espacial multiplicadas por un peso por categoría.
- Los scores se agregan para obtener la intensidad total de una zona.

## Hotspots
- Un hotspot es una celda/punto caracterizado por latitud, longitud y score acumulado.
- Sirven para construir el mapa de calor y priorizar acciones (movilidad, seguridad, marketing).
