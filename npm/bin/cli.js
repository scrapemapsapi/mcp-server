#!/usr/bin/env node

/**
 * npm wrapper for the ScrapeMapsAPI MCP server.
 * Spawns the Python package via uvx (preferred) or `python3 -m scrapemapsapi_mcp.server`.
 */

const { spawn } = require("child_process");

function run(command, args) {
  const child = spawn(command, args, {
    stdio: "inherit",
    env: process.env,
  });
  child.on("error", () => {
    console.error(
      "scrapemapsapi-mcp: could not start the server. Install uv (https://docs.astral.sh/uv/) " +
        "or run `pip install scrapemapsapi-mcp`."
    );
    process.exit(1);
  });
  child.on("exit", (code) => process.exit(code ?? 1));
  return child;
}

// Try uvx first (fast, no install needed)
const uvx = spawn("uvx", ["scrapemapsapi-mcp"], {
  stdio: "inherit",
  env: process.env,
});

uvx.on("error", () => {
  // uvx not available, fall back to python3 -m
  run("python3", ["-m", "scrapemapsapi_mcp.server"]);
});

uvx.on("exit", (code) => {
  if (code !== null) process.exit(code);
});
