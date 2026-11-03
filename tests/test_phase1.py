# root/tests/test_phase1.py
"""Regression tests for Phase 1, using no GUI or network dependencies."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.script_generator import MARKER, escape_routeros_string, generate_script
from core.script_manager import ScriptManager


class GeneratorTests(unittest.TestCase):
    def test_header_changes_but_body_is_byte_for_byte_unchanged(self):
        source = '# site - Site name\n:global site "old"\n' + MARKER + '\n/system identity set name=$site\n# $site\n'
        generated = generate_script(source, {"site": "new"})
        self.assertEqual(generated, '# site - Site name\n:global site "new"\n' + MARKER + '\n/system identity set name=$site\n# $site\n')

    def test_overlapping_variable_names(self):
        source = ':global ip "old"\n:global ip2 "old2"\n' + MARKER + '\n:put $ip2'
        result = generate_script(source, {"ip": "new"})
        self.assertIn(':global ip "new"', result)
        self.assertIn(':global ip2 "old2"', result)
        self.assertTrue(result.endswith(':put $ip2'))

    def test_set_declaration(self):
        source = ':set $name "old"\n' + MARKER + '\n:put $name'
        self.assertIn(':set $name "new"', generate_script(source, {"name": "new"}))

    def test_escape_special_characters(self):
        value = 'a"b\\c$d'
        self.assertEqual(escape_routeros_string(value), '"a\\"b\\\\c\\$d"')

    def test_reject_newlines_and_nul(self):
        for value in ('a\nb', 'a\rb', 'a\x00b'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                escape_routeros_string(value)

    def test_reject_missing_and_duplicate_marker(self):
        for source in (':global a "x"', MARKER + MARKER):
            with self.subTest(source=source), self.assertRaises(ValueError):
                generate_script(source, {"a": "y"})

    def test_reject_unknown_or_unsupported_declaration(self):
        for source, params in (
            (':global a 123\n' + MARKER, {"a": "x"}),
            (':global a "x"\n' + MARKER, {"b": "y"}),
            (':global a "x"\n' + MARKER, {"a;bad": "y"}),
        ):
            with self.subTest(source=source), self.assertRaises(ValueError):
                generate_script(source, params)

    def test_preserves_crlf(self):
        source = ':global a "old"\r\n' + MARKER + '\r\n:put $a\r\n'
        self.assertEqual(generate_script(source, {"a": "new"}),
                         ':global a "new"\r\n' + MARKER + '\r\n:put $a\r\n')


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.original_cwd = os.getcwd()
        os.chdir(self.directory.name)
        self.addCleanup(os.chdir, self.original_cwd)
        self.path = Path("data/mikrotik_data.json")

    def test_roundtrip_preserves_legacy_schema(self):
        manager = ScriptManager()
        manager.scripts["sample"] = {
            "code": ':global x "old"\n' + MARKER, "description": "test", "category": "Ops"
        }
        manager.categories["Ops"] = ["sample"]
        manager.dark_mode = True
        manager.save_data()
        reloaded = ScriptManager()
        self.assertEqual(reloaded.scripts, manager.scripts)
        self.assertEqual(reloaded.categories, manager.categories)
        self.assertTrue(reloaded.dark_mode)

    def test_corrupt_library_blocks_startup_without_overwriting(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{broken", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "original file was not changed"):
            ScriptManager()
        self.assertEqual(self.path.read_text(encoding="utf-8"), "{broken")

    def test_second_save_rotates_valid_backup(self):
        manager = ScriptManager()
        manager.save_data()
        old = self.path.read_bytes()
        manager.dark_mode = True
        manager.save_data()
        self.assertEqual((self.path.parent / (self.path.name + ".bak")).read_bytes(), old)
        self.assertTrue(json.loads(self.path.read_text(encoding="utf-8"))["dark_mode"])

    def test_corrupt_existing_file_cannot_be_overwritten(self):
        manager = ScriptManager()
        manager.save_data()
        self.path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(ValueError):
            manager.save_data()
        self.assertEqual(self.path.read_text(encoding="utf-8"), "{broken")

    def test_atomic_replace_failure_preserves_original(self):
        manager = ScriptManager()
        manager.save_data()
        before = self.path.read_bytes()
        manager.dark_mode = True
        original_replace = os.replace

        def fail_on_primary(src, dst):
            if os.fspath(dst) == os.fspath(self.path):
                raise OSError("simulated disk failure")
            return original_replace(src, dst)

        with patch("core.script_manager.os.replace", side_effect=fail_on_primary):
            with self.assertRaisesRegex(OSError, "simulated"):
                manager.save_data()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(list(self.path.parent.glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()
