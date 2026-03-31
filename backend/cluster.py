"""K-Means thematic clustering for YouTube comments.

Groups comments into three semantic categories:
    - Content   — feedback about the video's subject matter, story, or information
    - Technical — feedback about audio, video quality, editing, or production
    - General   — off-topic praise, reactions, jokes, or unrelated remarks

Pipeline:
    cleaned texts → SpaCy lemmatization → TF-IDF vectors → K-Means (k=3)
    → per-cluster keyword analysis → category label assignment
"""

import logging
from dataclasses import dataclass, field

import numpy as np
import spacy
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score

logger = logging.getLogger(__name__)

# ── SpaCy model ────────────────────────────────────────────────────────────────
# Run: python -m spacy download en_core_web_sm
_nlp = None

def _get_nlp():
    global _nlp
    if _nlp is None:
        logger.info("Loading SpaCy model...")
        _nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
        logger.info("SpaCy loaded.")
    return _nlp


# ── Category keyword signatures ────────────────────────────────────────────────
# These keyword sets guide label assignment after clustering.
# K-Means finds the clusters unsupervised; we then match each cluster
# centroid's top terms against these sets to assign a human-readable label.

_CATEGORY_KEYWORDS = {
    "Content": {
        "topic", "explain", "information", "fact", "point", "argument",
        "concept", "idea", "story", "narrative", "research", "detail",
        "example", "accurate", "wrong", "mislead", "miss", "teach",
        "learn", "knowledge", "subject", "cover", "mention", "forget",
        "section", "part", "video", "content", "tutorial", "guide",
    },
    "Technical": {
        "audio", "video", "sound", "quality", "camera", "edit", "cut",
        "transition", "music", "background", "noise", "subtitle", "caption",
        "resolution", "blur", "lag", "buffer", "stream", "mic", "volume",
        "lighting", "thumbnail", "title", "description", "upload", "render",
        "fps", "bitrate", "encode", "production", "visual",
    },
    "General": {
        "love", "hate", "great", "awesome", "bad", "good", "wow", "lol",
        "haha", "funny", "amazing", "terrible", "like", "dislike", "share",
        "subscribe", "comment", "notification", "bell", "fan", "follow",
        "channel", "creator", "youtuber", "thanks", "thank", "appreciate",
        "first", "early", "here", "watch", "again", "back", "new",
    },
}

K = 3  # number of clusters = number of categories


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class ClusterResult:
    category: str       # "Content" | "Technical" | "General"
    cluster_id: int     # raw K-Means cluster index (0, 1, 2)
    x: float = 0.0     # PCA dimension 1 (for scatter plot)
    y: float = 0.0     # PCA dimension 2 (for scatter plot)


@dataclass
class ClusterSummary:
    content_count: int
    technical_count: int
    general_count: int
    content_pct: float
    technical_pct: float
    general_pct: float
    top_keywords: dict[str, list[str]] = field(default_factory=dict)
    silhouette: float = 0.0


# ── SpaCy lemmatization ────────────────────────────────────────────────────────

def _lemmatize(texts: list[str]) -> list[str]:
    """Lemmatize and lowercase texts using SpaCy for better TF-IDF clustering."""
    nlp = _get_nlp()
    lemmatized = []
    for doc in nlp.pipe(texts, batch_size=64):
        tokens = [
            token.lemma_.lower()
            for token in doc
            if not token.is_stop and not token.is_punct and token.is_alpha
        ]
        lemmatized.append(" ".join(tokens) if tokens else " ")
    return lemmatized


# ── Label assignment ───────────────────────────────────────────────────────────

def _assign_label(top_terms: list[str]) -> str:
    """Match a cluster's top TF-IDF terms to the best category label.

    Scores each category by counting how many of its signature keywords
    appear in the cluster's top terms, then picks the highest scorer.
    Falls back to 'General' on a tie or no match.
    """
    scores = {cat: 0 for cat in _CATEGORY_KEYWORDS}
    for term in top_terms:
        for cat, keywords in _CATEGORY_KEYWORDS.items():
            if term in keywords:
                scores[cat] += 1

    best = max(scores, key=lambda c: scores[c])
    # Fall back to General if no keywords matched at all
    if scores[best] == 0:
        return "General"
    return best


