import logging
from contextlib import asynccontextmanager


from fastapi import FastAPI
from app.api.v1.chat import router as chat_router
from app.resources.router import router as resources_router
from fastapi.middleware.cors import CORSMiddleware
from app.orchestrator.orchestrator import build_graph, LangGraphOrchestrator



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup: runs once, before the app serves any request ---
    async with build_graph() as graph:
        app.state.orchestrator = LangGraphOrchestrator(graph)
        yield
    # --- shutdown: runs once, after the app stops serving requests ---
    # exiting the `async with` above closes the SQLite connection cleanly


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