import unittest
from unittest.mock import MagicMock, patch

import ollama

from core.config import settings
from manuals_agent.bootstrap import ensure_model, main, verify_gpu, verify_inference


class BootstrapTest(unittest.TestCase):
    def setUp(self):
        cpu_mode = patch.object(settings, "SETUP_REQUIRE_GPU", False)
        cpu_mode.start()
        self.addCleanup(cpu_mode.stop)

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

    def test_gpu_mode_checks_resident_model_using_sdk_response(self):
        client = MagicMock()
        client.chat.return_value = ollama.ChatResponse(
            model="llama3.1:8b", done=True, message={"role": "assistant", "content": "OK"},
        )
        client.ps.return_value = ollama.ProcessResponse(models=[{
            "model": "llama3.1:8b", "size": 6_000_000_000, "size_vram": 6_000_000_000,
        }])
        with patch.object(settings, "SETUP_REQUIRE_GPU", True):
            verify_inference(client)
        self.assertEqual(client.chat.call_args.kwargs["keep_alive"], "5m")
        client.ps.assert_called_once()

    def test_cpu_mode_does_not_require_gpu_introspection(self):
        client = MagicMock()
        client.chat.return_value = {"done": True}
        verify_inference(client)
        client.ps.assert_not_called()

    def test_gpu_mode_rejects_cpu_fallback_missing_model_and_unrelated_gpu(self):
        for models in (
            [],
            [{"model": "llama3.1:8b", "size_vram": 0}],
            [{"model": "llama3.1:8b"}],
            [{"model": "nomic-embed-text:latest", "size_vram": 500_000_000}],
        ):
            with self.subTest(models=models):
                client = MagicMock()
                client.chat.return_value = {"done": True, "model": "llama3.1:8b"}
                client.ps.return_value = {"models": models}
                with patch.object(settings, "SETUP_REQUIRE_GPU", True), \
                        self.assertRaisesRegex(RuntimeError, "no GPU memory"):
                    verify_inference(client)

    def test_partial_gpu_offload_is_allowed_but_reported(self):
        client = MagicMock()
        client.ps.return_value = {"models": [
            {"model": "llama3.1:8b", "size": 6_000_000_000, "size_vram": 3_000_000_000},
        ]}
        with patch("builtins.print") as output:
            verify_gpu(client, "llama3.1:8b")
        self.assertTrue(any("partially on GPU" in str(call) for call in output.call_args_list))

    def test_gpu_model_name_accepts_implicit_latest_tag(self):
        client = MagicMock()
        client.ps.return_value = {"models": [{"name": "custom:latest", "size_vram": 100}]}
        verify_gpu(client, "custom")

    def test_gpu_introspection_error_is_not_success(self):
        client = MagicMock()
        client.ps.side_effect = ollama.ResponseError("Unavailable", status_code=503)
        with self.assertRaises(ollama.ResponseError):
            verify_gpu(client, "llama3.1:8b")

    def test_failed_device_check_prevents_ingestion(self):
        with patch("manuals_agent.bootstrap.prepare_manuals", return_value=[MagicMock()]), \
                patch("manuals_agent.bootstrap.ensure_model"), \
                patch("manuals_agent.bootstrap.verify_inference", side_effect=RuntimeError("no GPU memory")), \
                patch("manuals_agent.bootstrap.seed_manuals") as ingest:
            with self.assertRaisesRegex(RuntimeError, "no GPU memory"):
                main()
        ingest.assert_not_called()


if __name__ == "__main__":
    unittest.main()
