# 01 - Architecture

## 1. Visión general de la arquitectura
El sistema `tfm-hotspots` es una aplicación web que analiza eventos urbanos para anticipar zonas de alta actividad. Opera con un backend expuesto vía API REST y un frontend desacoplado que consume dicha API. La arquitectura responde al principio de Clean Architecture, separando claramente dominio, aplicación y presentación, garantizando mantenibilidad sin incurrir en sobreingeniería.

## 2. Componentes principales
### Backend (FastAPI)
- **Importación de eventos**: coordina jobs que consumen APIs y fuentes CSV, normaliza los datos y ejecuta upserts.
- **Cálculo de zonas calientes**: invoca módulos de dominio para convertir eventos en scores geoespaciales.
- **Exposición de API**: ofrece endpoints `/api/heatmap`, `/api/events` y `/api/admin/import-events` siguiendo contratos definidos.

### Base de datos (PostgreSQL)
- Almacena eventos normalizados, audita importaciones y soporta consultas geoespaciales (PostGIS).

### Frontend (React + Leaflet)
- Muestra el mapa de calor, filtros por fecha/hora/categoría y listado de eventos, consumiendo únicamente la API REST.

### Job de importación
- Proceso programado (cron/manual) que ejecuta conectores de fuentes, aplica transformaciones y persiste resultados.

## 3. Diagrama de arquitectura
```
[ API Eventos ]      [ CSV ]
       |                |
       +---- Import Job ----+
                            |
                         PostgreSQL
                            |
                     FastAPI Backend
                            |
                         REST API
                            |
                      React + Leaflet
```

## 4. Separación de responsabilidades
- La lógica de dominio (scoring, agregaciones) vive en módulos puros sin dependencias de frameworks, cumpliendo SOLID.
- Servicios de infraestructura (repositorios, cache, conectores) implementan interfaces y pueden sustituirse sin tocar el dominio.
- Providers encapsulan llamadas a fuentes externas, aislan autenticación y formatos para facilitar pruebas y cambios de proveedor.

## 5. Justificación de decisiones
- **Monolito modular**: facilita despliegue y coordinación en un TFM; evita el overhead de microservicios (latencia, observabilidad), manteniendo capas internas bien definidas.
- **REST**: front y potenciales integraciones externas interactúan mediante contratos claros; elimina el acoplamiento directo a la base de datos y permite escalar el backend independientemente.
- **FastAPI**: framework ligero en Python, tipado moderno y herramientas integradas (OpenAPI) que aceleran el desarrollo del backend.
- **React**: ecosistema maduro y componentes reutilizables (Leaflet) para visualización interactiva.
- **PostgreSQL**: robustez, soporte geoespacial (PostGIS) y compatibilidad con las necesidades transaccionales del proyecto.

## 6. Evolución futura
- Integración con Odoo u otros ERPs para sincronizar recursos disponibles con las previsiones de actividad.
- Extensión a múltiples ciudades mediante configuración por tenant y segmentación de datos.
- Incorporación de modelos de IA avanzados (RAG/Ollama, predictores de demanda) manteniendo el módulo opcional desacoplado.
