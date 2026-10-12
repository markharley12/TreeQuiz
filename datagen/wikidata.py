"""Querying Wikidata, for the builders that read it with SPARQL.

Two endpoints:

- **query.wikidata.org**, Wikidata's own, for everything that starts from a
  known list of items: `batched` sends them `BATCH` at a time in a VALUES
  clause, which it answers quickly.
- **QLever** (qlever.dev, University of Freiburg), for the one kind of query
  Wikidata's endpoint cannot answer inside its 60 seconds: a scan over
  millions of items by a property and their sitelinks — every species of
  plant, for instance. QLever answers it in about two seconds. Its copy of
  Wikidata is a few days old, which a build cached on disk does not mind.

QLever's dialect differs in small ways: a variable named `?label` came back
empty where `?l` did not, and a VALUES clause beside a property path
returned nothing. Keep its queries plain.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from common import USER_AGENT

WDQS = "https://query.wikidata.org/sparql"
QLEVER = "https://qlever.dev/api/wikidata"
BATCH = 200
# QLever has no default prefixes.
PREFIXES = """PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX schema: <http://schema.org/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
"""


def sparql(query: str, retries: int = 4, endpoint: str = WDQS) -> list[dict]:
    """The bindings a query returns, retried with backoff on the errors a busy
    endpoint gives."""
    if endpoint == QLEVER:
        query = PREFIXES + query
    data = urllib.parse.urlencode({"query": query}).encode()
    req = urllib.request.Request(endpoint, data=data, headers={
        "User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.load(resp)["results"]["bindings"]
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            if attempt == retries - 1:
                raise
            time.sleep(5 * 2 ** attempt)
    raise AssertionError("unreachable")


def qlever(query: str) -> list[dict]:
    return sparql(query, endpoint=QLEVER)


def qid(b: dict, key: str) -> str | None:
    """The QID bound to `key`, or None."""
    v = b.get(key, {}).get("value")
    return v.rsplit("/", 1)[1] if v else None


def title(b: dict, key: str = "enwiki") -> str | None:
    """An English Wikipedia article's title, from its URL bound to `key`."""
    v = b.get(key, {}).get("value")
    return urllib.parse.unquote(v.rsplit("/wiki/", 1)[1]).replace("_", " ") if v else None


def batched(query: str, qids: list[str]) -> list[dict]:
    """`query`'s `%s` filled with `BATCH` items at a time; every row."""
    rows = []
    for i in range(0, len(qids), BATCH):
        rows += sparql(query % " ".join(f"wd:{q}" for q in qids[i:i + BATCH]))
        time.sleep(1)
    return rows
