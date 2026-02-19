# 00 - Project Overview

## Situación / Problema
Las grandes ciudades experimentan picos de afluencia difíciles de anticipar, lo que complica la planificación de servicios y recursos. Ciudadanos, operadores de ocio, movilidad y seguridad se ven afectados por la incertidumbre sobre dónde se concentrará la actividad. Actualmente existen pocas herramientas accesibles basadas en datos que permitan anticipar esas zonas calientes con antelación suficiente para actuar.

## Contexto
- Crecimiento sostenido de eventos culturales, deportivos y de ocio en núcleos urbanos con fuerte carga estacional.
- Amplia disponibilidad de datos abiertos, APIs municipales y fuentes privadas que publican agendas y aforos estimados.
- Avances recientes en análisis geoespacial, ciencia de datos urbana e inteligencia artificial que habilitan modelos predictivos más precisos.

## Motivación
- La IA permite combinar datos históricos y streams en tiempo real para generar modelos explicables que apoyan la toma de decisiones públicas y privadas.
- Se busca un sistema predictivo que sirva como asistencia para operadores de planificación, evitando decisiones reactivas.
- El enfoque tiene aplicabilidad transversal en movilidad, ocio, turismo y seguridad ciudadana, aportando valor a múltiples actores.

## Objetivo general
Diseñar y desarrollar un sistema capaz de predecir zonas de alta actividad urbana basándose en eventos y contexto temporal, ofreciendo visualizaciones y recomendaciones accionables.

## Objetivos específicos
1. Importar y normalizar eventos desde APIs abiertas, feeds municipales y ficheros externos.
2. Calcular la intensidad de actividad por zona y franja horaria empleando agregaciones geoespaciales.
3. Visualizar las zonas calientes mediante un mapa interactivo que destaque los hotspots.
4. Mostrar eventos relevantes en una línea temporal filtrable por categoría y ubicación.
5. (Opcional) Permitir consultas en lenguaje natural apoyadas en Ollama/RAG para explorar el histórico de eventos.

## Alcance
- MVP incluye backend FastAPI, base de datos Postgres con PostGIS, frontend React con mapa de calor y job de importación de eventos.
- Se emplean datos abiertos de eventos culturales y simulaciones controladas para completar lagunas.
- Madrid se adopta como ciudad de referencia para la validación inicial.

## Fuera de alcance
- Asignación automática de servicios o personal operativo en campo.
- Funcionalidades de pago, reserva o interacción transaccional con usuarios finales.
- Integración directa con plataformas externas de transporte o ticketing en esta fase.

## Metodología
- Enfoque incremental por fases: descubrimiento de datos, modelado, visualización y validación.
- Desarrollo guiado por tests (TDD) para backend y pruebas ligeras en frontend.
- Uso combinado de datos reales y simulados que permiten evaluar el modelo sin depender únicamente de feeds productivos.

## Planificación
- Semana 1 (03/02 - 09/02): análisis de datos, definición del modelo y diseño arquitectónico.
- Semana 2 (10/02 - 16/02): implementación del backend, pipeline de importación y base de datos.
- Semana 3 (17/02 - 23/02): desarrollo del frontend, integración completa, pruebas, documentación final y preparación de demo.

## Entregables
- Código fuente completo en un repositorio Git monorepo `tfm-hotspots`.
- Documentación técnica y académica en formato Markdown.
- Despliegue local reproducible mediante Docker Compose.
- Demo funcional que muestre el mapa de calor y el listado de eventos.
- Presentación final para el tribunal del TFM.
