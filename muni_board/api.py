"""Fetch 511 StopMonitoring data on the laptop."""

import json
import time
from datetime import datetime
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

API_URL = "https://api.511.org/transit/StopMonitoring"
USER_AGENT = "n-time/0.1 (+https://511.org/open-data)"


class ApiError(RuntimeError):
    """An API error whose message leaves out the token."""


def build_url(token, agency, stop_code):
    return f"{API_URL}?{urlencode({'api_key': token, 'agency': agency, 'stopCode': stop_code, 'format': 'json'})}"


def redact_url(url):
    """Redact query-string credentials before logging or raising errors."""
    parts = urlsplit(url)
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        query.append((key, "REDACTED" if key.lower() == "api_key" else value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def parse_511_time(value):
    """Convert an ISO-8601 timestamp to Unix seconds."""
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    return datetime.fromisoformat(text).timestamp()


def fetch_stop(token, agency, stop_code, timeout_seconds=15, sleep=time.sleep):
    """Fetch one stop. Retry one transient server or network failure."""
    url = build_url(token, agency, stop_code)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})

    for attempt in range(2):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw_body = response.read()
                content_type = response.headers.get_content_type()
                if content_type != "application/json":
                    raise ApiError(f"511 returned {content_type or 'an unknown content type'}")
                try:
                    return json.loads(raw_body.decode("utf-8-sig"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ApiError("511 returned invalid JSON") from exc
        except HTTPError as exc:
            exc.close()
            if 500 <= exc.code < 600 and attempt == 0:
                sleep(1)
                continue
            message = f"511 returned HTTP {exc.code}"
            if exc.code == 429:
                message += "; wait for the rate-limit window"
            raise ApiError(message) from None
        except (OSError, HTTPException):
            if attempt == 0:
                sleep(1)
                continue
            raise ApiError("Could not reach 511") from None

    raise ApiError("511 request failed")
