import unittest
from unittest.mock import patch

import httpx
from tenacity import wait_none

from app.clients.base import HttpAgentClient
from app.clients.exceptions import AgentUnavailableError
from app.clients.iot_client import IoTClient
from app.config import settings


class AgentClientTest(unittest.IsolatedAsyncioTestCase):
    async def request_with_transport(self, handler):
        # Exercise real HTTPX timeout propagation and the production retry wrapper.
        transport = httpx.MockTransport(handler)
        client_class = httpx.AsyncClient

        def client_factory(**kwargs):
            return client_class(transport=transport, **kwargs)

        with (
            patch("app.clients.base.httpx.AsyncClient", side_effect=client_factory),
            patch.object(HttpAgentClient._post.retry, "wait", wait_none()),
        ):
            return await IoTClient().search("Open alarms?", "MCH-0001")

    async def test_iot_response_and_configured_timeout(self):
        def handler(request):
            self.assertEqual(request.url.path, "/agents/iot/search")
            self.assertEqual(request.extensions["timeout"]["read"], 180.0)
            self.assertEqual(request.extensions["timeout"]["connect"], 5.0)
            return httpx.Response(200, json={
                "answer": "One open alarm.",
                "observations": [{"kind": "alarms", "data": {"machine_id": "MCH-0001"}}],
                "confidence": 1.0,
            })

        with patch.object(settings, "AGENTS_REQUEST_TIMEOUT_SECONDS", 180.0):
            result = await self.request_with_transport(handler)
        self.assertEqual(result.observations[0].data["machine_id"], "MCH-0001")

    async def test_read_timeout_does_not_duplicate_inference(self):
        calls = []

        def handler(request):
            calls.append(request)
            raise httpx.ReadTimeout("Inference still running", request=request)

        with self.assertRaisesRegex(AgentUnavailableError, "Timeout while contacting IoT"):
            await self.request_with_transport(handler)
        self.assertEqual(len(calls), 1)

    async def test_connection_failures_are_retried(self):
        for error_type in (httpx.ConnectError, httpx.ConnectTimeout):
            with self.subTest(error=error_type.__name__):
                calls = []

                def handler(request):
                    calls.append(request)
                    raise error_type("Connection unavailable", request=request)

                with self.assertRaises(AgentUnavailableError):
                    await self.request_with_transport(handler)
                self.assertEqual(len(calls), 3)

    async def test_http_error_is_not_retried(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(503)

        with self.assertRaisesRegex(AgentUnavailableError, "IoT agent returned an error"):
            await self.request_with_transport(handler)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
