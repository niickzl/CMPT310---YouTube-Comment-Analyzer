from dataclasses import dataclass

import numpy as np
from transformers import pipeline as hf_pipeline

classifier = None
sarcasm_classifier = None

def get_roberta():
    global classifier
    if classifier is None:
        classifier = hf_pipeline(
            "text-classification",
            model="cardiffnlp/twitter-roberta-base-sentiment-latest",
            truncation=True,
            max_length=512,
        )
    return classifier


def get_helinivan():
    global sarcasm_classifier
    if sarcasm_classifier is None:
        sarcasm_classifier = hf_pipeline(
            "text-classification",
            model="helinivan/english-sarcasm-detector",
            truncation=True,
            max_length=512,
        )
    return sarcasm_classifier

@dataclass
class SentimentResult:
    label: str
    raw_label: str # RoBERTa output
    score: float
    is_positive: bool
    is_neutral: bool
    is_sarcastic: bool

def predict(texts: list[str], classifier=None) -> list[SentimentResult]:
    if not texts:
        return []

    classifier = get_roberta()
    sarcasm_clf = get_helinivan()

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

def summarize(results: list[SentimentResult]) -> dict:
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