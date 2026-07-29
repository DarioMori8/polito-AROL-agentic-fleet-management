from fastapi import FastAPI
from contracts import SearchManualTask, SearchManualResponse, SearchDocsTask, SearchDocsResponse
from core.llm_adapter import OllamaAdapter
from manuals_agent.agent import ManualsAgent
from docs_agent.agent import DocsAgent
app = FastAPI(title="AROL Agents Service")

adapter = OllamaAdapter()

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/agents/manuals/search", response_model=SearchManualResponse)
async def invoke_manuals_agent(task: SearchManualTask):
    return await ManualsAgent(adapter).run(task)


@app.post("/agents/docs/search", response_model=SearchDocsResponse)
async def invoke_docs_agent(task: SearchDocsTask):
    return await DocsAgent(adapter).run(task)
