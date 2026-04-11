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

logger = logging.getLogger(__name__)

# SpaCy model 
# Run: python -m spacy download en_core_web_sm
nlp = None

def get_nlp():
    global nlp
    if nlp is None:
        logger.info("Loading SpaCy model...")
        nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
        logger.info("SpaCy loaded.")
    return nlp


# Category keyword signatures
# These keyword sets guide label assignment after clustering.
# K-Means finds the clusters unsupervised; we then match each cluster
# centroid's top terms against these sets to assign a human-readable label.

CATEGORY_KEYWORDS = {
    "Content": {
        # Subject matter, information, structure
        "topic", "information", "fact", "argument", "concept", "idea",
        "story", "narrative", "research", "detail", "example", "knowledge",
        "subject", "section", "video", "content", "tutorial", "guide",
        "explanation", "lesson", "point", "theory", "source", "mistake",
        "question", "answer", "chapter", "claim", "data", "reference",
    },
    "Technical": {
        # Production, equipment, quality
        "audio", "sound", "quality", "camera", "transition", "music",
        "background", "noise", "subtitle", "caption", "resolution", "stream",
        "mic", "volume", "lighting", "thumbnail", "title", "description",
        "production", "fps", "bitrate", "microphone", "footage", "clip",
        "animation", "effect", "intro", "outro", "screen", "render",
        "encoder", "lag", "buffer", "visual",
    }
}

K = 3  # number of clusters = number of categories


# Data classes

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


# SpaCy lemmatization

def lemmatize(texts: list[str]) -> list[str]:
    nlp = get_nlp()
    lemmatized = []
    for doc in nlp.pipe(texts, batch_size=64):
        tokens = [
            token.lemma_.lower()
            for token in doc
            if token.pos_ in ("NOUN", "PROPN")
            and not token.is_stop
            and not token.is_punct
            and token.is_alpha
        ]
        lemmatized.append(" ".join(tokens) if tokens else " ")
    return lemmatized


# Label assignment

def assign_label(top_terms: list[str]) -> str:
    scores = {cat: 0 for cat in CATEGORY_KEYWORDS}
    for term in top_terms:
        for cat, keywords in CATEGORY_KEYWORDS.items():
            if term in keywords:
                scores[cat] += 1

    best = max(scores, key=lambda c: scores[c])
    # Fall back to General if no keywords matched at all
    if scores[best] == 0:
        return "General"
    return best


# Main clustering function

def cluster_comments(
    cleaned_texts: list[str],
    n_top_keywords: int = 10,
) -> tuple[list[ClusterResult], ClusterSummary]:
    if not cleaned_texts:
        empty_summary = ClusterSummary(
            content_count=0, technical_count=0, general_count=0,
            content_pct=0.0, technical_pct=0.0, general_pct=0.0,
        )
        return [], empty_summary

    # Need at least K comments to form K clusters
    effective_k = min(K, len(cleaned_texts))

    # 1. Lemmatize with SpaCy for better cluster separation
    lemmatized = lemmatize(cleaned_texts)

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
        cluster_id_to_category[cid] = assign_label(top_terms)

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
    )

    return results, summary