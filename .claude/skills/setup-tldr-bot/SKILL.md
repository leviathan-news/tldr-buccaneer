---
name: setup-tldr-bot
description: Guide for setting up the TL;DR Buccaneer bot on Leviathan News
---

# Setting Up TL;DR Buccaneer

This skill guides users through setting up the TL;DR Buccaneer bot for posting automated summaries on Leviathan News.

## Prerequisites

- Python 3.10 or higher
- A BIP-39 mnemonic (seed phrase) - generate one at [iancoleman.io/bip39](https://iancoleman.io/bip39/)
- A Deepseek API key from [platform.deepseek.com](https://platform.deepseek.com/)

## Setup Steps

### 1. Run the Setup Script

```bash
./setup.sh
```

This creates a virtual environment, installs dependencies, and creates a `.env` template.

### 2. Configure Environment Variables

Edit `.env` with your secrets:

```env
MNEMONIC="your twelve or twenty four word seed phrase here"
DEEPSEEK_API_KEY=your_deepseek_api_key
FLEET_MODE=true
```

### 3. Set Up Persona Display Names

Run once after configuring `.env`:

```bash
source venv/bin/activate
python scripts/setup_profiles.py
```

This registers human-readable names (e.g., "Cap'n TL;DR", "Skeptical Sam") for each persona wallet on Leviathan News.

### 4. Test the Bot

```bash
python scripts/run_bot.py --once --debug
```

This runs a single iteration with debug output to verify everything works.

## Common Commands

| Command | Description |
|---------|-------------|
| `python scripts/run_bot.py --once` | Run once and exit |
| `python scripts/run_bot.py` | Run continuously |
| `python scripts/run_bot.py --stats` | Show persona leaderboard |
| `python scripts/run_bot.py --recent` | Show recently posted TL;DRs |
| `python scripts/run_bot.py --debug` | Enable debug logging |

## Troubleshooting

### Authentication Errors

1. Verify your mnemonic is correct
2. Check that wallet addresses are registered on Leviathan News
3. Run with `--debug` to see detailed output

### Profile Names Not Updating

- The API requires form data (not JSON) for profile updates
- Run `python scripts/setup_profiles.py` to set display names
- Verify by checking the Leviathan News website

### No Articles Found

- The bot only processes articles without existing TL;DRs from this wallet
- Check `python scripts/run_bot.py --recent` to see what was posted

## Configuration Files

- `.env` - Secrets (mnemonic, API keys) - never commit
- `src/personas_config.py` - Persona definitions (safe to commit)
- `stats.json` - Performance tracking data

## Adding New Personas

Edit `src/personas_config.py`:

```python
{
    "id": "newpersona",
    "index": 5,  # Next available index
    "name": "Display Name",
    "bio": "Short bio",
    "system_prompt": """Your prompt here...""",
}
```

No `.env` changes needed - the wallet derives automatically from your mnemonic.
