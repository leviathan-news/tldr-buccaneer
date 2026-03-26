# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Project Overview

TL;DR Buccaneer is a bot that automatically generates TL;DR summaries for articles on [Leviathan News](https://leviathannews.xyz) to earn SQUID tokens. It supports multiple personas with different writing styles for A/B testing.

## Important URLs

- **Frontend (for humans):** https://leviathannews.xyz
- **API (for bots):** https://api.leviathannews.xyz/api/v1

The bot interacts with the API, not the frontend. Users view articles and TL;DRs on the frontend.

**Key Features:**
- HD wallet derivation from single BIP-39 mnemonic (no per-persona keys)
- 5 personas with distinct styles (pirate, straight, ornery, hype, fud)
- Dice roll system for randomized posting (0-3 TL;DRs per article)
- Deepseek API for AI-generated summaries

## Common Commands

```bash
# Initial setup (creates venv, installs deps, creates .env)
./setup.sh

# Activate virtual environment
source venv/bin/activate

# IMPORTANT: Set up persona display names (run once after configuring .env)
python scripts/setup_profiles.py

# Run once (good for testing)
python scripts/run_bot.py --once --debug

# Run continuously
python scripts/run_bot.py

# Show persona performance leaderboard
python scripts/run_bot.py --stats

# Show recently posted TL;DRs with news IDs
python scripts/run_bot.py --recent

# Run tests
pytest tests/

# Show derived wallet addresses (after .env is configured)
python -c "
import sys; sys.path.insert(0, 'src')
from wallet import HDWalletDeriver
from personas_config import PERSONAS
import os; from dotenv import load_dotenv; load_dotenv()
d = HDWalletDeriver(os.getenv('MNEMONIC'))
for p in PERSONAS: print(f\"{p['id']}: {d.derive_wallet(p['index'])[0]}\")
"
```

## File Structure

```
src/
├── personas_config.py  # Persona definitions (id, index, name, bio, prompt, temperature, max_tokens) - NO SECRETS
├── config.py           # Loads MNEMONIC from .env, personas from personas_config.py
├── wallet.py           # HDWalletDeriver (BIP-44) + WalletAuth (signing)
├── personas.py         # Persona dataclass, loads from personas_config.py
├── coordinator.py      # FleetCoordinator - evaluation gate, dice rolls, persona selection
├── api_client.py       # Leviathan News API client (auth, fetch articles/comments, post yaps)
├── summarizer.py       # Deepseek API wrapper with tool-use loop for research-before-commenting
├── tools.py            # Research tools: web_search (DuckDuckGo), web_fetch, optional twitter_search
├── validators.py       # Output validation: preamble strip, banned AI-tell phrases, monologue detection
└── bot.py              # Legacy single-bot mode

scripts/
└── run_bot.py          # Entry point - parses args, runs fleet or single mode

cron/
└── run_bot.sh          # Cron runner script (activates venv, runs --once)

tests/
├── test_hd_wallet.py   # HD derivation tests (13 tests)
├── test_api_client.py  # API client tests (12 tests)
├── test_validators.py  # Output validation tests (53 tests)
└── test_tools.py       # Research tool tests (12 tests)
```

## Configuration

### .env (SECRET - never commit)
```env
MNEMONIC="twelve or twenty four word seed phrase"
DEEPSEEK_API_KEY=your_key
FLEET_MODE=true
# Optional: DICE_WEIGHTS=0.25,0.40,0.25,0.10
# Optional: TWITTER_BEARER_TOKEN=your_token  # Enable Twitter/X search for research
# Optional: MAX_BOT_COMMENTS_PER_ARTICLE=2  # Limit total bot comments per article
```

### src/personas_config.py (safe to commit)
Contains persona definitions. Each persona has:
- `id`: Unique identifier (e.g., "pirate")
- `index`: BIP-44 derivation index for HD wallet
- `name`: Display name
- `bio`: Profile bio
- `system_prompt`: Deepseek system prompt

## HD Wallet System

Single mnemonic derives all persona wallets using BIP-44 path `m/44'/60'/0'/0/{index}`:

| Index | Persona |
|-------|---------|
| 0 | pirate |
| 1 | straight |
| 2 | ornery |
| 3 | hype |
| 4 | fud |

Derivation happens at runtime in `FleetCoordinator.add_persona()`.

## Common Tasks

### Add a New Persona
Edit `src/personas_config.py`:
```python
PERSONAS = [
    # ... existing ...
    {
        "id": "newpersona",
        "index": 5,  # Next available index
        "name": "Display Name",
        "bio": "Short bio",
        "system_prompt": """Your prompt here...""",
    },
]
```
No .env changes needed - wallet derives automatically.

### Change Dice Roll Weights
In `.env`:
```env
DICE_WEIGHTS=0.25,0.40,0.25,0.10  # probabilities for 0,1,2,3 TL;DRs
```

### Set Up Cron Job
```bash
crontab -e
# Add:
*/30 * * * * /path/to/tldr-buccaneer/cron/run_bot.sh >> /tmp/tldr-buccaneer.log 2>&1
```

### Debug Authentication Issues
1. Check wallet addresses are registered on Leviathan News
2. Verify mnemonic is correct: `python scripts/run_bot.py --once --debug`
3. Check API responds: the bot authenticates via wallet signature

## Architecture Flow

```
run_bot.py
    │
    ▼
FleetCoordinator (coordinator.py)
    │
    ├── HDWalletDeriver.derive_wallet(index) → wallet credentials
    │
    ├── DiceRollConfig.roll() → how many TL;DRs (0-3)
    │
    ├── _select_personas(count) → random persona selection
    │
    └── PersonaBot (per persona)
            │
            ├── should_comment() → evaluation gate (reads existing comments via API)
            ├── generate_comment_with_tools() → Deepseek + web_search/web_fetch/twitter_search
            ├── validate_comment() → preamble strip, banned phrases, monologue detection
            ├── WalletAuth → signs auth messages
            ├── LeviathanAPIClient → fetches articles, comments, posts yaps
            └── DeepseekSummarizer → generates comments with persona's prompt + tool use
```

## Testing

```bash
# All tests
pytest

# Just HD wallet tests
pytest tests/test_hd_wallet.py -v

# Just API client tests
pytest tests/test_api_client.py -v
```

Test mnemonic used: `abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about` (standard BIP-39 test vector - never use for real funds!)

## Security Notes

- `.env` is in `.gitignore` - never commit it
- Mnemonic is never logged (check `wallet.py`)
- Private keys only used for signing, no transactions sent
- `personas_config.py` contains no secrets
