"""Actual filesystem operations, including Windows canonical temporary paths."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.knowledge import Storage, settings


class LocalStorageTests(unittest.TestCase):
    def test_configured_root_is_canonical_and_nested_content_roundtrips(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(settings, "KNOWLEDGE_STORAGE_BACKEND", "local"), patch.object(settings, "KNOWLEDGE_STORAGE_PATH", directory):
            store = Storage()
            self.assertEqual(store.local, Path(directory).resolve())
            store.put("staging/nested/upload.md", b"durable content")
            self.assertTrue(store.exists("staging/nested/upload.md"))
            self.assertEqual(store.get("staging/nested/upload.md"), b"durable content")
            store.remove("staging/nested/upload.md")
            self.assertFalse(store.exists("staging/nested/upload.md"))

    def test_traversal_absolute_paths_and_root_never_escape_boundary(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(settings, "KNOWLEDGE_STORAGE_BACKEND", "local"), patch.object(settings, "KNOWLEDGE_STORAGE_PATH", str(Path(directory) / "root")):
            store = Storage()
            outside = Path(directory) / "outside.md"
            outside.write_bytes(b"keep")
            for key in ["../outside.md", str(outside), "."]:
                with self.subTest(key=key):
                    with self.assertRaisesRegex(ValueError, "invalid storage key"):
                        store.put(key, b"overwrite")
                    with self.assertRaisesRegex(ValueError, "invalid storage key"):
                        store.get(key)
                    self.assertFalse(store.exists(key))
                    store.remove(key)
                    self.assertEqual(outside.read_bytes(), b"keep")
