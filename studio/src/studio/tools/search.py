"""Tavily web search — the Deep Research agent's grounding tool
(blueprint.md Section 5.5 lists Exa/Tavily; this project uses Tavily).

A direct REST call rather than the tavily-python SDK: httpx is already a
dependency and this is one endpoint.
"""

from typing import TypedDict

import httpx

from studio.config import settings

TAVILY_URL = "https://api.tavily.com/search"


class SearchResult(TypedDict):
    title: str
    url: str
    content: str


def tavily_search(query: str, max_results: int = 5) -> list[SearchResult]:
    if not settings.tavily_api_key:
        raise RuntimeError(
            "TAVILY_API_KEY missing — Deep Research needs it to ground claims "
            "in real sources. Get a key at tavily.com and add it to .env."
        )
    response = httpx.post(
        TAVILY_URL,
        json={
            "api_key": settings.tavily_api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
        },
        timeout=30.0,
    )
    response.raise_for_status()
    data = response.json()
    return [
        {"title": r["title"], "url": r["url"], "content": r["content"]}
        for r in data.get("results", [])
    ]
