"""
Bot coordinator for multi-persona A/B/C testing.

This module handles:
1. Dice rolls to determine how many TL;DRs per article (0, 1, 2, or 3)
2. Random selection of which personas post
3. Tracking which articles have been processed
4. Performance metrics per persona
"""
import json
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from api_client import APIError, LeviathanAPIClient
from config import Config
from personas import Persona, get_persona, get_persona_index, list_personas
from summarizer import DeepseekSummarizer
from wallet import HDWalletDeriver, WalletAuth

logger = logging.getLogger(__name__)


@dataclass
class DiceRollConfig:
    """Configuration for the dice roll probability distribution."""

    # Probability weights for 0, 1, 2, 3 TL;DRs
    # Default: weighted toward 1 (40% one, 25% zero, 25% two, 10% three)
    weights: tuple[float, float, float, float] = (0.25, 0.40, 0.25, 0.10)

    def roll(self) -> int:
        """Roll the dice and return number of TL;DRs to post (0-3)."""
        return random.choices([0, 1, 2, 3], weights=self.weights, k=1)[0]


@dataclass
class PersonaBot:
    """A single persona's bot instance with its own API client."""

    persona: Persona
    config: Config
    api_client: LeviathanAPIClient | None = None
    summarizer: DeepseekSummarizer | None = None

    def __post_init__(self):
        """Initialize the persona's bot components."""
        # Create wallet auth for this persona
        wallet = WalletAuth(
            address=self.persona.wallet_address,
            private_key=self.persona.wallet_private_key,
        )

        # Create API client with persona's wallet
        self.api_client = LeviathanAPIClient(
            config=self.config,
            wallet=wallet,
        )

        # Create summarizer with persona's prompt
        self.summarizer = DeepseekSummarizer(config=self.config)
        # Override the system prompt for this persona
        self.summarizer._persona_prompt = self.persona.system_prompt

    def generate_comment(
        self,
        headline: str,
        url: str | None = None,
        existing_comments: list[dict[str, str]] | None = None,
    ) -> str | None:
        """Generate a comment using this persona's style with tool-use and validation.

        Calls the summarizer's tool-use loop (generate_comment_with_tools) to
        produce a comment, then runs the output through validators.validate_comment.
        On a "retry" verdict (banned AI-tell phrase detected), re-generates once
        with a stricter system prompt.  On a "reject" verdict (monologue leak or
        empty output), returns None immediately.

        Args:
            headline: Article headline text.
            url: Optional article URL for content fetching.
            existing_comments: Previously posted comments on this article,
                each a dict with "author" and "text" keys.

        Returns:
            Cleaned comment string on success, None on failure/rejection.
        """
        from validators import validate_comment

        # --- First attempt: normal generation via tool-use loop ---------------
        comment = self.summarizer.generate_comment_with_tools(
            headline=headline,
            system_prompt=self.persona.system_prompt,
            url=url,
            existing_comments=existing_comments,
            temperature=self.persona.temperature,
            max_tokens=self.persona.max_tokens,
            twitter_bearer_token=self.config.twitter_bearer_token,
        )

        if not comment:
            logger.warning("[%s] Tool-use loop returned empty comment for: %s", self.persona.id, headline[:40])
            return None

        cleaned, status = validate_comment(comment)

        if status == "ok":
            return cleaned

        if status == "reject":
            # Monologue leak or empty after cleaning — hard reject, no retry.
            logger.warning("[%s] Comment rejected (monologue leak) for: %s", self.persona.id, headline[:40])
            return None

        # --- status == "retry": banned phrase detected, try once more ---------
        logger.info("[%s] Banned phrase detected, retrying with stricter prompt for: %s", self.persona.id, headline[:40])

        stricter_prompt = (
            self.persona.system_prompt
            + "\n\nYour previous attempt contained banned AI patterns. "
            "Write a completely different comment. Start with a specific fact "
            "or number. Do NOT use 'The real X here isn't Y' or any banned opener."
        )

        comment = self.summarizer.generate_comment_with_tools(
            headline=headline,
            system_prompt=stricter_prompt,
            url=url,
            existing_comments=existing_comments,
            temperature=self.persona.temperature,
            max_tokens=self.persona.max_tokens,
            twitter_bearer_token=self.config.twitter_bearer_token,
        )

        if not comment:
            logger.warning("[%s] Retry also returned empty comment for: %s", self.persona.id, headline[:40])
            return None

        cleaned, status = validate_comment(comment)

        if status == "ok":
            return cleaned

        # Both attempts failed validation — give up.
        logger.warning("[%s] Retry also failed validation (status=%s) for: %s", self.persona.id, status, headline[:40])
        return None

    def should_comment(
        self,
        headline: str,
        content: str | None,
        existing_comments: list[dict[str, str]],
    ) -> bool:
        """Evaluation gate: decide whether this persona should comment on an article.

        Asks the LLM (using the persona's system prompt) whether it has a
        genuinely new angle that existing comments haven't covered.  Uses a low
        temperature (0.3) and very short max_tokens (10) for consistent,
        deterministic evaluation.

        Fails open on errors — returns True so we don't silently drop articles
        due to transient API failures.

        Args:
            headline: Article headline text.
            content: Optional pre-fetched article body (truncated to 1000 chars
                inside the prompt).
            existing_comments: Already posted comments, each a dict with
                "author" and "text" keys.

        Returns:
            True if the persona should comment, False to skip.
        """
        # Format the existing comments (cap at 10 for prompt budget).
        if existing_comments:
            shown = existing_comments[:10]
            formatted_comments = "\n".join(
                f"  - {c.get('author', 'Unknown')}: {c.get('text', '')}"
                for c in shown
            )
            comments_block = f"\nExisting comments ({len(shown)}):\n{formatted_comments}\n"
        else:
            comments_block = "\nExisting comments (0): none\n"

        # Build the content preview section.
        content_section = ""
        if content:
            content_section = f"\nContent preview: {content[:1000]}\n"

        eval_prompt = (
            f"You are evaluating whether to comment on this article as {self.persona.name}.\n"
            f"\nArticle: {headline}\n"
            f"{content_section}"
            f"{comments_block}"
            "\nShould you comment? Criteria:\n"
            "- Do you have a genuinely new angle not covered by existing comments?\n"
            "- Does this article relate to your expertise/perspective?\n"
            "- Can you add specific facts, data, or context — not just react?\n"
            "\nIf existing comments already cover your angle, skip.\n"
            "If the article is outside your expertise, skip.\n"
            "If you'd just be restating the headline, skip.\n"
            "\nRespond with ONLY: \"comment\" or \"skip\""
        )

        try:
            response = self.summarizer._client.chat.completions.create(
                model=self.config.deepseek_model,
                messages=[
                    {"role": "system", "content": self.persona.system_prompt},
                    {"role": "user", "content": eval_prompt},
                ],
                max_tokens=10,
                temperature=0.3,
            )

            answer = (response.choices[0].message.content or "").strip().lower()
            should = "comment" in answer
            logger.debug(
                "[%s] Evaluation gate for '%s': %s (raw=%r)",
                self.persona.id, headline[:40], "comment" if should else "skip", answer,
            )
            return should

        except Exception as e:
            # Fail open — don't drop articles due to transient API issues.
            logger.warning("[%s] Evaluation gate error (failing open): %s", self.persona.id, e)
            return True

    def post_comment(self, article_id: int, comment: str, headline: str = "") -> dict | None:
        """
        Post a comment for the given article.

        Returns:
            Dict with posted yap info on success, None on failure
        """
        try:
            result = self.api_client.post_yap(
                article_id=article_id,
                text=comment,
                tags=[],  # No tags - comments are varied styles, not just TL;DRs
            )
            self.persona.tldrs_posted += 1  # Keep stat name for now

            # Print clear output for easy querying
            print(f"POSTED: news_id={article_id} persona={self.persona.id} wallet={self.persona.wallet_address[:10]}...")
            print(f"  Headline: {headline[:60]}...")
            print(f"  Comment: {comment[:80]}...")
            print(f"  URL: https://leviathannews.xyz/news/{article_id}")
            print()

            logger.info(f"[{self.persona.id}] Posted comment for article {article_id}")
            return {"article_id": article_id, "persona": self.persona.id, "comment": comment}
        except APIError as e:
            if "Duplicate yap" in str(e):
                logger.warning(f"[{self.persona.id}] Duplicate comment for article {article_id}")
            else:
                logger.error(f"[{self.persona.id}] Failed to post comment: {e}")
            return None


