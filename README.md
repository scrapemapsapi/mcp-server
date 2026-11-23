# ScrapeMapsAPI MCP Server

<!-- mcp-name: com.scrapemapsapi/scrapemapsapi -->

[![Listed on mcpservers.org](https://mcpservers.org/badge.svg)](https://mcpservers.org/servers/scrapemapsapi/mcp-server)

An [MCP](https://modelcontextprotocol.io) server that gives AI assistants (Claude Desktop, Claude Code, Cursor, Cline, ...) access to Google Maps places, place details and **all** the reviews of a place, via the [ScrapeMapsAPI](https://scrapemapsapi.com) API.

## No install: connect from Claude or ChatGPT

ScrapeMapsAPI also runs as a **remote MCP server** with OAuth sign-in, so you can use the same tools from
Claude (claude.ai, Desktop, mobile), ChatGPT or any client that supports remote servers, without an API key or
anything to install:

```
https://api.scrapemapsapi.com/mcp
```

- **Claude**: Customize → Connectors → + Add → Add custom connector, paste the URL, then sign in with your
  ScrapeMapsAPI account and allow access.
- **ChatGPT**: chatgpt.com/plugins → + → Add custom MCP server, paste the URL as Server URL, OAuth authentication.
- **Claude Code**: `claude mcp add --transport http scrapemapsapi https://api.scrapemapsapi.com/mcp`, then `/mcp`
  to sign in.

Calls use your account's credits exactly like the API; see or disconnect connected apps in Dashboard → Connected
apps. Step-by-step guide: https://scrapemapsapi.com/docs/mcp. The package below is the **local** server (stdio,
API key), for developers who prefer to run it themselves; both offer the same tools, prompts and resources.

## Features

**4 tools**: `search_places`, `get_place`, `get_reviews`, `resolve_place`. Results are compact text built for LLMs: the useful fields only, long texts capped, and the identifiers and cursors needed for the next call.

**4 documentation resources**: API reference, quickstart, pricing, workflow examples.

**3 prompts**: summarize the reviews of a place, compare places, find the best places of a kind in an area.

## Quick start

### 1. Get an API key

Create one at [scrapemapsapi.com](https://scrapemapsapi.com/dashboard/api-keys).

### 2. Configure your client

Claude Desktop (`claude_desktop_config.json`), Cursor (`.cursor/mcp.json`), Cline and most other clients:

```json
{
  "mcpServers": {
    "scrapemapsapi": {
      "command": "uvx",
      "args": ["scrapemapsapi-mcp"],
      "env": {
        "SCRAPEMAPSAPI_API_KEY": "your_api_key"
      }
    }
  }
}
```

Claude Code:

```bash
claude mcp add scrapemapsapi -e SCRAPEMAPSAPI_API_KEY=your_api_key -- uvx scrapemapsapi-mcp
```

### 3. Use it

- "Find the five best-rated ramen places in Milan and check what recent reviews say"
- "Summarize the reviews of https://maps.app.goo.gl/..."
- "Show me the one-star reviews of Pizzeria Da Michele in Naples, written in Italian"
- "Is the Louvre open on Monday?"

## Tools

| Tool | What it does | Credits |
|------|-------------|---------|
| `search_places` | Text search, optionally near `lat`/`lng` within `radius_km`; `limit` 1-20 (default 10), `cursor` for more | 1 per place |
| `get_place` | Details: address, phone, website, opening hours, description, features, photos, IDs | 2 |
| `get_reviews` | One page of reviews; `sort` relevant/newest/highest/lowest, `language` (translation target), `original_language` filter, `limit` 1-50, `cursor` | 1 per 2 reviews |
| `resolve_place` | Google Maps URL (short links too), place ID, CID or feature ID into every identifier | 0-1 |

Places are identified by a place ID (`ChIJ...`), a CID (digits) or a feature ID (`0x...:0x...`). Review texts are capped at 600 characters and owner replies at 200. API errors are returned as tool errors with a readable message and what to do next (e.g. top up credits, use `resolve_place`).

## Installation alternatives

```bash
# pip
pip install scrapemapsapi-mcp
SCRAPEMAPSAPI_API_KEY=... scrapemapsapi-mcp

# npx (wraps uvx, or python3 -m as a fallback)
SCRAPEMAPSAPI_API_KEY=... npx -y scrapemapsapi-mcp

# Docker
docker build -t scrapemapsapi-mcp . && docker run -i --rm -e SCRAPEMAPSAPI_API_KEY=... scrapemapsapi-mcp
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SCRAPEMAPSAPI_API_KEY` | Yes | Your API key |
| `SCRAPEMAPSAPI_BASE_URL` | No | Override the API base URL (default `https://api.scrapemapsapi.com`), e.g. `http://localhost:8000` |

## Development

```bash
cd sdks/mcp
uv venv && uv pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/ruff check .
```

Test with the MCP Inspector:

```bash
SCRAPEMAPSAPI_API_KEY=... SCRAPEMAPSAPI_BASE_URL=http://localhost:8000 uv run mcp dev dev_server.py
```

## License

MIT
