"""FastAPI backend for YT Comment Analyzer — Milestone 2.

Exposes:
    GET  /health   — liveness check
    POST /analyze  — fetch, preprocess, sentiment-score, and cluster comments
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from cluster import ClusterResult, ClusterSummary, cluster_comments
from model import SentimentResult, get_or_load, get_sarcasm_classifier, predict, summarize
from preprocess import sentiment_batch, clustering_batch
from youtube import (
    CommentsDisabledError,
    QuotaExceededError,
    VideoNotFoundError,
    extract_video_id,
    fetch_comments,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="YT Comment Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

_classifier = None


@app.on_event("startup")
def load_model():
    global _classifier
    logger.info("Loading models...")
    _classifier = get_or_load()       # Twitter RoBERTa
    get_sarcasm_classifier()          # sarcasm detector — pre-warmed
    logger.info("All models ready.")


# ── Schemas ────────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    url: str
    max_results: int = 250


class CommentResult(BaseModel):
    author: str
    text: str               # original raw text shown in UI
    cleaned_text: str       # sentiment-cleaned text (emojis kept)
    likes: int
    published_at: str
    sentiment: str          # "positive" | "negative"
    raw_sentiment: str      # "positive" | "neutral" | "negative"
    confidence: float       # 0.0 – 1.0
    is_sarcastic: bool
    category: str           # "Content" | "Technical" | "General"


class SentimentSummary(BaseModel):
    positive_count: int
    negative_count: int
    positive_pct: float
    negative_pct: float
    avg_confidence: float


class ClusterSummarySchema(BaseModel):
    content_count: int
    technical_count: int
    general_count: int
    content_pct: float
    technical_pct: float
    general_pct: float
    top_keywords: dict[str, list[str]]


class AnalyzeResponse(BaseModel):
    video_id: str
    comment_count: int
    sentiment_summary: SentimentSummary
    cluster_summary: ClusterSummarySchema
    comments: list[CommentResult]


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    """Fetch, preprocess, sentiment-score, and cluster YouTube comments."""

    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="YOUTUBE_API_KEY is not set in the environment.",
        )

    # 1. Extract video ID — supports /watch and /shorts URLs
    try:
        video_id = extract_video_id(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Fetch raw comments from YouTube Data API
    try:
        raw_comments = fetch_comments(
            video_id=video_id,
            api_key=api_key,
            max_results=req.max_results,
        )
    except VideoNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CommentsDisabledError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except QuotaExceededError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error fetching comments")
        raise HTTPException(status_code=500, detail=str(e))

    raw_texts = [c["text"] for c in raw_comments]

    # 3a. Sentiment path — keeps emojis, RoBERTa reads them as signal
    sentiment_texts = sentiment_batch(raw_texts)

    # 3b. Clustering path — strips emojis, cleaner for TF-IDF / K-Means
    cluster_texts = clustering_batch(raw_texts)

    # 4. RoBERTa sentiment inference + sarcasm correction
    sentiment_results: list[SentimentResult] = predict(sentiment_texts, _classifier)

    # 5. K-Means thematic clustering (SpaCy lemmatization happens inside)
    cluster_results: list[ClusterResult]
    cluster_summary: ClusterSummary
    cluster_results, cluster_summary = cluster_comments(cluster_texts)

    # 6. Assemble per-comment results
    comments = [
        CommentResult(
            author=raw["author"],
            text=raw["text"],
            cleaned_text=s_text,
            likes=raw["likes"],
            published_at=raw["published_at"],
            sentiment=sentiment.label,
            raw_sentiment=sentiment.raw_label,
            confidence=sentiment.score,
            is_sarcastic=sentiment.is_sarcastic,
            category=cluster.category,
        )
        for raw, s_text, sentiment, cluster in zip(
            raw_comments, sentiment_texts, sentiment_results, cluster_results
        )
    ]

    # 7. Aggregate summaries
    sentiment_summary = SentimentSummary(**summarize(sentiment_results))
    cluster_summary_schema = ClusterSummarySchema(
        content_count=cluster_summary.content_count,
        technical_count=cluster_summary.technical_count,
        general_count=cluster_summary.general_count,
        content_pct=cluster_summary.content_pct,
        technical_pct=cluster_summary.technical_pct,
        general_pct=cluster_summary.general_pct,
        top_keywords=cluster_summary.top_keywords,
    )

    logger.info(
        "video=%s comments=%d pos=%.1f%% neg=%.1f%% "
        "content=%d technical=%d general=%d",
        video_id, len(comments),
        sentiment_summary.positive_pct, sentiment_summary.negative_pct,
        cluster_summary.content_count, cluster_summary.technical_count,
        cluster_summary.general_count,
    )

    return AnalyzeResponse(
        video_id=video_id,
        comment_count=len(comments),
        sentiment_summary=sentiment_summary,
        cluster_summary=cluster_summary_schema,
        comments=comments,
    )