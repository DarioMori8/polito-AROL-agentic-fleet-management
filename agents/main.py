import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from contracts import (
    SearchDocsResponse,
    SearchDocsTask,
    SearchIoTResponse,
    SearchIoTTask,
    SearchManualResponse,
    SearchManualTask,
)
from core.llm_adapter import OllamaAdapter
from core.observability import AgentTraceContextMiddleware, get_langfuse
from manuals_agent.agent import ManualsAgent
from docs_agent.agent import DocsAgent
from iot_agent.agent import IoTAgent


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = get_langfuse()
    try:
        yield
    finally:
        await asyncio.to_thread(client.shutdown)


app = FastAPI(title="AROL Agents Service", lifespan=lifespan)
app.add_middleware(AgentTraceContextMiddleware)

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


@app.post("/agents/iot/search", response_model=SearchIoTResponse)
async def invoke_iot_agent(task: SearchIoTTask):
    return await IoTAgent(adapter).run(task)
