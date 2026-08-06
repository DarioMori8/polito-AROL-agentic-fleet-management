import logging
from contextlib import asynccontextmanager


from fastapi import FastAPI
from app.api.v1.chat import router as chat_router
from app.resources.router import router as resources_router
from fastapi.middleware.cors import CORSMiddleware
from app.orchestrator.orchestrator import build_graph, LangGraphOrchestrator
from app.db.engine import engine, create_db_and_tables
from app.db.seed import seed_data


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

@asynccontextmanager
async def lifespan(app: FastAPI):

    # --- startup 
    await create_db_and_tables()      # domain tables: created only if missing
    await seed_data()               

    async with build_graph() as graph:
        app.state.orchestrator = LangGraphOrchestrator(graph)
        yield
    # --- shutdown

    await engine.dispose()            # close pooled DB connections cleanly


app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],   # l'origine da cui è servito il frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(chat_router)
app.include_router(resources_router)