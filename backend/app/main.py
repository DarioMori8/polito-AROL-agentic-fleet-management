import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langfuse import get_client

from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.db.engine import async_session_factory, create_db_and_tables, engine
from app.db.seed import seed_data
from app.orchestrator.orchestrator import LangGraphOrchestrator, build_graph
from app.resources.router import router as resources_router

# Configured before anything logs. Every module uses
# logging.getLogger(__name__), so all app.* loggers inherit this setup.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup
    await create_db_and_tables()      # domain tables: created only if missing
    await seed_data()

    try:
        async with build_graph() as graph:
            app.state.orchestrator = LangGraphOrchestrator(graph, async_session_factory)
            yield
    finally:
        await engine.dispose()
        await asyncio.to_thread(get_client().shutdown)


app = FastAPI(title="AROL Customer Platform API", lifespan=lifespan)


# The browser only sends the session cookie cross-origin if the request is
# made with credentials AND the origin is listed here explicitly: with
# allow_credentials=True a wildcard origin is not allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",   # frontend Docker container
        "http://localhost:3001",   # Vite dev server
        "http://localhost:3000",   # alternative dev port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Liveness probe used by the docker-compose healthcheck: no auth, no DB."""
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(resources_router)

# NOTE: there is intentionally no StaticFiles mount for the manuals. A static
# mount would serve every PDF to anyone who guesses a filename, bypassing both
# authentication and tenant scoping. PDFs are served only by
# GET /v1/manuals/{manual_id}/file, behind the same checks as every resource.
