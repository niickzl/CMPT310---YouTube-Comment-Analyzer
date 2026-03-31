"""FastAPI backend for YT Comment Analyzer.

Exposes:
    GET  /health   — liveness check
    POST /analyze  — fetch, preprocess, and sentiment-score YouTube comments
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from model import SentimentResult, get_or_load, get_sarcasm_classifier, predict, summarize
from cluster import ClusterResult, ClusterSummary, cluster_comments
from keywords import extract_keywords
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

@app.on_event("startup")
def load_model():
    logger.info("Loading models...")
    get_or_load()           # twitter-roberta-large
    get_sarcasm_classifier()
    logger.info("All models ready.")


# ── Schemas ────────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    url: str
    max_results: int = 100

      
class CommentItem(BaseModel):
    author: str
    text: str
    cleaned_text: str
    likes: int
    published_at: str

class CommentResult(BaseModel):
    author: str
    text: str            # original raw text shown in UI
    cleaned_text: str    # preprocessed text fed to model
    likes: int
    published_at: str
    sentiment: str       # "positive" | "neutral" | "negative"
    confidence: float    # 0.0 – 1.0
    is_sarcastic: bool
    category: str        # "Content" | "Technical" | "General"
    x: float             # PCA dimension 1
    y: float             # PCA dimension 2


class SentimentSummary(BaseModel):
    positive_count: int
    negative_count: int
    neutral_count:  int
    positive_pct: float
    negative_pct: float
    neutral_pct:  float
    avg_confidence: float


class KeywordItem(BaseModel):
    word: str
    count: int


class ClusterSummarySchema(BaseModel):
    content_count: int
    technical_count: int
    general_count: int
    content_pct: float
    technical_pct: float
    general_pct: float
    top_keywords: dict[str, list[str]]
    silhouette: float


class AnalyzeResponse(BaseModel):
    video_id: str
    comment_count: int
    sentiment_summary: SentimentSummary
    cluster_summary: ClusterSummarySchema
    keywords: list[KeywordItem]
    comments: list[CommentResult]


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    """Fetch, preprocess, and sentiment-score comments for a YouTube video."""

    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="YOUTUBE_API_KEY is not set in the environment.",
        )

    # 1. Extract video ID from URL
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

    # 3. Two preprocessing paths — sentiment keeps emojis/casing, clustering strips them
    raw_texts       = [c["text"] for c in raw_comments]
    sentiment_texts = sentiment_batch(raw_texts)   # emojis kept, slang normalized
    cleaned_texts   = clustering_batch(raw_texts)  # emojis stripped, slang normalized

    # 4. Run RoBERTa-large sentiment inference + sarcasm correction
    sentiment_results: list[SentimentResult] = predict(sentiment_texts)

    # 5. K-Means thematic clustering (done before assembly so coords are available)
    cluster_results: list[ClusterResult]
    cluster_summary: ClusterSummary
    cluster_results, cluster_summary = cluster_comments(cleaned_texts)

    # 6. Assemble per-comment results
    comments = [
        CommentResult(
            author=raw["author"],
            text=raw["text"],
            cleaned_text=s_text,
            likes=raw["likes"],
            published_at=raw["published_at"],
            sentiment=result.label,
            confidence=result.score,
            is_sarcastic=result.is_sarcastic,
            category=cluster.category,
            x=cluster.x,
            y=cluster.y,
        )
        for raw, s_text, result, cluster in zip(
            raw_comments, sentiment_texts, sentiment_results, cluster_results
        )
    ]

    # 7. Aggregate sentiment summary
    summary = SentimentSummary(**summarize(sentiment_results))

    # 8. Get keywords
    top_keywords = extract_keywords(cleaned_texts, top_n=5)

    cluster_summary_schema = ClusterSummarySchema(
        content_count=cluster_summary.content_count,
        technical_count=cluster_summary.technical_count,
        general_count=cluster_summary.general_count,
        content_pct=cluster_summary.content_pct,
        technical_pct=cluster_summary.technical_pct,
        general_pct=cluster_summary.general_pct,
        top_keywords=cluster_summary.top_keywords,
        silhouette=cluster_summary.silhouette,
    )

    logger.info(
        "video=%s comments=%d positive=%.1f%% negative=%.1f%% neutral=%.1f%% silhouette=%.3f",
        video_id, len(comments), summary.positive_pct, summary.negative_pct,
        summary.neutral_pct, cluster_summary.silhouette,
    )

    return AnalyzeResponse(
        video_id=video_id,
        comment_count=len(comments),
        sentiment_summary=summary,
        cluster_summary=cluster_summary_schema,
        keywords=[KeywordItem(word=w, count=c) for w, c in top_keywords],
        comments=comments,
    )