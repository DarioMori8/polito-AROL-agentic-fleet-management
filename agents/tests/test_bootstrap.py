import unittest
from unittest.mock import MagicMock, patch

import ollama

from core.config import settings
from manuals_agent.bootstrap import ensure_model, main, verify_inference


class BootstrapTest(unittest.TestCase):
    def test_existing_model_is_reused_without_network_pull(self):
        client = MagicMock()
        client.show.return_value = {"capabilities": ["tools"]}
        ensure_model(client, "llama3.1:8b", require_tools=True)
        client.pull.assert_not_called()

    def test_missing_model_is_downloaded_and_checked(self):
        client = MagicMock()
        client.show.side_effect = [ollama.ResponseError("missing", status_code=404), {"capabilities": ["tools"]}]
        client.pull.return_value = [
            ollama.ProgressResponse(status="pulling manifest"),
            ollama.ProgressResponse(status="pulling", total=100, completed=None),
            ollama.ProgressResponse(status="pulling", total=100, completed=100),
            ollama.ProgressResponse(status="success"),
        ]
        ensure_model(client, "llama3.1:8b", require_tools=True)
        client.pull.assert_called_once_with("llama3.1:8b", stream=True)

    def test_server_error_is_not_treated_as_missing_model(self):
        client = MagicMock()
        client.show.side_effect = ollama.ResponseError("failure", status_code=500)
        with self.assertRaises(ollama.ResponseError):
            ensure_model(client, "llama3.1:8b")
        client.pull.assert_not_called()

    def test_download_failure_propagates(self):
        client = MagicMock()
        client.show.side_effect = ollama.ResponseError("missing", status_code=404)
        client.pull.side_effect = ConnectionError("download interrupted")
        with self.assertRaises(ConnectionError):
            ensure_model(client, "llama3.1:8b")

    def test_model_without_tools_is_rejected(self):
        client = MagicMock()
        client.show.return_value = {"capabilities": ["completion"]}
        with self.assertRaisesRegex(ValueError, "tool calling"):
            ensure_model(client, "wrong-model", require_tools=True)

    def test_missing_manuals_prevent_download_and_ingestion(self):
        with patch("manuals_agent.bootstrap.prepare_manuals", side_effect=ValueError("missing")), \
                patch("manuals_agent.bootstrap.ensure_model") as download, \
                patch("manuals_agent.bootstrap.seed_manuals") as ingest:
            with self.assertRaises(ValueError):
                main()
        download.assert_not_called()
        ingest.assert_not_called()

    def test_inference_checks_real_context_size_and_unloads_model(self):
        client = MagicMock()
        client.chat.return_value = {"done": True}
        verify_inference(client)
        arguments = client.chat.call_args.kwargs
        self.assertEqual(arguments["model"], settings.OLLAMA_MODEL)
        self.assertEqual(arguments["options"]["num_ctx"], settings.OLLAMA_NUM_CTX)
        self.assertEqual(arguments["keep_alive"], 0)
        self.assertNotIn("think", arguments)

    def test_out_of_memory_produces_an_actionable_setup_error(self):
        client = MagicMock()
        client.chat.side_effect = ollama.ResponseError("llama runner process terminated: signal: killed", status_code=500)
        with self.assertRaisesRegex(RuntimeError, "16 GB.*preserved"):
            verify_inference(client)

    def test_other_inference_errors_are_preserved(self):
        client = MagicMock()
        client.chat.side_effect = ollama.ResponseError("invalid request", status_code=400)
        with self.assertRaises(ollama.ResponseError):
            verify_inference(client)

    def test_incomplete_inference_is_not_success(self):
        client = MagicMock()
        client.chat.return_value = {"done": False}
        with self.assertRaisesRegex(RuntimeError, "did not complete"):
            verify_inference(client)


if __name__ == "__main__":
    unittest.main()
