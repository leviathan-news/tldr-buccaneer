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

    def generate_comment_with_tools(
        self,
        headline: str,
        system_prompt: str,
        url: str | None = None,
        content: str | None = None,
        existing_comments: list[dict[str, str]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 300,
        twitter_bearer_token: str = "",
    ) -> str | None:
        """
        Generate a comment using Deepseek with tool-use loop.

        Unlike generate_tldr (single-shot completion), this method lets Deepseek
        call web_search / web_fetch / twitter_search during generation.  The loop
        runs up to MAX_TOOL_ROUNDS iterations; on the final round, tools are
        withheld to force a text response.

        Args:
            headline: Article headline.
            system_prompt: Persona-specific system prompt (defines voice/style).
            url: Optional article URL — content is fetched if not provided.
            content: Optional pre-fetched article body text.
            existing_comments: List of dicts with "author" and "text" keys
                representing comments already posted on this article.
            temperature: Sampling temperature (higher = more creative).
            max_tokens: Maximum tokens for the LLM response.
            twitter_bearer_token: Twitter API bearer token; when empty,
                the twitter_search tool is not offered.

        Returns:
            Generated comment string, or None on failure.
        """
        # Lazy import to avoid circular dependency (tools.py imports
        # summarizer.ContentFetcher, so summarizer must not import tools
        # at module level).
        from tools import execute_tool_call, get_tool_definitions

        MAX_TOOL_ROUNDS = 3
        # Budget for article content inside the prompt — keeps the first
        # LLM call small enough to leave room for tool results later.
        PROMPT_CONTENT_LIMIT = 3000
        # Tool output strings are truncated to this length before being
        # appended to the conversation, preventing context blowout.
        TOOL_RESULT_LIMIT = 3000

        # -- 1. Fetch article content if not already provided ----------------
        if content is None and url:
            content = self.content_fetcher.fetch(url)

        # -- 2. Build the user prompt ----------------------------------------
        # Start with headline and (truncated) article body.
        article_section = f"Article headline: {headline}\n"
        if content:
            truncated = content[:PROMPT_CONTENT_LIMIT]
            if len(content) > PROMPT_CONTENT_LIMIT:
                truncated += "..."
            article_section += f"\nArticle content:\n{truncated}\n"
        else:
            article_section += "\n(Full article content not available — use tools to research the topic.)\n"

        # Append existing comments so the model can differentiate.
        comments_section = ""
        if existing_comments:
            # Cap at 10 to stay within budget.
            shown = existing_comments[:10]
            formatted = "\n".join(
                f"- {c.get('author', 'Unknown')}: {c.get('text', '')}"
                for c in shown
            )
            comments_section = f"\nExisting comments:\n{formatted}\n"

        user_prompt = (
            f"{article_section}"
            f"{comments_section}"
            "\nResearch the topic using available tools, then write your comment. "
            "Add something the existing comments haven't covered."
        )

        # -- 3. Prepare messages and tool definitions ------------------------
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        tool_defs = get_tool_definitions(twitter_bearer_token=twitter_bearer_token)

        # -- 4. Tool-use loop (max MAX_TOOL_ROUNDS rounds) -------------------
        try:
            for round_num in range(1, MAX_TOOL_ROUNDS + 1):
                is_final_round = round_num == MAX_TOOL_ROUNDS

                # On the final round, withhold tools to force a text response.
                call_tools = None if is_final_round else tool_defs

                logger.debug(
                    "Tool-use round %d/%d for '%s' (tools=%s)",
                    round_num,
                    MAX_TOOL_ROUNDS,
                    headline[:40],
                    "disabled" if is_final_round else "enabled",
                )

                response = self._client.chat.completions.create(
                    model=self.config.deepseek_model,
                    messages=messages,
                    tools=call_tools,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

                choice = response.choices[0]

                # -- 4a. Model returned tool calls: execute and loop ----------
                if choice.message.tool_calls:
                    # Append the assistant message as a dict for Deepseek compatibility
                    # (mixing SDK objects with plain dicts can break non-OpenAI providers)
                    messages.append(choice.message.model_dump())

                    for tc in choice.message.tool_calls:
                        logger.debug(
                            "Executing tool %s (id=%s)",
                            tc.function.name,
                            tc.id,
                        )
                        result = execute_tool_call(
                            tc, twitter_bearer_token=twitter_bearer_token
                        )
                        # Truncate to stay within context budget.
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": result[:TOOL_RESULT_LIMIT],
                            }
                        )
                    # Continue to the next round.
                    continue

                # -- 4b. No tool calls — extract final text response ----------
                # Prefix cleaning (TL;DR:, Comment:, etc.) is handled by
                # validators.validate_comment() in the coordinator layer.
                comment = (choice.message.content or "").strip()
                if not comment:
                    logger.warning("Empty comment generated for: %s", headline[:40])
                    return None

                logger.info(
                    "Generated comment (%d chars, %d tool rounds) for: %s",
                    len(comment),
                    round_num,
                    headline[:30],
                )
                return comment

            # If the loop completes without returning (all rounds had tool calls
            # and the forced-text final round also somehow failed), return None.
            logger.warning(
                "Tool loop exhausted without final text for: %s", headline[:40]
            )
            return None

        except Exception as e:
            logger.error("Failed to generate comment with tools: %s", e)
            return None

    @classmethod
    def from_config(cls, config: Config) -> "DeepseekSummarizer":
        """Create a summarizer from configuration."""
        return cls(config=config)
