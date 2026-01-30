"""
Main bot logic for the TL;DR Buccaneer.

Arrr! This be the captain's quarters where all the magic happens!
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from api_client import APIError, LeviathanAPIClient
from config import Config, get_config
from summarizer import DeepseekSummarizer

logger = logging.getLogger(__name__)


@dataclass
class TLDRBuccaneer:
    """
    The TL;DR Buccaneer bot - automatically generates summaries for pending articles.

    This bot:
    1. Polls the Leviathan API for pending (submitted) articles
    2. Checks if articles already have TL;DRs
    3. Generates piratey TL;DRs using Deepseek
    4. Posts the TL;DRs back to earn SQUID tokens
    """

    config: Config
    api_client: LeviathanAPIClient | None = None
    summarizer: DeepseekSummarizer | None = None
    _processed_ids: set[int] = field(default_factory=set)
    _stats: dict[str, int] = field(default_factory=lambda: {
        "articles_checked": 0,
        "tldrs_generated": 0,
        "tldrs_posted": 0,
        "errors": 0,
    })

    def __post_init__(self):
        """Initialize bot components."""
        if self.api_client is None:
            self.api_client = LeviathanAPIClient.from_config(self.config)

        if self.summarizer is None:
            self.summarizer = DeepseekSummarizer.from_config(self.config)

    def _get_original_url(self, article: dict[str, Any]) -> str | None:
        """
        Extract the original article URL from the API response.

        The API returns a redirect URL, but we need the original source URL.
        """
        # The API provides the original URL in the article data
        # The 'url' field contains the redirect URL, but we can construct
        # the original from the article's source URL if available
        url = article.get("url", "")

        # If the URL is a leviathan redirect, we need to follow it or
        # extract from article metadata
        # For now, we'll use the redirect URL and let requests follow it
        return url if url else None

    def process_article(self, article: dict[str, Any]) -> bool:
        """
        Process a single article - generate and post TL;DR if needed.

        Args:
            article: Article data from the API

        Returns:
            True if TL;DR was posted, False otherwise
        """
        article_id = article.get("id")
        headline = article.get("headline", "Unknown")

        self._stats["articles_checked"] += 1

        # Skip if already processed in this session
        if article_id in self._processed_ids:
            logger.debug(f"Article {article_id} already processed this session")
            return False

        # Check if article already has a TL;DR
        if self.api_client.article_has_tldr(article):
            logger.debug(f"Article {article_id} already has TL;DR, skippin'")
            self._processed_ids.add(article_id)
            return False

        logger.info(f"Processin' article {article_id}: {headline[:50]}...")

        # Get the article URL for content fetching
        url = self._get_original_url(article)

        # Generate TL;DR
        tldr = self.summarizer.generate_tldr(
            headline=headline,
            url=url,
        )

        if not tldr:
            logger.warning(f"Failed to generate TL;DR for article {article_id}")
            self._stats["errors"] += 1
            return False

        self._stats["tldrs_generated"] += 1

        # Post the TL;DR
        try:
            self.api_client.post_yap(
                article_id=article_id,
                text=tldr,
                tags=["tldr"],
            )

            self._stats["tldrs_posted"] += 1
            self._processed_ids.add(article_id)
            logger.info(f"Posted TL;DR for article {article_id}! Arrr!")
            return True

        except APIError as e:
            if "Duplicate yap" in str(e):
                logger.warning(f"TL;DR already exists for article {article_id}")
                self._processed_ids.add(article_id)
            else:
                logger.error(f"Failed to post TL;DR for article {article_id}: {e}")
                self._stats["errors"] += 1
            return False

    def run_once(self) -> int:
        """
        Run a single polling cycle.

        Returns:
            Number of TL;DRs posted in this cycle
        """
        logger.info("Settin' sail for pending articles...")

        try:
            articles = self.api_client.get_pending_articles(
                limit=self.config.max_articles_per_run
            )
        except APIError as e:
            logger.error(f"Failed to fetch articles: {e}")
            self._stats["errors"] += 1
            return 0

        if not articles:
            logger.info("No pending articles found, the seas be calm")
            return 0

        posted_count = 0
        for article in articles:
            try:
                if self.process_article(article):
                    posted_count += 1

                # Small delay between articles to be nice to the API
                time.sleep(2)

            except Exception as e:
                logger.error(f"Error processing article {article.get('id')}: {e}")
                self._stats["errors"] += 1
                continue

        return posted_count

    def run_forever(self) -> None:
        """
        Run the bot in an infinite loop.

        Polls for pending articles at the configured interval.
        """
        logger.info(
            f"TL;DR Buccaneer settin' sail! "
            f"Pollin' every {self.config.poll_interval_minutes} minutes..."
        )
        logger.info(f"Pirate mode: {'Aye!' if self.config.pirate_mode else 'Nay'}")

        while True:
            try:
                posted = self.run_once()
                if posted > 0:
                    logger.info(f"Cycle complete! Posted {posted} TL;DRs. Arrr!")

            except KeyboardInterrupt:
                logger.info("Receivin' the signal to drop anchor. Goodbye, matey!")
                break

            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                self._stats["errors"] += 1

            # Wait for next polling interval
            logger.debug(f"Droppin' anchor for {self.config.poll_interval_minutes} minutes...")
            time.sleep(self.config.poll_interval_minutes * 60)

    def get_stats(self) -> dict[str, int]:
        """Get bot statistics."""
        return dict(self._stats)

    @classmethod
    def from_config(cls, config: Config | None = None) -> "TLDRBuccaneer":
        """Create a bot instance from configuration."""
        if config is None:
            config = get_config()
        return cls(config=config)


def main() -> None:
    """Main entry point for the TL;DR Buccaneer bot."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Create and run the bot
    bot = TLDRBuccaneer.from_config()
    bot.run_forever()


if __name__ == "__main__":
    main()
