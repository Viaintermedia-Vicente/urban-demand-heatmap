# 05 - Deployment Local

## 1. Requisitos previos
- Docker Desktop (Windows/macOS) o motor Docker 24+ (Linux).
- Docker Compose v2 disponible (`docker compose version`).
- Puertos libres: 5432 (PostgreSQL), 8000 (backend), 5173 (frontend).

## 2. Servicios incluidos en Docker Compose
- **PostgreSQL** (`db`): almacén persistente para eventos y auditoría.
- **Backend FastAPI** (`backend`): expone la API REST y ejecuta importaciones bajo demanda.
- **Frontend React** (`frontend`): interfaz web con Leaflet para visualizar el mapa de calor.
- (Opcional) **Importer**: contenedor programado para lanzar el job cada hora.

## 3. Variables de entorno
Crear un archivo `.env` en la raíz antes de levantar los servicios:
- `DB_URL=postgresql://tfm:tfm@db:5432/tfm_hotspots`
- `API_PORT=8000`
- `FRONT_PORT=5173`
- `IMPORT_SOURCES=madrid_cultura,madrid_deportes`
- `OLLAMA_URL=` (vacío por defecto si no hay módulo IA)
Estas variables permiten parametrizar puertos y credenciales sin tocar el compose.

## 4. Pasos de ejecución
1. Construir e iniciar: `docker compose up --build`
2. Verificar logs iniciales (backend debe mostrar "Application startup complete").
3. Detener manteniendo volúmenes: `docker compose down`
4. Reiniciar tras cambios: repetir el paso 1.
5. Reset completo (elimina datos): `docker compose down -v`

## 5. URLs de acceso
- Frontend: `http://localhost:5173`
- Backend (Swagger / OpenAPI): `http://localhost:8000/docs`
- Endpoint de salud (cuando exista): `http://localhost:8000/health`

## 6. Importación de eventos
- **Job automático**: el servicio `importer` ejecuta el comando de ingesta cada 60 minutos usando los `IMPORT_SOURCES` configurados.
- **Ejecución manual** (referencial hasta tener script definitivo):
  - `docker compose run --rm backend python -m app.jobs.import_events --source madrid_cultura --days 3`
  - Ajustar parámetros `--source` y `--days` según la prueba.
- En producción se recomienda cron horario y ejecución manual bajo supervisión cuando se añadan nuevas fuentes.

## 7. Resolución de problemas comunes
- **Puertos ocupados**: modificar `API_PORT` o `FRONT_PORT` en `.env` y relanzar `docker compose up`.
- **Errores de conexión a DB**: revisar que el contenedor `db` está "healthy" (`docker compose ps`) y, si es necesario, reiniciar sólo esa pieza (`docker compose restart db`).
- **Migraciones pendientes**: ejecutar el script de migración del backend (por definir) antes de exponer la API.
- **Import job fallido**: inspeccionar logs con `docker compose logs importer` y validar credenciales/API externas.
- **Datos dañados o obsoletos**: realizar `docker compose down -v` para recrear la base desde cero (se perderán eventos).

Con estos pasos, cualquier evaluador puede levantar el entorno localmente sin soporte adicional.
