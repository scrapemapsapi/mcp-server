"""ScrapeMapsAPI MCP server entry point."""

from __future__ import annotations

import os
import sys

from mcp.server.fastmcp import FastMCP

from .client import DEFAULT_BASE_URL, ScrapeMapsAPIClient
from .errors import API_KEYS_URL
from .prompts import register_prompts
from .resources import register_resources
from .tools import register_tools

API_KEY_ENV = "SCRAPEMAPSAPI_API_KEY"
BASE_URL_ENV = "SCRAPEMAPSAPI_BASE_URL"

mcp = FastMCP(
    "ScrapeMapsAPI",
    instructions=(
        "Google Maps places and reviews via the ScrapeMapsAPI API. Use search_places to find places "
        "by text (optionally near lat/lng), get_place for full details and opening hours, "
        "get_reviews to read reviews page by page (follow the cursor; sort and language filters "
        "available) and resolve_place to turn a Google Maps URL into place identifiers. "
        "Calls cost credits: request only what the task needs."
    ),
)

# Lazy-init client so import doesn't fail without env var (tests, --help, etc.)
_client: ScrapeMapsAPIClient | None = None


def _get_client() -> ScrapeMapsAPIClient:
    global _client
    if _client is None:
        api_key = os.environ.get(API_KEY_ENV, "")
        if not api_key:
            print(
                f"Error: {API_KEY_ENV} environment variable is required.\nGet your API key at {API_KEYS_URL}",
                file=sys.stderr,
            )
            sys.exit(1)
        base_url = os.environ.get(BASE_URL_ENV) or DEFAULT_BASE_URL
        _client = ScrapeMapsAPIClient(api_key=api_key, base_url=base_url)
    return _client


register_tools(mcp, _get_client)
register_resources(mcp)
register_prompts(mcp)


def main() -> None:
    """Run the MCP server (stdio transport)."""
    _get_client()  # fail fast if the key is missing
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
