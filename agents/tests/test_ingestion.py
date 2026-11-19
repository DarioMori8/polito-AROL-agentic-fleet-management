import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.config import settings
from manuals_agent import ingestion


class MemoryStore:
    def __init__(self):
        self.rows = {}
        self.calls = 0
        self.fail = False

    def add(self, ids, chunks, metadatas):
        self.calls += 1
        for index, metadata in zip(ids, metadatas):
            self.rows[index] = metadata
            if self.fail:
                raise RuntimeError("Interrupted embedding batch")

    def delete_document(self, name):
        self.rows = {key: meta for key, meta in self.rows.items() if meta["doc"] != name}

    def count_document(self, name):
        return sum(meta["doc"] == name for meta in self.rows.values())


class IngestionTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.manuals = self.root / "manuals"
        self.manuals.mkdir()
        self.pdf = self.manuals / "15610_manual_EN.pdf"
        self.pdf.write_bytes(b"test PDF contents")
        self.store = MemoryStore()
        self.start_patch(patch.object(settings, "CHROMA_PATH", str(self.root / "index")))
        self.start_patch(patch.object(ingestion, "MANUALS_DIR", self.manuals))
        self.start_patch(patch.object(ingestion, "load_serial_to_machine_id", return_value={"15610": "MCH-0001"}))
        self.start_patch(patch.object(ingestion, "get_vector_store", return_value=self.store))
        self.reset = self.start_patch(patch.object(ingestion, "reset_vector_store", side_effect=self.reset_store))
        self.start_patch(patch.object(ingestion, "extract_pages", return_value=[(1, "a" * 1600)]))

    def start_patch(self, patcher):
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def reset_store(self):
        self.store.rows.clear()
        return self.store

    def manifest(self):
        return json.loads((self.root / "index/ingestion-manifest.json").read_text())

    def test_unchanged_manual_does_not_recompute_embeddings(self):
        ingestion.seed_manuals()
        ingestion.seed_manuals()
        self.assertEqual(self.store.calls, 1)
        self.assertEqual(self.store.count_document(self.pdf.name), 3)

    def test_interrupted_pdf_is_retried_not_marked_complete(self):
        self.store.fail = True
        with self.assertRaisesRegex(RuntimeError, "Interrupted"):
            ingestion.seed_manuals()
        self.assertTrue(self.manifest()["documents"][self.pdf.name]["pending"])
        self.assertEqual(self.store.count_document(self.pdf.name), 1)
        self.store.fail = False
        ingestion.seed_manuals()
        self.assertEqual(self.store.count_document(self.pdf.name), 3)
        self.assertEqual(self.store.calls, 2)

    def test_removed_interrupted_pdf_does_not_leave_stale_chunks(self):
        self.store.fail = True
        with self.assertRaises(RuntimeError):
            ingestion.seed_manuals()
        self.pdf.unlink()
        replacement = self.manuals / "15610_manual_IT.pdf"
        replacement.write_bytes(b"replacement")
        self.store.fail = False
        ingestion.seed_manuals()
        self.assertEqual(self.store.count_document(self.pdf.name), 0)
        self.assertEqual(self.store.count_document(replacement.name), 3)

    def test_changed_pdf_and_missing_index_rows_are_rebuilt(self):
        ingestion.seed_manuals()
        self.pdf.write_bytes(b"updated PDF")
        ingestion.seed_manuals()
        self.store.rows.pop(next(iter(self.store.rows)))
        ingestion.seed_manuals()
        self.assertEqual(self.store.calls, 3)
        self.assertEqual(self.store.count_document(self.pdf.name), 3)

    def test_translations_have_distinct_chunk_ids_and_removed_files_are_pruned(self):
        translated = self.manuals / "15610_manual_IT.pdf"
        translated.write_bytes(b"Italian PDF")
        ingestion.seed_manuals()
        self.assertEqual(len(self.store.rows), 6)
        translated.unlink()
        ingestion.seed_manuals()
        self.assertEqual(len(self.store.rows), 3)
        self.assertNotIn(translated.name, self.manifest()["documents"])

    def test_embedding_model_change_rebuilds_collection(self):
        ingestion.seed_manuals()
        with patch.object(settings, "EMBEDDING_MODEL", "another-model"):
            ingestion.seed_manuals()
        self.assertEqual(self.reset.call_count, 2)
        self.assertEqual(self.store.calls, 2)

    def test_missing_manual_fails_before_index_changes(self):
        with patch.object(ingestion, "load_serial_to_machine_id", return_value={
            "15610": "MCH-0001", "17203": "MCH-0002",
        }):
            with self.assertRaisesRegex(ValueError, "17203"):
                ingestion.prepare_manuals(require_all=True)
        self.reset.assert_not_called()

    def test_empty_folder_invalid_name_unknown_serial_and_unreadable_pdf_fail(self):
        with patch.object(ingestion, "extract_pages", return_value=[(1, "")]):
            with self.assertRaisesRegex(ValueError, "No extractable text"):
                ingestion.seed_manuals()
        self.assertTrue(self.manifest()["documents"][self.pdf.name]["pending"])
        renamed = self.pdf.with_name("wrong.pdf")
        self.pdf.rename(renamed)
        with self.assertRaisesRegex(ValueError, "Invalid filename"):
            ingestion.prepare_manuals()
        renamed.rename(self.manuals / "unknown_manual_EN.pdf")
        with self.assertRaisesRegex(ValueError, "Unknown serial"):
            ingestion.prepare_manuals()
        (self.manuals / "unknown_manual_EN.pdf").unlink()
        with self.assertRaisesRegex(ValueError, "No PDF manuals"):
            ingestion.prepare_manuals()


if __name__ == "__main__":
    unittest.main()
