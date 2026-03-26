"""
Tests for the Leviathan API client.

Arrr! These tests verify our communications with the mothership!
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api_client import LeviathanAPIClient, APIError
from config import Config
from wallet import WalletAuth


@dataclass
class MockConfig:
    """Mock configuration for testing."""
    wallet_address: str = "0x1234567890123456789012345678901234567890"
    wallet_private_key: str = "0x" + "a" * 64
    api_base_url: str = "https://api.example.com"
    utm_source: str = "test"
    deepseek_api_key: str = "test-key"
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    poll_interval_minutes: int = 5
    max_articles_per_run: int = 10
    pirate_mode: bool = True
    bot_name: str = "Test Bot"
    bot_bio: str = "Test bio"


class TestLeviathanAPIClient:
    """Tests for LeviathanAPIClient."""

    @pytest.fixture
    def mock_wallet(self):
        """Create a mock wallet."""
        wallet = Mock(spec=WalletAuth)
        wallet.address = "0x1234567890123456789012345678901234567890"
        wallet.sign_message.return_value = "0x" + "b" * 130
        return wallet

    @pytest.fixture
    def mock_config(self):
        """Create a mock config."""
        return MockConfig()

    @pytest.fixture
    def client(self, mock_config, mock_wallet):
        """Create a client with mocked dependencies."""
        return LeviathanAPIClient(
            config=mock_config,
            wallet=mock_wallet,
        )

    def test_base_url_strips_trailing_slash(self, client, mock_config):
        """Test that base URL strips trailing slashes."""
        mock_config.api_base_url = "https://api.example.com/"
        assert client.base_url == "https://api.example.com"

    @patch.object(LeviathanAPIClient, '_authenticate')
    def test_ensure_authenticated_calls_authenticate_when_no_token(self, mock_auth, client):
        """Test that authentication is triggered when no token exists."""
        client._access_token = None
        client._ensure_authenticated()
        mock_auth.assert_called_once()

    @patch.object(LeviathanAPIClient, '_authenticate')
    def test_ensure_authenticated_skips_when_token_valid(self, mock_auth, client):
        """Test that authentication is skipped when token is valid."""
        import time
        client._access_token = "valid-token"
        client._token_expiry = time.time() + 3600  # Valid for 1 hour
        client._ensure_authenticated()
        mock_auth.assert_not_called()

    def test_article_has_tldr_returns_true_when_tldr_exists(self, client):
        """Test TL;DR detection when article has a TL;DR."""
        article = {
            "id": 1,
            "headline": "Test",
            "top_tldr": {"id": 100, "text": "Summary"},
        }
        assert client.article_has_tldr(article) is True

    def test_article_has_tldr_returns_false_when_no_tldr(self, client):
        """Test TL;DR detection when article has no TL;DR."""
        article = {
            "id": 1,
            "headline": "Test",
            "top_tldr": None,
        }
        assert client.article_has_tldr(article) is False

    def test_article_has_tldr_returns_false_when_key_missing(self, client):
        """Test TL;DR detection when key is missing."""
        article = {
            "id": 1,
            "headline": "Test",
        }
        assert client.article_has_tldr(article) is False


    @patch.object(LeviathanAPIClient, 'get_article_yaps')
    def test_get_article_comments_returns_formatted_list(self, mock_yaps, client):
        """Test that get_article_comments returns correctly formatted author/text dicts."""
        mock_yaps.return_value = [
            {
                "id": 1,
                "text": "First comment here",
                "author": {"display_name": "Alice", "username": "alice123"},
            },
            {
                "id": 2,
                "text": "Second comment here",
                "author": {"display_name": "Bob", "username": "bob456"},
            },
        ]
        result = client.get_article_comments(42)
        assert len(result) == 2
        assert result[0] == {"author": "Alice", "text": "First comment here"}
        assert result[1] == {"author": "Bob", "text": "Second comment here"}
        mock_yaps.assert_called_once_with(42)

    @patch.object(LeviathanAPIClient, 'get_article_yaps')
    def test_get_article_comments_handles_empty(self, mock_yaps, client):
        """Test that get_article_comments returns [] when no yaps exist."""
        mock_yaps.return_value = []
        result = client.get_article_comments(99)
        assert result == []
        mock_yaps.assert_called_once_with(99)

    @patch.object(LeviathanAPIClient, 'get_article_yaps')
    def test_get_article_comments_handles_missing_author(self, mock_yaps, client):
        """Test that missing/empty author dicts resolve to 'Anonymous'."""
        mock_yaps.return_value = [
            # author dict exists but both fields are empty strings
            {"id": 1, "text": "No author info", "author": {"display_name": "", "username": ""}},
            # author key is missing entirely
            {"id": 2, "text": "No author key"},
            # author is None
            {"id": 3, "text": "Null author", "author": None},
        ]
        result = client.get_article_comments(1)
        assert len(result) == 3
        for comment in result:
            assert comment["author"] == "Anonymous"

    @patch.object(LeviathanAPIClient, 'get_article_yaps')
    def test_persona_has_commented(self, mock_yaps, client):
        """Test detecting a specific persona's comment among yaps via set comparison."""
        mock_yaps.return_value = [
            {"id": 1, "text": "Generic take", "author": {"display_name": "RandomUser", "username": "rando"}},
            {"id": 2, "text": "Arrr, a pirate summary!", "author": {"display_name": "Cap'n Saltbeard", "username": "saltbeard"}},
            {"id": 3, "text": "Boring analysis", "author": {"display_name": "SomeGuy", "username": "guy"}},
        ]
        comments = client.get_article_comments(10)
        # Simulate the evaluation gate check: does our persona already have
        # a comment on this article?
        bot_names = {"Cap'n Saltbeard", "Dr. Doom"}
        commented_authors = {c["author"] for c in comments}
        found = bot_names & commented_authors
        assert "Cap'n Saltbeard" in found
        assert "Dr. Doom" not in found


class TestAPIError:
    """Tests for APIError exception."""

    def test_api_error_with_all_params(self):
        """Test APIError with all parameters."""
        error = APIError(
            "Test error",
            status_code=400,
            response={"error": "Bad request"},
        )
        assert str(error) == "Test error"
        assert error.status_code == 400
        assert error.response == {"error": "Bad request"}

    def test_api_error_with_message_only(self):
        """Test APIError with message only."""
        error = APIError("Simple error")
        assert str(error) == "Simple error"
        assert error.status_code is None
        assert error.response is None
