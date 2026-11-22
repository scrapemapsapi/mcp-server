"""MCP prompt templates for common places and reviews workflows."""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP


def register_prompts(mcp: FastMCP) -> None:
    """Register prompt templates on the MCP server."""

    @mcp.prompt()
    async def summarize_reviews(place: str, language: str = "en", max_reviews: int = 100) -> str:
        """Summarize what customers say about a place, from its reviews.

        Args:
            place: Place name with its city, a Google Maps URL, a place ID (ChIJ...), CID or feature ID.
            language: Language for the reviews and the summary, e.g. 'en', 'it'.
            max_reviews: How many reviews to read at most (cost: 1 credit per 2 reviews).
        """
        return (
            f"Summarize the Google Maps reviews of: {place}\n\n"
            "Steps:\n"
            "1. Identify the place: if it is a URL, call `resolve_place`; if it is a name, call "
            "`search_places` and pick the matching result (ask me if several match); if it is an ID, use it.\n"
            "2. Call `get_place` for the name, rating and review count.\n"
            f'3. Call `get_reviews` with sort="newest", language="{language}", limit=50, following the '
            f"cursor until you have read about {max_reviews} reviews or there are no more.\n"
            '4. If the newest reviews are few or one-sided, also read one page with sort="lowest".\n'
            f"5. Write the summary in {language}:\n"
            "   - **Overall verdict** (2-3 sentences, with the rating and how many reviews you read)\n"
            "   - **What people love** (bullets, with how often it comes up)\n"
            "   - **Common complaints** (bullets, with how often it comes up)\n"
            "   - **Recent trend** (are the latest reviews better or worse than the average?)\n"
            "   - **Owner replies** (does the owner answer, and how?)\n"
            "Quote short excerpts as evidence. Do not invent reviews.\n"
        )

    @mcp.prompt()
    async def compare_places(places: str, criteria: Optional[str] = None) -> str:
        """Compare several places side by side using details and reviews.

        Args:
            places: Places separated by ';' (names with city, URLs or IDs), e.g. 'Da Michele, Naples; Sorbillo, Naples'.
            criteria: What matters most, e.g. 'price, waiting time, gluten-free options'.
        """
        items = [p.strip() for p in places.split(";") if p.strip()]
        listed = "\n".join(f"- {p}" for p in items)
        focus = f" Focus on: {criteria}." if criteria else ""
        return (
            f"Compare these places:\n{listed}\n\n"
            "Steps:\n"
            "1. Find each place (`resolve_place` for URLs, `search_places` for names) and call `get_place`.\n"
            '2. For each place read about 40 reviews with `get_reviews` (sort="newest", limit=40).\n'
            "3. Produce a comparison table (rating, review count, price level if mentioned, hours, "
            "strengths, weaknesses), then a short recommendation for different kinds of visitors."
            f"{focus}\n"
        )

    @mcp.prompt()
    async def find_best_places(what: str, where: str, how_many: int = 5) -> str:
        """Find and rank the best places of a kind in an area, checking recent reviews.

        Args:
            what: What to look for, e.g. 'ramen', 'coworking', 'vet open on Sunday'.
            where: City or neighbourhood.
            how_many: How many places to recommend.
        """
        return (
            f'Find the {how_many} best options for "{what}" in {where}.\n\n'
            "Steps:\n"
            f'1. Call `search_places` with query="{what} in {where}" and limit=20.\n'
            "2. Drop closed places and places with very few reviews; shortlist the most promising.\n"
            "3. For each shortlisted place read one page of newest reviews (`get_reviews`, limit=20) "
            "to check that recent experiences confirm the rating.\n"
            f"4. Rank the top {how_many} with: name, rating and review count, address, one-line "
            "verdict, and one recent quote. Mention any red flags.\n"
        )
