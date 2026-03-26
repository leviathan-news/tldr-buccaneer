"""
Tests for the tools module.

Validates web search, web fetch, Twitter search tool definitions,
and the execution dispatch loop used by Deepseek function calling.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Allow imports from src/ without package installation
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tools import (
    execute_tool_call,
    get_tool_definitions,
    web_fetch,
    web_search,
)


# ---------------------------------------------------------------------------
# TestToolDefinitions (6 tests)
# ---------------------------------------------------------------------------


class TestToolDefinitions:
    """Tests for get_tool_definitions — schema shape and conditional inclusion."""

    def test_returns_list(self):
        """get_tool_definitions always returns a list."""
        result = get_tool_definitions()
        assert isinstance(result, list)

    def test_includes_web_search(self):
        """web_search is always present in the tool list."""
        names = [t["function"]["name"] for t in get_tool_definitions()]
        assert "web_search" in names

    def test_includes_web_fetch(self):
        """web_fetch is always present in the tool list."""
        names = [t["function"]["name"] for t in get_tool_definitions()]
        assert "web_fetch" in names

    def test_excludes_twitter_without_token(self):
        """twitter_search is excluded when no bearer token is provided."""
        names = [t["function"]["name"] for t in get_tool_definitions()]
        assert "twitter_search" not in names

    def test_includes_twitter_with_token(self):
        """twitter_search is included when a bearer token is provided."""
        names = [
            t["function"]["name"]
            for t in get_tool_definitions(twitter_bearer_token="tok_test")
        ]
        assert "twitter_search" in names

    def test_schemas_have_required_fields(self):
        """Every tool schema has type, function.name, function.description, function.parameters."""
        for tool in get_tool_definitions(twitter_bearer_token="tok_test"):
            assert tool["type"] == "function"
            fn = tool["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn
            # parameters must declare a JSON Schema type
            assert fn["parameters"]["type"] == "object"
            assert "properties" in fn["parameters"]


# ---------------------------------------------------------------------------
# TestWebFetch (3 tests)
# ---------------------------------------------------------------------------


class TestWebFetch:
    """Tests for web_fetch — delegates to ContentFetcher."""

    @patch("tools._content_fetcher")
    def test_returns_content(self, mock_fetcher):
        """Returns fetched content string on success."""
        mock_fetcher.fetch.return_value = "Article body text."
        result = web_fetch("https://example.com/article")
        assert result == "Article body text."
        mock_fetcher.fetch.assert_called_once_with("https://example.com/article")

    @patch("tools._content_fetcher")
    def test_returns_error_on_failure(self, mock_fetcher):
        """Returns an error message string when ContentFetcher returns None."""
        mock_fetcher.fetch.return_value = None
        result = web_fetch("https://example.com/bad")
        assert "error" in result.lower() or "failed" in result.lower()

    @patch("tools._content_fetcher")
    def test_truncates_long_content(self, mock_fetcher):
        """Content exceeding 5000 chars is truncated."""
        mock_fetcher.fetch.return_value = "x" * 6000
        result = web_fetch("https://example.com/long")
        assert len(result) <= 5003  # 5000 + "..."


# ---------------------------------------------------------------------------
# TestExecuteToolCall (3 tests)
# ---------------------------------------------------------------------------


class TestExecuteToolCall:
    """Tests for execute_tool_call — dispatches by tool name."""

    @patch("tools.web_search")
    def test_dispatches_web_search(self, mock_ws):
        """Routes a web_search tool call to the web_search function."""
        mock_ws.return_value = "search results"

        # Build a mock tool_call object matching OpenAI's schema
        tool_call = MagicMock()
        tool_call.function.name = "web_search"
        tool_call.function.arguments = json.dumps({"query": "bitcoin price"})

        result = execute_tool_call(tool_call)
        assert result == "search results"
        mock_ws.assert_called_once_with("bitcoin price")

    @patch("tools.web_fetch")
    def test_dispatches_web_fetch(self, mock_wf):
        """Routes a web_fetch tool call to the web_fetch function."""
        mock_wf.return_value = "page content"

        tool_call = MagicMock()
        tool_call.function.name = "web_fetch"
        tool_call.function.arguments = json.dumps({"url": "https://example.com"})

        result = execute_tool_call(tool_call)
        assert result == "page content"
        mock_wf.assert_called_once_with("https://example.com")

    def test_returns_error_for_unknown_tool(self):
        """Returns an error string for an unrecognised tool name."""
        tool_call = MagicMock()
        tool_call.function.name = "nonexistent_tool"
        tool_call.function.arguments = "{}"

        result = execute_tool_call(tool_call)
        assert "error" in result.lower() or "unknown" in result.lower()
