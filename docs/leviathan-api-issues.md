# Leviathan API Issues for Bot Developers

Hi Leviathan team! We've been building [TL;DR Buccaneer](https://github.com/leviathan-news/tldr-buccaneer), a multi-persona bot for posting TL;DR summaries. We hit a few API issues that would help bot developers if fixed.

---

## Issue 1: Profile Update - Partial Fix

**Endpoint:** `PUT /api/v1/wallet/profile/`

**Status:** **PARTIALLY FIXED** (2026-01-30) - `display_name` now persists when using form data.

**What's fixed:**
```python
# This now works correctly:
response = session.put(
    "https://api.leviathannews.xyz/api/v1/wallet/profile/",
    data={"display_name": "My Bot Name", "bio": "A helpful bot"}
)
print(response.json())
# Returns: {"success": true, "user": {"display_name": "My Bot Name", ...}}
```

**What's still broken:** JSON body requests return 500 error:
```python
# This still fails with 500:
session.put(url, json={"display_name": "Name"})
# Error: "You cannot access body after reading from request's data stream"

# Workaround: Use form data instead
session.put(url, data={"display_name": "Name"})  # Works!
```

**Recommendation:** Use form data (`data=`) instead of JSON (`json=`) for profile updates.

---

## Issue 2: No Endpoint to Get User's Yaps by Wallet

**Current state:** To see what a bot posted, you must either:
- Iterate through all articles checking each one's yaps (slow, expensive)
- Track posts locally (what we do now in `stats.json`)

**Proposed endpoint:** `GET /api/v1/wallet/{address}/yaps/` or `GET /api/v1/user/{user_id}/yaps/`

**Example response:**
```json
{
  "count": 42,
  "results": [
    {
      "id": 24255,
      "text": "TL;DR summary...",
      "parent_id": 24178,
      "parent_headline": "Article headline...",
      "tags": ["tldr"],
      "created_at": "2026-01-30T20:06:35Z",
      "score": 5
    }
  ]
}
```

**Use cases:**
- Bot developers verifying posts went through
- Users viewing their own comment history
- Analytics and leaderboards

---

## Issue 3: Public Profile Lookup (Future Enhancement)

**Current state:** `/api/v1/wallet/me/` exists but requires authentication. No public endpoint to look up profiles.

**Proposed endpoint:** `GET /api/v1/wallet/{address}/` (for future consideration)

This would be nice for bot analytics and leaderboards, but we understand if it's not a priority right now. The authenticated `/wallet/me/` endpoint covers the main use case of checking your own profile.

---

## Summary

| Priority | Issue | Status |
|----------|-------|--------|
| ~~**High**~~ | ~~display_name not persisting~~ | **FIXED** (use form data) |
| **High** | JSON body returns 500 | Bug - open |
| **Medium** | Get user's yaps by wallet | Missing - would help a lot |
| **Low** | Public profile lookup | Future enhancement |

Happy to provide more details or help test fixes. Thanks for building a great platform!

---

*From the TL;DR Buccaneer team*
*2026-01-30*
