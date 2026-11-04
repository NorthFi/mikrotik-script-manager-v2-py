# root/core/github_importer.py
"""Bounded HTTPS-only imports from GitHub raw file hosts."""
import os
from urllib.parse import urlparse

import requests
from requests.exceptions import RequestException


class GitHubImporter:
    GITHUB_RAW_DOMAINS = frozenset({
        "raw.githubusercontent.com",
        "gist.githubusercontent.com",
    })
    MAX_SCRIPT_BYTES = 2 * 1024 * 1024

    @classmethod
    def import_from_url(cls, url):
        parsed = urlparse(url)
        if (parsed.scheme != "https" or
                parsed.hostname not in cls.GITHUB_RAW_DOMAINS or
                parsed.port is not None or
                parsed.username is not None or
                parsed.password is not None):
            raise ValueError("Only HTTPS GitHub raw URLs without credentials or custom ports are allowed")

        filename = os.path.basename(parsed.path)
        if not filename:
            raise ValueError("Could not determine filename from URL")

        try:
            with requests.get(
                url, timeout=(5, 15), allow_redirects=False, stream=True
            ) as response:
                if 300 <= response.status_code < 400:
                    raise ValueError("GitHub raw URL redirects are not allowed")
                response.raise_for_status()
                declared = response.headers.get("Content-Length")
                if declared is not None:
                    try:
                        if int(declared) > cls.MAX_SCRIPT_BYTES:
                            raise ValueError("Script exceeds the 2 MiB import limit")
                    except (TypeError, ValueError) as exc:
                        if isinstance(exc, ValueError) and str(exc).startswith("Script exceeds"):
                            raise
                        raise ValueError("Invalid Content-Length from GitHub") from exc

                payload = bytearray()
                for chunk in response.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    if len(payload) + len(chunk) > cls.MAX_SCRIPT_BYTES:
                        raise ValueError("Script exceeds the 2 MiB import limit")
                    payload.extend(chunk)
        except RequestException as exc:
            raise ValueError("Failed to fetch from GitHub: " + str(exc)) from exc

        try:
            code = bytes(payload).decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("GitHub script is not valid UTF-8") from exc
        if not code.strip():
            raise ValueError("Empty script content")

        name = os.path.splitext(filename)[0]
        return name, code, "Imported from GitHub: " + url
