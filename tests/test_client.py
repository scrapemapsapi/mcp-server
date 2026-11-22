"""Tests for the async HTTP client."""

from __future__ import annotations

import httpx
import pytest
import respx
from conftest import PLACE, PLACE_IDS, PLACE_SUMMARY, make_review, reviews_body, search_body

from scrapemapsapi_mcp.client import ScrapeMapsAPIClient
from scrapemapsapi_mcp.errors import (
    AuthenticationError,
    ConnectionFailedError,
    InsufficientCreditsError,
    InvalidRequestError,
    NotFoundError,
    RateLimitError,
    ScrapeMapsAPIError,
    ServiceUnavailableError,
    UpstreamError,
)


def err(status: int, code: str, message: str = "boom", headers: dict | None = None, **extra) -> httpx.Response:
    return httpx.Response(status, json={"detail": {"error": code, "message": message, **extra}}, headers=headers)


async def test_search(mock_api: respx.MockRouter, client: ScrapeMapsAPIClient):
    route = mock_api.get("/v1/places/search").respond(
        200, json=search_body([PLACE_SUMMARY], "c1"), headers={"X-Credits-Used": "1", "X-Credits-Remaining": "99"}
    )
    result = await client.search("pizza", region="it", limit=5)
    req = route.calls.last.request
    assert dict(req.url.params) == {"q": "pizza", "region": "it", "limit": "5"}
    assert req.headers["X-API-Key"] == "test_key"
    assert req.headers["User-Agent"].startswith("scrapemapsapi-mcp/")
    assert result.data[0]["name"] == "Pizzeria Da Michele"
    assert result.pagination["next_cursor"] == "c1"
    assert result.credits_used == 1 and result.credits_remaining == 99


async def test_get_place_encodes_feature_id(mock_api, client):
    route = mock_api.get(url__regex=r".*/v1/places/0x.*").respond(
        200, json={"data": PLACE, "meta": {"credits_used": 2, "cached": False, "language": "en"}}
    )
    result = await client.get_place(PLACE_IDS["feature_id"], language="it")
    assert route.calls.last.request.url.raw_path.startswith(b"/v1/places/0x6b12ae37b4b75b37%3A0x8eadf8dc1b32ca52")
    assert result.data["timezone"] == "Europe/Rome"


async def test_get_reviews(mock_api, client):
    route = mock_api.get("/v1/places/123/reviews").respond(200, json=reviews_body([make_review(1)]))
    result = await client.get_reviews("123", sort="newest", original_language="it", limit=10, cursor="abc")
    assert dict(route.calls.last.request.url.params) == {
        "sort": "newest",
        "original_language": "it",
        "limit": "10",
        "cursor": "abc",
    }
    assert result.data[0]["id"] == "rev1"


async def test_resolve(mock_api, client):
    route = mock_api.get("/v1/places/resolve").respond(
        200, json={"data": PLACE_IDS, "meta": {"credits_used": 0, "cached": False}}
    )
    result = await client.resolve("https://maps.app.goo.gl/x")
    assert route.calls.last.request.url.params["input"] == "https://maps.app.goo.gl/x"
    assert result.data["cid"] == PLACE_IDS["cid"]


@pytest.mark.parametrize(
    "status,code,cls",
    [
        (400, "invalid_place_id", InvalidRequestError),
        (401, "invalid_api_key", AuthenticationError),
        (402, "insufficient_credits", InsufficientCreditsError),
        (404, "place_not_found", NotFoundError),
        (429, "insufficient_credits_retry_later", InsufficientCreditsError),
        (502, "upstream_error", UpstreamError),
        (502, "proxy_error", UpstreamError),
        (502, "rate_limited", UpstreamError),
        (418, "teapot", ScrapeMapsAPIError),
    ],
)
async def test_errors(mock_api, client, status, code, cls):
    route = mock_api.get("/v1/places/resolve").mock(return_value=err(status, code, "explained"))
    with pytest.raises(cls) as ei:
        await client.resolve("x")
    assert type(ei.value) is cls and ei.value.code == code and ei.value.message == "explained"
    assert route.call_count == (2 if status == 502 else 1)  # only 502 is retried (once)


async def test_422(mock_api, client):
    mock_api.get("/v1/places/search").respond(
        422, json={"detail": [{"loc": ["query", "limit"], "msg": "Input should be <= 20"}]}
    )
    with pytest.raises(InvalidRequestError, match="limit: Input should be <= 20"):
        await client.search("x", limit=50)


async def test_retries_once_then_succeeds(mock_api, client):
    route = mock_api.get("/v1/places/resolve").mock(
        side_effect=[
            err(503, "upstream_unavailable"),
            httpx.Response(200, json={"data": PLACE_IDS, "meta": {"credits_used": 0, "cached": False}}),
        ]
    )
    await client.resolve("x")
    assert route.call_count == 2


async def test_retry_gives_up(mock_api, client):
    route = mock_api.get("/v1/places/resolve").mock(
        side_effect=[
            err(429, "rate_limited", headers={"Retry-After": "1"}),
            err(429, "rate_limited", headers={"Retry-After": "1"}),
        ]
    )
    with pytest.raises(RateLimitError) as ei:
        await client.resolve("x")
    assert ei.value.retry_after == 1.0 and route.call_count == 2


async def test_long_retry_after_not_waited(mock_api, client):
    route = mock_api.get("/v1/places/resolve").mock(
        return_value=err(503, "upstream_unavailable", headers={"Retry-After": "600"})
    )
    with pytest.raises(ServiceUnavailableError):
        await client.resolve("x")
    assert route.call_count == 1


async def test_connection_error(mock_api, client):
    mock_api.get("/v1/places/resolve").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(ConnectionFailedError, match="Could not reach"):
        await client.resolve("x")


def test_for_tool_message():
    e = InsufficientCreditsError("Insufficient credits. Please purchase more credits.", 402, "insufficient_credits")
    text = e.for_tool()
    assert "insufficient_credits" in text and "dashboard/billing" in text
    assert "Retry after 30 seconds" in RateLimitError("slow", 429, "rate_limited", retry_after=30).for_tool()
