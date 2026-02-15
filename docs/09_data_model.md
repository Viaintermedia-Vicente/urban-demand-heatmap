# 09 - Data Model (Fase 2.B)

## 1. Motivación de `expected_attendance`
Los hotspots no solo dependen del número de eventos sino del volumen de personas que podrían concentrarse en cada zona. Un concierto masivo y una obra íntima generan impactos distintos, aunque compartan coordenadas. `expected_attendance` permite ponderar el score de cada celda con un estimador de asistencia, mejorando la priorización de recursos (movilidad, seguridad, marketing) y alineándose con el objetivo de ofrecer recomendaciones accionables.

## 2. Limitaciones de las APIs
Las agendas municipales y proveedores privados rara vez publican aforos o asistencia esperada. Algunos venues anuncian la capacidad máxima, pero no los tickets vendidos; otros eventos se listan sin venue asociado o con espacios temporales. Estas lagunas impiden calcular la intensidad real únicamente con datos brutos. La Fase 2.B reconoce esta brecha y propone un modelo propio de estimación para cubrirla hasta que haya fuentes oficiales más completas.

## 3. Enfoque de estimación basado en venues + categoría
1. **Capacidades de venues**: mantenemos un catálogo local de recintos con coordenadas y `max_capacity`. Cuando la API proporcione el ID del venue, podremos derivar una asistencia base multiplicando la capacidad por un factor configurable.
2. **Reglas por categoría (`category_rules`)**: definimos `fill_factor`, `fallback_attendance`, duración por defecto y ventanas pre/post según el tipo de evento. Si un venue carece de capacidad registrada, se usa el `fallback_attendance`.
3. **Configuración y evolución**: el enfoque es declarativo. Los valores pueden ajustarse por ciudad, temporada o incluso evolucionar a un modelo ML (p. ej. regresiones o gradient boosting) que aprenda de históricos de asistencia cuando dispongamos de datos reales.

## 4. Estructura de base de datos
- **`venues`**: catálogo de recintos con metadatos y capacidad. Incluye claves para mapear fuentes externas (`source`, `external_id`) y campos geográficos (lat, lon, ciudad, país).
- **`category_rules`**: tabla de configuración con parámetros de estimación por categoría. Define el `fill_factor`, duración estándar y buffers temporales para calcular la influencia temporal.
- **`events`**: registros normalizados con referencia opcional a `venues`. Almacena la estimación `expected_attendance`, junto con `popularity_score` para modular el impacto cuando haya métricas externas (tickets vendidos, interacciones sociales).

## 5. Uso en fases posteriores
- **Cálculo de hotspots**: el dominio combinará `expected_attendance` y las reglas temporales para ajustar los scores por celda.
- **Validación y tuning**: los seeds proporcionan datos de partida para pruebas automatizadas y demos. Las reglas podrán versionarse para nuevos mercados sin tocar el código.
- **Futuras extensiones ML**: al contar con `venues`, `events` y `category_rules`, será sencillo incorporar características adicionales (histórico de llenos, eventos similares) y entrenar modelos supervisados que mejoren la estimación de asistencia conforme se recopilen datasets reales.
