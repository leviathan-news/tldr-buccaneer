"""
Configuration management for the TL;DR Buccaneer bot.

Arrr! This be where we keep all the treasure maps and secret codes!

Supports two modes:
1. Single-bot mode: One wallet via WALLET_PRIVATE_KEY (legacy)
2. Fleet mode: HD wallet derivation from MNEMONIC with persona configs
"""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

from personas_config import PERSONAS, DEFAULT_DICE_WEIGHTS

# Load environment variables from .env file
load_dotenv()


@dataclass
class PersonaConfig:
    """Configuration for a single persona bot (loaded from personas_config.py)."""

    id: str
    index: int  # BIP-44 derivation index
    name: str
    bio: str
    system_prompt: str
    temperature: float = 0.7  # Generation temperature (higher = more creative)
    max_tokens: int = 300  # Max response length


@dataclass
class Config:
    """Configuration settings for the TL;DR Buccaneer bot."""

    # Leviathan API Configuration
    api_base_url: str
    utm_source: str = "tldr-buccaneer"

    # Deepseek API Configuration
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"

    # Bot Settings
    poll_interval_minutes: int = 5
    max_articles_per_run: int = 10
    max_bot_comments_per_article: int = 2  # Max total comments from ALL our personas per article
    max_article_age_days: int = 7  # Only comment on articles newer than this
    pirate_mode: bool = True  # For legacy single-bot mode

    # Optional: Twitter API for research-before-commenting (function calling)
    twitter_bearer_token: str = ""

    # Fleet Mode Settings
    fleet_mode: bool = False
    dice_weights: tuple[float, float, float, float] = DEFAULT_DICE_WEIGHTS

    # HD Wallet (fleet mode) - mnemonic for deriving all persona wallets
    mnemonic: str = ""

    # Single-bot mode settings (legacy)
    wallet_address: str = ""
    wallet_private_key: str = ""
    bot_name: str = "Cap'n TL;DR"
    bot_bio: str = "Arrr! I be summarizin' the news for ye landlubbers!"

    # Multi-persona configurations (fleet mode) - loaded from personas_config.py
    personas: list[PersonaConfig] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "Config":
        """
        Load configuration from environment variables.

        Supports two modes:
        1. Single-bot: WALLET_PRIVATE_KEY (legacy)
        2. Fleet mode: FLEET_MODE=true + MNEMONIC (HD wallet derivation)

        Raises:
            ValueError: If required environment variables are missing.
        """
        fleet_mode = os.getenv("FLEET_MODE", "false").lower() == "true"

        # Always require Deepseek API key
        if not os.getenv("DEEPSEEK_API_KEY"):
            raise ValueError("DEEPSEEK_API_KEY is required")

        # Parse dice weights if provided (override personas_config.py default)
        dice_weights_str = os.getenv("DICE_WEIGHTS")
        if dice_weights_str:
            try:
                dice_weights = tuple(float(x) for x in dice_weights_str.split(","))
                if len(dice_weights) != 4:
                    raise ValueError("DICE_WEIGHTS must have exactly 4 values")
            except Exception:
                dice_weights = DEFAULT_DICE_WEIGHTS
        else:
            dice_weights = DEFAULT_DICE_WEIGHTS

        config = cls(
            api_base_url=os.getenv("API_BASE_URL", "https://api.leviathannews.xyz/api/v1"),
            utm_source=os.getenv("UTM_SOURCE", "tldr-buccaneer"),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            poll_interval_minutes=int(os.getenv("POLL_INTERVAL_MINUTES", "5")),
            max_articles_per_run=int(os.getenv("MAX_ARTICLES_PER_RUN", "10")),
            max_bot_comments_per_article=int(os.getenv("MAX_BOT_COMMENTS_PER_ARTICLE", "2")),
            max_article_age_days=int(os.getenv("MAX_ARTICLE_AGE_DAYS", "7")),
            pirate_mode=os.getenv("PIRATE_MODE", "true").lower() == "true",
            twitter_bearer_token=os.getenv("TWITTER_BEARER_TOKEN", ""),
            fleet_mode=fleet_mode,
            dice_weights=dice_weights,
            bot_name=os.getenv("BOT_NAME", "Cap'n TL;DR"),
            bot_bio=os.getenv("BOT_BIO", "Arrr! I be summarizin' the news for ye landlubbers!"),
        )

        if fleet_mode:
            # Load mnemonic for HD wallet derivation
            mnemonic = os.getenv("MNEMONIC", "").strip()
            if not mnemonic:
                raise ValueError(
                    "FLEET_MODE=true requires MNEMONIC environment variable! "
                    "Set your BIP-39 seed phrase in .env"
                )
            config.mnemonic = mnemonic

            # Load persona configurations from personas_config.py
            config.personas = cls._load_persona_configs()
            if not config.personas:
                raise ValueError(
                    "No personas defined in personas_config.py! "
                    "Add persona definitions to the PERSONAS list."
                )
        else:
            # Single-bot mode - require wallet config (legacy)
            # Support both old WALLET_ADDRESS+WALLET_PRIVATE_KEY and new MNEMONIC
            mnemonic = os.getenv("MNEMONIC", "").strip()
            if mnemonic:
                # Use HD wallet derivation even in single-bot mode
                config.mnemonic = mnemonic
                # Wallet will be derived at runtime from index 0
            elif os.getenv("WALLET_PRIVATE_KEY"):
                config.wallet_private_key = os.getenv("WALLET_PRIVATE_KEY", "")
                # Address can be derived from private key, but accept explicit too
                config.wallet_address = os.getenv("WALLET_ADDRESS", "")
            else:
                raise ValueError(
                    "Single-bot mode requires either MNEMONIC or WALLET_PRIVATE_KEY"
                )

        return config

    @staticmethod
    def _load_persona_configs() -> list[PersonaConfig]:
        """Load persona configurations from personas_config.py."""
        return [
            PersonaConfig(
                id=p["id"],
                index=p["index"],
                name=p["name"],
                bio=p["bio"],
                system_prompt=p["system_prompt"],
                temperature=p.get("temperature", 0.7),
                max_tokens=p.get("max_tokens", 300),
            )
            for p in PERSONAS
        ]


# Global config instance - lazy loaded
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config
