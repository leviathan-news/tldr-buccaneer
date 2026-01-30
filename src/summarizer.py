"""
Deepseek-powered TL;DR summarizer for the TL;DR Buccaneer bot.

Arrr! This be where we distill the news into bite-sized treasure!
"""
import logging
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup
from openai import OpenAI

from config import Config

logger = logging.getLogger(__name__)


# The legendary pirate prompt for TL;DR generation
PIRATE_SYSTEM_PROMPT = """Ye be a salty sea dog tasked with summarizin' crypto news for the Leviathan News crew!

Your mission:
1. Read the article content provided
2. Create a concise TL;DR summary (2-4 sentences maximum)
3. Capture the KEY points - what happened, who's involved, why it matters
4. Use mild pirate flavor but keep it READABLE and INFORMATIVE
5. DO NOT use excessive pirate speak - just a light touch
6. Focus on FACTS, not fluff

Good TL;DR examples:
- "Ethereum's Dencun upgrade went live today, slashin' gas fees for Layer 2 rollups by up to 90%. This be a major milestone for scalability."
- "SEC delayed their decision on the spot Bitcoin ETF again, pushin' the deadline to March. The regulatory seas remain choppy, matey."
- "Solana's network went down for 5 hours due to a bug in the validator software. The team patched it and transactions be flowin' again."

Bad TL;DR examples (too much pirate):
- "ARRR MATEY! Ye scallywags at Ethereum be hostin' the Dencun treasure!" (too theatrical)
- "Shiver me timbers! The SEC be... " (cringey)

Remember: You're summarizing NEWS, not writing a pirate novel. Keep it professional with just a dash of nautical charm."""

STANDARD_SYSTEM_PROMPT = """You are a professional news summarizer for Leviathan News, a cryptocurrency and Web3 news platform.

Your mission:
1. Read the article content provided
2. Create a concise TL;DR summary (2-4 sentences maximum)
3. Capture the KEY points - what happened, who's involved, why it matters
4. Be direct and informative
5. Focus on facts, not opinions

Good TL;DR examples:
- "Ethereum's Dencun upgrade went live today, reducing gas fees for Layer 2 rollups by up to 90%. This is a major milestone for scalability."
- "SEC delayed their decision on the spot Bitcoin ETF again, pushing the deadline to March."
- "Solana's network experienced a 5-hour outage due to a validator bug. The team has deployed a patch."

Keep summaries professional and factual."""


@dataclass
class ContentFetcher:
    """Fetches and extracts article content from URLs."""

    timeout: int = 30
    max_content_length: int = 15000  # Characters

    def fetch(self, url: str) -> str | None:
        """
        Fetch and extract readable content from a URL.

        Args:
            url: The article URL to fetch

        Returns:
            Extracted text content, or None if extraction fails
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; TLDRBuccaneer/1.0; +https://leviathannews.xyz)",
            }

            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style elements
            for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
                element.decompose()

            # Try to find article content
            article = soup.find("article") or soup.find("main") or soup.find("body")

            if article:
                # Extract text
                text = article.get_text(separator="\n", strip=True)

                # Clean up excessive whitespace
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                text = "\n".join(lines)

                # Truncate if too long
                if len(text) > self.max_content_length:
                    text = text[: self.max_content_length] + "..."

                return text

            logger.warning(f"Could not extract content from {url}")
            return None

        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return None


@dataclass
class DeepseekSummarizer:
    """Generates TL;DR summaries using Deepseek API."""

    config: Config
    content_fetcher: ContentFetcher | None = None
    _client: OpenAI | None = None

    def __post_init__(self):
        """Initialize the summarizer."""
        if self.content_fetcher is None:
            self.content_fetcher = ContentFetcher()

        # Initialize OpenAI client configured for Deepseek
        self._client = OpenAI(
            api_key=self.config.deepseek_api_key,
            base_url=self.config.deepseek_base_url,
        )

    def _get_system_prompt(self) -> str:
        """Get the appropriate system prompt based on pirate mode."""
        if self.config.pirate_mode:
            return PIRATE_SYSTEM_PROMPT
        return STANDARD_SYSTEM_PROMPT

    def generate_tldr(
        self,
        headline: str,
        url: str | None = None,
        content: str | None = None,
    ) -> str | None:
        """
        Generate a TL;DR summary for an article.

        Args:
            headline: The article headline
            url: Optional article URL to fetch content from
            content: Optional pre-fetched content (if not provided, will fetch from URL)

        Returns:
            Generated TL;DR text, or None if generation fails
        """
        # Get content if not provided
        if content is None and url:
            content = self.content_fetcher.fetch(url)

        # Build the user prompt
        if content:
            user_prompt = f"""Article headline: {headline}

Article content:
{content}

Please provide a concise TL;DR summary (2-4 sentences)."""
        else:
            # Fallback to headline-only summary
            user_prompt = f"""Article headline: {headline}

(Full article content not available - summarize based on headline)

Please provide a concise TL;DR summary (1-2 sentences) based on the headline."""

        try:
            logger.debug(f"Generating TL;DR for: {headline[:50]}...")

            response = self._client.chat.completions.create(
                model=self.config.deepseek_model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=300,
                temperature=0.7,
            )

            tldr = response.choices[0].message.content.strip()

            # Clean up any markdown formatting
            if tldr.startswith("TL;DR:"):
                tldr = tldr[6:].strip()
            if tldr.startswith("**TL;DR:**"):
                tldr = tldr[10:].strip()

            logger.info(f"Generated TL;DR ({len(tldr)} chars) for: {headline[:30]}...")
            return tldr

        except Exception as e:
            logger.error(f"Failed to generate TL;DR: {e}")
            return None

    @classmethod
    def from_config(cls, config: Config) -> "DeepseekSummarizer":
        """Create a summarizer from configuration."""
        return cls(config=config)
