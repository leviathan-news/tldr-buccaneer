# TL;DR Buccaneer

**Automatic SQUID Token Farming Through News Summaries**

A bot that automatically generates TL;DR summaries for pending articles on [Leviathan News](https://leviathannews.xyz) to earn SQUID tokens.

## Features

- **Single-Bot Mode**: One persona, one wallet - simple and straightforward
- **Fleet Mode**: Multiple personas with A/B/C testing to find which style earns the most
- **Dice Roll System**: Randomized posting (0-3 TL;DRs per article) to keep things unpredictable
- **4 Distinct Personas**: Pirate, Straight News, Ornery/Skeptical, and Hype/Bullish
- **Performance Tracking**: Stats and leaderboard to see which persona wins

## The 4 Personas

| Persona | Name | Style |
|---------|------|-------|
| `pirate` | Cap'n TL;DR | Salty sea dog with nautical flair |
| `straight` | TL;DR Wire | Professional, just-the-facts journalist |
| `ornery` | Skeptical Sam | Contrarian, skeptical, critical eye |
| `hype` | Bullish Betty | Excited, enthusiastic, positive spin |

### Example Outputs

**Pirate** (on ETH upgrade):
> "Ethereum's Dencun upgrade went live today, slashin' gas fees for Layer 2 rollups by up to 90%. This be a major milestone for scalability, matey."

**Straight** (same story):
> "Ethereum's Dencun upgrade activated today, reducing Layer 2 transaction fees by up to 90%. The upgrade implements EIP-4844 (proto-danksharding)."

**Ornery** (same story):
> "Another L2 claims to cut gas fees by 90%. Ethereum's Dencun upgrade is live - we'll see if the numbers hold up under actual load."

**Hype** (same story):
> "Huge news! Ethereum's Dencun upgrade just went live, slashing L2 fees by up to 90%. This is a game-changer for mainstream adoption!"

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/yourusername/tldr-buccaneer.git
cd tldr-buccaneer

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
nano .env  # Edit with your settings
```

### 3. Run

```bash
# Fleet mode (multi-persona)
python scripts/run_bot.py

# Single-bot mode
python scripts/run_bot.py --single

# Run once and exit
python scripts/run_bot.py --once

# Show persona leaderboard
python scripts/run_bot.py --stats
```

## Configuration

### Fleet Mode (Recommended for A/B Testing)

Set `FLEET_MODE=true` and configure wallets for each persona:

```env
FLEET_MODE=true
DEEPSEEK_API_KEY=your_key

# Each persona needs its own wallet
PERSONA_PIRATE_ADDRESS=0x...
PERSONA_PIRATE_KEY=...

PERSONA_STRAIGHT_ADDRESS=0x...
PERSONA_STRAIGHT_KEY=...

PERSONA_ORNERY_ADDRESS=0x...
PERSONA_ORNERY_KEY=...

PERSONA_HYPE_ADDRESS=0x...
PERSONA_HYPE_KEY=...

# Dice roll weights: probability of 0, 1, 2, 3 TL;DRs per article
DICE_WEIGHTS=0.25,0.40,0.25,0.10
```

### Single-Bot Mode (Legacy)

Set `FLEET_MODE=false` (or omit it):

```env
FLEET_MODE=false
DEEPSEEK_API_KEY=your_key
WALLET_ADDRESS=0x...
WALLET_PRIVATE_KEY=...
PIRATE_MODE=true  # or false for professional tone
```

## Dice Roll System

Each time an article comes in, the bot rolls dice to determine how many TL;DRs to post:

| Roll | Default Probability | Result |
|------|---------------------|--------|
| 0 | 25% | Skip this article |
| 1 | 40% | One random persona posts |
| 2 | 25% | Two random personas post |
| 3 | 10% | Three random personas post |

This creates natural variation - not every article gets a TL;DR, and when they do, it's unpredictable which persona(s) will respond.

Configure with `DICE_WEIGHTS=0.25,0.40,0.25,0.10`

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
    "hype": {"tldrs_posted": 41, "articles_processed": 41, "errors": 3}
  }
}
```

View the leaderboard:
```bash
python scripts/run_bot.py --stats
```

## How SQUID Farming Works

Leviathan News rewards contributors with SQUID tokens for valuable contributions. TL;DR summaries tagged with `tldr` earn tokens when:

1. Users find them helpful (upvotes)
2. The summary is accurate and well-written
3. The content adds value to the article

The A/B/C testing approach helps determine which writing style resonates most with the community, maximizing token earnings.

## Architecture

```
tldr-buccaneer/
├── src/
│   ├── config.py       # Configuration (single + fleet mode)
│   ├── personas.py     # Persona definitions and prompts
│   ├── wallet.py       # Ethereum wallet auth
│   ├── api_client.py   # Leviathan API client
│   ├── summarizer.py   # Deepseek TL;DR generation
│   ├── bot.py          # Single-bot logic (legacy)
│   └── coordinator.py  # Fleet coordinator + dice rolls
├── scripts/
│   └── run_bot.py      # Entry point
└── tests/
```

## Security Notes

- **Never commit your `.env` file**
- Private keys are used ONLY for signing authentication messages
- No blockchain transactions are sent; no gas is spent
- Use dedicated wallets for each persona

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

## License

MIT

---

*Built for the Leviathan News community. May the best bot win!*
