import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

from app.domain.models import Event
from app.domain.scoring import compute_hotspots

app = typer.Typer(help="CLI para operar hotspots urbanos")

_EXAMPLE_DATA = Path(__file__).parent / "sample_events.json"


def _load_events() -> list[Event]:
    if _EXAMPLE_DATA.exists():
        payload = json.loads(_EXAMPLE_DATA.read_text())
    else:
        payload = [
            {
                "id": "ev1",
                "title": "Concierto demo",
                "category": "concierto",
                "start_dt": "2026-02-10T19:00:00",
                "end_dt": None,
                "lat": 40.4,
                "lon": -3.7,
            },
            {
                "id": "ev2",
                "title": "Teatro demo",
                "category": "teatro",
                "start_dt": "2026-02-10T20:00:00",
                "end_dt": "2026-02-10T22:00:00",
                "lat": 40.41,
                "lon": -3.71,
            },
        ]
    events = []
    for item in payload:
        events.append(
            Event(
                id=item["id"],
                title=item.get("title", ""),
                category=item.get("category", "otros"),
                start_dt=datetime.fromisoformat(item["start_dt"]),
                end_dt=datetime.fromisoformat(item["end_dt"]) if item.get("end_dt") else None,
                lat=float(item.get("lat", 0)),
                lon=float(item.get("lon", 0)),
                source=item.get("source"),
            )
        )
    return events


@app.command("heatmap")
def cli_heatmap(
    date: str = typer.Option(..., help="Fecha YYYY-MM-DD"),
    hour: int = typer.Option(..., help="Hora 0-23"),
    categories: Optional[str] = typer.Option(None, help="Lista de categorías separadas por comas"),
    top: int = typer.Option(10, help="Número de hotspots a mostrar"),
):
    target = datetime.fromisoformat(f"{date}T{hour:02d}:00:00")
    cats = [c.strip() for c in categories.split(",")] if categories else None
    events = _load_events()
    hotspots = compute_hotspots(events, target, cats, max_points=top)
    if not hotspots:
        typer.echo("No se encontraron hotspots para ese horario")
        raise typer.Exit(code=0)
    typer.echo("lat\tlon\tscore")
    for hs in hotspots:
        typer.echo(f"{hs.lat:.5f}\t{hs.lon:.5f}\t{hs.score:.3f}")


@app.command("events")
def cli_events(
    date: str = typer.Option(..., help="Fecha YYYY-MM-DD"),
    from_hour: int = typer.Option(0, help="Hora inicial"),
    categories: Optional[str] = typer.Option(None, help="Categorías"),
    limit: int = typer.Option(10, help="Límite"),
):
    typer.echo("TODO: listar eventos (demo)")
    raise typer.Exit(code=0)


@app.command("import")
def cli_import(
    source: str = typer.Option(..., help="Fuente (csv, api, etc.)"),
    file: Optional[str] = typer.Option(None, help="Ruta del archivo"),
):
    typer.echo(f"TODO: importación desde {source} (file={file})")
    raise typer.Exit(code=0)


if __name__ == "__main__":
    app()
