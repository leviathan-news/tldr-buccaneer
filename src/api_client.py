"""
Leviathan News API client for the TL;DR Buccaneer bot.

Arrr! This be how we communicate with the mothership!
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import requests

from config import Config
from wallet import WalletAuth

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Raised when an API request fails."""

    def __init__(self, message: str, status_code: int | None = None, response: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


@dataclass
class LeviathanAPIClient:
    """Client for interacting with the Leviathan News API."""

    config: Config
    wallet: WalletAuth
    _access_token: str | None = field(default=None, repr=False)
    _token_expiry: float = field(default=0, repr=False)
    _session: requests.Session = field(default_factory=requests.Session, repr=False)

    def __post_init__(self):
        """Initialize the API client."""
        self._session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": f"TLDRBuccaneer/1.0 ({self.config.utm_source})",
        })

    @property
    def base_url(self) -> str:
        """Get the API base URL."""
        return self.config.api_base_url.rstrip("/")

    def _ensure_authenticated(self) -> None:
        """Ensure we have a valid access token."""
        # Token valid for ~55 minutes (refresh 5 min before expiry)
        if self._access_token and time.time() < self._token_expiry - 300:
            return

        logger.info("Authenticating with Leviathan API...")
        self._authenticate()

    def _authenticate(self) -> None:
        """
        Authenticate with the Leviathan API using wallet signature.

        Flow:
        1. Request nonce from /api/v1/wallet/nonce/<address>/
        2. Sign the nonce message with wallet
        3. Verify signature at /api/v1/wallet/verify/
        4. Store the JWT access token
        """
        # Step 1: Get nonce
        nonce_url = f"{self.base_url}/wallet/nonce/{self.wallet.address}/"
        logger.debug(f"Requesting nonce from {nonce_url}")

        response = self._session.get(nonce_url)
        if response.status_code != 200:
            raise APIError(
                f"Failed to get nonce: {response.text}",
                status_code=response.status_code,
            )

        nonce_data = response.json()
        nonce = nonce_data["nonce"]
        message = nonce_data["message"]

        logger.debug(f"Got nonce: {nonce[:10]}...")

        # Step 2: Sign the message
        signature = self.wallet.sign_message(message)
        logger.debug("Message signed successfully")

        # Step 3: Verify signature
        verify_url = f"{self.base_url}/wallet/verify/"
        verify_payload = {
            "address": self.wallet.address,
            "nonce": nonce,
            "signature": signature,
        }

        response = self._session.post(verify_url, json=verify_payload)
        if response.status_code != 200:
            raise APIError(
                f"Failed to verify signature: {response.text}",
                status_code=response.status_code,
            )

        # Extract token from cookies
        access_token = response.cookies.get("access_token")
        if not access_token:
            # Try to get from response JSON (some APIs return it in body)
            data = response.json()
            access_token = data.get("access_token")

        if not access_token:
            raise APIError("No access token received from authentication")

        self._access_token = access_token
        # Token typically valid for 60 minutes
        self._token_expiry = time.time() + 3600

        # Update session headers with token
        self._session.headers["Authorization"] = f"Bearer {self._access_token}"

        logger.info(f"Successfully authenticated as {self.wallet.address[:10]}...")

    def _request(
        self,
        method: str,
        endpoint: str,
        auth_required: bool = True,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Make an API request.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            auth_required: Whether authentication is required
            **kwargs: Additional arguments to pass to requests

        Returns:
            Response JSON data

        Raises:
            APIError: If the request fails
        """
        if auth_required:
            self._ensure_authenticated()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        logger.debug(f"Making {method} request to {url}")

        response = self._session.request(method, url, **kwargs)

        if response.status_code >= 400:
            raise APIError(
                f"API request failed: {response.text}",
                status_code=response.status_code,
                response=response.json() if response.text else None,
            )

        return response.json()

    def get_pending_articles(self, limit: int | None = None) -> list[dict[str, Any]]:
        """
        Fetch articles that need TL;DRs - both approved and submitted, newest first.

        Prioritizes:
        1. Recently approved (published) articles - these have active readers
        2. Recently submitted articles - get in early before approval

        Args:
            limit: Maximum number of articles to fetch

        Returns:
            List of article data dictionaries, sorted by newest first
        """
        per_page = limit or self.config.max_articles_per_run
        all_articles = []

        # Fetch approved (published) articles - these have readers
        try:
            approved_data = self._request("GET", "/news/", params={
                "status": "approved",
                "sort_type": "new",
                "per_page": per_page,
            })
            all_articles.extend(approved_data.get("results", []))
            logger.debug(f"Found {len(approved_data.get('results', []))} approved articles")
        except Exception as e:
            logger.warning(f"Failed to fetch approved articles: {e}")

        # Fetch submitted (pending) articles - be first to comment
        try:
            submitted_data = self._request("GET", "/news/", params={
                "status": "submitted",
                "sort_type": "new",
                "per_page": per_page // 2,  # Fewer submitted, focus on approved
            })
            all_articles.extend(submitted_data.get("results", []))
            logger.debug(f"Found {len(submitted_data.get('results', []))} submitted articles")
        except Exception as e:
            logger.warning(f"Failed to fetch submitted articles: {e}")

        # Sort all by date_created (newest first) and dedupe
        seen_ids = set()
        unique_articles = []
        for article in sorted(all_articles, key=lambda x: x.get("date_created", ""), reverse=True):
            if article.get("id") not in seen_ids:
                seen_ids.add(article.get("id"))
                unique_articles.append(article)

        # Limit to requested amount
        articles = unique_articles[:per_page]

        logger.info(f"Found {len(articles)} articles (approved + submitted, newest first)")
        return articles

    def get_article(self, article_id: int) -> dict[str, Any]:
        """
        Fetch a single article by ID.

        Args:
            article_id: The article ID

        Returns:
            Article data dictionary
        """
        return self._request("GET", f"/news/{article_id}/")

    def post_yap(
        self,
        article_id: int,
        text: str,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Post a yap (comment) on an article.

        Args:
            article_id: The article ID to comment on
            text: The yap text content
            tags: Optional list of tags (e.g., ["tldr"])

        Returns:
            Response data with the created yap
        """
        payload = {
            "text": text,
            "tags": tags or [],
        }

        return self._request("POST", f"/news/{article_id}/post_yap", json=payload)

    def article_has_tldr(self, article: dict[str, Any]) -> bool:
        """
        Check if an article already has a TL;DR yap.

        Args:
            article: Article data dictionary

        Returns:
            True if article has a TL;DR, False otherwise
        """
        top_tldr = article.get("top_tldr")
        return top_tldr is not None

    def get_article_yaps(self, article_id: int) -> list[dict[str, Any]]:
        """
        Fetch all yaps (comments) on an article.

        Args:
            article_id: The article ID

        Returns:
            List of yap data dictionaries
        """
        try:
            data = self._request("GET", f"/news/{article_id}/list_yaps", auth_required=False)
            return data if isinstance(data, list) else data.get("results", [])
        except APIError as e:
            logger.warning(f"Failed to fetch yaps for article {article_id}: {e}")
            return []

    def count_bot_comments(self, article_id: int, bot_names: list[str]) -> int:
        """
        Count how many comments from our bots exist on an article.

        Args:
            article_id: The article ID
            bot_names: List of our bot display names

        Returns:
            Number of comments from our bots
        """
        yaps = self.get_article_yaps(article_id)
        name_set = {name.lower() for name in bot_names}
        count = 0
        for yap in yaps:
            author = yap.get("author", {})
            display_name = author.get("display_name", "").lower()
            if display_name in name_set:
                count += 1
                logger.debug(f"Found existing comment from {display_name} on article {article_id}")
        return count

    @classmethod
    def from_config(cls, config: Config) -> "LeviathanAPIClient":
        """Create an API client from configuration."""
        wallet = WalletAuth.from_config(config)
        return cls(config=config, wallet=wallet)
