"""Package name and versions agree across pyproject, the npm wrapper, server.json and the README."""

from __future__ import annotations

import json
import re
from pathlib import Path

from scrapemapsapi_mcp import __version__

ROOT = Path(__file__).resolve().parents[1]
_PYPROJECT_TEXT = (ROOT / "pyproject.toml").read_text()  # no tomllib on Python 3.10
PYPROJECT = {
    "name": re.search(r'^name = "([^"]+)"', _PYPROJECT_TEXT, re.M).group(1),
    "version": re.search(r'^version = "([^"]+)"', _PYPROJECT_TEXT, re.M).group(1),
    "dependencies": re.findall(
        r'^    "([^"]+)",', _PYPROJECT_TEXT.split("dependencies = [", 1)[1].split("\n]", 1)[0], re.M
    ),
}
NPM = json.loads((ROOT / "npm" / "package.json").read_text())
SERVER = json.loads((ROOT / "server.json").read_text())


def test_versions_match():
    pypi = next(p for p in SERVER["packages"] if p["registryType"] == "pypi")
    assert PYPROJECT["version"] == __version__ == NPM["version"] == pypi["version"]


def test_registry_entry_names_the_package_and_the_remote():
    pypi = next(p for p in SERVER["packages"] if p["registryType"] == "pypi")
    assert pypi["identifier"] == PYPROJECT["name"]
    assert pypi["environmentVariables"][0]["name"] == "SCRAPEMAPSAPI_API_KEY"
    assert SERVER["remotes"] == [{"type": "streamable-http", "url": "https://api.scrapemapsapi.com/mcp"}]
    assert len(SERVER["description"]) <= 100


def test_readme_carries_the_registry_name():
    # PyPI ownership check of the MCP Registry: the README must contain mcp-name: <server name>
    match = re.search(r"mcp-name:\s*(\S+)", (ROOT / "README.md").read_text())
    assert match and match.group(1) == SERVER["name"]


def test_dependencies_are_pinned_below_the_next_major():
    deps = {re.split(r"[\[<>=]", d, maxsplit=1)[0]: d for d in PYPROJECT["dependencies"]}
    assert "<2" in deps["mcp"]
    assert "<1" in deps["httpx"]
