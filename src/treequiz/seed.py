"""Shareable game seeds. TaxoQuiz's format, unchanged but for the hash prefixes.

A seed names one round: the same seed always gives the same secret, so two
people can play the same round apart. The daily is this mechanism with the body
derived from the date, which is what makes today's round the same for everyone.

Format `FFFF-BBBBBB`:

- `FFFF` fingerprints the dataset's leaf list, so a seed made on one tree is
  **rejected** on another rather than silently naming a different leaf. With
  several datasets in one app this does a second job: a seed alone says which
  dataset it belongs to, so a pasted seed can switch to the right one.
- `BBBBBB` is the body: random for practice, from the date for the daily.

The alphabet excludes I, L, O and U, so a seed survives being read aloud.

Seeds are deliberately not secret: the mapping is a hash over a public list.
That is the price of needing no server.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import date

from .tree import label_of

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
FINGERPRINT_LEN = 4
BODY_LEN = 6


def _encode(digest: bytes, length: int) -> str:
    n = int.from_bytes(digest, "big")
    out = []
    for _ in range(length):
        n, rem = divmod(n, len(ALPHABET))
        out.append(ALPHABET[rem])
    return "".join(reversed(out))


def fingerprint(leaves: list[dict]) -> str:
    """A short tag over the leaves' labels in tree order: any change to what can
    be guessed, or to its order, changes the tag and retires old seeds."""
    h = hashlib.sha256()
    for leaf in leaves:
        h.update(label_of(leaf).encode())
        h.update(b"\n")
    return _encode(h.digest(), FINGERPRINT_LEN)


def body_for_date(day: date) -> str:
    return _encode(hashlib.sha256(f"treequiz-daily:{day.isoformat()}".encode()).digest(), BODY_LEN)


def new_body() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(BODY_LEN))


def make_seed(leaves: list[dict], body: str | None = None, *, day: date | None = None) -> str:
    if day is not None:
        body = body_for_date(day)
    return f"{fingerprint(leaves)}-{body or new_body()}"


def normalise(seed: str) -> str:
    """Accept what a person types: any case, spaces, a missing dash."""
    cleaned = "".join(c for c in seed.upper() if c in ALPHABET)
    if len(cleaned) != FINGERPRINT_LEN + BODY_LEN:
        raise ValueError(
            f"'{seed}' is not a seed — expected {FINGERPRINT_LEN + BODY_LEN} "
            f"characters like ABCD-234567."
        )
    return f"{cleaned[:FINGERPRINT_LEN]}-{cleaned[FINGERPRINT_LEN:]}"


def body_of(seed: str, leaves: list[dict]) -> str:
    """A seed's body, once its tag is checked against the tree. Raises
    ValueError for a seed made on another tree."""
    seed = normalise(seed)
    fp, body = seed.split("-")
    expected = fingerprint(leaves)
    if fp != expected:
        raise ValueError(
            f"Seed '{seed}' is for a different dataset (its tag is {fp}, "
            f"this one is {expected})."
        )
    return body


def draw(key: str, n: int) -> int:
    """A number in 0..n-1 from a hash of `key`: the one source of chance a
    seed may use, since both engines must draw the same."""
    return int.from_bytes(hashlib.sha256(key.encode()).digest(), "big") % n


def resolve(seed: str, leaves: list[dict]) -> dict:
    """The leaf a seed names. Raises ValueError for a seed made on another tree."""
    return leaves[draw(f"treequiz-seed:{body_of(seed, leaves)}", len(leaves))]
