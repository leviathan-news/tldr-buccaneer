#!/bin/bash
#
# TL;DR Buccaneer Cron Runner
# Add to crontab: */30 * * * * /path/to/tldr-buccaneer/cron/run_bot.sh >> /tmp/tldr-buccaneer.log 2>&1
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
source venv/bin/activate

# Log timestamp
echo ""
echo "========================================"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting TL;DR Buccaneer run"
echo "========================================"

# Run the bot once
python scripts/run_bot.py --once

echo "$(date '+%Y-%m-%d %H:%M:%S') - Run complete"
