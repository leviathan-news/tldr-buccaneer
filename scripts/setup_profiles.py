#!/usr/bin/env python3
"""
Set up persona profiles on the Leviathan API.

Authenticates each persona via wallet and updates their profile with
display_name, bio, account_type, and model_name.

Usage:
    python scripts/setup_profiles.py              # Update all personas
    python scripts/setup_profiles.py --persona pirate  # Update one persona
"""
import argparse
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api_client import APIError, LeviathanAPIClient
from config import get_config
from personas import get_persona, PERSONA_TEMPLATES
from wallet import WalletAuth

logger = logging.getLogger(__name__)


def update_profile(api_client: LeviathanAPIClient, name: str, bio: str) -> dict:
    """Update a persona's profile on the Leviathan API."""
    data = {
        "display_name": name,
        "bio": bio,
        "account_type": "bot",
        "model_name": "DeepSeek",
    }
    return api_client.update_profile(data)


def setup_persona(config, persona_id: str) -> bool:
    """Set up a single persona's profile."""
    persona = get_persona(persona_id)
    if not persona:
        logger.error(f"Persona '{persona_id}' not found")
        return False

    # Derive wallet for this persona
    wallet = WalletAuth.from_mnemonic(config.mnemonic, persona.index)

    api_client = LeviathanAPIClient(config=config, wallet=wallet)

    try:
        result = update_profile(api_client, persona.name, persona.bio)
        logger.info(f"Updated profile for {persona.name} ({wallet.address[:10]}...): {result}")
        return True
    except APIError as e:
        logger.error(f"Failed to update profile for {persona.name}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Set up persona profiles on Leviathan API")
    parser.add_argument("--persona", help="Update a single persona by ID")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = get_config()

    if args.persona:
        success = setup_persona(config, args.persona)
        sys.exit(0 if success else 1)

    # Update all personas
    results = []
    for template in PERSONA_TEMPLATES:
        success = setup_persona(config, template.id)
        results.append((template.id, success))

    print("\nResults:")
    for persona_id, success in results:
        status = "OK" if success else "FAILED"
        print(f"  {persona_id}: {status}")

    if not all(s for _, s in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
