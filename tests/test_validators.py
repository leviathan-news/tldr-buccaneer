"""
Tests for output validators.

Validates that AI-generated comments are cleaned of meta-commentary,
banned AI-tell phrases, and internal LLM reasoning leaks before posting.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from validators import strip_preamble, check_banned_phrases, check_monologue_leak, validate_comment


# ---------------------------------------------------------------------------
# strip_preamble tests (12 tests)
# ---------------------------------------------------------------------------

class TestStripPreamble:
    """Tests for stripping AI meta-commentary prefixes and trailing sign-offs."""

    def test_strips_heres_my_comment_prefix(self):
        """Strips 'Here's my comment:' prefix from single-paragraph text."""
        text = "Here's my comment: Bitcoin mining difficulty just hit a new ATH."
        result = strip_preamble(text)
        assert result == "Bitcoin mining difficulty just hit a new ATH."

    def test_strips_here_is_the_prefix(self):
        """Strips 'Here is the' prefix from multi-paragraph text."""
        text = "Here is the summary of the article.\n\nETH staking yields are dropping."
        result = strip_preamble(text)
        assert result == "ETH staking yields are dropping."

    def test_strips_let_me_analyze_prefix(self):
        """Strips 'Let me analyze' prefix from text."""
        text = "Let me analyze this article.\n\nThe SEC just approved another ETF."
        result = strip_preamble(text)
        assert result == "The SEC just approved another ETF."

    def test_strips_sure_here_prefix(self):
        """Strips 'Sure, here' prefix from multi-paragraph text."""
        text = "Sure, here is a TL;DR.\n\nBinance delisted three tokens today."
        result = strip_preamble(text)
        assert result == "Binance delisted three tokens today."

    def test_strips_ill_provide_prefix(self):
        """Strips 'I'll provide' prefix from text."""
        text = "I'll provide a brief summary.\n\nLayer 2 fees are at historic lows."
        result = strip_preamble(text)
        assert result == "Layer 2 fees are at historic lows."

    def test_strips_based_on_my_research_prefix(self):
        """Strips 'Based on my research,' prefix from text."""
        text = "Based on my research, the token burn mechanism is deflationary."
        result = strip_preamble(text)
        assert result == "the token burn mechanism is deflationary."

    def test_strips_after_reviewing_prefix(self):
        """Strips 'After reviewing,' prefix from text."""
        text = "After reviewing, the governance proposal passed with 80% support."
        result = strip_preamble(text)
        assert result == "the governance proposal passed with 80% support."

    def test_strips_hope_this_helps_signoff(self):
        """Strips 'Hope this helps!' trailing sign-off."""
        text = "Solana TPS hit 5000 this week. Hope this helps!"
        result = strip_preamble(text)
        assert result == "Solana TPS hit 5000 this week."

    def test_strips_let_me_know_signoff(self):
        """Strips 'Let me know if...' trailing sign-off."""
        text = "The bridge exploit drained $50M. Let me know if you need more details."
        result = strip_preamble(text)
        assert result == "The bridge exploit drained $50M."

    def test_strips_what_do_you_think_signoff(self):
        """Strips 'What do you think?' trailing sign-off."""
        text = "DAO voting closes tomorrow. What do you think?"
        result = strip_preamble(text)
        assert result == "DAO voting closes tomorrow."

    def test_clean_text_passes_through(self):
        """Clean text without preamble or sign-off passes through unchanged."""
        text = "Bitcoin dominance is rising as alts bleed."
        result = strip_preamble(text)
        assert result == text

    def test_empty_string_returns_empty(self):
        """Empty input returns empty string."""
        assert strip_preamble("") == ""

    def test_only_preamble_returns_empty(self):
        """Text that is only a preamble prefix returns empty string after strip."""
        text = "Here's my comment:"
        result = strip_preamble(text)
        assert result.strip() == ""


# ---------------------------------------------------------------------------
# check_banned_phrases tests (19 tests)
# ---------------------------------------------------------------------------

