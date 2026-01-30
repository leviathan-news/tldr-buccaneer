"""
Ethereum wallet authentication for the TL;DR Buccaneer bot.

Arrr! This be where we prove our identity on the blockchain seas!

Supports two modes:
1. Direct private key authentication (legacy)
2. HD wallet derivation from BIP-39 mnemonic (fleet mode)
"""
import logging
from dataclasses import dataclass
from eth_account import Account
from eth_account.messages import encode_defunct

logger = logging.getLogger(__name__)


@dataclass
class HDWalletDeriver:
    """
    Derives Ethereum wallets from a BIP-39 mnemonic using BIP-44 derivation paths.

    Arrr! One master key to rule 'em all - each persona gets their own treasure chest
    derived from the same seed phrase!

    Uses standard Ethereum derivation path: m/44'/60'/0'/0/N
    where N is the persona index (0, 1, 2, ...)
    """

    mnemonic: str

    def __post_init__(self):
        """Enable HD wallet features and validate the mnemonic."""
        # eth-account requires explicit opt-in for HD wallet features
        Account.enable_unaudited_hdwallet_features()

        # Normalize the mnemonic - strip whitespace and ensure single spaces
        self.mnemonic = " ".join(self.mnemonic.split())

        # Validate the mnemonic by attempting to derive the first account
        try:
            self.derive_wallet(0)
        except Exception as e:
            raise ValueError(f"Invalid mnemonic phrase: {e}")

    def derive_wallet(self, index: int) -> tuple[str, str]:
        """
        Derive a wallet at the given BIP-44 index.

        Args:
            index: The derivation index (0, 1, 2, ...)

        Returns:
            Tuple of (address, private_key_hex)
        """
        if index < 0:
            raise ValueError(f"Derivation index must be non-negative, got {index}")

        account = Account.from_mnemonic(
            self.mnemonic,
            account_path=f"m/44'/60'/0'/0/{index}"
        )

        # Return address and private key as hex string
        return account.address, account.key.hex()

    def derive_multiple(self, count: int, start_index: int = 0) -> list[tuple[str, str]]:
        """
        Derive multiple wallets starting from the given index.

        Args:
            count: Number of wallets to derive
            start_index: Starting derivation index

        Returns:
            List of (address, private_key_hex) tuples
        """
        return [
            self.derive_wallet(start_index + i)
            for i in range(count)
        ]


@dataclass
class WalletAuth:
    """Handles Ethereum wallet authentication with the Leviathan API."""

    address: str
    private_key: str

    def __post_init__(self):
        """Validate the wallet configuration."""
        # Ensure address is checksum format
        self.address = Account.from_key(self.private_key).address

        # Verify the private key matches the address
        derived_address = Account.from_key(self.private_key).address
        if derived_address.lower() != self.address.lower():
            raise ValueError(
                f"Arrr! The private key don't match the address ye gave me! "
                f"Expected {self.address}, got {derived_address}"
            )

    def sign_message(self, message: str) -> str:
        """
        Sign a message with the wallet's private key.

        Args:
            message: The message to sign (typically the nonce message from the API).

        Returns:
            The signature as a hex string.
        """
        # Encode the message for signing
        message_encoded = encode_defunct(text=message)

        # Sign with private key
        signed = Account.sign_message(message_encoded, private_key=self.private_key)

        logger.debug(f"Signed message for address {self.address[:10]}...")
        return signed.signature.hex()

    @classmethod
    def from_config(cls, config) -> "WalletAuth":
        """Create a WalletAuth instance from configuration."""
        return cls(
            address=config.wallet_address,
            private_key=config.wallet_private_key,
        )
