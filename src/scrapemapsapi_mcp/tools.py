"""MCP tools for ScrapeMapsAPI.

Responses are compact text for an LLM: the useful fields only, long texts capped, and every
identifier needed for the next call (place ID / CID, next cursor) spelled out.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from .client import ApiResult, ScrapeMapsAPIClient
from .errors import ScrapeMapsAPIError

REVIEW_TEXT_MAX = 600
OWNER_RESPONSE_MAX = 200
DESCRIPTION_MAX = 600
ATTRIBUTE_GROUPS_MAX = 8
ATTRIBUTE_ITEMS_MAX = 8
PHOTOS_MAX = 3
SEARCH_LIMIT_MAX = 20
REVIEWS_LIMIT_MAX = 50  # the API allows 100; 50 keeps one tool result readable

_DAY_ABBR = {
    "monday": "Mon",
    "tuesday": "Tue",
    "wednesday": "Wed",
    "thursday": "Thu",
    "friday": "Fri",
    "saturday": "Sat",
    "sunday": "Sun",
}

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)


def cap(text: Optional[str], limit: int) -> str:
    """Collapse whitespace and cut to ``limit`` characters on a word boundary."""
    if not text:
        return ""
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    cut = flat[:limit].rsplit(" ", 1)[0] if " " in flat[:limit] else flat[:limit]
    return cut.rstrip(",.;:") + "…"


def place_ref(place: dict[str, Any]) -> str:
    ids = place.get("ids") or {}
    return place.get("id") or ids.get("place_id") or ids.get("cid") or "?"


def _rating(place: dict[str, Any]) -> str:
    rating, count = place.get("rating"), place.get("review_count")
    if rating is None:
        return "no rating"
    return f"{rating}★ ({count:,} reviews)" if isinstance(count, int) else f"{rating}★"


def _credits(result: ApiResult) -> str:
    used = result.credits_used if result.credits_used is not None else result.meta.get("credits_used")
    parts = []
    if used is not None:
        parts.append(f"credits used: {used}")
    if result.credits_remaining is not None:
        parts.append(f"remaining: {result.credits_remaining}")
    return f"[{', '.join(parts)}]" if parts else ""


def _status(place: dict[str, Any]) -> str:
    status = place.get("status")
    return "" if status in (None, "operational") else status.replace("_", " ").upper()


def format_search(result: ApiResult, query: str) -> str:
    places = result.data or []
    if not places:
        return f'No places found for "{query}". {_credits(result)}'.strip()
    lines = [f'{len(places)} places for "{query}" {_credits(result)}'.rstrip()]
    for i, p in enumerate(places, 1):
        cats = ", ".join((p.get("categories") or [])[:3])
        head = f"{i}. {p.get('name')} | {_rating(p)}"
        if cats:
            head += f" | {cats}"
        if _status(p):
            head += f" | {_status(p)}"
        lines.append(head)
        addr = (p.get("address") or {}).get("formatted")
        if addr:
            lines.append(f"   {addr}")
        extra = [f"ref: {place_ref(p)}"]
        if p.get("phone"):
            extra.append(f"phone: {p['phone']}")
        if p.get("website"):
            extra.append(f"web: {p['website']}")
        lines.append("   " + " | ".join(extra))
    cursor = result.pagination.get("next_cursor")
    if result.pagination.get("has_more") and cursor:
        lines.append(f'\nMore results: call search_places again with the same query and cursor="{cursor}".')
    return "\n".join(lines)


def _hours(hours: dict[str, Any]) -> list[str]:
    out = []
    for day in hours.get("weekly") or []:
        name = _DAY_ABBR.get(day.get("day", ""), day.get("day", "?"))
        if day.get("closed"):
            value = "closed"
        elif day.get("open_24h"):
            value = "open 24h"
        elif day.get("periods"):
            value = ", ".join(f"{p['open']}–{p['close']}" for p in day["periods"])
        else:
            value = day.get("text") or "?"
        out.append(f"{name} {value}")
    return out


def format_place(result: ApiResult) -> str:
    p = result.data or {}
    ids = p.get("ids") or {}
    lines = [f"{p.get('name')} {_credits(result)}".rstrip()]
    if p.get("local_name") and p.get("local_name") != p.get("name"):
        lines.append(f"Local name: {p['local_name']}")
    if p.get("categories"):
        lines.append("Categories: " + ", ".join(p["categories"]))
    lines.append(f"Rating: {_rating(p)}")
    if _status(p):
        lines.append(f"Status: {_status(p)}")
    addr = (p.get("address") or {}).get("formatted")
    if addr:
        lines.append(f"Address: {addr}")
    loc = p.get("location") or {}
    if "lat" in loc:
        lines.append(
            f"Location: {loc['lat']}, {loc['lng']}" + (f" | plus code {p['plus_code']}" if p.get("plus_code") else "")
        )
    phone = p.get("phone_international") or p.get("phone")
    if phone:
        lines.append(f"Phone: {phone}")
    if p.get("website"):
        lines.append(f"Website: {p['website']}")
    hours = p.get("opening_hours")
    if hours:
        status_text = f" ({hours['status_text']})" if hours.get("status_text") else ""
        lines.append(f"Hours{status_text}: " + "; ".join(_hours(hours)))
    if p.get("timezone"):
        lines.append(f"Timezone: {p['timezone']}")
    if p.get("description"):
        lines.append(f"Description: {cap(p['description'], DESCRIPTION_MAX)}")
    attributes = p.get("attributes") or {}
    if attributes:
        lines.append("Features:")
        for group, items in list(attributes.items())[:ATTRIBUTE_GROUPS_MAX]:
            more = f" (+{len(items) - ATTRIBUTE_ITEMS_MAX})" if len(items) > ATTRIBUTE_ITEMS_MAX else ""
            lines.append(f"- {group}: {', '.join(items[:ATTRIBUTE_ITEMS_MAX])}{more}")
    links = p.get("booking_links") or []
    if links:
        lines.append("Booking: " + ", ".join(link.get("domain") or link["url"] for link in links[:3]))
    photos = p.get("photos") or []
    if photos:
        lines.append(f"Photos ({len(photos)}): " + " ".join(ph["url"] for ph in photos[:PHOTOS_MAX]))
    lines.append(
        f"IDs: place_id {ids.get('place_id') or '-'} | cid {ids.get('cid')} | feature_id {ids.get('feature_id')}"
    )
    if ids.get("google_maps_url"):
        lines.append(f"Google Maps: {ids['google_maps_url']}")
    return "\n".join(lines)


def format_review(r: dict[str, Any]) -> str:
    rating = f"{r['rating']}★" if r.get("rating") else "no rating"
    when = (r.get("published_at") or "")[:10] or r.get("relative_date") or "date unknown"
    text = r.get("translated_text") or r.get("text")
    lang = r.get("language")
    translated = f" (translated from {lang})" if r.get("translated_text") and lang else ""
    line = f"- {rating} | {when}{translated}: {cap(text, REVIEW_TEXT_MAX) if text else '(no text)'}"
    details = r.get("details") or {}
    if details:
        line += "\n  details: " + "; ".join(f"{k}: {v}" for k, v in list(details.items())[:6])
    owner = r.get("owner_response")
    if owner:
        reply = owner.get("translated_text") or owner.get("text")
        line += f"\n  owner reply: {cap(reply, OWNER_RESPONSE_MAX)}"
    return line


def format_reviews(result: ApiResult, place: str) -> str:
    reviews = result.data or []
    meta = result.meta
    head = f"{len(reviews)} reviews of {place} (sort: {meta.get('sort', '?')}"
    if meta.get("original_language"):
        head += f", only written in {meta['original_language']}"
    head += f") {_credits(result)}"
    if not reviews:
        return head.rstrip() + "\nNo reviews on this page."
    lines = [head.rstrip()]
    lines.extend(format_review(r) for r in reviews)
    cursor = result.pagination.get("next_cursor")
    if result.pagination.get("has_more") and cursor:
        lines.append(f'\nMore reviews: call get_reviews with the same place, sort and filters and cursor="{cursor}".')
    else:
        lines.append("\nNo more reviews.")
    return "\n".join(lines)


def format_resolve(result: ApiResult) -> str:
    d = result.data or {}
    return "\n".join(
        [
            f"Resolved {_credits(result)}".rstrip(),
            f"place_id: {d.get('place_id') or '-'}",
            f"cid: {d.get('cid')}",
            f"feature_id: {d.get('feature_id')}",
            f"google_maps_url: {d.get('google_maps_url')}",
        ]
    )


def register_tools(mcp: FastMCP, get_client: Callable[[], ScrapeMapsAPIClient]) -> None:
    """Register all tools. API errors become ToolError (isError) with a readable message."""

    @mcp.tool(annotations=READ_ONLY)
    async def search_places(
        query: str,
        language: str = "en",
        region: Optional[str] = None,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        radius_km: Optional[float] = None,
        limit: int = 10,
        cursor: Optional[str] = None,
    ) -> str:
        """Search Google Maps places by text, e.g. "pizzeria in Naples" or "dentist near Brooklyn".

        Returns name, rating, categories, address, phone, website and the `ref` to pass to
        get_place / get_reviews. Costs 1 credit per place returned.

        Args:
            query: What to search, ideally with the area ("coffee in Milan").
            language: Language of the results, e.g. 'en', 'it', 'pt-BR'.
            region: 2-letter country code that biases results, e.g. 'it', 'us'.
            lat: Latitude of the area centre (use together with lng).
            lng: Longitude of the area centre (use together with lat).
            radius_km: Area radius in km around lat/lng (max 100).
            limit: Places to return, 1-20 (default 10).
            cursor: `cursor` value from a previous search_places result, for the next page.
        """
        if (lat is None) != (lng is None):
            raise ToolError("Provide both lat and lng, or neither.")
        try:
            result = await get_client().search(
                query,
                language=language,
                region=region,
                lat=lat,
                lng=lng,
                radius_km=radius_km,
                limit=max(1, min(limit, SEARCH_LIMIT_MAX)),
                cursor=cursor,
            )
        except ScrapeMapsAPIError as e:
            raise ToolError(e.for_tool()) from e
        return format_search(result, query)

    @mcp.tool(annotations=READ_ONLY)
    async def get_place(place: str, language: str = "en", region: Optional[str] = None) -> str:
        """Full details of a Google Maps place: address, phone, website, opening hours,
        description, features, photos and all its identifiers. Costs 2 credits.

        Args:
            place: Place ID (ChIJ...), CID (digits) or feature ID (0x...:0x...). For a Google
                Maps URL call resolve_place first.
            language: Language of the results, e.g. 'en', 'it'.
            region: 2-letter country code, e.g. 'it', 'us'.
        """
        try:
            result = await get_client().get_place(place, language=language, region=region)
        except ScrapeMapsAPIError as e:
            raise ToolError(e.for_tool()) from e
        return format_place(result)

    @mcp.tool(annotations=READ_ONLY)
    async def get_reviews(
        place: str,
        sort: Literal["relevant", "newest", "highest", "lowest"] = "relevant",
        language: str = "en",
        original_language: Optional[str] = None,
        limit: int = 20,
        cursor: Optional[str] = None,
    ) -> str:
        """Reviews of a Google Maps place, one page at a time (all reviews are reachable by
        following the cursor). Texts are shown translated into `language` when Google provides a
        translation, and capped at 600 characters. Costs 1 credit per 2 reviews returned.

        Args:
            place: Place ID (ChIJ...), CID (digits) or feature ID (0x...:0x...).
            sort: 'relevant' (default), 'newest', 'highest' or 'lowest' rating first.
            language: Language to translate reviews into, e.g. 'en'.
            original_language: Only reviews originally written in this language, e.g. 'it'.
            limit: Reviews per page, 1-50 (default 20).
            cursor: `cursor` value from a previous get_reviews result (same place, sort and filters).
        """
        try:
            result = await get_client().get_reviews(
                place,
                sort=sort,
                language=language,
                original_language=original_language,
                limit=max(1, min(limit, REVIEWS_LIMIT_MAX)),
                cursor=cursor,
            )
        except ScrapeMapsAPIError as e:
            raise ToolError(e.for_tool()) from e
        return format_reviews(result, place)

    @mcp.tool(annotations=READ_ONLY)
    async def resolve_place(input: str) -> str:
        """Convert a Google Maps URL (including maps.app.goo.gl short links), place ID, CID or
        feature ID into all identifiers of the place. Free, or 1 credit when a lookup is needed.

        Args:
            input: A Google Maps URL or any place identifier.
        """
        try:
            result = await get_client().resolve(input)
        except ScrapeMapsAPIError as e:
            raise ToolError(e.for_tool()) from e
        return format_resolve(result)
