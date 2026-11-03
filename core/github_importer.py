# root/core/github_importer.py
import requests
import os
from urllib.parse import urlparse
from requests.exceptions import RequestException

class GitHubImporter:
    GITHUB_RAW_DOMAINS = [
        'raw.githubusercontent.com',
        'gist.githubusercontent.com'
    ]

    @classmethod
    def import_from_url(cls, url):
        try:
            parsed = urlparse(url)
            if parsed.hostname not in cls.GITHUB_RAW_DOMAINS or parsed.port is not None or parsed.username is not None or parsed.password is not None:
                raise ValueError("Only GitHub raw URLs are allowed")
            
            if parsed.scheme != 'https':
                raise ValueError("GitHub raw imports require HTTPS")
            
            # Reject redirects to unapproved hosts instead of following them.
            response = requests.get(url, timeout=10, allow_redirects=False)
            if 300 <= response.status_code < 400:
                raise ValueError("GitHub raw URL redirects are not allowed")
            response.raise_for_status()
            
            if not response.text.strip():
                raise ValueError("Empty script content")
            
            filename = os.path.basename(parsed.path)
            if not filename:
                raise ValueError("Could not determine filename from URL")
            
            name = os.path.splitext(filename)[0]
            code = response.text
            description = f"Imported from GitHub: {url}"
            
            return name, code, description
            
        except RequestException as e:
            raise ValueError(f"Failed to fetch from GitHub: {str(e)}")
        except Exception as e:
            raise ValueError(f"Import error: {str(e)}")