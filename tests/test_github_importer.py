# root/tests/test_github_importer.py
"""Offline tests for bounded, restricted GitHub raw imports."""
import unittest
from unittest.mock import patch

from core.github_importer import GitHubImporter


class FakeResponse:
    def __init__(self, chunks=(b':put "ok"',), status=200, headers=None):
        self.chunks = chunks
        self.status_code = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise __import__("requests").exceptions.HTTPError("HTTP failure")

    def iter_content(self, chunk_size):
        yield from self.chunks


class GitHubImportTests(unittest.TestCase):
    URL = "https://raw.githubusercontent.com/owner/repo/main/script.rsc"

    def test_valid_import(self):
        with patch("core.github_importer.requests.get", return_value=FakeResponse()):
            name, code, description = GitHubImporter.import_from_url(self.URL)
        self.assertEqual(name, "script")
        self.assertEqual(code, ':put "ok"')
        self.assertIn(self.URL, description)

    def test_invalid_hosts_and_protocols_do_not_trigger_network(self):
        urls = (
            "http://raw.githubusercontent.com/owner/repo/main/script.rsc",
            "https://raw.githubusercontent.com.evil.example/script.rsc",
            "https://user:pass@raw.githubusercontent.com/script.rsc",
            "https://raw.githubusercontent.com:444/script.rsc",
            "https://example.com/script.rsc",
        )
        with patch("core.github_importer.requests.get") as get:
            for url in urls:
                with self.subTest(url=url), self.assertRaises(ValueError):
                    GitHubImporter.import_from_url(url)
            get.assert_not_called()

    def test_redirect_rejected(self):
        with patch("core.github_importer.requests.get", return_value=FakeResponse(status=302)):
            with self.assertRaisesRegex(ValueError, "redirect"):
                GitHubImporter.import_from_url(self.URL)

    def test_declared_oversize_rejected(self):
        response = FakeResponse(headers={"Content-Length": str(GitHubImporter.MAX_SCRIPT_BYTES + 1)})
        with patch("core.github_importer.requests.get", return_value=response):
            with self.assertRaisesRegex(ValueError, "2 MiB"):
                GitHubImporter.import_from_url(self.URL)

    def test_streamed_oversize_rejected(self):
        response = FakeResponse(chunks=(b"a" * GitHubImporter.MAX_SCRIPT_BYTES, b"b"))
        with patch("core.github_importer.requests.get", return_value=response):
            with self.assertRaisesRegex(ValueError, "2 MiB"):
                GitHubImporter.import_from_url(self.URL)

    def test_invalid_utf8_and_empty_rejected(self):
        for payload in (b"\xff", b"  \n"):
            with self.subTest(payload=payload):
                with patch("core.github_importer.requests.get", return_value=FakeResponse(chunks=(payload,))):
                    with self.assertRaises(ValueError):
                        GitHubImporter.import_from_url(self.URL)

    def test_request_is_bounded_and_no_redirects(self):
        with patch("core.github_importer.requests.get", return_value=FakeResponse()) as get:
            GitHubImporter.import_from_url(self.URL)
        self.assertFalse(get.call_args.kwargs["allow_redirects"])
        self.assertTrue(get.call_args.kwargs["stream"])
        self.assertEqual(get.call_args.kwargs["timeout"], (5, 15))


if __name__ == "__main__":
    unittest.main()
