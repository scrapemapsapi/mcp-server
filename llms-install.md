# Installing the ScrapeMapsAPI MCP server (for AI agents)

The server runs locally over stdio and is published on PyPI as `scrapemapsapi-mcp`. It gives access to Google Maps places, place details and reviews.

## 1. Requirements

- `uv` (provides `uvx`): `curl -LsSf https://astral.sh/uv/install.sh | sh` (or `brew install uv`). Alternatively Python 3.10+ and `pip install scrapemapsapi-mcp`.
- A ScrapeMapsAPI API key. Ask the user for it; they can create one (free monthly credits included) at https://scrapemapsapi.com/dashboard/api-keys. Never invent a key.

## 2. MCP client configuration

Add this server to the client's MCP settings (for Cline: `cline_mcp_settings.json`), replacing the key:

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

Without uv, use `"command": "scrapemapsapi-mcp"` after `pip install scrapemapsapi-mcp`.

## 3. Check it works

After the client restarts the server it should list 4 tools: `search_places`, `get_place`, `get_reviews`, `resolve_place`. Try `search_places` with `query` `pizzeria in Naples` and `limit` `3` (3 credits).

An `invalid_api_key` error means the key is wrong or revoked; `insufficient_credits` means the credits are used up (top up at https://scrapemapsapi.com/dashboard/billing).
