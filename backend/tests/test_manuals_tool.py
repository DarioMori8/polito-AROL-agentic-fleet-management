import unittest
from unittest.mock import AsyncMock, patch

from contracts import Citation, SearchManualResponse
from app.orchestrator.agent_registry import search_manuals, manuals_client


class ManualsToolTest(unittest.IsolatedAsyncioTestCase):
    async def test_full_sources_stay_in_artifact_without_flooding_model_context(self):
        response = SearchManualResponse(
            answer="Maintenance overview.", confidence=1.0,
            citations=[Citation(doc="manual.pdf", page=94, snippet="Full retrieved passage." * 30)],
        )
        with patch.object(manuals_client, "search", new=AsyncMock(return_value=response)):
            content, artifact = await search_manuals.coroutine("maintenance", "MCH-0001")
        self.assertIn("Maintenance overview.", content)
        self.assertIn("94", content)
        self.assertNotIn("Full retrieved passage", content)
        self.assertEqual(artifact["citations"][0]["snippet"], response.citations[0].snippet)
