from urllib.parse import parse_qs, urlparse

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class VideoNotFoundError(Exception):
    """Video ID does not exist on YouTube."""


class CommentsDisabledError(Exception):
    """Comments are disabled for the given video."""


def extract_video_id(url: str) -> str:
    if not url or not isinstance(url, str):
        raise ValueError(f"Invalid URL: {url!r}")

    url = url.strip()
    parsed = urlparse(url)
    host = parsed.hostname or ""

    # (consulted LLM for types of YT links)

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

    if not video_id:
        raise ValueError(f"Could not extract a valid video ID from: {url}")

    return video_id


def fetch_comments(
    video_id: str,
    api_key: str,
    max_results: int = 100,
) -> list[dict]:
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
            if e.resp:
                status = e.resp.status
            else:
                status = None

            if status == 403 and "commentsDisabled" in str(e):
                raise CommentsDisabledError(
                    f"Comments are disabled for video: {video_id}"
                ) from e

            if status == 404:
                raise VideoNotFoundError(
                    f"Video not found: {video_id}"
                ) from e

        for item in response.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "text": snippet.get("textDisplay", ""),
            })
            if len(comments) >= max_results:
                break

        page_token = response.get("nextPageToken")
        if not page_token:
            break
        
    return comments
