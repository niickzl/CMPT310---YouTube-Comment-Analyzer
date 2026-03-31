"""Gets Keywords with spacy.

Takes the most frequently mentioned nouns and proper nouns,
filtering out stop words and short tokens.
"""

import logging
from collections import Counter

import spacy

logger = logging.getLogger(__name__)

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        logger.info("Loading spaCy model...")
        _nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
    return _nlp


def extract_keywords(
    texts: list[str],
    top_n: int = 5,
) -> list[tuple[str, int]]:
    """Extract top keywords from a list of cleaned comment texts.

    Keeps nouns and proper nouns, skips stop words and short ones,
    then returns the most common ones with their counts.

    Args:
        texts: List of cleaned comment strings.
        top_n: Number of top keywords to return.

    Returns:
        List of (word, count) tuples sorted by frequency descending.
    """
    if not texts:
        return []

    nlp = _get_nlp()
    counter: Counter = Counter()

    for doc in nlp.pipe(texts, batch_size=50):
        for token in doc:
            if (
                token.pos_ in ("NOUN", "PROPN")
                and not token.is_stop
                and len(token.text) > 2
            ):
                counter[token.lemma_.lower()] += 1

    return counter.most_common(top_n)