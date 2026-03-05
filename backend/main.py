"""FastAPI backend for YT Comment Analyzer.

Exposes a single POST /analyze endpoint that accepts a YouTube URL,
fetches comments via the YouTube Data API, preprocesses them, and
returns the cleaned comment list ready for NLP/clustering.
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from preprocess import clean_batch
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

# Allow requests from the Chrome extension (chrome-extension://* origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)


class AnalyzeRequest(BaseModel):
    url: str
    max_results: int = 100

      
class CommentItem(BaseModel):
    author: str
    text: str
    cleaned_text: str
    likes: int
    published_at: str

      
class AnalyzeResponse(BaseModel):
    video_id: str
    total_fetched: int
    comments: list[CommentItem]
      
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    """Fetch and preprocess comments for a YouTube video URL."""

    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="YOUTUBE_API_KEY is not set in the environment.",
        )

    # 1. Extract video ID
    try:
        video_id = extract_video_id(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Fetch comments from YouTube Data API
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

    cleaned_texts = clean_batch([c["text"] for c in raw_comments])

    comments = [
        {
            "author": raw["author"],
            "text": raw["text"],
            "cleaned_text": cleaned,
            "likes": raw["likes"],
            "published_at": raw["published_at"],
        }
        for raw, cleaned in zip(raw_comments, cleaned_texts)
    ]

    return {
        "video_id": video_id,
        "comment_count": len(comments),
        "comments": comments,
    }
