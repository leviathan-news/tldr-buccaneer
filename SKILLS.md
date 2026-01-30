# TL;DR Buccaneer - Claude Code Skills

This repository includes **Claude Code skills** that help you set up and use the bot with AI assistance.

## Quick Start with Claude Code

1. **Install Claude Code** (if you haven't already):
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```

2. **Clone this repo and open it with Claude**:
   ```bash
   git clone https://github.com/leviathan-news/tldr-buccaneer.git
   cd tldr-buccaneer
   claude
   ```

3. **Ask Claude to help you set up**:
   ```
   Help me set up the TL;DR bot
   ```

Claude will automatically use the `setup-tldr-bot` skill to guide you through the entire setup process.

---

## Available Skills

### `setup-tldr-bot`

**What it does:** Guides you through setting up the TL;DR Buccaneer bot from scratch.

**Covers:**
- Running the setup script
- Configuring your `.env` file (mnemonic, API keys)
- Setting up persona display names on Leviathan News
- Testing the bot
- Common commands and troubleshooting

**How to trigger:** Just ask Claude anything about setting up the bot:
- "Help me set up the bot"
- "How do I configure this?"
- "I'm new, where do I start?"

---

## What Are Claude Code Skills?

Skills are contextual guides that help Claude understand your project and provide better assistance. When you open this repository in Claude Code, these skills are automatically available.

**Learn more:** [Claude Code Documentation](https://docs.anthropic.com/en/docs/claude-code)

---

## Manual Setup (Without Claude Code)

If you prefer to set up manually without AI assistance, see the [README.md](README.md) for traditional setup instructions.
