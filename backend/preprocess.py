"""Text preprocessing utilities for YouTube comment analysis.

Two separate cleaning paths:
  - clean_for_sentiment()  — keeps emojis, DistilBERT/RoBERTa reads them
  - clean_for_clustering() — strips emojis, cleaner for TF-IDF / K-Means

SpaCy-based lemmatization is intentionally kept in cluster.py rather than
here, because:
  - Transformer models work best on natural, un-lemmatized text
  - K-Means clustering benefits from lemmatization for cleaner TF-IDF vectors
  - This module stays fast and dependency-light for the sentiment pipeline

Slang normalization runs on both paths so the models receive semantically
clear text instead of internet shorthand they may misread.
"""

import logging
import re

logger = logging.getLogger(__name__)

# ── Regex patterns ─────────────────────────────────────────────────────────────

_URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001f600-\U0001f64f"  # emoticons
    "\U0001f300-\U0001f5ff"  # symbols & pictographs
    "\U0001f680-\U0001f6ff"  # transport & map symbols
    "\U0001f1e0-\U0001f1ff"  # flags
    "\U00002700-\U000027bf"  # dingbats
    "\U0000fe00-\U0000fe0f"  # variation selectors
    "\U0001f900-\U0001f9ff"  # supplemental symbols
    "\U0001fa00-\U0001fa6f"  # chess symbols
    "\U0001fa70-\U0001faff"  # symbols extended-A
    "\U00002702-\U000027b0"
    "]+",
    flags=re.UNICODE,
)
_WHITESPACE_PATTERN = re.compile(r"\s+")

# ── Slang normalization map ────────────────────────────────────────────────────
# Maps common internet/YouTube slang to plain English equivalents.
#
# Design notes:
#   - Keys are lowercase; matching is case-insensitive (see normalize_slang)
#   - Replacements preserve the original sentiment signal in plain English
#   - Multi-word slang (e.g. "no cap") uses exact phrase matching via regex
#   - Sorted by length descending so longer phrases match before substrings
#   - Expand this list as new slang is observed in real comment data

_SLANG_MAP = {
    # Positive slang
    "slaps":                        "sounds amazing",
    "banger":                       "excellent",
    "fire":                         "excellent",
    "bussin bussin":                "extremely good",
    "bussin":                       "very good",
    "goat":                         "greatest of all time",
    "goated":                       "greatest",
    "slay":                         "performed excellently",
    "based":                        "admirable",
    "hits different":               "feels special",
    "understood the assignment":    "performed excellently",
    "ate and left no crumbs":       "performed perfectly",
    "ate":                          "performed excellently",
    "on point":                     "accurate and excellent",
    "lowkey fire":                  "somewhat excellent",
    "actually bussin":              "genuinely very good",
    "big w":                        "great success",
    "certified w":                  "great success",
    "w":                            "success",
    "no cap":                       "honestly",
    "facts":                        "that is true",
    "lowkey":                       "somewhat",
    "highkey":                      "very much",
    "lit":                          "exciting",
    "valid":                        "correct",
    "iykyk":                        "this is great if you know",
    "gg":                           "well done",
    "fav":                          "favorite",
    "fave":                         "favorite",
    "omg":                          "this is amazing",

    # Negative slang
    "mid af":                       "very mediocre",
    "mid":                          "mediocre",
    "big l":                        "major failure",
    "l":                            "failure",
    "ratioed":                      "this was disliked by many",
    "ratio":                        "this is disliked",
    "dogwater":                     "very bad",
    "trash":                        "very bad",
    "cap":                          "that is a lie",
    "sus":                          "suspicious",
    "cooked":                       "ruined",
    "bricked":                      "failed badly",
    "flopped":                      "failed",
    "flop":                         "failure",
    "cringe":                       "embarrassing",
    "yikes":                        "that is bad",
    "oof":                          "that is unfortunate",
    "smh":                          "that is disappointing",
    "bruh":                         "this is ridiculous",
    "not it":                       "this is wrong",
    "fell off":                     "declined in quality",

    # Neutral / contextual
    "fr fr":                        "seriously",
    "fr":                           "seriously",
    "deadass":                      "seriously",
    "no shot":                      "that is unbelievable",
    "ngl":                          "honestly",
    "tbh":                          "to be honest",
    "imo":                          "in my opinion",
    "istg":                         "i promise",
    "ong":                          "honestly",
    "rn":                           "right now",

    # YouTube / domain specific
    "collab":                       "collaboration",
    "asmrtist":                     "asmr creator",
    "yt":                           "youtube",
    "vid":                          "video",
    "sub":                          "subscriber",
    "unsub":                        "unsubscribe",
    "ain't it":                     "this is wrong",
}

# Compiled regex — longer phrases sorted first to prevent partial matches
_SLANG_PATTERN = re.compile(
    r"\b(" + "|".join(
        re.escape(k)
        for k in sorted(_SLANG_MAP.keys(), key=len, reverse=True)
    ) + r")\b",
    flags=re.IGNORECASE,
)


# ── Slang normalization ────────────────────────────────────────────────────────

def normalize_slang(text: str) -> str:
    """Replace internet slang with plain English equivalents.

    Uses whole-word regex matching so context is preserved — e.g.
    "fire station" is left alone but standalone "fire" is normalized.

    Args:
        text: A single comment string.

    Returns:
        Text with slang terms replaced by plain English equivalents.
    """
    return _SLANG_PATTERN.sub(
        lambda m: _SLANG_MAP[m.group(0).lower()], text
    )


# ── Two cleaning paths ─────────────────────────────────────────────────────────

def clean_for_sentiment(text: str) -> str:
    """Clean a comment for transformer sentiment inference.

    Keeps emojis — RoBERTa/DistilBERT tokenizers handle them natively
    and they carry strong sentiment signal (e.g. 😍 🔥 💀).

    Pipeline:
        1. Strip URLs
        2. Normalize slang → plain English
        3. Collapse whitespace

    Args:
        text: A single raw comment string.

    Returns:
        Cleaned text with emojis preserved, ready for sentiment model.
    """
    if not text or not isinstance(text, str):
        return ""
    text = _URL_PATTERN.sub("", text)
    text = normalize_slang(text)
    text = _WHITESPACE_PATTERN.sub(" ", text).strip()
    return text


def clean_for_clustering(text: str) -> str:
    """Clean a comment for TF-IDF vectorization and K-Means clustering.

    Strips emojis — they add noise to TF-IDF term frequency counts and
    hurt cluster separation. SpaCy lemmatization in cluster.py runs after
    this step for further normalization.

    Pipeline:
        1. Strip URLs
        2. Strip emojis
        3. Normalize slang → plain English
        4. Collapse whitespace

    Args:
        text: A single raw comment string.

    Returns:
        Cleaned text without emojis, ready for clustering pipeline.
    """
    if not text or not isinstance(text, str):
        return ""
    text = _URL_PATTERN.sub("", text)
    text = _EMOJI_PATTERN.sub("", text)
    text = normalize_slang(text)
    text = _WHITESPACE_PATTERN.sub(" ", text).strip()
    return text


# ── Batch helpers ──────────────────────────────────────────────────────────────

def sentiment_batch(comments: list[str]) -> list[str]:
    """Apply clean_for_sentiment to a list of raw comments."""
    return [clean_for_sentiment(c) for c in comments] if comments else []


def clustering_batch(comments: list[str]) -> list[str]:
    """Apply clean_for_clustering to a list of raw comments."""
    return [clean_for_clustering(c) for c in comments] if comments else []