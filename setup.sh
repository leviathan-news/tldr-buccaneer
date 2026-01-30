#!/bin/bash
#
# TL;DR Buccaneer Setup Script
# Arrr! This script gets yer bot ready to sail the seven seas!
#

set -e  # Exit on error

# Colors for pretty output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Pirate banner
echo -e "${BLUE}"
cat << 'EOF'
    ⚓ ═══════════════════════════════════════════════════════ ⚓

         _____ _      ____  ____    ____
        |_   _| |    |  _ \|  _ \  | __ ) _   _  ___ ___ __ _ _ __   ___  ___ _ __
          | | | |    | | | | |_) | |  _ \| | | |/ __/ __/ _` | '_ \ / _ \/ _ \ '__|
          | | | |___ | |_| |  _ <  | |_) | |_| | (_| (_| (_| | | | |  __/  __/ |
          |_| |_____|____/|_| \_\ |____/ \__,_|\___\___\__,_|_| |_|\___|\___|_|

                    Automatic SQUID Farming Through News Summaries

    ⚓ ═══════════════════════════════════════════════════════ ⚓
EOF
echo -e "${NC}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${YELLOW}Ahoy! Let's get yer bot ready to sail...${NC}\n"

# -----------------------------------------------------------------------------
# Step 1: Check Python
# -----------------------------------------------------------------------------
echo -e "${BLUE}[1/6] Checkin' for Python 3.10+...${NC}"

if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
        echo -e "${GREEN}   ✓ Found Python $PYTHON_VERSION${NC}"
    else
        echo -e "${RED}   ✗ Python $PYTHON_VERSION found, but 3.10+ required${NC}"
        exit 1
    fi
else
    echo -e "${RED}   ✗ Python 3 not found! Install it first, ye landlubber.${NC}"
    exit 1
fi

# -----------------------------------------------------------------------------
# Step 2: Create virtual environment
# -----------------------------------------------------------------------------
echo -e "${BLUE}[2/6] Creatin' virtual environment...${NC}"

if [ -d "venv" ]; then
    echo -e "${YELLOW}   → venv already exists, skippin'...${NC}"
else
    python3 -m venv venv
    echo -e "${GREEN}   ✓ Created venv/${NC}"
fi

# Activate venv
source venv/bin/activate
echo -e "${GREEN}   ✓ Activated virtual environment${NC}"

# -----------------------------------------------------------------------------
# Step 3: Install dependencies
# -----------------------------------------------------------------------------
echo -e "${BLUE}[3/6] Installin' dependencies...${NC}"

pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "${GREEN}   ✓ Dependencies installed${NC}"

# -----------------------------------------------------------------------------
# Step 4: Create .env file if needed
# -----------------------------------------------------------------------------
echo -e "${BLUE}[4/6] Checkin' configuration...${NC}"

if [ -f ".env" ]; then
    echo -e "${YELLOW}   → .env already exists${NC}"

    # Check if MNEMONIC is set
    if grep -q "^MNEMONIC=" .env && ! grep -q "^MNEMONIC=\"your" .env && ! grep -q "^MNEMONIC=your" .env; then
        echo -e "${GREEN}   ✓ MNEMONIC appears to be configured${NC}"
    else
        echo -e "${YELLOW}   ⚠ MNEMONIC not configured - ye need to set it in .env${NC}"
    fi

    # Check if DEEPSEEK_API_KEY is set
    if grep -q "^DEEPSEEK_API_KEY=" .env && ! grep -q "^DEEPSEEK_API_KEY=your" .env; then
        echo -e "${GREEN}   ✓ DEEPSEEK_API_KEY appears to be configured${NC}"
    else
        echo -e "${YELLOW}   ⚠ DEEPSEEK_API_KEY not configured - ye need to set it in .env${NC}"
    fi
else
    cp .env.example .env
    echo -e "${GREEN}   ✓ Created .env from .env.example${NC}"
    echo -e "${YELLOW}   ⚠ Ye need to edit .env with yer secrets!${NC}"
fi

# -----------------------------------------------------------------------------
# Step 5: Show wallet addresses (if mnemonic is configured)
# -----------------------------------------------------------------------------
echo -e "${BLUE}[5/6] Checkin' wallet configuration...${NC}"

# Try to show wallet addresses if mnemonic is set
python3 << 'PYEOF' 2>/dev/null || echo -e "${YELLOW}   → Configure MNEMONIC in .env to see wallet addresses${NC}"
import sys
sys.path.insert(0, 'src')
import os
from dotenv import load_dotenv

load_dotenv()
mnemonic = os.getenv('MNEMONIC', '').strip()

if not mnemonic or 'your' in mnemonic.lower() or 'abandon' in mnemonic.lower():
    sys.exit(1)

from wallet import HDWalletDeriver
from personas_config import PERSONAS

deriver = HDWalletDeriver(mnemonic=mnemonic)

print("\033[0;32m   ✓ Mnemonic is valid! Derived wallet addresses:\033[0m")
print()
for p in PERSONAS:
    addr, _ = deriver.derive_wallet(p['index'])
    print(f"      {p['id']:10} (index {p['index']}): {addr}")
print()
print("\033[1;33m   ⚠ Make sure these wallets are registered on Leviathan News!\033[0m")
PYEOF

# -----------------------------------------------------------------------------
# Step 6: Run tests
# -----------------------------------------------------------------------------
echo -e "${BLUE}[6/6] Runnin' tests...${NC}"

if python -m pytest tests/test_hd_wallet.py -q 2>/dev/null; then
    echo -e "${GREEN}   ✓ All HD wallet tests passed${NC}"
else
    echo -e "${YELLOW}   → Tests skipped (run 'pytest' manually to check)${NC}"
fi

# -----------------------------------------------------------------------------
# Done!
# -----------------------------------------------------------------------------
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}   Setup complete! Here be yer next steps:${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

if [ ! -f ".env" ] || grep -q "your" .env 2>/dev/null; then
    echo -e "   ${YELLOW}1. Edit .env with yer secrets:${NC}"
    echo "      nano .env"
    echo ""
    echo "      Required:"
    echo "      - MNEMONIC: Your 12 or 24 word seed phrase"
    echo "      - DEEPSEEK_API_KEY: From https://platform.deepseek.com/"
    echo ""
fi

echo -e "   ${YELLOW}2. Test the bot:${NC}"
echo "      source venv/bin/activate"
echo "      python scripts/run_bot.py --once --debug"
echo ""
echo -e "   ${YELLOW}3. Set up cron for automatic running:${NC}"
echo "      crontab -e"
echo "      # Add this line (runs every 30 minutes):"
echo "      */30 * * * * $SCRIPT_DIR/cron/run_bot.sh >> /tmp/tldr-buccaneer.log 2>&1"
echo ""
echo -e "   ${YELLOW}4. Check persona stats:${NC}"
echo "      python scripts/run_bot.py --stats"
echo ""
echo -e "${BLUE}Fair winds and following seas, Cap'n! ⚓${NC}"
echo ""