@dataclass
class FleetCoordinator:
    """
    Coordinates multiple persona bots for A/B/C testing.

    Arrr! This be the captain's bridge where we command the whole fleet!

    Handles:
    - HD wallet derivation from mnemonic
    - Loading persona configurations
    - Dice rolls for article coverage
    - Random persona selection
    - Performance tracking
    """

    config: Config
    dice_config: DiceRollConfig = field(default_factory=DiceRollConfig)
    persona_bots: dict[str, PersonaBot] = field(default_factory=dict)
    _processed_articles: set[int] = field(default_factory=set)
    _stats_file: Path = field(default=Path("stats.json"))
    _wallet_deriver: HDWalletDeriver | None = field(default=None, repr=False)

    # Stats tracking
    _stats: dict[str, Any] = field(default_factory=lambda: {
        "total_articles_seen": 0,
        "total_dice_rolls": 0,
        "roll_distribution": {0: 0, 1: 0, 2: 0, 3: 0},
        "persona_stats": {},
        "posted_tldrs": [],  # Recent posted TL;DRs for easy lookup
        "last_run": None,
    })

    def __post_init__(self):
        """Initialize HD wallet deriver and load stats."""
        self._load_stats()

        # Initialize HD wallet deriver if mnemonic is provided
        if self.config.mnemonic:
            self._wallet_deriver = HDWalletDeriver(mnemonic=self.config.mnemonic)
            logger.info("HD wallet deriver initialized from mnemonic")

    def add_persona(self, persona_id: str, wallet_address: str | None = None, wallet_private_key: str | None = None) -> None:
        """
        Add a persona bot to the fleet.

        If wallet credentials are not provided, they will be derived from the
        mnemonic using the persona's BIP-44 index.

        Args:
            persona_id: The persona identifier (e.g., "pirate", "straight")
            wallet_address: Optional - explicit wallet address (legacy support)
            wallet_private_key: Optional - explicit private key (legacy support)
        """
        persona = get_persona(persona_id)

        # Derive wallet from mnemonic if credentials not explicitly provided
        if wallet_address is None or wallet_private_key is None:
            if self._wallet_deriver is None:
                raise ValueError(
                    f"Cannot add persona '{persona_id}' without wallet credentials. "
                    "Either provide wallet_address/wallet_private_key or configure MNEMONIC."
                )

            # Use the persona's configured index for derivation
            derived_address, derived_key = self._wallet_deriver.derive_wallet(persona.index)
            wallet_address = derived_address
            wallet_private_key = derived_key
            logger.debug(f"Derived wallet for {persona_id} at index {persona.index}: {wallet_address[:10]}...")

        persona.wallet_address = wallet_address
        persona.wallet_private_key = wallet_private_key

        bot = PersonaBot(persona=persona, config=self.config)
        self.persona_bots[persona_id] = bot

        # Initialize stats for this persona
        if persona_id not in self._stats["persona_stats"]:
            self._stats["persona_stats"][persona_id] = {
                "tldrs_posted": 0,
                "articles_processed": 0,
                "errors": 0,
            }

        logger.info(f"Added persona bot: {persona.name} ({persona_id}) - wallet {wallet_address[:10]}...")

    def _select_personas(self, count: int) -> list[PersonaBot]:
        """Randomly select N personas to post TL;DRs."""
        available = list(self.persona_bots.values())
        if count >= len(available):
            return available
        return random.sample(available, count)

    def process_article(self, article: dict[str, Any], max_posts: int | None = None) -> int:
        """Process a single article: fetch context, dice roll, evaluate, generate, post.

        Full flow:
          1. Skip if already processed (in-memory or restored from stats).
          2. Fetch existing comments once via the API (shared across personas).
          3. Pre-fetch article content once (avoids duplicate fetches per persona).
          4. Dice roll to decide how many personas will comment.
          5. Select personas randomly.
          6. For each selected persona:
             a. Skip if this persona already commented (duplicate guard).
             b. Run should_comment evaluation gate — skip if False.
             c. Generate comment with tool-use + validation — skip if None.
             d. Post the comment.
             e. Update tracking sets so subsequent personas see the new comment.
          7. Mark article as processed and persist stats.

        Args:
            article: Article data dictionary from the Leviathan API.
            max_posts: Maximum posts allowed (caps the dice roll result).

        Returns:
            Number of comments successfully posted.
        """
        article_id = article.get("id")
        headline = article.get("headline", "Unknown")
        url = article.get("url")

        # --- 1. Skip if already processed ------------------------------------
        if article_id in self._processed_articles:
            return 0

        self._stats["total_articles_seen"] += 1

        # --- 2. Fetch existing comments once for all personas ----------------
        first_bot = next(iter(self.persona_bots.values()))
        existing_comments = first_bot.api_client.get_article_comments(article_id)

        # --- 3. Pre-fetch article content once -------------------------------
        content = None
        if url:
            content = first_bot.summarizer.content_fetcher.fetch(url)

        # --- 4. Dice roll ----------------------------------------------------
        num_tldrs = self.dice_config.roll()
        self._stats["total_dice_rolls"] += 1
        # Handle both string and int keys (JSON loads as strings).
        roll_key = str(num_tldrs) if str(num_tldrs) in self._stats["roll_distribution"] else num_tldrs
        self._stats["roll_distribution"][roll_key] = self._stats["roll_distribution"].get(roll_key, 0) + 1

        # Respect max_posts limit (from cross-persona bot-comment cap).
        if max_posts is not None and num_tldrs > max_posts:
            logger.info("Article %d: Rolled %d but capped to %d (max per article)", article_id, num_tldrs, max_posts)
            num_tldrs = max_posts

        logger.info("Article %d: Posting %d TL;DRs - '%s...'", article_id, num_tldrs, headline[:40])

        if num_tldrs == 0:
            self._processed_articles.add(article_id)
            return 0

        # --- 5. Select personas ----------------------------------------------
        selected_bots = self._select_personas(num_tldrs)
        posted_count = 0

        # --- 6. Build already-commented set from existing comments -----------
        # Lowercase author names for case-insensitive duplicate detection.
        already_commented: set[str] = {
            c.get("author", "").lower() for c in existing_comments
        }

        for bot in selected_bots:
            persona_id = bot.persona.id
            persona_name_lower = bot.persona.name.lower()

            # --- 6a. Skip if this persona already commented -------------------
            if persona_name_lower in already_commented:
                logger.debug("[%s] Already commented on article %d, skipping", persona_id, article_id)
                continue

            # --- 6b. Evaluation gate — does this persona have a new angle? ----
            if not bot.should_comment(headline, content, existing_comments):
                logger.info("[%s] Evaluation gate: skip article %d", persona_id, article_id)
                continue

            # --- 6c. Generate comment with tool-use + validation --------------
            comment = bot.generate_comment(
                headline=headline,
                url=url,
                existing_comments=existing_comments,
            )
            if not comment:
                self._stats["persona_stats"][persona_id]["errors"] += 1
                continue

            # --- 6d. Post the comment -----------------------------------------
            result = bot.post_comment(article_id, comment, headline=headline)
            if result:
                posted_count += 1
                self._stats["persona_stats"][persona_id]["tldrs_posted"] += 1
                self._stats["persona_stats"][persona_id]["articles_processed"] += 1

                # Track posted comment for easy lookup.
                self._stats.setdefault("posted_tldrs", []).append({
                    "news_id": article_id,
                    "headline": headline[:100],
                    "persona": persona_id,
                    "comment": comment[:200],
                    "timestamp": datetime.now().isoformat(),
                    "url": f"https://leviathannews.xyz/news/{article_id}",
                })
                # Keep only last 100 entries.
                if len(self._stats["posted_tldrs"]) > 100:
                    self._stats["posted_tldrs"] = self._stats["posted_tldrs"][-100:]

            # --- 6e. Update tracking for subsequent personas ------------------
            already_commented.add(persona_name_lower)
            # Append to existing_comments so the next persona sees this one too.
            existing_comments.append({
                "author": bot.persona.name,
                "text": (comment or "")[:200],
            })

            # Small delay between posts from different personas.
            time.sleep(3)

        # --- 7. Mark processed and persist ------------------------------------
        self._processed_articles.add(article_id)
        self._save_stats()

        return posted_count

    def _get_all_bot_names(self) -> list[str]:
        """Get all display names from our persona bots."""
        return [bot.persona.name for bot in self.persona_bots.values()]

    def _is_article_too_old(self, article: dict[str, Any]) -> bool:
        """Check if article is older than max_article_age_days."""
        date_str = article.get("date_created")
        if not date_str:
            return False  # If no date, assume it's recent

        try:
            # Parse ISO format date
            article_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            cutoff = datetime.now(timezone.utc) - timedelta(days=self.config.max_article_age_days)
            return article_date < cutoff
        except (ValueError, TypeError):
            return False  # If parsing fails, assume it's recent

    def run_once(self) -> dict[str, int]:
        """
        Run a single polling cycle across all personas.

        Returns:
            Dict with stats: {"articles_checked": N, "tldrs_posted": M}
        """
        if not self.persona_bots:
            logger.error("No persona bots configured! Add personas first.")
            return {"articles_checked": 0, "tldrs_posted": 0}

        # Use the first bot's client to fetch articles
        first_bot = next(iter(self.persona_bots.values()))

        try:
            articles = first_bot.api_client.get_pending_articles(
                limit=self.config.max_articles_per_run
            )
        except APIError as e:
            logger.error(f"Failed to fetch articles: {e}")
            return {"articles_checked": 0, "tldrs_posted": 0}

        if not articles:
            logger.info("No pending articles found")
            return {"articles_checked": 0, "tldrs_posted": 0}

        # Get all our bot names for cross-persona duplicate check
        our_bot_names = self._get_all_bot_names()
        max_per_article = self.config.max_bot_comments_per_article

        total_posted = 0
        skipped_old = 0
        for article in articles:
            article_id = article.get("id")

            # Skip articles older than max_article_age_days
            if self._is_article_too_old(article):
                skipped_old += 1
                logger.debug(f"Article {article_id}: Too old (>{self.config.max_article_age_days} days), skipping")
                continue

            # Check how many of OUR bots have already commented on this article
            existing_count = first_bot.api_client.count_bot_comments(article_id, our_bot_names)
            if existing_count >= max_per_article:
                logger.debug(f"Article {article_id}: Already have {existing_count}/{max_per_article} bot comments, skipping")
                continue

            # Calculate how many more we can post
            slots_remaining = max_per_article - existing_count

            posted = self.process_article(article, max_posts=slots_remaining)
            total_posted += posted

            # Delay between articles
            time.sleep(2)

        self._stats["last_run"] = datetime.now().isoformat()
        self._save_stats()

        if skipped_old > 0:
            logger.info(f"Skipped {skipped_old} articles older than {self.config.max_article_age_days} days")

        return {
            "articles_checked": len(articles),
            "tldrs_posted": total_posted,
            "skipped_old": skipped_old,
        }

    def run_forever(self) -> None:
        """Run the coordinator in an infinite loop."""
        logger.info(f"Fleet Coordinator starting with {len(self.persona_bots)} personas!")
        logger.info(f"Dice weights: {self.dice_config.weights}")

        for persona_id, bot in self.persona_bots.items():
            logger.info(f"  - {bot.persona.name} ({persona_id})")

        while True:
            try:
                result = self.run_once()
                if result["tldrs_posted"] > 0:
                    logger.info(
                        f"Cycle complete! "
                        f"Checked {result['articles_checked']} articles, "
                        f"posted {result['tldrs_posted']} TL;DRs"
                    )

            except KeyboardInterrupt:
                logger.info("Shutting down fleet...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")

            time.sleep(self.config.poll_interval_minutes * 60)

    def get_stats(self) -> dict[str, Any]:
        """Get current statistics."""
        return dict(self._stats)

    def _load_stats(self) -> None:
        """Load stats from file and restore recent processed article IDs.

        After loading the JSON stats, any article IDs recorded in the
        "processed_ids" dict within the last 24 hours are restored into
        the in-memory _processed_articles set.  This prevents re-processing
        articles across bot restarts within the same day.
        """
        if self._stats_file.exists():
            try:
                with open(self._stats_file) as f:
                    self._stats = json.load(f)
                logger.debug("Loaded stats from %s", self._stats_file)
            except Exception as e:
                logger.warning("Failed to load stats: %s", e)

        # Restore processed article IDs from the last 24 hours.
        processed = self._stats.get("processed_ids", {})
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        for aid_str, timestamp in processed.items():
            if timestamp > cutoff:
                self._processed_articles.add(int(aid_str))
        if self._processed_articles:
            logger.debug(
                "Restored %d processed article IDs from stats", len(self._processed_articles)
            )

    def _save_stats(self) -> None:
        """Save stats to file with persistent processed article IDs.

        Before writing, merges the current session's processed article IDs
        into the "processed_ids" dict (keyed by article ID string, valued
        by ISO timestamp).  Entries older than 24 hours are pruned to keep
        the file from growing indefinitely.
        """
        try:
            # Merge current session's processed IDs into persistent store.
            processed = self._stats.get("processed_ids", {})
            now = datetime.now().isoformat()
            for aid in self._processed_articles:
                if str(aid) not in processed:
                    processed[str(aid)] = now

            # Prune entries older than 24 hours.
            cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
            processed = {k: v for k, v in processed.items() if v > cutoff}
            self._stats["processed_ids"] = processed

            with open(self._stats_file, "w") as f:
                json.dump(self._stats, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save stats: %s", e)

    def print_recent(self, limit: int = 20) -> None:
        """Print recently posted comments for easy lookup."""
        print("\n" + "=" * 70)
        print("RECENT COMMENTS POSTED")
        print("=" * 70)

        posted = self._stats.get("posted_tldrs", [])
        if not posted:
            print("No comments posted yet.")
            return

        # Show most recent first
        for entry in reversed(posted[-limit:]):
            print(f"\n[{entry['news_id']}] {entry['headline']}")
            print(f"  Persona: {entry['persona']}")
            # Handle both old 'tldr' and new 'comment' keys
            comment_text = entry.get('comment') or entry.get('tldr', '')
            print(f"  Comment: {comment_text[:100]}...")
            print(f"  URL: {entry['url']}")
            print(f"  Posted: {entry['timestamp']}")

        print("\n" + "=" * 70)

    def print_leaderboard(self) -> None:
        """Print a leaderboard of persona performance."""
        print("\n" + "=" * 50)
        print("PERSONA LEADERBOARD")
        print("=" * 50)

        stats = self._stats["persona_stats"]
        sorted_personas = sorted(
            stats.items(),
            key=lambda x: x[1]["tldrs_posted"],
            reverse=True
        )

        for rank, (persona_id, persona_stats) in enumerate(sorted_personas, 1):
            persona = get_persona(persona_id)
            print(f"{rank}. {persona.name} ({persona_id})")
            print(f"   TL;DRs Posted: {persona_stats['tldrs_posted']}")
            print(f"   Articles: {persona_stats['articles_processed']}")
            print(f"   Errors: {persona_stats['errors']}")
            print()

        print(f"Roll Distribution: {self._stats['roll_distribution']}")
        print("=" * 50)
