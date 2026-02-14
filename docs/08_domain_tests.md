# 08 - Tests del dominio

## Influencia temporal
- **Given** un evento que comienza a las 20:00 y dura 2 horas.
- **When** consultamos las 19:30 (pre), 20:30 (pico), 22:15 (post) y 23:30 (fuera de ventana).
- **Then** el score debe ser >0 en pre/pico/post y exactamente 0 fuera de la ventana.

## Ventanas por categoría
- **Given** dos eventos de categorías distintas con ventanas personalizadas.
- **When** calculamos el score en la misma hora.
- **Then** la categoría con ventana más amplia debe seguir aportando peso mientras la otra ya cae a cero.

## Influencia espacial
- **Given** un evento con radio de 250 m.
- **When** calculamos el score en el punto exacto y en otro a más de 250 m.
- **Then** el punto exacto tiene score >0 y el lejano tiene score 0.

## Composición
- **Given** dos eventos cercanos en la misma zona y hora.
- **When** se calcula el hotspot.
- **Then** el score acumulado debe ser mayor que el score de cualquiera de ellos por separado.

## Determinismo
- **Given** un conjunto fijo de eventos y parámetros.
- **When** se calcula el score varias veces.
- **Then** el resultado debe ser idéntico, garantizando determinismo del dominio.