# ── Main clustering function ───────────────────────────────────────────────────

def cluster_comments(
    cleaned_texts: list[str],
    n_top_keywords: int = 10,
) -> tuple[list[ClusterResult], ClusterSummary]:
    """Cluster a list of cleaned comments into Content / Technical / General.

    Args:
        cleaned_texts:   Output of preprocess.clean_batch().
        n_top_keywords:  Number of top TF-IDF terms to extract per cluster
                         for label assignment and summary display.

    Returns:
        A tuple of:
            - list[ClusterResult]: one entry per comment, with category label
            - ClusterSummary: aggregate counts, percentages, and top keywords
    """
    if not cleaned_texts:
        empty_summary = ClusterSummary(
            content_count=0, technical_count=0, general_count=0,
            content_pct=0.0, technical_pct=0.0, general_pct=0.0,
        )
        return [], empty_summary

    # Need at least K comments to form K clusters
    effective_k = min(K, len(cleaned_texts))

    # 1. Lemmatize with SpaCy for better cluster separation
    lemmatized = _lemmatize(cleaned_texts)

    # 2. TF-IDF vectorization
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=5_000,
        sublinear_tf=True,
        min_df=1,
        strip_accents="unicode",
    )
    X = vectorizer.fit_transform(lemmatized)
    feature_names = vectorizer.get_feature_names_out()

    # 3. K-Means clustering with chosen K
    km = KMeans(n_clusters=effective_k, random_state=42, n_init=10)
    km.fit(X)
    raw_labels = km.labels_
    centroids  = km.cluster_centers_

    # Silhouette score — measures how well-separated the clusters are (-1 to 1)
    if effective_k > 1 and X.shape[0] > effective_k:
        sil = round(float(silhouette_score(X, raw_labels)), 3)
    else:
        sil = 0.0
    logger.info("Silhouette score (k=%d): %.3f", effective_k, sil)

    # PCA — reduce to 2D for scatter plot visualisation
    n_components = min(2, X.shape[0], X.shape[1])
    pca = PCA(n_components=n_components, random_state=42)
    coords = pca.fit_transform(X.toarray())  # shape: (n_comments, 2)

    # 5. Extract top terms per cluster centroid and assign category labels
    cluster_id_to_category: dict[int, str] = {}
    cluster_id_to_keywords: dict[int, list[str]] = {}

    for cid in range(effective_k):
        top_indices = centroids[cid].argsort()[::-1][:n_top_keywords]
        top_terms = [feature_names[i] for i in top_indices]
        cluster_id_to_keywords[cid] = top_terms
        cluster_id_to_category[cid] = _assign_label(top_terms)

    logger.info("Cluster label assignments: %s", cluster_id_to_category)

    # 6. Build per-comment results
    results = [
        ClusterResult(
            category=cluster_id_to_category[int(label)],
            cluster_id=int(label),
            x=round(float(coords[i, 0]), 4),
            y=round(float(coords[i, 1]), 4),
        )
        for i, label in enumerate(raw_labels)
    ]

    # 7. Aggregate summary
    total = len(results)
    counts = {"Content": 0, "Technical": 0, "General": 0}
    for r in results:
        counts[r.category] += 1

    top_keywords_by_category: dict[str, list[str]] = {}
    for cid, category in cluster_id_to_category.items():
        # If multiple clusters map to the same category, merge keywords
        existing = top_keywords_by_category.get(category, [])
        merged = existing + [k for k in cluster_id_to_keywords[cid] if k not in existing]
        top_keywords_by_category[category] = merged[:n_top_keywords]

    summary = ClusterSummary(
        content_count=counts["Content"],
        technical_count=counts["Technical"],
        general_count=counts["General"],
        content_pct=round(counts["Content"] / total * 100, 1),
        technical_pct=round(counts["Technical"] / total * 100, 1),
        general_pct=round(counts["General"] / total * 100, 1),
        top_keywords=top_keywords_by_category,
        silhouette=sil,
    )

    return results, summary