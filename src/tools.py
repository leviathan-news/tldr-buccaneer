"""
Tool definitions and execution dispatch for Deepseek function calling.

Provides web_search (DuckDuckGo), web_fetch (article reader), and optional
twitter_search as callable tools.  get_tool_definitions() returns OpenAI-
compatible schemas; execute_tool_call() routes an LLM tool-call object to
the correct function.
"""

import json
import logging
from typing import Any

import requests
from duckduckgo_search import DDGS

from summarizer import ContentFetcher

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared content fetcher — one instance reused across all web_fetch calls.
# max_content_length is intentionally lower than the default (15 000) because
# tool output feeds back into the LLM context window.
# ---------------------------------------------------------------------------
_content_fetcher = ContentFetcher(max_content_length=5000)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def web_search(query: str) -> str:
    """
    Search DuckDuckGo and return the top 5 results.

    Each result is formatted as:
        - title
          snippet
          url

    Returns an error message string on failure (never raises).
    """
    try:
        with DDGS() as ddgs:
            # text() returns a generator; pull at most 5 results
            results = list(ddgs.text(query, max_results=5))

        if not results:
            return "No results found."

        # Format each result as a readable block
        lines: list[str] = []
        for r in results:
            title = r.get("title", "No title")
            snippet = r.get("body", "No snippet")
            url = r.get("href", "No URL")
            lines.append(f"- {title}\n  {snippet}\n  {url}")

        return "\n\n".join(lines)

    except Exception as exc:
        logger.error("web_search failed for query %r: %s", query, exc)
        return f"Error: web search failed — {exc}"


def _is_safe_url(url: str) -> bool:
    """Validate a URL is safe to fetch (not targeting internal/private networks).

    Blocks SSRF attempts where the LLM could request internal endpoints
    like cloud metadata services (169.254.x.x) or localhost.
    """
    from urllib.parse import urlparse
    import socket

    try:
        parsed = urlparse(url)
        # Only allow http/https schemes
        if parsed.scheme not in ("http", "https"):
            return False
        if not parsed.hostname:
            return False

        # Resolve hostname and check for private/reserved IP ranges
        addr = socket.gethostbyname(parsed.hostname)
        parts = [int(p) for p in addr.split(".")]

        # Block private, loopback, link-local, and reserved ranges
        if parts[0] == 127:  # 127.0.0.0/8 loopback
            return False
        if parts[0] == 10:  # 10.0.0.0/8 private
            return False
        if parts[0] == 172 and 16 <= parts[1] <= 31:  # 172.16.0.0/12 private
            return False
        if parts[0] == 192 and parts[1] == 168:  # 192.168.0.0/16 private
            return False
        if parts[0] == 169 and parts[1] == 254:  # 169.254.0.0/16 link-local
            return False
        if parts[0] == 0:  # 0.0.0.0/8 reserved
            return False

        return True
    except Exception:
        return False


def web_fetch(url: str) -> str:
    """
    Fetch readable text from a URL via ContentFetcher.

    Validates the URL is not targeting internal/private networks (SSRF protection)
    before fetching. Returns the extracted text (truncated to 5 000 chars) or
    an error message string on failure.
    """
    try:
        # SSRF protection — block requests to internal/private IPs
        if not _is_safe_url(url):
            return f"Error: URL blocked (private/internal network): {url}"

        content = _content_fetcher.fetch(url)

        if content is None:
            return f"Error: failed to fetch content from {url}"

        # Defensive truncation — ContentFetcher already truncates at
        # max_content_length, but guard against future config drift.
        if len(content) > 5000:
            content = content[:5000] + "..."

        return content

    except Exception as exc:
        logger.error("web_fetch failed for %r: %s", url, exc)
        return f"Error: web fetch failed — {exc}"


def twitter_search(query: str, bearer_token: str) -> str:
    """
    Search recent tweets via Twitter API v2 /2/tweets/search/recent.

    Returns the top 5 tweets formatted as:
        @username (N likes, M RTs):
          tweet text

    Requires a valid bearer_token. Returns an error message string on failure.
    """
    try:
        headers = {"Authorization": f"Bearer {bearer_token}"}
        params = {
            "query": query,
            "max_results": 10,  # API minimum; we slice to 5 below
            "tweet.fields": "public_metrics,author_id",
            "expansions": "author_id",
            "user.fields": "username",
        }

        resp = requests.get(
            "https://api.twitter.com/2/tweets/search/recent",
            headers=headers,
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        # Build an author_id -> username lookup from the includes block
        users = {
            u["id"]: u["username"]
            for u in data.get("includes", {}).get("users", [])
        }

        tweets = data.get("data", [])[:5]
        if not tweets:
            return "No tweets found."

        lines: list[str] = []
        for t in tweets:
            username = users.get(t.get("author_id", ""), "unknown")
            metrics = t.get("public_metrics", {})
            likes = metrics.get("like_count", 0)
            rts = metrics.get("retweet_count", 0)
            text = t.get("text", "")
            lines.append(f"@{username} ({likes} likes, {rts} RTs):\n  {text}")

        return "\n\n".join(lines)

    except Exception as exc:
        logger.error("twitter_search failed for query %r: %s", query, exc)
        return f"Error: Twitter search failed — {exc}"


# ---------------------------------------------------------------------------
# Tool schema definitions (OpenAI function-calling format)
# ---------------------------------------------------------------------------

_WEB_SEARCH_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web using DuckDuckGo. Returns the top 5 results "
            "with title, snippet, and URL."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                },
            },
            "required": ["query"],
        },
    },
}

_WEB_FETCH_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "web_fetch",
        "description": (
            "Fetch and extract the readable text content of a web page. "
            "Returns up to 5 000 characters of cleaned article text."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch.",
                },
            },
            "required": ["url"],
        },
    },
}

_TWITTER_SEARCH_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "twitter_search",
        "description": (
            "Search recent tweets on Twitter/X. Returns the top 5 tweets "
            "with username, like/RT counts, and text."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The Twitter search query.",
                },
            },
            "required": ["query"],
        },
    },
}


# ---------------------------------------------------------------------------
# Public API — schema retrieval and dispatch
# ---------------------------------------------------------------------------


def get_tool_definitions(twitter_bearer_token: str | None = None) -> list[dict]:
    """
    Return OpenAI-compatible tool schemas for all available tools.

    web_search and web_fetch are always included.  twitter_search is only
    included when a twitter_bearer_token is provided (non-None, non-empty).
    """
    tools: list[dict] = [_WEB_SEARCH_SCHEMA, _WEB_FETCH_SCHEMA]

    if twitter_bearer_token:
        tools.append(_TWITTER_SEARCH_SCHEMA)

    return tools


def execute_tool_call(
    tool_call: Any,
    twitter_bearer_token: str | None = None,
) -> str:
    """
    Dispatch a single tool call returned by the LLM.

    Expects an object with `function.name` (str) and `function.arguments`
    (JSON string).  Returns the tool's string output, or an error message
    for unknown tools / malformed arguments.
    """
    name: str = tool_call.function.name
    try:
        args: dict = json.loads(tool_call.function.arguments)
    except (json.JSONDecodeError, TypeError) as exc:
        return f"Error: failed to parse tool arguments — {exc}"

    # Route to the correct implementation
    if name == "web_search":
        return web_search(args.get("query", ""))

    if name == "web_fetch":
        return web_fetch(args.get("url", ""))

    if name == "twitter_search":
        if not twitter_bearer_token:
            return "Error: Twitter bearer token not configured."
        return twitter_search(args.get("query", ""), twitter_bearer_token)

    return f"Error: unknown tool '{name}'"
