"""Tests for the MCP tool handlers and formatters."""

from __future__ import annotations

import httpx
import pytest
import respx
from conftest import BASE_URL, PLACE, PLACE_IDS, PLACE_SUMMARY, make_review, reviews_body, search_body
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from scrapemapsapi_mcp.client import ScrapeMapsAPIClient
from scrapemapsapi_mcp.tools import REVIEW_TEXT_MAX, cap, register_tools


@pytest.fixture
def tools():
    client = ScrapeMapsAPIClient(api_key="test", base_url=BASE_URL, retry_wait=0)
    server = FastMCP("test")
    register_tools(server, lambda: client)
    return server._tool_manager._tools


def test_cap():
    assert cap(None, 10) == ""
    assert cap("  short \n text ", 50) == "short text"
    out = cap("word " * 100, 50)
    assert len(out) <= 51 and out.endswith("…")


async def test_search_places(tools, mock_api: respx.MockRouter):
    closed = {
        **PLACE_SUMMARY,
        "name": "Old Place",
        "id": None,
        "ids": {**PLACE_IDS, "place_id": None},
        "status": "permanently_closed",
        "rating": None,
    }
    route = mock_api.get("/v1/places/search").respond(
        200, json=search_body([PLACE_SUMMARY, closed], "next123"), headers={"X-Credits-Remaining": "42"}
    )
    out = await tools["search_places"].fn(query="pizza in Naples", limit=50)
    assert route.calls.last.request.url.params["limit"] == "20"  # capped
    assert route.calls.last.request.url.params["language"] == "en"
    assert "region" not in route.calls.last.request.url.params
    assert "1. Pizzeria Da Michele | 4.6★ (52,000 reviews) | Pizza restaurant, Restaurant" in out
    assert f"ref: {PLACE_IDS['place_id']}" in out
    assert f"ref: {PLACE_IDS['cid']}" in out  # falls back to the CID
    assert "PERMANENTLY CLOSED" in out and "no rating" in out
    assert 'cursor="next123"' in out
    assert "remaining: 42" in out


async def test_search_places_empty(tools, mock_api):
    mock_api.get("/v1/places/search").respond(200, json=search_body([]))
    assert "No places found" in await tools["search_places"].fn(query="zzz")


async def test_search_places_lat_without_lng(tools):
    with pytest.raises(ToolError, match="both lat and lng"):
        await tools["search_places"].fn(query="x", lat=1.0)


async def test_get_place(tools, mock_api):
    mock_api.get(f"/v1/places/{PLACE_IDS['place_id']}").respond(
        200,
        json={"data": PLACE, "meta": {"credits_used": 2, "cached": False, "language": "en"}},
        headers={"X-Credits-Used": "2"},
    )
    out = await tools["get_place"].fn(place=PLACE_IDS["place_id"])
    assert out.startswith("Pizzeria Da Michele [credits used: 2]")
    assert "Local name: L'Antica Pizzeria da Michele" in out
    assert "Hours (Open · Closes 3 pm): Mon 11:00–15:00, 18:00–23:00; Tue open 24h; Sun closed" in out
    assert "Phone: +39 081 553 9204" in out
    assert "(+4)" in out  # attributes capped at 8 per group
    assert out.count("https://lh3.example/") == 3  # photos capped
    assert f"cid {PLACE_IDS['cid']}" in out and PLACE_IDS["feature_id"] in out
    description_line = next(line for line in out.splitlines() if line.startswith("Description:"))
    assert len(description_line) < 650


async def test_get_reviews(tools, mock_api):
    long = make_review(2, text="x " * 1000, translated_text=None, language="en", owner_response=None, details={})
    route = mock_api.get("/v1/places/123/reviews").respond(
        200, json=reviews_body([make_review(1), long], "cur2", sort="lowest", original_language="it")
    )
    out = await tools["get_reviews"].fn(place="123", sort="lowest", original_language="it", limit=500, cursor="c1")
    params = route.calls.last.request.url.params
    assert params["limit"] == "50" and params["sort"] == "lowest" and params["cursor"] == "c1"
    assert params["original_language"] == "it"
    assert "2 reviews of 123 (sort: lowest, only written in it)" in out
    assert "- 4★ | 2026-10-01 (translated from it): Great pizza number 1" in out
    assert "details: Food: 5; Service: 4" in out
    assert "owner reply: Thank you so much!" in out
    long_line = next(line for line in out.splitlines() if line.startswith("- 4★ | 2026-10-01: x"))
    assert len(long_line) < REVIEW_TEXT_MAX + 40
    assert 'cursor="cur2"' in out


async def test_get_reviews_last_page(tools, mock_api):
    mock_api.get("/v1/places/123/reviews").respond(200, json=reviews_body([make_review(1)]))
    out = await tools["get_reviews"].fn(place="123")
    assert "No more reviews." in out and "cursor=" not in out


async def test_resolve_place(tools, mock_api):
    mock_api.get("/v1/places/resolve").respond(
        200, json={"data": PLACE_IDS, "meta": {"credits_used": 1, "cached": False}}
    )
    out = await tools["resolve_place"].fn(input="https://maps.app.goo.gl/x")
    assert f"place_id: {PLACE_IDS['place_id']}" in out and "credits used: 1" in out


@pytest.mark.parametrize(
    "status,code,expect",
    [
        (404, "place_not_found", "search_places"),
        (400, "invalid_place_id", "resolve_place"),
        (402, "insufficient_credits", "top up"),
        (401, "invalid_api_key", "SCRAPEMAPSAPI_API_KEY"),
        (503, "upstream_unavailable", "nothing was charged"),
    ],
)
async def test_errors_become_tool_errors(tools, mock_api, status, code, expect):
    mock_api.get("/v1/places/bad").mock(
        return_value=httpx.Response(status, json={"detail": {"error": code, "message": "API says no"}})
    )
    with pytest.raises(ToolError) as ei:
        await tools["get_place"].fn(place="bad")
    assert "API says no" in str(ei.value) and expect in str(ei.value) and code in str(ei.value)
