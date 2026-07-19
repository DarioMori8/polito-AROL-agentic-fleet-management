from fastapi import FastAPI
from app.api.v1.chat import router as chat_router


app=FastAPI()

@app.get("/")
def health():
    return {"status": "ok"}

app.include_router(chat_router)
