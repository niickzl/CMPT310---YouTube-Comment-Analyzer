"""Twitter RoBERTa sentiment model for YouTube comment analysis.

Swapped from distilbert-base-uncased-finetuned-sst-2-english (trained on
movie reviews) to cardiffnlp/twitter-roberta-base-sentiment-latest (trained
on tweets) — much closer to YouTube comment style: short, informal, slangy,
and emoji-heavy.

Returns three labels: positive, neutral, negative.
Neutral comments are bucketed as negative for the binary dashboard display
but stored separately so future UI iterations can show them distinctly.

Pipeline:
    cleaned text (with emojis) → RoBERTa tokenizer → transformer
    → sarcasm check → flipped label if sarcastic → SentimentResult
"""

import logging
from dataclasses import dataclass

import numpy as np
from transformers import pipeline as hf_pipeline

logger = logging.getLogger(__name__)

_classifier = None
_sarcasm_classifier = None


# ── Model loaders ──────────────────────────────────────────────────────────────

def get_or_load():
    """Return the RoBERTa classifier, loading it on first call.

    Downloads from HuggingFace on first run, then caches locally in
    ~/.cache/huggingface/. Subsequent startups load from cache instantly.
    """
    global _classifier
    if _classifier is None:
        logger.info("Loading Twitter RoBERTa sentiment model...")
        _classifier = hf_pipeline(
            "text-classification",
            model="cardiffnlp/twitter-roberta-base-sentiment-latest",
            truncation=True,
            max_length=512,
        )
        logger.info("RoBERTa sentiment model loaded.")
    return _classifier


def get_sarcasm_classifier():
    """Return the sarcasm detector, loading it on first call."""
    global _sarcasm_classifier
    if _sarcasm_classifier is None:
        logger.info("Loading sarcasm classifier...")
        _sarcasm_classifier = hf_pipeline(
            "text-classification",
            model="helinivan/english-sarcasm-detector",
            truncation=True,
            max_length=512,
        )
        logger.info("Sarcasm classifier loaded.")
    return _sarcasm_classifier


# ── Data class ─────────────────────────────────────────────────────────────────

@dataclass
class SentimentResult:
    label: str          # "positive" | "negative"
    raw_label: str      # "positive" | "neutral" | "negative" (original RoBERTa output)
    score: float        # confidence 0.0 – 1.0
    is_positive: bool
    is_sarcastic: bool  # True if sarcasm detector fired


# ── Inference ──────────────────────────────────────────────────────────────────

def predict(texts: list[str], classifier=None) -> list[SentimentResult]:
    """Run RoBERTa sentiment inference with sarcasm correction.

    Sarcasm detection:
        - Runs a second model (helinivan/english-sarcasm-detector) in parallel
        - If a comment is flagged as SARCASM with confidence >= 0.80,
          the sentiment label is flipped
        - Threshold is set high (0.80) to avoid over-correcting

    Neutral handling:
        - RoBERTa returns positive / neutral / negative
        - Neutral is bucketed as negative for the binary dashboard
        - raw_label preserves the original three-way classification

    Args:
        texts:      List of sentiment-cleaned comment strings (emojis kept).
        classifier: Optional pre-loaded pipeline. Auto-loads if None.

    Returns:
        A list of SentimentResult, one per input, in the same order.
    """
    if not texts:
        return []

    if classifier is None:
        classifier = get_or_load()

    sarcasm_clf = get_sarcasm_classifier()

    sentiment_raw = classifier(texts, batch_size=16, truncation=True)
    sarcasm_raw   = sarcasm_clf(texts, batch_size=16, truncation=True)

    results = []
    for s, sar in zip(sentiment_raw, sarcasm_raw):
        # RoBERTa returns "positive", "neutral", "negative" (lowercase)
        raw_label    = s["label"].lower()
        is_positive  = raw_label == "positive"
        is_sarcastic = sar["label"] == "SARCASM" and sar["score"] >= 0.80

        # Flip sentiment if high-confidence sarcasm detected
        if is_sarcastic:
            is_positive = not is_positive

        results.append(SentimentResult(
            label="positive" if is_positive else "negative",
            raw_label=raw_label,
            score=round(float(s["score"]), 3),
            is_positive=is_positive,
            is_sarcastic=is_sarcastic,
        ))

    return results


# ── Aggregation ────────────────────────────────────────────────────────────────

def summarize(results: list[SentimentResult]) -> dict:
    """Aggregate SentimentResults into dashboard-ready stats.

    Returns:
        {
            "positive_count": int,
            "negative_count": int,
            "positive_pct":   float,   # 0–100
            "negative_pct":   float,   # 0–100
            "avg_confidence": float,   # 0–1
        }
    """
    if not results:
        return {
            "positive_count": 0,
            "negative_count": 0,
            "positive_pct":   0.0,
            "negative_pct":   0.0,
            "avg_confidence": 0.0,
        }

    total    = len(results)
    pos      = sum(1 for r in results if r.is_positive)
    neg      = total - pos
    avg_conf = float(np.mean([r.score for r in results]))

    return {
        "positive_count": pos,
        "negative_count": neg,
        "positive_pct":   round(pos / total * 100, 1),
        "negative_pct":   round(neg / total * 100, 1),
        "avg_confidence": round(avg_conf, 3),
    }