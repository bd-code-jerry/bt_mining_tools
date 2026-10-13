from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import api_router
from .config import FRONTEND_DIR
from .database import db_connection, init_database
from .features.balances.provider_catalog import seed_provider_catalog
from .core.version import APP_VERSION

app = FastAPI(title="BD Mining Tools", version=APP_VERSION)


@app.middleware("http")
async def fresh_dashboard_responses(request, call_next):
    response = await call_next(request)
    # Updates must not retain an older HTML/module graph or account capabilities.
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-BD-App-Version"] = APP_VERSION
    return response


@app.on_event("startup")
def startup() -> None:
    init_database()
    with db_connection() as conn:
        seed_provider_catalog(conn)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": APP_VERSION}


app.include_router(api_router)
# Relative imports inherit this release namespace, including lazy page imports.
app.mount(f"/static/v{APP_VERSION}", StaticFiles(directory=str(FRONTEND_DIR)), name="versioned-static")
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")
