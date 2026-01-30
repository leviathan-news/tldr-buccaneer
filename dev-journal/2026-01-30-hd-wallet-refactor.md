# HD Wallet Refactor - Single Mnemonic for All Personas

**Date:** 2026-01-30
**Status:** Complete
**Impact:** Major architectural improvement

## Overview

Refactored the TL;DR Buccaneer bot to use **HD (Hierarchical Deterministic) wallet derivation** from a single BIP-39 seed phrase, instead of requiring separate private keys for each persona in environment variables.

## Problem

The previous implementation required 8 environment variables for 4 personas:

```env
PERSONA_PIRATE_ADDRESS=0x...
PERSONA_PIRATE_KEY=...
PERSONA_STRAIGHT_ADDRESS=0x...
PERSONA_STRAIGHT_KEY=...
PERSONA_ORNERY_ADDRESS=0x...
PERSONA_ORNERY_KEY=...
PERSONA_HYPE_ADDRESS=0x...
PERSONA_HYPE_KEY=...
```

This approach had several issues:
- **Scaling pain**: Adding a new persona meant 2 new env vars + generating a new wallet
- **Secret sprawl**: Persona definitions were mixed with secrets
- **Error-prone**: Easy to mismatch addresses and keys
- **Hard to backup**: Multiple private keys to secure

## Solution

Single mnemonic in `.env`, personas defined in a Python config file:

```env
# .env (SECRET - never commit)
MNEMONIC="abandon abandon abandon ... (12-24 words)"
DEEPSEEK_API_KEY=...
FLEET_MODE=true
```

```python
# src/personas_config.py (SAFE TO COMMIT - no secrets!)
PERSONAS = [
    {"id": "pirate", "index": 0, "name": "Cap'n TL;DR", ...},
    {"id": "straight", "index": 1, "name": "TL;DR Wire", ...},
    {"id": "ornery", "index": 2, "name": "Skeptical Sam", ...},
    {"id": "hype", "index": 3, "name": "Bullish Betty", ...},
    {"id": "fud", "index": 4, "name": "Fearful Frank", ...},
]
```

Each persona's wallet is derived at runtime using BIP-44 standard path:
```
m/44'/60'/0'/0/{index}
```

## Technical Implementation

### 1. HDWalletDeriver Class (`src/wallet.py`)

New class that wraps `eth-account`'s HD wallet features:

```python
@dataclass
class HDWalletDeriver:
    mnemonic: str

    def __post_init__(self):
        Account.enable_unaudited_hdwallet_features()
        # Normalize whitespace and validate
        self.mnemonic = " ".join(self.mnemonic.split())
        self.derive_wallet(0)  # Validate by deriving first wallet

    def derive_wallet(self, index: int) -> tuple[str, str]:
        """Returns (address, private_key_hex)"""
        account = Account.from_mnemonic(
            self.mnemonic,
            account_path=f"m/44'/60'/0'/0/{index}"
        )
        return account.address, account.key.hex()
```

### 2. Persona Config File (`src/personas_config.py`)

Pure Python configuration with:
- System prompts for each persona style
- Persona definitions (id, index, name, bio, system_prompt)
- Default dice roll weights

This file contains NO secrets and can be safely committed to the repo.

### 3. Updated FleetCoordinator (`src/coordinator.py`)

The coordinator now:
- Creates `HDWalletDeriver` from mnemonic in `__post_init__`
- `add_persona()` derives wallet automatically using persona's configured index
- Still supports legacy explicit wallet credentials for backwards compatibility

```python
def add_persona(self, persona_id: str, wallet_address: str | None = None, ...):
    persona = get_persona(persona_id)

    if wallet_address is None or wallet_private_key is None:
        # Derive from mnemonic using persona's index
        derived_address, derived_key = self._wallet_deriver.derive_wallet(persona.index)
        wallet_address = derived_address
        wallet_private_key = derived_key

    persona.wallet_address = wallet_address
    persona.wallet_private_key = wallet_private_key
    # ... rest of setup
```

### 4. Simplified Config Loading (`src/config.py`)

