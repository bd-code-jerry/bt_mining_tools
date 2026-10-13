from backend.app.config import APP_HOST, APP_PORT
from backend.app.core.config import PROJECT_ROOT
from backend.app.core.version import APP_VERSION

if __name__ == "__main__":
    import uvicorn

    print(f"BD Mining Tools v{APP_VERSION} | Project: {PROJECT_ROOT}", flush=True)
    uvicorn.run(
        "backend.app.main:app",
        host=APP_HOST,
        port=APP_PORT,
        reload=False,
        access_log=True,
    )
