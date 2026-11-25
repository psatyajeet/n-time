import json
import unittest
from email.message import Message
from http.client import IncompleteRead
from io import BytesIO
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from muni_board.api import ApiError, build_url, fetch_stop, parse_511_time, redact_url


class FakeResponse:
    def __init__(self, body, content_type="application/json"):
        self._body = body
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._body


class ApiTests(unittest.TestCase):
    def test_url_and_redaction(self):
        url = build_url("secret token", "SF", "90001")
        self.assertIn("api_key=secret+token", url)
        redacted = redact_url(url)
        self.assertNotIn("secret", redacted)
        self.assertIn("api_key=REDACTED", redacted)
        self.assertIn("stopCode=90001", redacted)

    def test_timestamp_offsets(self):
        utc = parse_511_time("2025-01-02T00:00:00Z")
        offset = parse_511_time("2025-01-01T17:00:00-07:00")
        self.assertEqual(utc, offset)

    @patch("muni_board.api.urlopen")
    def test_fetch_accepts_utf8_bom(self, mocked_urlopen):
        payload = {"Siri": {"ServiceDelivery": {}}}
        body = b"\xef\xbb\xbf" + json.dumps(payload).encode()
        mocked_urlopen.return_value = FakeResponse(body)

        self.assertEqual(payload, fetch_stop("token", "SF", "90001"))

    @patch("muni_board.api.urlopen")
    def test_401_is_safe_and_not_retried(self, mocked_urlopen):
        mocked_urlopen.side_effect = HTTPError(
            "https://api.511.org/redacted",
            401,
            "Unauthorized",
            Message(),
            BytesIO(b"The API key provided is invalid."),
        )

        with self.assertRaisesRegex(ApiError, "HTTP 401"):
            fetch_stop("super-secret-token", "SF", "90001", sleep=lambda _: None)
        self.assertEqual(1, mocked_urlopen.call_count)

    @patch("muni_board.api.urlopen")
    def test_500_retries_once(self, mocked_urlopen):
        error = HTTPError(
            "https://api.511.org/redacted",
            500,
            "Server Error",
            Message(),
            BytesIO(b"temporary"),
        )
        mocked_urlopen.side_effect = [
            error,
            FakeResponse(b'{"Siri":{"ServiceDelivery":{}}}'),
        ]

        payload = fetch_stop("token", "SF", "90001", sleep=lambda _: None)

        self.assertIn("Siri", payload)
        self.assertEqual(2, mocked_urlopen.call_count)

    @patch("muni_board.api.urlopen")
    def test_dropped_connections_become_api_errors(self, mocked_urlopen):
        for error in (ConnectionResetError(), IncompleteRead(b"")):
            response = FakeResponse(b"")
            response.read = Mock(side_effect=error)
            mocked_urlopen.return_value = response
            with self.assertRaisesRegex(ApiError, "Could not reach 511"):
                fetch_stop("token", "SF", "90001", sleep=lambda _: None)


if __name__ == "__main__":
    unittest.main()
