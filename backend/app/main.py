from fastapi import FastAPI

from .api.health import router as health_router

app = FastAPI(title="TFM Hotspots API")
app.include_router(health_router)


@app.get("/")
def read_root():
    return {"message": "Hotspots urbanos API"}