class TestCheckBannedPhrases:
    """Tests for detecting banned AI-tell patterns in text."""

    # --- Template pattern: "The real X here isn't Y -- it's Z" ---

    def test_detects_the_real_x_here_template(self):
        """Detects 'the real X here' template pattern."""
        text = "The real story here isn't the hack -- it's the response time."
        assert check_banned_phrases(text) is True

    def test_detects_the_real_question_here(self):
        """Detects 'the real question here' variant."""
        text = "The real question here is whether DeFi can survive regulation."
        assert check_banned_phrases(text) is True

    # --- "What's more telling" variants ---

    def test_detects_whats_more_telling(self):
        """Detects 'What's more telling is...' filler."""
        text = "What's more telling is the lack of institutional buying."
        assert check_banned_phrases(text) is True

    def test_detects_the_more_interesting_signal(self):
        """Detects 'The more interesting signal is...' filler."""
        text = "The more interesting signal is the on-chain accumulation."
        assert check_banned_phrases(text) is True

    # --- Banned openers (start of text) ---

    def test_detects_the_real_opener(self):
        """Detects 'The real ' opener at start of text."""
        text = "The real impact of this merge will take months to see."
        assert check_banned_phrases(text) is True

    def test_detects_whats_interesting_opener(self):
        """Detects 'What's interesting' opener."""
        text = "What's interesting about this proposal is the tokenomics."
        assert check_banned_phrases(text) is True

    def test_detects_the_bigger_picture_opener(self):
        """Detects 'The bigger picture' opener."""
        text = "The bigger picture suggests a shift to modular blockchains."
        assert check_banned_phrases(text) is True

    def test_detects_worth_noting_opener(self):
        """Detects 'Worth noting' opener."""
        text = "Worth noting that the team has a history of delivering."
        assert check_banned_phrases(text) is True

    def test_detects_this_is_significant_opener(self):
        """Detects 'This is significant' opener."""
        text = "This is significant because it sets a regulatory precedent."
        assert check_banned_phrases(text) is True

    def test_detects_the_key_takeaway_opener(self):
        """Detects 'The key takeaway' opener."""
        text = "The key takeaway is that yields are compressing across the board."
        assert check_banned_phrases(text) is True

    def test_detects_timing_here_is_opener(self):
        """Detects 'Timing here is' opener."""
        text = "Timing here is suspicious given the insider wallet moves."
        assert check_banned_phrases(text) is True

    def test_detects_props_to_opener(self):
        """Detects 'Props to' opener."""
        text = "Props to the dev team for shipping on time."
        assert check_banned_phrases(text) is True

    def test_detects_theres_an_irony_opener(self):
        """Detects 'There's an irony' opener."""
        text = "There's an irony in a decentralization project having a single point of failure."
        assert check_banned_phrases(text) is True

    # --- Banned filler (anywhere in text) ---

    def test_detects_essentially_filler(self):
        """Detects 'essentially' filler word anywhere."""
        text = "This protocol is essentially a fork of Uniswap v3."
        assert check_banned_phrases(text) is True

    def test_detects_the_buried_lede_filler(self):
        """Detects 'the buried lede' filler phrase."""
        text = "But the buried lede is the new fee structure."
        assert check_banned_phrases(text) is True

    def test_detects_reveals_the_real_play_filler(self):
        """Detects 'reveals the real play' filler phrase."""
        text = "This partnership reveals the real play behind the merger."
        assert check_banned_phrases(text) is True

    def test_detects_signals_that_filler(self):
        """Detects 'signals that' filler phrase."""
        text = "The whale movement signals that a dump is incoming."
        assert check_banned_phrases(text) is True

    # --- Clean text (no banned phrases) ---

    def test_clean_comment_returns_false(self):
        """Clean comment without banned phrases returns False."""
        text = "ETH gas fees dropped to 3 gwei. Cheap transactions for everyone."
        assert check_banned_phrases(text) is False

    # --- Case insensitive ---

    def test_case_insensitive_detection(self):
        """Banned phrases detected regardless of case."""
        text = "THE REAL story HERE isn't the hack."
        assert check_banned_phrases(text) is True


# ---------------------------------------------------------------------------
# check_monologue_leak tests (13 tests)
# ---------------------------------------------------------------------------

