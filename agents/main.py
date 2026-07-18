from fastapi import FastAPI

app = FastAPI(title="AROL Agents Service")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/agents/{name}/invoke")
async def invoke_agent(name: str, task: dict):
    return {
        "answer": f"[stub] agente '{name}' non ancora implementato",
        "sources": [],
        "confidence": 0.0,
        "needs_escalation": True,
    }
