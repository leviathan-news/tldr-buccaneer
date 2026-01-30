"""
Tests for HD wallet derivation.

Arrr! These tests verify our treasure chest derivation be workin' shipshape!
"""
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from wallet import HDWalletDeriver


# Standard test mnemonic (DO NOT use this for real funds!)
# This is the well-known "abandon" test mnemonic
TEST_MNEMONIC = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"

# Expected addresses for the test mnemonic at various indices
# These are deterministic and can be verified against any BIP-44 tool
EXPECTED_ADDRESSES = {
    0: "0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
    1: "0x6Fac4D18c912343BF86fa7049364Dd4E424Ab9C0",
    2: "0xb6716976A3ebe8D39aCEB04372f22Ff8e6802D7A",
    3: "0xF3f50213C1d2e255e4B2bAD430F8A38EEF8D718E",
}


class TestHDWalletDeriver:
    """Tests for HDWalletDeriver class."""

    def test_derive_wallet_deterministic(self):
        """Test that same mnemonic + index always produces same address."""
        deriver1 = HDWalletDeriver(mnemonic=TEST_MNEMONIC)
        deriver2 = HDWalletDeriver(mnemonic=TEST_MNEMONIC)

        address1, key1 = deriver1.derive_wallet(0)
        address2, key2 = deriver2.derive_wallet(0)

        assert address1 == address2, "Same mnemonic should produce same address"
        assert key1 == key2, "Same mnemonic should produce same private key"

    def test_derive_wallet_different_indices_different_addresses(self):
        """Test that different indices produce different addresses."""
        deriver = HDWalletDeriver(mnemonic=TEST_MNEMONIC)

        addresses = set()
        for i in range(10):
            address, _ = deriver.derive_wallet(i)
            addresses.add(address)

        assert len(addresses) == 10, "Each index should produce a unique address"

    def test_derive_wallet_expected_addresses(self):
        """Test that derivation produces expected addresses for known mnemonic."""
        deriver = HDWalletDeriver(mnemonic=TEST_MNEMONIC)

        for index, expected_address in EXPECTED_ADDRESSES.items():
            address, _ = deriver.derive_wallet(index)
            assert address == expected_address, f"Address at index {index} should match expected"

    def test_derive_wallet_returns_valid_private_key(self):
        """Test that derived private key is valid hex format."""
        deriver = HDWalletDeriver(mnemonic=TEST_MNEMONIC)
        _, private_key = deriver.derive_wallet(0)

        # Should be hex string (0x prefix optional in our implementation)
        assert private_key, "Private key should not be empty"
        # Should be 64 hex chars (32 bytes) with possible 0x prefix
        key_hex = private_key.replace("0x", "")
        assert len(key_hex) == 64, f"Private key should be 64 hex chars, got {len(key_hex)}"
        # Should be valid hex
        try:
            int(key_hex, 16)
        except ValueError:
            pytest.fail("Private key should be valid hexadecimal")

    def test_derive_wallet_negative_index_raises(self):
        """Test that negative index raises ValueError."""
        deriver = HDWalletDeriver(mnemonic=TEST_MNEMONIC)

        with pytest.raises(ValueError, match="non-negative"):
            deriver.derive_wallet(-1)

    def test_invalid_mnemonic_raises(self):
        """Test that invalid mnemonic raises ValueError."""
        with pytest.raises(ValueError, match="Invalid mnemonic"):
            HDWalletDeriver(mnemonic="invalid mnemonic phrase that is not valid")

    def test_empty_mnemonic_raises(self):
        """Test that empty mnemonic raises ValueError."""
        with pytest.raises(ValueError):
            HDWalletDeriver(mnemonic="")

    def test_derive_multiple(self):
        """Test deriving multiple wallets at once."""
        deriver = HDWalletDeriver(mnemonic=TEST_MNEMONIC)
        wallets = deriver.derive_multiple(count=4, start_index=0)

        assert len(wallets) == 4, "Should derive 4 wallets"

        for i, (address, key) in enumerate(wallets):
            expected_address = EXPECTED_ADDRESSES[i]
            assert address == expected_address, f"Wallet {i} address should match"
            assert key, f"Wallet {i} should have private key"

    def test_derive_multiple_with_offset(self):
        """Test deriving multiple wallets with start offset."""
        deriver = HDWalletDeriver(mnemonic=TEST_MNEMONIC)
        wallets = deriver.derive_multiple(count=2, start_index=2)

        assert len(wallets) == 2, "Should derive 2 wallets"
        assert wallets[0][0] == EXPECTED_ADDRESSES[2], "First wallet should be at index 2"
        assert wallets[1][0] == EXPECTED_ADDRESSES[3], "Second wallet should be at index 3"

    def test_large_index_works(self):
        """Test that large indices work (for scalability)."""
        deriver = HDWalletDeriver(mnemonic=TEST_MNEMONIC)

        # Test index 1000
        address, key = deriver.derive_wallet(1000)
        assert address.startswith("0x"), "Should produce valid Ethereum address"
        assert len(address) == 42, "Address should be 42 chars (0x + 40 hex)"

    def test_private_key_can_derive_same_address(self):
        """Test that the private key derives the same address (roundtrip)."""
        from eth_account import Account

        deriver = HDWalletDeriver(mnemonic=TEST_MNEMONIC)
        address, private_key = deriver.derive_wallet(0)

        # Verify the private key produces the same address
        account = Account.from_key(private_key)
        assert account.address == address, "Private key should derive same address"


class TestHDWalletDeriverEdgeCases:
    """Edge case tests for HDWalletDeriver."""

    def test_different_mnemonic_different_addresses(self):
        """Test that different mnemonics produce different addresses."""
        mnemonic1 = TEST_MNEMONIC
        mnemonic2 = "zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo wrong"

        deriver1 = HDWalletDeriver(mnemonic=mnemonic1)
        deriver2 = HDWalletDeriver(mnemonic=mnemonic2)

        address1, _ = deriver1.derive_wallet(0)
        address2, _ = deriver2.derive_wallet(0)

        assert address1 != address2, "Different mnemonics should produce different addresses"

    def test_whitespace_in_mnemonic_handled(self):
        """Test that extra whitespace in mnemonic is handled."""
        # Mnemonic with extra spaces
        mnemonic_with_spaces = "  abandon  abandon  abandon  abandon  abandon  abandon  abandon  abandon  abandon  abandon  abandon  about  "

        deriver = HDWalletDeriver(mnemonic=mnemonic_with_spaces)
        address, _ = deriver.derive_wallet(0)

        assert address == EXPECTED_ADDRESSES[0], "Whitespace should be normalized"
