# Runs the ScrapeMapsAPI MCP server over stdio (for registries' automated checks and container use).
# Usage: docker run -i --rm -e SCRAPEMAPSAPI_API_KEY=... scrapemapsapi-mcp
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .
ENTRYPOINT ["scrapemapsapi-mcp"]
