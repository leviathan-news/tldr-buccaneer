# TL;DR Buccaneer

**Automated TL;DR summaries for Leviathan News - earn SQUID tokens with multi-persona A/B testing**

A bot that automatically generates TL;DR summaries for pending articles on [Leviathan News](https://leviathannews.xyz) to earn SQUID tokens.

## Features

- **HD Wallet Support**: Single mnemonic derives wallets for all personas (no per-persona keys needed)
- **Fleet Mode**: Multiple personas with A/B testing to find which style earns the most
- **Dice Roll System**: Randomized posting (0-3 TL;DRs per article) to keep things unpredictable
- **5 Distinct Personas**: Pirate, Straight News, Skeptical, Hype, and FUD
- **Performance Tracking**: Stats and leaderboard to see which persona wins
- **Easy Setup**: One-command setup script for Mac/Linux

## The 5 Personas

| Persona | Name | Style |
|---------|------|-------|
| `pirate` | Cap'n TL;DR | Salty sea dog with nautical flair |
| `straight` | TL;DR Wire | Professional, just-the-facts journalist |
| `ornery` | Skeptical Sam | Contrarian, skeptical, critical eye |
| `hype` | Bullish Betty | Excited, enthusiastic, positive spin |
| `fud` | Fearful Frank | Paranoid, risk-focused, highlights dangers |

### Example Outputs

**Pirate** (on ETH upgrade):
> "Ethereum's Dencun upgrade went live today, slashin' gas fees for Layer 2 rollups by up to 90%. This be a major milestone for scalability, matey."

**Straight** (same story):
> "Ethereum's Dencun upgrade activated today, reducing Layer 2 transaction fees by up to 90%. The upgrade implements EIP-4844 (proto-danksharding)."

**Ornery** (same story):
> "Another L2 claims to cut gas fees by 90%. Ethereum's Dencun upgrade is live - we'll see if the numbers hold up under actual load."

**Hype** (same story):
> "Huge news! Ethereum's Dencun upgrade just went live, slashing L2 fees by up to 90%. This is a game-changer for mainstream adoption!"

**FUD** (same story):
> "Ethereum's Dencun upgrade is live, but don't celebrate yet. Untested code on a $200B network? History shows major upgrades often have hidden bugs."

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/leviathan-news/tldr-buccaneer.git
cd tldr-buccaneer
./setup.sh
```

### 2. Configure

Edit `.env` with your secrets:

```env
# Your BIP-39 seed phrase (12 or 24 words)
MNEMONIC="your twelve word seed phrase here"

# Get from https://platform.deepseek.com/
DEEPSEEK_API_KEY=your_key_here

# Enable multi-persona mode
FLEET_MODE=true
```

### 3. Run

```bash
source venv/bin/activate

# Run once (for testing)
python scripts/run_bot.py --once --debug

# Run continuously
python scripts/run_bot.py

# Show persona leaderboard
python scripts/run_bot.py --stats
```

### 4. Set Up Cron (Optional)

For automated running every 30 minutes:

```bash
crontab -e
# Add this line:
*/30 * * * * /path/to/tldr-buccaneer/cron/run_bot.sh >> /tmp/tldr-buccaneer.log 2>&1
```

## HD Wallet System

Instead of managing separate private keys for each persona, TL;DR Buccaneer uses **HD (Hierarchical Deterministic) wallet derivation**. One seed phrase derives all persona wallets:

```
MNEMONIC="your seed phrase"
        │
        ├─ index 0 → pirate wallet
        ├─ index 1 → straight wallet
        ├─ index 2 → ornery wallet
        ├─ index 3 → hype wallet
        └─ index 4 → fud wallet
```

Uses standard BIP-44 derivation path: `m/44'/60'/0'/0/{index}`

**To add a new persona**, just edit `src/personas_config.py` - no new secrets needed!

## Dice Roll System

Each time an article comes in, the bot rolls dice to determine how many TL;DRs to post:

| Roll | Default Probability | Result |
|------|---------------------|--------|
| 0 | 25% | Skip this article |
| 1 | 40% | One random persona posts |
| 2 | 25% | Two random personas post |
| 3 | 10% | Three random personas post |

This creates natural variation - not every article gets a TL;DR, and when they do, it's unpredictable which persona(s) will respond.

Configure with `DICE_WEIGHTS=0.25,0.40,0.25,0.10` in `.env`.

## Performance Tracking

The bot tracks stats in `stats.json`:

```json
{
  "total_articles_seen": 150,
  "roll_distribution": {"0": 38, "1": 60, "2": 40, "3": 12},
  "persona_stats": {
    "pirate": {"tldrs_posted": 45, "articles_processed": 45, "errors": 2},
    "straight": {"tldrs_posted": 52, "articles_processed": 52, "errors": 0},
    "ornery": {"tldrs_posted": 48, "articles_processed": 48, "errors": 1},
    "hype": {"tldrs_posted": 41, "articles_processed": 41, "errors": 3},
    "fud": {"tldrs_posted": 38, "articles_processed": 38, "errors": 0}
  }
}
```

View the leaderboard:
```bash
python scripts/run_bot.py --stats
```

## Architecture

```
tldr-buccaneer/
├── src/
│   ├── config.py          # Configuration loading
│   ├── personas_config.py # Persona definitions (no secrets!)
│   ├── personas.py        # Persona dataclass and loading
│   ├── wallet.py          # HD wallet derivation + auth
│   ├── api_client.py      # Leviathan API client
│   ├── summarizer.py      # Deepseek TL;DR generation
│   ├── bot.py             # Single-bot logic (legacy)
│   └── coordinator.py     # Fleet coordinator + dice rolls
├── scripts/
│   └── run_bot.py         # Entry point
├── cron/
│   └── run_bot.sh         # Cron runner script
├── tests/
│   ├── test_hd_wallet.py  # HD wallet tests
│   └── test_api_client.py # API client tests
└── dev-journal/           # Development notes
```

## Adding New Personas

Edit `src/personas_config.py`:

```python
PERSONAS = [
    # ... existing personas ...
    {
        "id": "academic",
        "index": 5,  # Just increment the index!
        "name": "Professor Summary",
        "bio": "Scholarly analysis of crypto news.",
        "system_prompt": """You are an academic researcher...""",
    },
]
```

No `.env` changes needed - the wallet is derived automatically from your mnemonic at index 5.

## CLI Options

```
python scripts/run_bot.py [options]

Options:
  --once     Run once and exit
  --fleet    Force fleet mode
  --single   Force single-bot mode
  --stats    Show persona leaderboard
  --debug    Enable debug logging
  --quiet    Only show warnings/errors
```

## Security Notes

- **Never commit your `.env` file** (it's in `.gitignore`)
- Private keys are used ONLY for signing authentication messages
- No blockchain transactions are sent; no gas is spent
- The mnemonic is never logged or exposed
- `personas_config.py` contains no secrets and is safe to commit

## Requirements

- Python 3.10+
- Deepseek API key
- BIP-39 mnemonic (generate at [iancoleman.io/bip39](https://iancoleman.io/bip39/))

## License

MIT

---

*Built for the Leviathan News community. May the best bot win!*
