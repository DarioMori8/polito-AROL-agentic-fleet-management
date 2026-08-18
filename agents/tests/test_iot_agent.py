import asyncio
import unittest
from unittest.mock import patch

from contracts import SearchIoTTask

from core.llm_adapter import LLMResponse, ToolCall
from core.iot_client import ALARM_SEVERITIES, _canonical, _clean_params
from iot_agent.agent import IoTAgent


class FakeLLM:
    def __init__(self, responses):
        self.responses = iter(responses)

    async def complete(self, messages, tools=None):
        return next(self.responses)


class FakeIoTClient:
    def __init__(self):
        self.calls = []

    async def search_alarms(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "machine_id": kwargs["machine_id"],
            "summary": {"matched_alarms": 1},
            "results": [{"alarm_id": "ALM-0228", "status": "Open"}],
        }

    async def search_maintenance(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "machine_id": kwargs["machine_id"],
            "summary": {"matched_tickets": 1},
            "results": [
                {
                    "ticket_id": "TKT-0001",
                    "alarm_id": "ALM-0228",
                    "status": "Open",
                    "priority": "High",
                    "owner_role": "Field Service Engineer",
                }
            ],
        }


class IoTAgentTest(unittest.TestCase):
    def test_agent_uses_trusted_machine_and_stops_on_plain_response(self):
        llm = FakeLLM(
            [
                LLMResponse(
                    tool_calls=[
                        ToolCall(
                            name="search_alarms",
                            arguments={"status": "Open", "window_hours": 24},
                        )
                    ]
                ),
                LLMResponse(content="There is one open alarm."),
            ]
        )
        client = FakeIoTClient()
        agent = IoTAgent(llm)

        with patch("iot_agent.agent.get_iot_client", return_value=client):
            response = asyncio.run(
                agent.run(
                    SearchIoTTask(query="Any open alarms?", machine_id="MCH-0007")
                )
            )

        self.assertEqual(client.calls[0]["machine_id"], "MCH-0007")
        self.assertEqual(response.answer, "There is one open alarm.")
        self.assertEqual(response.observations[0].kind, "alarms")
        self.assertEqual(response.confidence, 1.0)

    def test_plain_response_without_tool_has_no_observations(self):
        agent = IoTAgent(FakeLLM([LLMResponse(content="I need more detail.")]))
        response = asyncio.run(
            agent.run(SearchIoTTask(query="Help", machine_id="MCH-0001"))
        )

        self.assertEqual(response.observations, [])
        self.assertEqual(response.confidence, 0.0)

    def test_alarm_ticket_coverage_marks_covered_and_uncovered_alarms(self):
        client = FakeIoTClient()

        async def search_alarms(**kwargs):
            client.calls.append(kwargs)
            return {
                "machine_id": kwargs["machine_id"],
                "window": {"from": "2026-08-01T00:00", "to": "2026-08-04T23:00"},
                "filters": {"status": "Open"},
                "summary": {"matched_alarms": 2},
                "results": [
                    {"alarm_id": "ALM-0228", "status": "Open"},
                    {"alarm_id": "ALM-0229", "status": "Open"},
                ],
            }

        client.search_alarms = search_alarms
        agent = IoTAgent(
            FakeLLM(
                [
                    LLMResponse(
                        tool_calls=[
                            ToolCall(
                                name="analyze_alarm_ticket_coverage",
                                arguments={"status": "Open", "window_hours": 96},
                            )
                        ]
                    ),
                    LLMResponse(content="One alarm has a ticket and one does not."),
                ]
            )
        )

        with patch("iot_agent.agent.get_iot_client", return_value=client):
            response = asyncio.run(
                agent.run(
                    SearchIoTTask(query="Which alarms have tickets?", machine_id="MCH-0007")
                )
            )

        coverage = response.observations[0].data
        self.assertEqual(coverage["machine_id"], "MCH-0007")
        self.assertEqual(coverage["summary"]["with_ticket"], 1)
        self.assertEqual(coverage["summary"]["without_ticket"], 1)
        self.assertTrue(coverage["alarms"][0]["has_ticket"])
        self.assertFalse(coverage["alarms"][1]["has_ticket"])
        self.assertEqual(coverage["alarms"][0]["tickets"][0]["owner_role"], "Field Service Engineer")

    def test_blank_optional_filters_are_dropped(self):
        self.assertIsNone(_canonical("   ", ALARM_SEVERITIES))
        self.assertEqual(
            _clean_params(
                {
                    "status": " Open ",
                    "severity": "",
                    "alarm_code": "   ",
                    "limit": 50,
                }
            ),
            {"status": "Open", "limit": 50},
        )


if __name__ == "__main__":
    unittest.main()