- Loads `MNEMONIC` from environment
- Loads persona definitions from `personas_config.py`
- Supports legacy `WALLET_PRIVATE_KEY` for single-bot mode

## Files Changed

| File | Change |
|------|--------|
| `src/wallet.py` | Added `HDWalletDeriver` class |
| `src/personas_config.py` | **NEW** - Persona definitions (no secrets) |
| `src/config.py` | Load mnemonic + personas from Python config |
| `src/personas.py` | Load from `personas_config.py`, added `index` field |
| `src/coordinator.py` | Runtime wallet derivation |
| `scripts/run_bot.py` | Simplified persona loading |
| `.env.example` | Simplified - just `MNEMONIC` + `DEEPSEEK_API_KEY` |

### Bonus Fix: Import Structure

Fixed relative imports (`from .module`) to absolute imports (`from module`) in:
- `src/coordinator.py`
- `src/api_client.py`
- `src/bot.py`
- `src/summarizer.py`

The relative imports were incompatible with how `run_bot.py` adds `src/` to `sys.path`.

## New Persona: Fearful Frank (FUD)

Added a 5th persona for fear-mongering/FUD style summaries:

| Field | Value |
|-------|-------|
| ID | `fud` |
| Index | 4 |
| Name | Fearful Frank |
| Style | Paranoid, risk-focused, highlights dangers |

Example output:
> "Ethereum's Dencun upgrade is live, but don't celebrate yet. Untested code on a $200B network? History shows major upgrades often have hidden bugs that surface weeks later."

## Testing

Created comprehensive test suite in `tests/test_hd_wallet.py`:

| Test | Purpose |
|------|---------|
| `test_derive_wallet_deterministic` | Same mnemonic + index = same address |
| `test_derive_wallet_different_indices_different_addresses` | Different indices = different addresses |
| `test_derive_wallet_expected_addresses` | Known test vectors match |
| `test_derive_wallet_returns_valid_private_key` | Key is valid hex format |
| `test_derive_wallet_negative_index_raises` | Negative index rejected |
| `test_invalid_mnemonic_raises` | Bad mnemonic rejected |
| `test_derive_multiple` | Batch derivation works |
| `test_whitespace_in_mnemonic_handled` | Extra spaces normalized |
| `test_private_key_can_derive_same_address` | Roundtrip verification |

**All 21 tests passing** (13 HD wallet + 8 existing API client tests).

## Derived Addresses (Test Mnemonic)

Using the standard "abandon" test mnemonic:

| Index | Persona | Address |
|-------|---------|---------|
| 0 | pirate | `0x9858EfFD232B4033E47d90003D41EC34EcaEda94` |
| 1 | straight | `0x6Fac4D18c912343BF86fa7049364Dd4E424Ab9C0` |
| 2 | ornery | `0xb6716976A3ebe8D39aCEB04372f22Ff8e6802D7A` |
| 3 | hype | `0xF3f50213C1d2e255e4B2bAD430F8A38EEF8D718E` |
| 4 | fud | `0x51cA8ff9f1C0a99f88E86B8112eA3237F55374cA` |

## Benefits

1. **Single secret to manage**: One mnemonic backs up all personas
2. **Easy scaling**: Add persona = add 7 lines to `personas_config.py`
3. **No env var changes**: New personas don't need new secrets
4. **Standard derivation**: BIP-44 compatible with hardware wallets
5. **Clean separation**: Config (committable) vs secrets (env only)

## Migration Guide

1. Generate a BIP-39 mnemonic (or use existing one)
2. Update `.env`:
   ```env
   MNEMONIC="your twelve word seed phrase here"
   FLEET_MODE=true
   # Remove old PERSONA_*_ADDRESS and PERSONA_*_KEY vars
   ```
3. Fund the derived addresses for each persona you want to use
4. Run `python scripts/run_bot.py --once --debug` to verify

## Dependencies

No new dependencies! `eth-account` (already in requirements.txt) has built-in HD wallet support.

## Security Notes

- Mnemonic is NEVER logged (HDWalletDeriver doesn't expose it)
- `.env` remains in `.gitignore`
- `personas_config.py` contains no secrets
- Private keys derived in memory only when needed
