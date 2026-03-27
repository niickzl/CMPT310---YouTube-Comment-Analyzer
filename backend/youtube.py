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
    """Extract the video ID from a YouTube URL.

    Handles standard and shortened URL formats:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://www.youtube.com/embed/VIDEO_ID
        - URLs with extra query params (playlists, timestamps, etc.)

    Args:
        url: A full YouTube URL string.

    Returns:
        The 11-character video ID.

    Raises:
        ValueError: If the URL cannot be parsed as a valid YouTube video URL.
    """
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
    max_results: int = 250,
) -> list[dict]:
    """Fetch top-level comments for a YouTube video.

    Paginates through the API automatically until `max_results` comments
    are collected or no more pages remain.

    Args:
        video_id: An 11-character YouTube video ID.
        api_key: A valid YouTube Data API v3 key.
        max_results: Maximum number of comments to retrieve (default 100).

    Returns:
        A list of comment dicts, each containing::

            {
                "author": str,
                "text": str,
                "likes": int,
                "published_at": str,   # ISO 8601 timestamp
            }

    Raises:
        VideoNotFoundError: If the video does not exist.
        CommentsDisabledError: If comments are turned off for the video.
        QuotaExceededError: If the API key's daily quota is exhausted.
        ValueError: If video_id or api_key is empty.
    """
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
