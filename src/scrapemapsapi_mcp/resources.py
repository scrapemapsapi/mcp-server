"""MCP resources: static documentation exposed to AI clients."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def register_resources(mcp: FastMCP) -> None:
    """Register documentation resources on the MCP server."""

    @mcp.resource("scrapemapsapi://docs/api-reference", mime_type="text/markdown")
    async def api_reference() -> str:
        """ScrapeMapsAPI REST API reference (endpoints, parameters, fields, errors)."""
        return API_REFERENCE

    @mcp.resource("scrapemapsapi://docs/quickstart", mime_type="text/markdown")
    async def quickstart() -> str:
        """Setting up the ScrapeMapsAPI MCP server."""
        return QUICKSTART

    @mcp.resource("scrapemapsapi://docs/pricing", mime_type="text/markdown")
    async def pricing() -> str:
        """Credit costs of each call."""
        return PRICING

    @mcp.resource("scrapemapsapi://docs/examples", mime_type="text/markdown")
    async def examples() -> str:
        """Common workflows with the tools."""
        return EXAMPLES


API_REFERENCE = """\
# ScrapeMapsAPI API Reference

Base URL: `https://api.scrapemapsapi.com` (override with `SCRAPEMAPSAPI_BASE_URL`).
Authentication: `X-API-Key: <key>` header. JSON only. Lists use opaque cursors.

Every response is `{"data": ..., "meta": {"credits_used", "cached", ...}}`, plus
`"pagination": {"next_cursor", "has_more"}` for lists.
Headers: `X-Credits-Used`, `X-Credits-Remaining`, `X-Cache` (HIT/MISS).

A `place` is a place ID (`ChIJ...`), a CID (decimal, as in `maps?cid=`) or a feature ID
(`0x...:0x...`, URL-encoded in paths).

## GET /v1/places/search
Text search, optionally biased to an area.

| Param | Default | Notes |
|---|---|---|
| q | (required) | e.g. `pizzeria in Naples` |
| language | en | e.g. `it`, `pt-BR` |
| region | us | 2-letter country code |
| lat, lng | | both or neither |
| radius_km | | up to 100, with lat/lng |
| limit | 20 | 1-20 |
| cursor | | `next_cursor` of the previous page |

`data` items (PlaceSummary): `id`, `ids {place_id, cid, feature_id, google_maps_url}`, `name`,
`categories`, `address {formatted, street, postal_code, city, region, country_code}`,
`location {lat, lng}`, `rating`, `review_count`, `phone`, `website`,
`status` (operational / temporarily_closed / permanently_closed / null).
`meta`: `credits_used`, `cached`, `query`, `language`, `region`.

## GET /v1/places/{place}
Full details: PlaceSummary fields plus `local_name`, `phone_international`, `plus_code`,
`timezone`, `description`, `opening_hours {weekly: [{day, closed, open_24h, periods: [{open, close}],
text}], status_text}`, `attributes {group: [features]}`, `photos [{url, width, height}]`,
`booking_links [{url, domain}]`, `knowledge_graph_id`. Params: `language`, `region`.

## GET /v1/places/{place}/reviews
| Param | Default | Notes |
|---|---|---|
| sort | relevant | relevant, newest, highest, lowest |
| language | en | also the translation target |
| original_language | | only reviews written in this language |
| limit | 20 | 1-100 |
| cursor | | `next_cursor` of the previous page |

`data` items (Review): `id`, `rating` (1-5), `published_at` (ISO 8601 UTC), `relative_date`,
`language`, `text`, `translated_text`, `author {id}` (pseudonymous; no names or photos),
`owner_response {text, translated_text, relative_date}`, `photos`, `details {question: answer}`,
`source`. `meta`: `credits_used`, `cached`, `place_id`, `cid`, `sort`, `language`, `original_language`.

## GET /v1/places/resolve?input=
Converts a place ID, CID, feature ID or Google Maps URL (short links too) into
`{place_id, cid, feature_id, google_maps_url}`.

## Errors
Body: `{"detail": {"error": "<code>", "message": "<text>"}}`. Errors are never billed.

| HTTP | Code | Meaning |
|---|---|---|
| 400 | invalid_place_id, invalid_cursor, invalid_location | bad identifier, cursor, or lat without lng |
| 401 | missing_api_key, invalid_api_key | |
| 402 | insufficient_credits | top up |
| 404 | place_not_found | |
| 422 | (validation) | parameter out of range |
| 429 | rate_limited, insufficient_credits_retry_later | see `Retry-After` |
| 502 | upstream_error | Google Maps error, retry later |
| 503 | upstream_unavailable | Google Maps unreachable, retry in a minute |
"""

QUICKSTART = """\
# ScrapeMapsAPI MCP: Quick Start

1. Create an API key at https://scrapemapsapi.com/dashboard/api-keys.
2. Add the server to your MCP client (Claude Desktop, Cursor, Cline, ...):

```json
{
  "mcpServers": {
    "scrapemapsapi": {
      "command": "uvx",
      "args": ["scrapemapsapi-mcp"],
      "env": { "SCRAPEMAPSAPI_API_KEY": "your_api_key" }
    }
  }
}
```

Alternatives: `npx -y scrapemapsapi-mcp` (needs uv or Python 3.10+), or
`pip install scrapemapsapi-mcp` and `"command": "scrapemapsapi-mcp"`.

3. Ask, for example:
- "Find the best ramen places in Milan and check their recent reviews"
- "Summarize the reviews of https://maps.app.goo.gl/..."
- "What are the opening hours of Pizzeria Da Michele in Naples?"
"""

PRICING = """\
# ScrapeMapsAPI Pricing

| Call | Credits |
|---|---|
| search_places | 1 per place returned |
| get_place | 2 |
| get_reviews | 1 per 2 reviews returned (rounded up) |
| resolve_place | 0, or 1 when a lookup is needed (short links, CID only) |

- Errors and empty results cost nothing.
- Monthly free credits; paid credit packs never expire.
- Each tool result shows the credits used and remaining.
- Top up at https://scrapemapsapi.com/dashboard/billing.
"""

EXAMPLES = """\
# ScrapeMapsAPI: Common Workflows

## Find places
`search_places(query="vegan restaurant in Berlin", limit=10)`; near a point:
`search_places(query="pharmacy", lat=45.4642, lng=9.19, radius_km=1)`.
Use the `ref` of a result with `get_place` / `get_reviews`.

## From a Google Maps link
`resolve_place(input="https://maps.app.goo.gl/...")`, then `get_place(place=<place_id or cid>)`.

## Read all the reviews
`get_reviews(place=..., sort="newest", limit=50)`, then call again with the returned `cursor`
until there are no more. Keep sort and filters the same while following a cursor.

## Reviews in one language
`get_reviews(place=..., original_language="it", language="en")`: only reviews written in Italian,
shown translated to English.

## Worst reviews first
`get_reviews(place=..., sort="lowest")` to see complaints quickly.
"""
