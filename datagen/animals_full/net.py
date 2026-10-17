"""The few lines of `requests` these scripts used, on urllib.

TaxoQuiz's datagen needed `requests`, as an extra the game did not. TreeQuiz's
builders are standard library only and CI installs pytest alone, so this keeps
the scripts' calls (`get(url, params=, headers=, timeout=)`, `status_code`,
`raise_for_status()`, `json()`) and their two exceptions, and nothing else.

An HTTP error is returned as a response, not raised, as `requests` does: the
callers read `status_code` to tell "later" (5xx) from "no" (4xx).
"""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request


class ConnectionError(OSError):  # noqa: A001  (the name callers catch, as with requests)
    """Nothing came back: refused, reset, or no route."""


class Timeout(ConnectionError):
    """The server took longer than `timeout`."""


class HTTPError(Exception):
    def __init__(self, status: int, url: str) -> None:
        super().__init__(f"HTTP {status} for {url}")
        self.status_code = status


class Response:
    def __init__(self, url: str, status_code: int, body: bytes) -> None:
        self.url = url
        self.status_code = status_code
        self.content = body

    def json(self):
        return json.loads(self.content)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise HTTPError(self.status_code, self.url)


def get(url: str, params: dict | None = None, headers: dict | None = None,
        timeout: float = 60) -> Response:
    if params:
        url = f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return Response(url, resp.status, resp.read())
    except urllib.error.HTTPError as e:
        return Response(url, e.code, e.read() or b"")
    except (socket.timeout, TimeoutError) as e:
        raise Timeout(str(e)) from e
    except urllib.error.URLError as e:
        if isinstance(e.reason, (socket.timeout, TimeoutError)):
            raise Timeout(str(e)) from e
        raise ConnectionError(str(e)) from e
