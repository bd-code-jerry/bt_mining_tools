from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import api_router
from .config import FRONTEND_DIR
from .database import db_connection, init_database
from .features.balances.provider_catalog import seed_provider_catalog

app = FastAPI(title="BD API Key Balances", version="1.2.0")


@app.on_event("startup")
def startup() -> None:
    init_database()
    with db_connection() as conn:
        seed_provider_catalog(conn)


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.include_router(api_router)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")
