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
| `maxi` | SatoshiMaxi | Bitcoin maximalist, dismissive of altcoins |
| `spark` | CryptoSpark | Good vibes, emoji-heavy, short & sweet |
| `chart` | ChartWhisperer | Technical analysis, price levels, TA |
| `degen` | DegenDan | Ape mentality, memecoins, slang-heavy |
| `oracle` | OnChainOracle | Data analyst, whale watching, metrics |

### Example Outputs

**SatoshiMaxi** (on ETH upgrade):
> "Cool, another centralized database update. Meanwhile, Bitcoin keeps producing blocks."

**CryptoSpark** (same story):
> "This is huge for the ecosystem!! Layer 2s about to get so much better 🚀✨ wagmi"

**ChartWhisperer** (same story):
> "Interesting timing - ETH was consolidating at the 200 MA. If this drives volume above $3,800 resistance, measured move targets $4,200. Watching the daily close for confirmation."

**DegenDan** (same story):
> "FINALLY some good news ser 🚀🚀 wen airdrop for using L2s tho?? asking for a fren"

**OnChainOracle** (same story):
> "On-chain data aligns with this. L2 TVL hit $40B last week, up 300% YoY. Gas savings should accelerate the shift - watching bridged ETH flows for confirmation."

## Quick Start

> **Using Claude Code?** Run `claude` in this directory and ask "Help me set up the bot" for guided setup. See [SKILLS.md](SKILLS.md) for details.

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

### 3. Set Up Persona Profiles

> **Note:** Use form data (not JSON) when calling the profile endpoint. The `display_name` field now persists correctly with form data. JSON body requests still return a 500 error.

Register display names for your bot personas (run once after setup):

```bash
source venv/bin/activate
python scripts/setup_profiles.py
```

This sets proper display names (e.g., "Cap'n TL;DR", "Skeptical Sam") instead of ugly wallet addresses.

### 4. Run

```bash
source venv/bin/activate

# Run once (for testing)
python scripts/run_bot.py --once --debug

# Run continuously
python scripts/run_bot.py

# Show persona leaderboard
python scripts/run_bot.py --stats

# Show recently posted TL;DRs
python scripts/run_bot.py --recent
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
  --recent   Show recently posted TL;DRs with news IDs
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
