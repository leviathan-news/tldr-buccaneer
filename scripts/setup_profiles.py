#!/usr/bin/env python3
"""
Set up display names and bios for all persona wallets on Leviathan News.

This script authenticates each persona and updates their profile with
the display name and bio from personas_config.py.

Usage:
    python scripts/setup_profiles.py
"""

import sys
import os
from urllib.parse import urlparse

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import requests
from dotenv import load_dotenv
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct

from personas_config import PERSONAS

load_dotenv()

BASE_URL = os.getenv("API_BASE_URL", "https://api.leviathannews.xyz/api/v1")


def _get_csrf_origin() -> str:
    """Derive CSRF Origin from API base URL, or use CSRF_ORIGIN env override."""
    override = os.getenv("CSRF_ORIGIN")
    if override:
        return override.rstrip("/")
    parsed = urlparse(BASE_URL)
    host = parsed.hostname or ""
    if host.startswith("api."):
        host = host[4:]
    scheme = parsed.scheme or "https"
    port_suffix = f":{parsed.port}" if parsed.port and parsed.port not in (80, 443) else ""
    return f"{scheme}://{host}{port_suffix}"


def get_wallet(mnemonic: str, index: int):
    """Derive wallet from mnemonic at given index."""
    Account.enable_unaudited_hdwallet_features()
    return Account.from_mnemonic(mnemonic, account_path=f"m/44'/60'/0'/0/{index}")


def authenticate(session: requests.Session, account) -> str:
    """Authenticate wallet and return access token."""
    # Get nonce
    r = session.get(f"{BASE_URL}/wallet/nonce/{account.address}/")
    r.raise_for_status()
    nonce_data = r.json()

    # Sign message
    message = encode_defunct(text=nonce_data["message"])
    signed = Web3().eth.account.sign_message(message, private_key=account.key)

    # Verify
    r = session.post(
        f"{BASE_URL}/wallet/verify/",
        json={
            "address": account.address,
            "signature": signed.signature.hex(),
            "nonce": nonce_data["nonce"],
        },
    )
    r.raise_for_status()

    # Get token from cookies
    return session.cookies.get("access_token")


def update_profile(session: requests.Session, display_name: str, bio: str):
    """Update user profile with display name and bio using session cookies."""
    # Use form data (not JSON) - the API has a bug with JSON body parsing
    # CSRF headers required for cookie-authenticated write requests
    csrf_origin = _get_csrf_origin()
    r = session.put(
        f"{BASE_URL}/wallet/profile/",
        data={"display_name": display_name, "bio": bio},
        headers={
            "Origin": csrf_origin,
            "Referer": f"{csrf_origin}/",
        },
    )
    r.raise_for_status()
    return r.json()


def main():
    mnemonic = os.getenv("MNEMONIC")
    if not mnemonic:
        print("Error: MNEMONIC not set in .env")
        sys.exit(1)

    print("Setting up persona profiles on Leviathan News...")
    print()
    print("Note: Using form data for profile updates (JSON body still returns 500).")
    print("Display names should persist correctly.")
    print()

    for persona in PERSONAS:
        persona_id = persona["id"]
        index = persona["index"]
        name = persona["name"]
        bio = persona["bio"]

        print(f"[{persona_id}] Setting up {name}...")

        # Derive wallet
        account = get_wallet(mnemonic, index)
        print(f"  Wallet: {account.address[:10]}...")

        # Authenticate
        session = requests.Session()
        try:
            authenticate(session, account)
            print(f"  Authenticated")

            # Update profile
            result = update_profile(session, name, bio)
            print(f"  Profile updated: display_name='{name}'")
            print()

        except requests.exceptions.HTTPError as e:
            print(f"  Error: {e}")
            print(f"  Response: {e.response.text[:200] if e.response else 'N/A'}")
            print()
            continue

    print("Done! All persona profiles have been configured.")


if __name__ == "__main__":
    main()
