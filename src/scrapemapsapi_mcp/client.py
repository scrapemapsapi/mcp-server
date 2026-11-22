"""Async HTTP client for the ScrapeMapsAPI REST API (kept dependency-free on purpose)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import quote

import httpx

from . import __version__
from .errors import ConnectionFailedError, ScrapeMapsAPIError, error_from_response

DEFAULT_BASE_URL = "https://api.scrapemapsapi.com"
DEFAULT_TIMEOUT = 60.0
RETRY_STATUSES = frozenset({429, 502, 503})
NO_RETRY_CODES = frozenset({"insufficient_credits_retry_later"})


@dataclass
class ApiResult:
    """Parsed JSON body plus the billing headers."""

    body: dict[str, Any]
    credits_used: Optional[int] = None
    credits_remaining: Optional[int] = None

    @property
    def data(self) -> Any:
        return self.body.get("data")

    @property
    def pagination(self) -> dict[str, Any]:
        return self.body.get("pagination") or {}

    @property
    def meta(self) -> dict[str, Any]:
        return self.body.get("meta") or {}


def _int(value: Optional[str]) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def place_path(place: str, suffix: str = "") -> str:
    return f"/v1/places/{quote(place.strip(), safe='')}{suffix}"


class ScrapeMapsAPIClient:
    """Async wrapper around the ScrapeMapsAPI REST API, with a short retry on 429/502/503."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        max_retries: int = 1,
        retry_wait: float = 1.0,
        max_retry_wait: float = 10.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.retry_wait = retry_wait
        self.max_retry_wait = max_retry_wait
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "X-API-Key": api_key,
                "Accept": "application/json",
                "User-Agent": f"scrapemapsapi-mcp/{__version__}",
            },
            timeout=DEFAULT_TIMEOUT,
            transport=transport,
        )

    async def _get(self, path: str, params: dict[str, Any]) -> ApiResult:
        params = {k: v for k, v in params.items() if v is not None}
        attempt = 0
        while True:
            try:
                response = await self._client.get(path, params=params)
            except httpx.TransportError as e:
                if attempt >= self.max_retries:
                    raise ConnectionFailedError(f"Could not reach {self.base_url}: {e}") from e
                wait = self.retry_wait
            else:
                if response.is_success:
                    try:
                        body = response.json()
                    except ValueError as e:
                        raise ScrapeMapsAPIError("The API returned invalid JSON", response.status_code) from e
                    return ApiResult(
                        body=body if isinstance(body, dict) else {"data": body},
                        credits_used=_int(response.headers.get("x-credits-used")),
                        credits_remaining=_int(response.headers.get("x-credits-remaining")),
                    )
                error = error_from_response(response)
                if (
                    attempt >= self.max_retries
                    or response.status_code not in RETRY_STATUSES
                    or error.code in NO_RETRY_CODES
                    or (error.retry_after or 0) > self.max_retry_wait
                ):
                    raise error
                wait = error.retry_after if error.retry_after is not None else self.retry_wait
            attempt += 1
            await asyncio.sleep(wait)

    async def search(
        self,
        query: str,
        *,
        language: Optional[str] = None,
        region: Optional[str] = None,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        radius_km: Optional[float] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> ApiResult:
        return await self._get(
            "/v1/places/search",
            {
                "q": query,
                "language": language,
                "region": region,
                "lat": lat,
                "lng": lng,
                "radius_km": radius_km,
                "limit": limit,
                "cursor": cursor,
            },
        )

    async def get_place(self, place: str, *, language: Optional[str] = None, region: Optional[str] = None) -> ApiResult:
        return await self._get(place_path(place), {"language": language, "region": region})

    async def get_reviews(
        self,
        place: str,
        *,
        sort: Optional[str] = None,
        language: Optional[str] = None,
        original_language: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> ApiResult:
        return await self._get(
            place_path(place, "/reviews"),
            {
                "sort": sort,
                "language": language,
                "original_language": original_language,
                "limit": limit,
                "cursor": cursor,
            },
        )

    async def resolve(self, input: str) -> ApiResult:
        return await self._get("/v1/places/resolve", {"input": input})

    async def close(self) -> None:
        await self._client.aclose()
