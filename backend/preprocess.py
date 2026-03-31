"""Text preprocessing utilities for YouTube comment analysis.

Two separate cleaning paths:
  - clean_for_sentiment()  — keeps emojis and casing, RoBERTa reads them as signal
  - clean_for_clustering() — strips emojis, lowercases, cleaner for TF-IDF / K-Means

Slang normalization runs on both paths so models receive semantically
clear text instead of internet shorthand they may misread.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Regex patterns

URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")
EMOJI_PATTERN = re.compile(
    "["
    "\U0001f600-\U0001f64f"
    "\U0001f300-\U0001f5ff"
    "\U0001f680-\U0001f6ff"
    "\U0001f1e0-\U0001f1ff"
    "\U00002700-\U000027bf"
    "\U0000fe00-\U0000fe0f"
    "\U0001f900-\U0001f9ff"
    "\U0001fa00-\U0001fa6f"
    "\U0001fa70-\U0001faff"
    "\U00002702-\U000027b0"
    "]+",
    flags=re.UNICODE,
)
WHITESPACE_PATTERN = re.compile(r"\s+")

# Slang normalization map

SLANG_MAP = {
    # Positive slang
    "slaps":                        "sounds amazing",
    "banger":                       "excellent",
    "fire":                         "excellent",
    "bussin":                       "very good",
    "goat":                         "greatest of all time",
    "goated":                       "greatest",
    "slay":                         "performed excellently",
    "based":                        "admirable",
    "hits different":               "feels special",
    "on point":                     "accurate and excellent",
    "w":                            "success",
    "no cap":                       "honestly",
    "facts":                        "that is true",
    "lit":                          "exciting",
    "valid":                        "correct",
    "gg":                           "well done",
    "fav":                          "favorite",
    # Negative slang
    "mid":                          "mediocre",
    "l":                            "failure",
    "ratioed":                      "this was disliked by many",
    "ratio":                        "this is disliked",
    "dogwater":                     "very bad",
    "trash":                        "very bad",
    "cap":                          "that is a lie",
    "sus":                          "suspicious",
    "cooked":                       "ruined",
    "flopped":                      "failed",
    "flop":                         "failure",
    "cringe":                       "embarrassing",
    "yikes":                        "that is bad",
    "oof":                          "that is unfortunate",
    "smh":                          "that is disappointing",
    "bruh":                         "this is ridiculous",
    "not it":                       "this is wrong",
    "fell off":                     "declined in quality",
    "ain't it":                     "this is wrong",
    # Neutral / contextual
    "ar":                           "very",
    "fr":                           "seriously",
    "deadass":                      "seriously",
    "no shot":                      "that is unbelievable",
    "ngl":                          "honestly",
    "tbh":                          "to be honest",
    "imo":                          "in my opinion",
    "istg":                         "i promise",
    "ong":                          "honestly",
    "rn":                           "right now",
    "lowkey":                       "somewhat",
    "highkey":                      "very much",
    "iykyk":                        "this is great if you know",
    "omg":                          "oh my god",

}

SLANG_PATTERN = re.compile(
    r"\b(" + "|".join(
        re.escape(k)
        for k in sorted(SLANG_MAP.keys(), key=len, reverse=True)
    ) + r")\b",
    flags=re.IGNORECASE,
)


# Slang normalization

def normalize_slang(text: str) -> str:
    return SLANG_PATTERN.sub(lambda m: SLANG_MAP[m.group(0).lower()], text)


# Two cleaning paths

def clean_for_sentiment(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""
    text = URL_PATTERN.sub("", text)
    text = normalize_slang(text)
    text = WHITESPACE_PATTERN.sub(" ", text).strip()
    return text


def clean_for_clustering(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""
    text = URL_PATTERN.sub("", text)
    text = EMOJI_PATTERN.sub("", text)
    text = normalize_slang(text)
    text = WHITESPACE_PATTERN.sub(" ", text).strip()
    text = text.lower()
    return text


# Batch helpers

def sentiment_batch(comments: list[str]) -> list[str]:
    return [clean_for_sentiment(c) for c in comments] if comments else []


def clustering_batch(comments: list[str]) -> list[str]:
    return [clean_for_clustering(c) for c in comments] if comments else []


# Backwards compatibility
def clean_batch(comments: list[str]) -> list[str]:
    return clustering_batch(comments)