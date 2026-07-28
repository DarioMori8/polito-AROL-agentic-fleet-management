import logging

from fastapi import FastAPI
from app.api.v1.chat import router as chat_router
from resources.router import router as resources_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI()


@app.get("/")
def health():
    return {"status": "ok"}


app.include_router(chat_router)
app.include_router(resources_router)