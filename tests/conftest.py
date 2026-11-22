"""Shared fixtures for MCP server tests."""

from __future__ import annotations

from typing import Any

import pytest
import respx

from scrapemapsapi_mcp.client import ScrapeMapsAPIClient

BASE_URL = "https://api.test.scrapemapsapi"

PLACE_IDS = {
    "place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4",
    "cid": "10281119596374313554",
    "feature_id": "0x6b12ae37b4b75b37:0x8eadf8dc1b32ca52",
    "google_maps_url": "https://www.google.com/maps?cid=10281119596374313554",
}

PLACE_SUMMARY: dict[str, Any] = {
    "id": PLACE_IDS["place_id"],
    "ids": PLACE_IDS,
    "name": "Pizzeria Da Michele",
    "categories": ["Pizza restaurant", "Restaurant"],
    "address": {"formatted": "Via Cesare Sersale, 1, 80139 Napoli NA, Italy", "city": "Napoli"},
    "location": {"lat": 40.8497, "lng": 14.2635},
    "rating": 4.6,
    "review_count": 52000,
    "phone": "081 553 9204",
    "website": "https://damichele.net",
    "status": "operational",
}

PLACE: dict[str, Any] = {
    **PLACE_SUMMARY,
    "local_name": "L'Antica Pizzeria da Michele",
    "phone_international": "+39 081 553 9204",
    "plus_code": "RQ2G+V9 Napoli",
    "timezone": "Europe/Rome",
    "description": "Historic pizzeria. " * 100,
    "opening_hours": {
        "weekly": [
            {
                "day": "monday",
                "closed": False,
                "open_24h": False,
                "periods": [{"open": "11:00", "close": "15:00"}, {"open": "18:00", "close": "23:00"}],
                "text": None,
            },
            {"day": "tuesday", "closed": False, "open_24h": True, "periods": [], "text": None},
            {"day": "sunday", "closed": True, "open_24h": False, "periods": [], "text": "Closed"},
        ],
        "status_text": "Open · Closes 3 pm",
    },
    "attributes": {"Accessibility": [f"feature {i}" for i in range(12)]},
    "photos": [{"url": f"https://lh3.example/p{i}", "width": 800, "height": 600} for i in range(5)],
    "booking_links": [{"url": "https://book.example/x", "domain": "book.example"}],
    "knowledge_graph_id": "/g/11b6",
}


def make_review(i: int, **over: Any) -> dict[str, Any]:
    return {
        "id": f"rev{i}",
        "rating": 4,
        "published_at": "2026-10-01T12:00:00Z",
        "relative_date": "a month ago",
        "language": "it",
        "text": f"Ottima pizza numero {i}",
        "translated_text": f"Great pizza number {i}",
        "author": {"id": f"a{i}"},
        "owner_response": {"text": "Grazie mille!", "translated_text": "Thank you so much!", "relative_date": None},
        "photos": [],
        "details": {"Food": "5", "Service": "4"},
        "source": "Google",
        **over,
    }


def reviews_body(reviews: list[dict], next_cursor: str | None = None, **meta: Any) -> dict[str, Any]:
    return {
        "data": reviews,
        "pagination": {"next_cursor": next_cursor, "has_more": next_cursor is not None},
        "meta": {
            "credits_used": (len(reviews) + 1) // 2,
            "cached": False,
            "place_id": PLACE_IDS["place_id"],
            "cid": PLACE_IDS["cid"],
            "sort": "newest",
            "language": "en",
            "original_language": None,
            **meta,
        },
    }


def search_body(places: list[dict], next_cursor: str | None = None) -> dict[str, Any]:
    return {
        "data": places,
        "pagination": {"next_cursor": next_cursor, "has_more": next_cursor is not None},
        "meta": {"credits_used": len(places), "cached": False, "query": "pizza", "language": "en", "region": "us"},
    }


@pytest.fixture
def mock_api():
    """respx router scoped to the test base URL."""
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
        yield router


@pytest.fixture
def client():
    return ScrapeMapsAPIClient(api_key="test_key", base_url=BASE_URL, retry_wait=0)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    import scrapemapsapi_mcp.client as client_mod

    async def instant(_: float) -> None:
        return None

    monkeypatch.setattr(client_mod.asyncio, "sleep", instant)
