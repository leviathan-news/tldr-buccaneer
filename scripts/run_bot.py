#!/usr/bin/env python3
"""
Entry point for the TL;DR Buccaneer bot.

Supports two modes:
1. Single-bot mode (legacy): One persona, one wallet
2. Fleet mode: Multiple personas with A/B/C testing

Usage:
    python scripts/run_bot.py              # Run in continuous mode
    python scripts/run_bot.py --once       # Run once and exit
    python scripts/run_bot.py --stats      # Show persona leaderboard
    python scripts/run_bot.py --fleet      # Force fleet mode
"""
import argparse
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import Config, get_config
from bot import TLDRBuccaneer
from coordinator import FleetCoordinator, DiceRollConfig


def print_banner(fleet_mode: bool = False):
    """Print the startup banner."""
    if fleet_mode:
        print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║     ⚓ TL;DR BUCCANEER FLEET ⚓                                ║
    ║     Multi-Persona A/B/C Testing Mode                          ║
    ║                                                               ║
    ║     "May the best bot win!"                                   ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
        """)
    else:
        print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║     ⚓ TL;DR BUCCANEER ⚓                                      ║
    ║     Automatic SQUID Farming Through News Summaries            ║
    ║                                                               ║
    ║     "Arrr! I be summarizin' the news for ye landlubbers!"     ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
        """)


def run_single_bot(config: Config, once: bool = False):
    """Run in single-bot mode (legacy)."""
    bot = TLDRBuccaneer.from_config(config)

    if once:
        posted = bot.run_once()
        stats = bot.get_stats()
        print(f"\nRun complete! Stats: {stats}")
        print(f"TL;DRs posted this run: {posted}")
    else:
        bot.run_forever()


def run_fleet(config: Config, once: bool = False, show_stats: bool = False):
    """Run in fleet mode with multiple personas."""
    # Create coordinator with dice roll config
    # The coordinator will handle HD wallet derivation from the mnemonic
    dice_config = DiceRollConfig(weights=config.dice_weights)
    coordinator = FleetCoordinator(config=config, dice_config=dice_config)

    # Add personas from config - wallets are derived from mnemonic using persona index
    for persona_config in config.personas:
        coordinator.add_persona(persona_id=persona_config.id)
        # No need to pass wallet credentials - they're derived from MNEMONIC!

    if show_stats:
        coordinator.print_leaderboard()
        return

    print(f"\nFleet configured with {len(config.personas)} personas:")
    for p in config.personas:
        print(f"  - {p.id} (index {p.index})")
    print(f"\nDice weights (0,1,2,3 TL;DRs): {config.dice_weights}")
    print()

    if once:
        result = coordinator.run_once()
        print(f"\nRun complete!")
        print(f"Articles checked: {result['articles_checked']}")
        print(f"TL;DRs posted: {result['tldrs_posted']}")
        coordinator.print_leaderboard()
    else:
        coordinator.run_forever()


def main():
    parser = argparse.ArgumentParser(
        description="TL;DR Buccaneer - Automatic SQUID farming through news summaries"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (don't loop)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only show warnings and errors",
    )
    parser.add_argument(
        "--fleet",
        action="store_true",
        help="Force fleet mode (multiple personas)",
    )
    parser.add_argument(
        "--single",
        action="store_true",
        help="Force single-bot mode (legacy)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show persona leaderboard and exit (fleet mode only)",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.debug else (logging.WARNING if args.quiet else logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        config = get_config()

        # Determine mode
        if args.single:
            fleet_mode = False
        elif args.fleet:
            fleet_mode = True
        else:
            fleet_mode = config.fleet_mode

        print_banner(fleet_mode)

        if fleet_mode:
            run_fleet(config, once=args.once, show_stats=args.stats)
        else:
            if args.stats:
                print("--stats is only available in fleet mode")
                sys.exit(1)
            run_single_bot(config, once=args.once)

    except ValueError as e:
        print(f"\nConfiguration error: {e}")
        print("Make sure your .env file is properly configured!")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nDroppin' anchor... Goodbye, matey!")
        sys.exit(0)
    except Exception as e:
        logging.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
