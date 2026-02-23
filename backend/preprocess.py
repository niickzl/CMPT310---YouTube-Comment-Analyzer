"""Text preprocessing utilities for YouTube comment analysis.

Provides two levels of cleaning:
    - light_clean / light_clean_batch: Strip noise (URLs, emojis, extra
      whitespace) but preserve original wording. Use with transformer models
      like DistilBERT that have their own tokenizers.
    - clean_comment / preprocess_batch: Full lemmatization via SpaCy on top
      of noise removal. Use with bag-of-words models (TF-IDF + LogReg).

Designed as a pure utility module -- the caller loads and passes in the
SpaCy language model to avoid hidden global state and repeated model loading.
"""

import logging
import re

import spacy
from spacy.tokens import Doc

logger = logging.getLogger(__name__)

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


def load_spacy_model(model_name: str = "en_core_web_sm") -> spacy.Language:
    """Load a SpaCy language model.

    Convenience function so callers don't need to import spacy directly.
    Call this once at startup and pass the result into cleaning functions.

    Args:
        model_name: Name of the SpaCy model to load.

    Returns:
        A loaded SpaCy Language pipeline.

    Raises:
        OSError: If the model is not installed.
    """
    logger.info("Loading SpaCy model: %s", model_name)
    nlp = spacy.load(model_name, disable=["parser", "ner"])
    return nlp


def _strip_noise(text: str) -> str:
    """Remove URLs, emojis, and collapse whitespace. Shared by both modes."""
    text = _URL_PATTERN.sub("", text)
    text = _EMOJI_PATTERN.sub("", text)
    text = _WHITESPACE_PATTERN.sub(" ", text).strip()
    return text


def light_clean(text: str) -> str:
    """Remove noise but preserve original wording.

    Strips URLs, emojis, and excess whitespace. Does NOT lowercase,
    lemmatize, or remove punctuation -- leaves text in its natural form
    so transformer models (DistilBERT) can leverage word forms and casing.

    Args:
        text: A single raw comment string.

    Returns:
        The cleaned text with original wording intact.
    """
    if not text or not isinstance(text, str):
        return ""
    return _strip_noise(text)


def light_clean_batch(comments: list[str]) -> list[str]:
    """Light-clean a batch of comments (no SpaCy needed).

    Args:
        comments: List of raw comment strings.

    Returns:
        A list of cleaned strings in the same order as input.
    """
    if not comments:
        return []
    return [light_clean(c) for c in comments]


def clean_comment(text: str, nlp: spacy.Language) -> str:
    """Clean and lemmatize a single comment string.

    Processing steps:
        1. Strip URLs
        2. Strip emoji characters
        3. Lowercase
        4. Run through SpaCy pipeline for lemmatization
        5. Remove punctuation and non-alphabetic tokens
        6. Collapse whitespace

    Stopwords are intentionally preserved -- removing them is a model-level
    decision that depends on the downstream task (e.g., sentiment models
    often benefit from keeping negation words like "not").

    Args:
        text: A single raw comment string.
        nlp: A loaded SpaCy Language model.

    Returns:
        The cleaned, lemmatized text. May be empty if the comment contained
        only URLs, emojis, or punctuation.
    """
    if not text or not isinstance(text, str):
        return ""

    text = _strip_noise(text).lower()

    doc: Doc = nlp(text)
    tokens = [
        token.lemma_
        for token in doc
        if token.is_alpha and not token.is_space
    ]

    return " ".join(tokens)


def preprocess_batch(
    comments: list[str],
    nlp: spacy.Language,
    batch_size: int = 50,
) -> list[str]:
    """Clean and lemmatize a batch of comments efficiently.

    Uses SpaCy's nlp.pipe() for batched processing, which is significantly
    faster than calling clean_comment() in a loop for large inputs.

    Args:
        comments: List of raw comment strings.
        nlp: A loaded SpaCy Language model.
        batch_size: Number of comments to process per SpaCy batch.

    Returns:
        A list of cleaned strings, in the same order as input. Empty strings
        are included (not filtered) to maintain index alignment with the
        original comment list.
    """
    if not comments:
        return []

    pre_cleaned = [
        _strip_noise(t).lower() if t and isinstance(t, str) else ""
        for t in comments
    ]

    results: list[str] = []
    for doc in nlp.pipe(pre_cleaned, batch_size=batch_size):
        tokens = [
            token.lemma_
            for token in doc
            if token.is_alpha and not token.is_space
        ]
        results.append(" ".join(tokens))

    non_empty = sum(1 for r in results if r)
    logger.info(
        "Preprocessed %d comments (%d non-empty)", len(results), non_empty
    )
    return results
