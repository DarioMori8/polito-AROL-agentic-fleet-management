from fastapi import FastAPI
from core.schemas import SearchManualTask, SearchManualResponse
from core.llm_adapter import OllamaAdapter
from manuals_agent.agent import ManualsAgent
app = FastAPI(title="AROL Agents Service")

adapter = OllamaAdapter()

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/agents/manuals/search", response_model=SearchManualResponse)
async def invoke_manuals_agent(task: SearchManualTask):
    return await ManualsAgent(adapter).run(task)
