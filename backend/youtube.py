"""YouTube Data API v3 comment fetching utilities.

Provides functions to extract video IDs from YouTube URLs and fetch
top-level comments via the YouTube Data API. Designed as a pure utility
module with no framework dependencies.
"""

import logging
import re
from urllib.parse import parse_qs, urlparse

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class VideoNotFoundError(Exception):
    """Raised when the given video ID does not exist on YouTube."""


class CommentsDisabledError(Exception):
    """Raised when comments are disabled for the given video."""


class QuotaExceededError(Exception):
    """Raised when the YouTube Data API quota has been exceeded."""


def extract_video_id(url: str) -> str:
    if not url or not isinstance(url, str):
        raise ValueError(f"Invalid URL: {url!r}")

    url = url.strip()
    parsed = urlparse(url)
    host = parsed.hostname or ""

    if host in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        elif parsed.path.startswith("/embed/"):
            video_id = parsed.path.split("/embed/")[1].split("/")[0]
        elif parsed.path.startswith("/shorts/"):
            video_id = parsed.path.split("/shorts/")[1].split("/")[0]
        else:
            raise ValueError(f"Unrecognized YouTube URL format: {url}")

    elif host in ("youtu.be",):
        video_id = parsed.path.lstrip("/").split("/")[0]

    else:
        raise ValueError(f"Not a YouTube URL: {url}")

    if not video_id or not re.match(r"^[A-Za-z0-9_-]{11}$", video_id):
        raise ValueError(f"Could not extract a valid video ID from: {url}")

    return video_id


def fetch_comments(
    video_id: str,
    api_key: str,
    max_results: int = 100,
) -> list[dict]:
    if not video_id:
        raise ValueError("video_id must not be empty")
    if not api_key:
        raise ValueError("api_key must not be empty")

    youtube = build("youtube", "v3", developerKey=api_key)
    comments: list[dict] = []
    page_token: str | None = None
    per_page = min(max_results, 100)

    while len(comments) < max_results:
        try:
            request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=per_page,
                pageToken=page_token,
                textFormat="plainText",
                order="relevance",
            )
            response = request.execute()

        except HttpError as e:
            status = e.resp.status if e.resp else None

            if status == 403 and "commentsDisabled" in str(e):
                raise CommentsDisabledError(
                    f"Comments are disabled for video: {video_id}"
                ) from e

            if status == 403 and "quotaExceeded" in str(e):
                raise QuotaExceededError(
                    "YouTube Data API quota exceeded. Try again tomorrow."
                ) from e

            if status == 404:
                raise VideoNotFoundError(
                    f"Video not found: {video_id}"
                ) from e

            logger.error("YouTube API error (status=%s): %s", status, e)
            raise

        for item in response.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "author": snippet.get("authorDisplayName", ""),
                "text": snippet.get("textDisplay", ""),
                "likes": snippet.get("likeCount", 0),
                "published_at": snippet.get("publishedAt", ""),
            })
            if len(comments) >= max_results:
                break

        page_token = response.get("nextPageToken")
        if not page_token:
            break

        logger.debug(
            "Fetched %d/%d comments, continuing to next page...",
            len(comments),
            max_results,
        )

    logger.info(
        "Fetched %d comments for video %s", len(comments), video_id
    )
    return comments
