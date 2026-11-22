"""Typed errors for the ScrapeMapsAPI API, with messages written for an AI assistant."""

from __future__ import annotations

from typing import Any, Optional

import httpx

BILLING_URL = "https://scrapemapsapi.com/dashboard/billing"
API_KEYS_URL = "https://scrapemapsapi.com/dashboard/api-keys"


class ScrapeMapsAPIError(Exception):
    """Base error for the ScrapeMapsAPI API."""

    hint: str = ""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        code: Optional[str] = None,
        retry_after: Optional[float] = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        self.retry_after = retry_after
        super().__init__(message)

    def for_tool(self) -> str:
        """Readable message for a tool error: what happened and what to do next."""
        parts = [self.message.rstrip(".") + "."]
        if self.code:
            parts.append(f"(error: {self.code})")
        if self.hint:
            parts.append(self.hint)
        if self.retry_after:
            parts.append(f"Retry after {int(self.retry_after)} seconds.")
        return " ".join(parts)


class InvalidRequestError(ScrapeMapsAPIError):
    hint = (
        "Pass a place ID (ChIJ...), a CID (digits) or a feature ID (0x...:0x...); "
        "for a Google Maps URL use resolve_place first."
    )


class AuthenticationError(ScrapeMapsAPIError):
    hint = f"Check the SCRAPEMAPSAPI_API_KEY environment variable of the MCP server ({API_KEYS_URL})."


class InsufficientCreditsError(ScrapeMapsAPIError):
    hint = f"The account is out of credits: the user can top up at {BILLING_URL}."


class NotFoundError(ScrapeMapsAPIError):
    hint = "Check the identifier, or find the place with search_places."


class RateLimitError(ScrapeMapsAPIError):
    hint = "Too many requests: wait before calling again."


class UpstreamError(ScrapeMapsAPIError):
    hint = "Temporary problem with Google Maps; nothing was charged. Try again in a minute."


class ServiceUnavailableError(UpstreamError):
    pass


class ConnectionFailedError(ScrapeMapsAPIError):
    hint = "The ScrapeMapsAPI API could not be reached. Check the network or SCRAPEMAPSAPI_BASE_URL."


_CODE_MAP: dict[str, type[ScrapeMapsAPIError]] = {
    "invalid_place_id": InvalidRequestError,
    "invalid_cursor": InvalidRequestError,
    "invalid_location": InvalidRequestError,
    "validation_error": InvalidRequestError,
    "missing_api_key": AuthenticationError,
    "invalid_api_key": AuthenticationError,
    "insufficient_credits": InsufficientCreditsError,
    "insufficient_credits_retry_later": InsufficientCreditsError,
    "place_not_found": NotFoundError,
    "rate_limited": RateLimitError,
    "rate_limit_exceeded": RateLimitError,
    "upstream_error": UpstreamError,
    "upstream_unavailable": ServiceUnavailableError,
}

_STATUS_MAP: dict[int, type[ScrapeMapsAPIError]] = {
    400: InvalidRequestError,
    401: AuthenticationError,
    402: InsufficientCreditsError,
    404: NotFoundError,
    422: InvalidRequestError,
    429: RateLimitError,
    502: UpstreamError,
    503: ServiceUnavailableError,
}


def _parse(status: int, body: Any, text: str) -> tuple[Optional[str], str]:
    code: Optional[str] = None
    message = text.strip()[:300] or f"HTTP {status}"
    if isinstance(body, dict):
        detail = body.get("detail", body)
        if isinstance(detail, dict):
            code = detail.get("error") if isinstance(detail.get("error"), str) else None
            if isinstance(detail.get("message"), str):
                message = detail["message"]
        elif isinstance(detail, list):  # FastAPI 422
            code = "validation_error"
            msgs = []
            for item in detail:
                if isinstance(item, dict):
                    loc = ".".join(str(p) for p in item.get("loc", []) if p not in ("query", "path"))
                    msgs.append(f"{loc}: {item.get('msg', 'invalid value')}" if loc else str(item.get("msg")))
            if msgs:
                message = "Invalid parameters: " + "; ".join(msgs)
        elif isinstance(detail, str):
            message = detail
    return code, message


def error_from_response(response: httpx.Response) -> ScrapeMapsAPIError:
    try:
        body: Any = response.json()
    except Exception:
        body = None
    code, message = _parse(response.status_code, body, response.text if body is None else "")
    # 5xx: the status decides (an upstream code such as "rate_limited" is not a client rate limit).
    by_code = _CODE_MAP.get(code or "") if response.status_code < 500 else None
    cls = by_code or _STATUS_MAP.get(response.status_code, ScrapeMapsAPIError)
    retry_after: Optional[float] = None
    try:
        retry_after = float(response.headers.get("retry-after", ""))
    except ValueError:
        pass
    return cls(message, status_code=response.status_code, code=code, retry_after=retry_after)


def raise_for_status(response: httpx.Response) -> None:
    if not response.is_success:
        raise error_from_response(response)
