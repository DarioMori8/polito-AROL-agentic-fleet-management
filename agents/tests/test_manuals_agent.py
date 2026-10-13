import asyncio
import copy
import json
import unittest
from unittest.mock import patch

from contracts import SearchManualTask
from core.config import settings
from core.llm_adapter import LLMResponse, ToolCall
from manuals_agent.agent import ManualsAgent


class FakeLLM:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    async def complete(self, messages, tools=None):
        self.requests.append((copy.deepcopy(messages), tools))
        return next(self.responses)


class FakeStore:
    def get_languages(self, where):
        assert where == {"machine_id": "MCH-0001"}
        return ["EN"]

    def query(self, text, k, where):
        assert where == {"machine_id": "MCH-0001"}
        return [{"doc": "manual.pdf", "page": 94, "text": "Maintenance schedule."}]


class ManualsAgentTest(unittest.TestCase):
    def run_agent(self, llm):
        with patch("manuals_agent.agent.get_vector_store", return_value=FakeStore()):
            return asyncio.run(ManualsAgent(llm).run(SearchManualTask(
                query="Quali sono le procedure di manutenzione?", machine_id="MCH-0001"
            )))

    def test_language_and_complete_tool_history(self):
        llm = FakeLLM([
            LLMResponse(thinking="Search the maintenance section.", tool_calls=[
                ToolCall(name="search_manual", arguments={"query": "maintenance procedures"})
            ]),
            LLMResponse(content="Consulta il programma di manutenzione a pagina 94."),
        ])
        result = self.run_agent(llm)
        messages, _ = llm.requests[1]
        self.assertIn("EN", messages[1]["content"])
        self.assertIn("Quali sono le procedure", messages[1]["content"])
        self.assertEqual(messages[2]["tool_calls"][0]["function"]["name"], "search_manual")
        self.assertEqual(messages[2]["thinking"], "Search the maintenance section.")
        self.assertEqual(messages[3]["tool_name"], "search_manual")
        self.assertEqual(json.loads(messages[3]["content"])["results"][0]["page"], 94)
        self.assertEqual(result.citations[0].page, 94)

    def test_tool_budget_reserves_final_synthesis(self):
        llm = FakeLLM([
            LLMResponse(tool_calls=[ToolCall(name="search_manual", arguments={"query": "maintenance"})]),
            LLMResponse(content="Il programma è a pagina 94."),
        ])
        with patch.object(settings, "MAX_ITERATIONS", 1):
            result = self.run_agent(llm)
        self.assertIsNone(llm.requests[-1][1])
        self.assertIn("Quali sono le procedure", llm.requests[-1][0][-1]["content"])
        self.assertTrue(result.answer)

    def test_empty_answer_is_not_reported_as_verified(self):
        llm = FakeLLM([
            LLMResponse(tool_calls=[ToolCall(name="search_manual", arguments={"query": "maintenance"})]),
            LLMResponse(content=""),
        ])
        result = self.run_agent(llm)
        self.assertTrue(result.answer)
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.citations, [])

    def test_repeated_passages_are_deduplicated(self):
        call = LLMResponse(tool_calls=[ToolCall(name="search_manual", arguments={"query": "maintenance"})])
        result = self.run_agent(FakeLLM([call, call, LLMResponse(content="Pagina 94.")]))
        self.assertEqual(len(result.citations), 1)


if __name__ == "__main__":
    unittest.main()