class TestCheckMonologueLeak:
    """Tests for detecting internal LLM reasoning leaks."""

    def test_detects_let_me_search(self):
        text = "Let me search for the latest data on this token."
        assert check_monologue_leak(text) is True

    def test_detects_let_me_check(self):
        text = "Let me check the blockchain explorer for this tx."
        assert check_monologue_leak(text) is True

    def test_detects_let_me_use(self):
        text = "Let me use the API to verify this claim."
        assert check_monologue_leak(text) is True

    def test_detects_ill_use(self):
        text = "I'll use the search tool to find more info."
        assert check_monologue_leak(text) is True

    def test_detects_ill_search(self):
        text = "I'll search for the original announcement."
        assert check_monologue_leak(text) is True

    def test_detects_i_need_to(self):
        text = "I need to verify this against the whitepaper."
        assert check_monologue_leak(text) is True

    def test_detects_i_cant_access(self):
        text = "I can't access the paywall content."
        assert check_monologue_leak(text) is True

    def test_detects_heres_the_comment(self):
        text = "Here's the comment I wrote about the protocol upgrade."
        assert check_monologue_leak(text) is True

    def test_detects_tool_use_tag(self):
        text = "The token price tool_use result shows a 5% gain."
        assert check_monologue_leak(text) is True

    def test_detects_function_call(self):
        text = "function_call: get_price('BTC')"
        assert check_monologue_leak(text) is True

    def test_detects_cookies_appear(self):
        text = "The cookies appear to be blocking the scraper."
        assert check_monologue_leak(text) is True

    def test_detects_cookies_expired(self):
        text = "The cookies expired, so the session data is gone."
        assert check_monologue_leak(text) is True

    def test_clean_comment_returns_false(self):
        """Clean comment without monologue patterns returns False."""
        text = "Ethereum just completed the Dencun upgrade. L2 blobs are live."
        assert check_monologue_leak(text) is False

    def test_unicode_normalization_catches_homoglyphs(self):
        """Unicode normalization (NFKD) catches homoglyph tricks.

        Uses a fullwidth 'I' (\uff29) to try to bypass 'I need to' detection.
        After NFKD normalization, fullwidth 'I' decomposes to ASCII 'I'.
        """
        # \uff29 is fullwidth 'I' -- NFKD normalizes it to ASCII 'I'
        text = "\uff29 need to verify this data."
        assert check_monologue_leak(text) is True


# ---------------------------------------------------------------------------
# validate_comment tests (7 tests)
# ---------------------------------------------------------------------------

class TestValidateComment:
    """Tests for the unified validation pipeline."""

    def test_clean_comment_returns_ok(self):
        """Clean comment returns ('ok', cleaned_text)."""
        text = "Bitcoin ETF inflows hit $500M today. Bullish momentum continues."
        status, cleaned = validate_comment(text)
        assert status == "ok"
        assert cleaned == text

    def test_preamble_stripped_then_ok(self):
        """Preamble is stripped, rest passes validation."""
        text = "Here's my comment: BTC dominance just broke 55%."
        status, cleaned = validate_comment(text)
        assert status == "ok"
        assert cleaned == "BTC dominance just broke 55%."

    def test_banned_phrase_returns_retry(self):
        """Comment with banned phrase returns ('retry', None)."""
        text = "The real story here is the whale accumulation."
        status, cleaned = validate_comment(text)
        assert status == "retry"
        assert cleaned is None

    def test_monologue_leak_returns_reject(self):
        """Comment with monologue leak returns ('reject', None)."""
        text = "Let me search for the transaction hash first."
        status, cleaned = validate_comment(text)
        assert status == "reject"
        assert cleaned is None

    def test_monologue_takes_priority_over_banned(self):
        """When both monologue and banned phrases present, monologue (reject) wins."""
        text = "Let me check -- the real question here is the TVL drop."
        status, cleaned = validate_comment(text)
        assert status == "reject"
        assert cleaned is None

    def test_empty_after_strip_returns_reject(self):
        """Text that becomes empty after preamble strip returns ('reject', None)."""
        text = "Here's my comment:"
        status, cleaned = validate_comment(text)
        assert status == "reject"
        assert cleaned is None

    def test_whitespace_only_returns_reject(self):
        """Whitespace-only input returns ('reject', None)."""
        text = "   \n\t  "
        status, cleaned = validate_comment(text)
        assert status == "reject"
        assert cleaned is None
