"""Integration tests: the server registers every component and runs them over MCP."""

from __future__ import annotations

import importlib
import os
from unittest.mock import patch

import pytest
from mcp.server.fastmcp import FastMCP


@pytest.fixture
def server():
    with patch.dict(os.environ, {"SCRAPEMAPSAPI_API_KEY": "test_integration"}):
        import scrapemapsapi_mcp.server as srv_mod

        importlib.reload(srv_mod)
        yield srv_mod.mcp


async def test_tools(server: FastMCP):
    tools = {t.name: t for t in await server.list_tools()}
    assert set(tools) == {"search_places", "get_place", "get_reviews", "resolve_place"}
    for tool in tools.values():
        assert tool.description
        assert tool.annotations is not None and tool.annotations.readOnlyHint is True
    sort = tools["get_reviews"].inputSchema["properties"]["sort"]
    assert set(sort["enum"]) == {"relevant", "newest", "highest", "lowest"}
    assert tools["search_places"].inputSchema["required"] == ["query"]


async def test_resources(server: FastMCP):
    uris = {str(r.uri) for r in await server.list_resources()}
    assert uris == {
        "scrapemapsapi://docs/api-reference",
        "scrapemapsapi://docs/quickstart",
        "scrapemapsapi://docs/pricing",
        "scrapemapsapi://docs/examples",
    }
    contents = await server.read_resource("scrapemapsapi://docs/api-reference")
    assert "/v1/places/{place}/reviews" in next(iter(contents)).content


async def test_prompts(server: FastMCP):
    names = {p.name for p in await server.list_prompts()}
    assert names == {"summarize_reviews", "compare_places", "find_best_places"}
    result = await server.get_prompt("summarize_reviews", {"place": "Da Michele, Naples", "language": "it"})
    text = result.messages[0].content.text
    assert "get_reviews" in text and "Da Michele, Naples" in text
    result = await server.get_prompt("compare_places", {"places": "A, Rome; B, Milan"})
    assert "- A, Rome\n- B, Milan" in result.messages[0].content.text


async def test_missing_key_exits(monkeypatch):
    import scrapemapsapi_mcp.server as srv_mod

    monkeypatch.delenv("SCRAPEMAPSAPI_API_KEY", raising=False)
    monkeypatch.setattr(srv_mod, "_client", None)
    with pytest.raises(SystemExit):
        srv_mod._get_client()


def test_base_url_env(monkeypatch):
    import scrapemapsapi_mcp.server as srv_mod

    monkeypatch.setenv("SCRAPEMAPSAPI_API_KEY", "k")
    monkeypatch.setenv("SCRAPEMAPSAPI_BASE_URL", "http://localhost:8000/")
    monkeypatch.setattr(srv_mod, "_client", None)
    assert srv_mod._get_client().base_url == "http://localhost:8000"
