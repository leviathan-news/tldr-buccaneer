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
from datetime import datetime
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

    def generate_tldr(self, headline: str, url: str | None = None) -> str | None:
        """Generate a TL;DR using this persona's style."""
        # Temporarily override the system prompt
        original_pirate_mode = self.config.pirate_mode

        # Use custom prompt generation
        content = None
        if url:
            content = self.summarizer.content_fetcher.fetch(url)

        # Build the user prompt
        if content:
            user_prompt = f"""Article headline: {headline}

Article content:
{content}

Please provide a concise TL;DR summary (2-4 sentences)."""
        else:
            user_prompt = f"""Article headline: {headline}

(Full article content not available - summarize based on headline)

Please provide a concise TL;DR summary (1-2 sentences) based on the headline."""

        try:
            response = self.summarizer._client.chat.completions.create(
                model=self.config.deepseek_model,
                messages=[
                    {"role": "system", "content": self.persona.system_prompt},
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

            return tldr

        except Exception as e:
            logger.error(f"[{self.persona.id}] Failed to generate TL;DR: {e}")
            return None

    def post_tldr(self, article_id: int, tldr: str) -> bool:
        """Post a TL;DR for the given article."""
        try:
            self.api_client.post_yap(
                article_id=article_id,
                text=tldr,
                tags=["tldr"],
            )
            self.persona.tldrs_posted += 1
            logger.info(f"[{self.persona.id}] Posted TL;DR for article {article_id}")
            return True
        except APIError as e:
            if "Duplicate yap" in str(e):
                logger.warning(f"[{self.persona.id}] Duplicate TL;DR for article {article_id}")
            else:
                logger.error(f"[{self.persona.id}] Failed to post TL;DR: {e}")
            return False


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

    def process_article(self, article: dict[str, Any]) -> int:
        """
        Process a single article - dice roll and post TL;DRs.

        Returns:
            Number of TL;DRs posted
        """
        article_id = article.get("id")
        headline = article.get("headline", "Unknown")
        url = article.get("url")

        # Skip if already processed
        if article_id in self._processed_articles:
            return 0

        self._stats["total_articles_seen"] += 1

        # Roll the dice!
        num_tldrs = self.dice_config.roll()
        self._stats["total_dice_rolls"] += 1
        self._stats["roll_distribution"][num_tldrs] += 1

        logger.info(f"Article {article_id}: Rolled {num_tldrs} TL;DRs - '{headline[:40]}...'")

        if num_tldrs == 0:
            self._processed_articles.add(article_id)
            return 0

        # Select which personas will post
        selected_bots = self._select_personas(num_tldrs)
        posted_count = 0

        for bot in selected_bots:
            persona_id = bot.persona.id

            # Generate TL;DR with this persona's style
            tldr = bot.generate_tldr(headline=headline, url=url)

            if not tldr:
                self._stats["persona_stats"][persona_id]["errors"] += 1
                continue

            # Post the TL;DR
            if bot.post_tldr(article_id, tldr):
                posted_count += 1
                self._stats["persona_stats"][persona_id]["tldrs_posted"] += 1
                self._stats["persona_stats"][persona_id]["articles_processed"] += 1

            # Small delay between posts from different personas
            time.sleep(3)

        self._processed_articles.add(article_id)
        self._save_stats()

        return posted_count

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

        total_posted = 0
        for article in articles:
            # Skip articles that already have TL;DRs
            if first_bot.api_client.article_has_tldr(article):
                continue

            posted = self.process_article(article)
            total_posted += posted

            # Delay between articles
            time.sleep(2)

        self._stats["last_run"] = datetime.now().isoformat()
        self._save_stats()

        return {
            "articles_checked": len(articles),
            "tldrs_posted": total_posted,
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
        """Load stats from file if it exists."""
        if self._stats_file.exists():
            try:
                with open(self._stats_file) as f:
                    self._stats = json.load(f)
                logger.debug(f"Loaded stats from {self._stats_file}")
            except Exception as e:
                logger.warning(f"Failed to load stats: {e}")

    def _save_stats(self) -> None:
        """Save stats to file."""
        try:
            with open(self._stats_file, "w") as f:
                json.dump(self._stats, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save stats: {e}")

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
