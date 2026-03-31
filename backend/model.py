"""Sentiment model for YouTube comment analysis.

Uses cardiffnlp/twitter-roberta-base-sentiment-latest (trained on tweets)
— strong domain match for YouTube comments: short, informal, emoji-heavy.

Sarcasm correction via helinivan/english-sarcasm-detector flips the label
when high-confidence sarcasm (>= 0.80) is detected.

Pipeline:
    cleaned text → RoBERTa tokenizer → transformer
    → sarcasm check → flipped label if sarcastic → SentimentResult
"""

import logging
from dataclasses import dataclass

import numpy as np
from transformers import pipeline as hf_pipeline

logger = logging.getLogger(__name__)

classifier = None
sarcasm_classifier = None


# Model loaders

def get_or_load():
    global classifier
    if classifier is None:
        logger.info("Loading twitter-roberta-base sentiment model...")
        classifier = hf_pipeline(
            "text-classification",
            model="cardiffnlp/twitter-roberta-base-sentiment-latest",
            truncation=True,
            max_length=512,
        )
        logger.info("RoBERTa base sentiment model loaded.")
    return classifier


def get_sarcasm_classifier():
    global sarcasm_classifier
    if sarcasm_classifier is None:
        logger.info("Loading sarcasm classifier...")
        sarcasm_classifier = hf_pipeline(
            "text-classification",
            model="helinivan/english-sarcasm-detector",
            truncation=True,
            max_length=512,
        )
        logger.info("Sarcasm classifier loaded.")
    return sarcasm_classifier


# Data class

@dataclass
class SentimentResult:
    label: str          # "positive" | "neutral" | "negative"
    raw_label: str      # "positive" | "neutral" | "negative" (RoBERTa output)
    score: float        # confidence 0.0 - 1.0
    is_positive: bool
    is_neutral: bool
    is_sarcastic: bool


# Inference

def predict(texts: list[str], classifier=None) -> list[SentimentResult]:
    if not texts:
        return []

    if classifier is None:
        classifier = get_or_load()

    sarcasm_clf = get_sarcasm_classifier()

    sentiment_raw = classifier(texts, batch_size=16, truncation=True)
    sarcasm_raw   = sarcasm_clf(texts, batch_size=16, truncation=True)

    results = []
    for s, sar in zip(sentiment_raw, sarcasm_raw):
        raw_label    = s["label"].lower()
        is_neutral   = raw_label == "neutral"
        is_positive  = raw_label == "positive"
        is_sarcastic = sar["label"] == "SARCASM" and sar["score"] >= 0.80

        # Sarcasm flips positive↔negative only, never neutral
        if is_sarcastic and not is_neutral:
            is_positive = not is_positive

        if is_neutral:
            label = "neutral"
        elif is_positive:
            label = "positive"
        else:
            label = "negative"

        results.append(SentimentResult(
            label=label,
            raw_label=raw_label,
            score=round(float(s["score"]), 3),
            is_positive=is_positive,
            is_neutral=is_neutral,
            is_sarcastic=is_sarcastic,
        ))

    return results


# Aggregation

def summarize(results: list[SentimentResult]) -> dict:
    """Aggregate SentimentResults into dashboard-ready stats."""
    if not results:
        return {
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count":  0,
            "positive_pct":   0.0,
            "negative_pct":   0.0,
            "neutral_pct":    0.0,
            "avg_confidence": 0.0,
        }

    total   = len(results)
    pos     = sum(1 for r in results if r.is_positive)
    neu     = sum(1 for r in results if r.is_neutral)
    neg     = total - pos - neu
    avg_conf = float(np.mean([r.score for r in results]))

    return {
        "positive_count": pos,
        "negative_count": neg,
        "neutral_count":  neu,
        "positive_pct":   round(pos / total * 100, 1),
        "negative_pct":   round(neg / total * 100, 1),
        "neutral_pct":    round(neu / total * 100, 1),
        "avg_confidence": round(avg_conf, 3),
    }