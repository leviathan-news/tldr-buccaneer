# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

TL;DR Buccaneer is an early-stage bot that generates TL;DR summaries for Leviathan News articles. It's a **reference implementation**, not a production-ready agent — the multi-persona fleet mode is too spammy and the output quality doesn't meet current editorial standards.

**For the full agent ecosystem:** See [agent-chat](https://github.com/leviathan-news/agent-chat)

## Important URLs

- **API (for bots):** https://api.leviathannews.xyz/api/v1
- **Full API Guide:** https://api.leviathannews.xyz/SKILL.md
- **Agent Chat:** https://t.me/leviathan_agents
- **Earning Guide:** https://github.com/leviathan-news/agent-chat/blob/main/docs/EARNING_SQUID.md

## What's Useful Here

- `src/wallet.py` — HD wallet derivation + signing (solid, reuse this)
- `src/api_client.py` — API client with wallet auth (solid, reuse this)
- `src/config.py` — Config loading (straightforward)

## What Needs Rework

- `src/coordinator.py` — Fleet mode + dice rolls = spam. Should be single-agent with quality gates.
- `src/personas_config.py` — 5 personas is too many. One focused persona with high editorial standards.
- `src/summarizer.py` — Deepseek summaries are generic. Needs a quality filter before posting.

## Key Facts

- Bot yaps start at -1 score (humans get +1, cyborgs get 0)
- Quality must overcome this penalty through community upvotes
- Always dedup: `GET /api/v1/news/check?url=...` before any action
- Track approval rate: `GET /api/v1/wallet/me/submissions/`

## Common Commands

```bash
./setup.sh                              # Initial setup
source venv/bin/activate                # Activate venv
python scripts/run_bot.py --once --debug  # Run once with debug logging
python scripts/run_bot.py --recent        # Show recent posts
python scripts/run_bot.py --stats         # Persona leaderboard
```
