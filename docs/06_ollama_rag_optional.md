# 06 - Ollama / RAG (Opcional)

## 1. Objetivo
Incorporar un módulo opcional de IA que permita consultas en lenguaje natural sobre zonas calientes y eventos, ofreciendo explicaciones y recomendaciones sin que el usuario deba navegar por filtros tradicionales.

## 2. Enfoque no bloqueante
- El sistema funciona plenamente sin IA: el backend y el frontend continúan sirviendo heatmaps y listados mediante la API estándar.
- La capa de IA es un módulo adicional activable cuando se dispone de recursos (servidor Ollama y embeddings), garantizando que el TFM pueda evaluarse incluso sin esta extensión.

## 3. Arquitectura propuesta
- El backend FastAPI actúa como intermediario: recibe la consulta en lenguaje natural, prepara el contexto y envía el prompt al servidor Ollama.
- Ollama se despliega en un servidor remoto o contenedor aparte, expuesto a través de API HTTP segura (`OLLAMA_URL`).
- La respuesta del LLM se devuelve al frontend junto con enlaces a zonas/eventos concretos.

## 4. Ejemplos de consultas
1. “¿Dónde hay más actividad esta noche?”
2. “¿Qué eventos hay cerca de esta zona?”
3. “Recomiéndame un recorrido cultural para turistas mañana por la tarde.”
El backend traduce estas preguntas en prompts estructurados, incorporando datos recientes.

## 5. RAG (Retrieval Augmented Generation)
- Información indexada: descripción del algoritmo de scoring, FAQ del sistema, catálogos de eventos/categorías, resúmenes diarios de actividad.
- Estrategia inicial (v1): búsqueda por palabras clave dentro de PostgreSQL o archivos estáticos para aportar párrafos de contexto al LLM.
- Evolución futura (v2): generación de embeddings y almacenamiento en `pgvector` o Chroma para recuperar contextos semánticos antes de invocar a Ollama.

## 6. Consideraciones éticas y de privacidad
- Evitar enviar datos personales o sensibles en los prompts; trabajar con información agregada y anonimizada.
- Informar al usuario de que las respuestas generadas pueden contener incertidumbre y requieren validación para decisiones críticas.
- Registrar únicamente métricas agregadas del uso de IA, nunca el contenido literal de las consultas.
