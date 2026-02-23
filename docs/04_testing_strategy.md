# 04 - Testing Strategy

## 1. Filosofía de testing
- Se priorizan pruebas funcionales básicas de dominio y API; no se ha aplicado TDD de forma estricta en todas las piezas.
- Los tests existentes sirven como documentación viva de los contratos; si faltan, se complementa con ejemplos en los docs.

## 2. Tipos de tests
- **Unitarios**: se enfocan en la lógica pura de cálculo de score temporal y ponderaciones por categoría dentro del dominio.
- **Integración**: validan la importación y el upsert en PostgreSQL, garantizando que `UNIQUE(source, external_id)` evita duplicados.
- **API**: ejercitan endpoints `GET /api/heatmap` y `GET /api/events` usando FastAPI TestClient para comprobar contratos y validaciones.
- **Frontend (ligero)**: pruebas con mocks que verifican el comportamiento del slider de hora, filtros por categorías y render del mapa usando datos simulados.

## 3. Casos Given / When / Then
1. **Evento antes/durante/después**
   - Given eventos que empiezan antes, durante y después de la franja solicitada.
   - When se calcula el score para la hora 18:00.
   - Then sólo el evento en la ventana activa contribuye al heatmap.
2. **Eventos cercanos suman intensidad**
   - Given dos eventos en celdas adyacentes.
   - When se agrega el heatmap.
   - Then el score resultante refleja la suma ponderada y aparece como hotspot principal.
3. **Heatmap vs. eventos actuales**
   - Given el endpoint `/api/heatmap` (predictivo) y `/api/events` (eventos actuales).
   - When se consulta `/api/heatmap`, la respuesta incluye `hotspots` y puede incluir `events` (o sintéticos si no hay datos).
   - Then `/api/events` devuelve la lista de eventos con `category` nullable o `"unknown"` y coordenadas si están disponibles.

## 4. Herramientas
- `python3 -m pytest` como runner general (en mac/Linux). En Docker: `docker compose exec backend python -m pytest`.
- FastAPI `TestClient` (o httpx) para las pruebas de endpoints REST.
- Base de datos temporal: contenedor Docker con PostgreSQL para integraciones; alternativa con sqlite/mocks cuando no se requieran features geoespaciales.

## 5. Criterios de aceptación
- **Dominio**: suite de tests unitarios verde con cobertura mínima del módulo de scoring.
- **Backend**: pruebas de integración y API ejecutadas en CI, validando import y contratos.
- **Frontend**: tests de interacción básicos (slider y filtros) pasan con mocks y se incluye evidencia en la documentación.
- **Entrega final**: todas las suites deben ejecutarse sin errores antes de la fecha límite; los resultados se adjuntan en el informe del TFM.

## 6. Cómo ejecutar los tests (macOS/Linux)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m pip install pytest
python3 -m pytest -q
```
Con Docker:
```bash
cd docker
docker compose exec backend python3 -m pytest -q
```
