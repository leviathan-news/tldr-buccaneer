"""
Output validators for AI-generated comments.

Three sequential validation checks filter out AI meta-commentary,
banned AI-tell phrases, and internal LLM reasoning leaks before
a comment is posted to Leviathan News.

Functions:
    strip_preamble    -- Remove AI prefix/suffix meta-commentary.
    check_banned_phrases -- Detect formulaic AI-tell patterns.
    check_monologue_leak -- Detect internal LLM reasoning leakage.
    validate_comment     -- Unified pipeline: strip -> check -> verdict.
"""

import re
import unicodedata
from typing import Tuple, Optional


# ---------------------------------------------------------------------------
# Preamble prefixes (case-insensitive) that AI models prepend to output.
# Each entry is matched at the start of the text (or the first paragraph
# if the text has multiple paragraphs).
# ---------------------------------------------------------------------------
_PREAMBLE_PREFIXES: list[str] = [
    "Here's my comment:",
    "Here is the",
    "Let me analyze",
    "Sure, here",
    "I'll provide",
    "Based on my research,",
    "After reviewing,",
]

# ---------------------------------------------------------------------------
# Trailing sign-offs AI models sometimes append.
# Matched case-insensitively against the tail of the text.
# ---------------------------------------------------------------------------
_SIGNOFF_PATTERNS: list[re.Pattern] = [
    re.compile(r"\s*Hope this helps!?\s*$", re.IGNORECASE),
    re.compile(r"\s*Let me know if[\s\S]*$", re.IGNORECASE),
    re.compile(r"\s*What do you think\??\s*$", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Banned openers -- only checked at the start of the text (case-insensitive).
# ---------------------------------------------------------------------------
_BANNED_OPENERS: list[str] = [
    "The real ",
    "What's interesting",
    "The bigger picture",
    "Worth noting",
    "This is significant",
    "The key takeaway",
    "Timing here is",
    "Props to",
    "There's an irony",
]

# ---------------------------------------------------------------------------
# Banned filler phrases -- checked anywhere in the text (case-insensitive).
# ---------------------------------------------------------------------------
_BANNED_FILLERS: list[str] = [
    "essentially",
    "fundamentally",
    "notably",
    "arguably",
    "it's worth mentioning",
    "it's worth noting",
    "which is effectively",
    "the buried lede",
    "the real lede",
    "reveals the real play",
    "signals that",
    "suggests that",
    "what's more telling",
    "the more interesting signal",
]

# ---------------------------------------------------------------------------
# Regex for the template pattern: "the real <word> here"
# Catches "The real story here", "the real question here", etc.
# ---------------------------------------------------------------------------
_TEMPLATE_REGEX = re.compile(r"the real\s+\w+\s+here", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Monologue-leak patterns -- internal LLM reasoning that should never appear
# in a published comment. Matched after NFKD unicode normalization + lowercase.
# ---------------------------------------------------------------------------
_MONOLOGUE_PATTERNS: list[str] = [
    "let me search",
    "let me check",
    "let me use",
    "i'll use",
    "i'll search",
    "i need to",
    "i can't access",
    "i cannot access",
    "here's the comment",
    "here is the comment",
    "here's my comment",
    "here is my comment",
    "tool_use",
    "tool_result",
    "function_call",
    "cookies appear",
    "cookies expired",
    "cookies are expired",
]


def strip_preamble(text: str) -> str:
    """Strip AI meta-commentary prefixes and trailing sign-offs.

    Processing order:
      1. If the text has multiple paragraphs (separated by blank lines) and
         the first paragraph matches a known preamble prefix, discard the
         first paragraph and keep the rest.
      2. If the text is a single paragraph (or step 1 didn't trigger),
         check if it starts with any preamble prefix and strip it.
      3. Strip any trailing sign-off patterns from the result.

    Args:
        text: Raw AI-generated comment text.

    Returns:
        Cleaned text with preamble and sign-offs removed.
    """
    if not text:
        return ""

    cleaned = text.strip()

    # --- Step 1: Multi-paragraph preamble removal ---
    # Split on double-newline (blank line separators).
    paragraphs = re.split(r"\n\s*\n", cleaned, maxsplit=1)
    if len(paragraphs) > 1:
        first_lower = paragraphs[0].strip().lower()
        # If the first paragraph begins with a known preamble, discard it.
        for prefix in _PREAMBLE_PREFIXES:
            if first_lower.startswith(prefix.lower()):
                cleaned = paragraphs[1].strip()
                break

    # --- Step 2: Single-paragraph prefix removal ---
    # After multi-paragraph handling, try inline prefix stripping on whatever remains.
    text_lower = cleaned.lower()
    for prefix in _PREAMBLE_PREFIXES:
        if text_lower.startswith(prefix.lower()):
            # Remove the prefix and any leading whitespace after it.
            cleaned = cleaned[len(prefix):].lstrip()
            break

    # --- Step 3: Trailing sign-off removal ---
    for pattern in _SIGNOFF_PATTERNS:
        cleaned = pattern.sub("", cleaned)

    return cleaned.strip()


def check_banned_phrases(text: str) -> bool:
    """Check if text contains banned AI-tell patterns.

    Checks three categories (all case-insensitive):
      1. Template regex: "the real <word> here" pattern.
      2. Banned openers: phrases that only trigger at the start of the text.
      3. Banned fillers: phrases that trigger anywhere in the text.

    Args:
        text: Comment text to check.

    Returns:
        True if any banned pattern is detected, False otherwise.
    """
    if not text:
        return False

    # Template regex match (anywhere in text).
    if _TEMPLATE_REGEX.search(text):
        return True

    text_lower = text.lower()

    # Banned openers -- must appear at the start of the text.
    for opener in _BANNED_OPENERS:
        if text_lower.startswith(opener.lower()):
            return True

    # Banned fillers -- can appear anywhere in the text.
    for filler in _BANNED_FILLERS:
        if filler.lower() in text_lower:
            return True

    return False


def check_monologue_leak(text: str) -> bool:
    """Check if text contains internal LLM reasoning patterns.

    Applies NFKD unicode normalization before matching to defeat
    homoglyph substitution tricks (e.g. fullwidth characters).

    Args:
        text: Comment text to check.

    Returns:
        True if any monologue-leak pattern is detected, False otherwise.
    """
    if not text:
        return False

    # NFKD normalization decomposes compatibility characters (e.g. fullwidth
    # latin letters \uff21-\uff3a) into their ASCII base forms, so homoglyph
    # tricks don't bypass detection.
    normalized = unicodedata.normalize("NFKD", text).lower()

    for pattern in _MONOLOGUE_PATTERNS:
        if pattern in normalized:
            return True

    return False


def validate_comment(text: str) -> Tuple[str, Optional[str]]:
    """Unified validation pipeline for AI-generated comments.

    Processing order:
      1. Strip preamble (prefixes + sign-offs).
      2. If empty after strip -> reject.
      3. Check for monologue leaks (highest severity) -> reject.
      4. Check for banned phrases -> retry (caller should re-generate).
      5. Otherwise -> ok, return cleaned text.

    Args:
        text: Raw AI-generated comment text.

    Returns:
        Tuple of (status, cleaned_text) where:
          - ("ok", cleaned_text)  -- comment is acceptable.
          - ("retry", None)       -- banned phrase detected, re-generate.
          - ("reject", None)      -- monologue leak or empty, do not post.
    """
    # Step 1: Strip preamble and sign-offs.
    cleaned = strip_preamble(text)

    # Step 2: Reject if empty after cleaning.
    if not cleaned or not cleaned.strip():
        return ("reject", None)

    # Step 3: Monologue leak detection (hard reject, highest priority).
    if check_monologue_leak(cleaned):
        return ("reject", None)

    # Step 4: Banned phrase detection (soft reject, allows retry).
    if check_banned_phrases(cleaned):
        return ("retry", None)

    # Step 5: All checks passed.
    return ("ok", cleaned)
