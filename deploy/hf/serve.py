"""Demo server: the API under /api and the built React app at /, on one port."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.main import app as api

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Orbit Helpdesk demo", docs_url=None, redoc_url=None)
app.mount("/api", api)
app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    """Single-page app: real files are served as-is, everything else gets index.html."""
    file = STATIC / path
    if path and file.is_file():
        return FileResponse(file)
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})
