import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.v1.chat import router as chat_router
from app.resources.router import router as resources_router
from fastapi.middleware.cors import CORSMiddleware


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI()


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
    return {"status": "ok"}


app.include_router(chat_router)
app.include_router(resources_router)

# Serve PDF manuals as static files.
# The Manual.url field in the schema points to /static/manuals/<filename>.
# In Docker this resolves to the shared ./data/manuals volume (read-only).
app.mount("/static/manuals", StaticFiles(directory="/data/manuals"), name="manuals")