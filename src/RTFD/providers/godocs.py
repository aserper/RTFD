"""GoDocs package metadata provider."""

from __future__ import annotations

from typing import Any, Callable, Dict

import httpx
from bs4 import BeautifulSoup

from ..utils import serialize_response
from .base import BaseProvider, ProviderMetadata, ProviderResult


class GoDocsProvider(BaseProvider):
    """Provider for GoDocs package metadata."""

    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="godocs",
            description="GoDocs package documentation metadata",
            expose_as_tool=True,
            tool_names=["godocs_metadata"],
            supports_library_search=True,
            required_env_vars=[],
            optional_env_vars=[],
        )

    async def search_library(self, library: str, limit: int = 5) -> ProviderResult:
        """Search GoDocs for library metadata."""
        try:
            data = await self._fetch_metadata(library)
            return ProviderResult(success=True, data=data, provider_name="godocs")
        except httpx.HTTPStatusError as exc:
            # 404 is expected for non-Go packages - don't report as error
            if exc.response.status_code == 404:
                return ProviderResult(success=False, error=None, provider_name="godocs")
            error_msg = f"GoDocs returned {exc.response.status_code}"
            return ProviderResult(success=False, error=error_msg, provider_name="godocs")
        except httpx.HTTPError as exc:
            error_msg = f"GoDocs request failed: {exc}"
            return ProviderResult(success=False, error=error_msg, provider_name="godocs")
        except Exception:
            # Parsing errors - silent fail
            return ProviderResult(success=False, error=None, provider_name="godocs")

    async def _fetch_metadata(self, package: str) -> Dict[str, Any]:
        """Scrape package metadata from godocs.io."""
        # Handle full URLs or just package paths
        if package.startswith("https://godocs.io/"):
            package = package.replace("https://godocs.io/", "")

        # godocs.io seems to block standard browser User-Agents but allows curl.
        # We'll use a curl-like User-Agent for this specific request.
        url = f"https://godocs.io/{package}"
        headers = {"User-Agent": "curl/7.68.0"}
        async with await self._http_client() as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

        # Extract description/synopsis
        description = ""

        # Try meta description first
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            description = meta_desc.get("content", "")

        # If meta description is missing or generic, try parsing the body
        # The structure is usually: <h2 id="pkg-overview">...</h2> <p>import ...</p> <p>Description...</p>
        if not description or "godocs.io" in description:
            overview_header = soup.find(["h2", "h3"], {"id": "pkg-overview"})
            if overview_header:
                # Look at next siblings
                for sibling in overview_header.find_next_siblings():
                    if sibling.name in ("h2", "h3"):  # Stop at next section
                        break
                    if sibling.name == "p":
                        text = sibling.get_text(strip=True)
                        # Skip the import statement
                        if text.startswith("import \""):
                            continue
                        description = text
                        break

        return {
            "name": package,
            "summary": description,
            "url": url,
            "source_url": f"https://pkg.go.dev/{package}",  # godocs often mirrors standard paths
        }

    def get_tools(self) -> Dict[str, Callable]:
        """Return MCP tool functions."""

        async def godocs_metadata(package: str) -> str:
            """Retrieve Go package documentation metadata from godocs.io. Returns data in TOON format."""
            result = await self._fetch_metadata(package)
            return serialize_response(result)

        return {"godocs_metadata": godocs_metadata}
