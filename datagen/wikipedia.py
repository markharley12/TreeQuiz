"""Popup text from English Wikipedia, for any builder that knows its titles.

The REST summary endpoint gives the lead paragraph and a picture in one
request. Results are cached in `_cache/wikipedia/<lang>.json` keyed by title,
written atomically every 50 fetches, so an interrupted run resumes where it
stopped and a rebuild asks for nothing it already has — TaxoQuiz's taxon scrape
was an hour long, and this is the habit that made that survivable.

A title is looked up by the exact name the builder hands over, which should come
from Wikidata's sitelink rather than a guess: a guessed title costs a 404 and a
retry, and worse, resolves to the wrong article without saying so.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from common import CACHE, USER_AGENT, read_json, write_json_atomic

DELAY_S = 0.05
CHECKPOINT_EVERY = 50


def _get(url: str, retries: int = 4) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code not in (429, 500, 502, 503, 504) or attempt == retries - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries - 1:
                raise
        time.sleep(2 ** attempt)
    return None


def summaries(titles: list[str], lang: str = "en") -> dict[str, dict | None]:
    """Title to {description, image_url, url, title}, or None for no article."""
    path = CACHE / "wikipedia" / f"{lang}.json"
    cache: dict[str, dict | None] = read_json(path) if path.exists() else {}
    todo = [t for t in dict.fromkeys(titles) if t not in cache]
    if todo:
        print(f"wikipedia: {len(todo)} of {len(set(titles))} summaries to fetch")
    for i, title in enumerate(todo, 1):
        quoted = urllib.parse.quote(title.replace(" ", "_"), safe="")
        data = _get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quoted}")
        if data is None or data.get("type") == "disambiguation":
            cache[title] = None
        else:
            cache[title] = {
                "description": data.get("extract", ""),
                "image_url": (data.get("thumbnail") or {}).get("source", ""),
                "url": (data.get("content_urls") or {}).get("desktop", {}).get("page", ""),
                "title": data.get("title", title),
            }
        if i % CHECKPOINT_EVERY == 0:
            write_json_atomic(path, cache)
            print(f"  {i}/{len(todo)}")
        time.sleep(DELAY_S)
    if todo:
        write_json_atomic(path, cache)
    return {t: cache.get(t) for t in titles}


def title_from_url(url: str) -> str:
    """'https://en.wikipedia.org/wiki/English_language' -> 'English language'."""
    return urllib.parse.unquote(url.rsplit("/wiki/", 1)[1]).replace("_", " ")


def info_entry(summary: dict | None) -> dict | None:
    """A summary in `info.json`'s shape, or None to leave the node without one."""
    if not summary or not summary.get("description"):
        return None
    entry = {"description": summary["description"].strip()}
    if summary.get("image_url"):
        entry["image_url"] = summary["image_url"]
    if summary.get("url"):
        entry["url"] = summary["url"]
        entry["url_title"] = f"{summary['title']} on Wikipedia"
    return entry
