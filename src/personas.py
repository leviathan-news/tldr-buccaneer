"""
Bot persona definitions for A/B/C testing.

Arrr! This module provides the Persona dataclass and loads persona definitions
from personas_config.py. The actual persona content (names, bios, prompts) be
defined in that config file so ye can add new crew members easily!

Each persona has:
- A unique name and identity
- A distinct system prompt for Deepseek
- Its own wallet derived from the master mnemonic
- Performance tracking
"""
from dataclasses import dataclass, field

from personas_config import PERSONAS


@dataclass
class Persona:
    """A bot persona with its own style and credentials."""

    id: str  # Unique identifier (e.g., "pirate", "straight")
    index: int  # BIP-44 derivation index for HD wallet
    name: str  # Display name (e.g., "Cap'n TL;DR")
    bio: str  # Profile bio
    system_prompt: str  # Deepseek system prompt
    temperature: float = 0.7  # Generation temperature (higher = more creative)
    max_tokens: int = 300  # Max response length

    # Wallet credentials - derived at runtime from mnemonic
    wallet_address: str = ""
    wallet_private_key: str = ""

    # Runtime stats (not persisted)
    articles_processed: int = field(default=0, repr=False)
    tldrs_posted: int = field(default=0, repr=False)


# =============================================================================
# PERSONA LOADING
# =============================================================================

# Build DEFAULT_PERSONAS dict from personas_config.py
DEFAULT_PERSONAS: dict[str, Persona] = {
    p["id"]: Persona(
        id=p["id"],
        index=p["index"],
        name=p["name"],
        bio=p["bio"],
        system_prompt=p["system_prompt"],
        temperature=p.get("temperature", 0.7),
        max_tokens=p.get("max_tokens", 300),
    )
    for p in PERSONAS
}


def get_persona(persona_id: str) -> Persona:
    """
    Get a persona by ID.

    Returns a new Persona instance (not the cached one) so wallet credentials
    can be set without affecting other uses.
    """
    if persona_id not in DEFAULT_PERSONAS:
        raise ValueError(f"Unknown persona: {persona_id}. Available: {list(DEFAULT_PERSONAS.keys())}")

    # Return a copy so we don't mutate the default
    template = DEFAULT_PERSONAS[persona_id]
    return Persona(
        id=template.id,
        index=template.index,
        name=template.name,
        bio=template.bio,
        system_prompt=template.system_prompt,
        temperature=template.temperature,
        max_tokens=template.max_tokens,
    )


def list_personas() -> list[str]:
    """List all available persona IDs."""
    return list(DEFAULT_PERSONAS.keys())


def get_persona_index(persona_id: str) -> int:
    """Get the BIP-44 derivation index for a persona."""
    if persona_id not in DEFAULT_PERSONAS:
        raise ValueError(f"Unknown persona: {persona_id}. Available: {list(DEFAULT_PERSONAS.keys())}")
    return DEFAULT_PERSONAS[persona_id].index
