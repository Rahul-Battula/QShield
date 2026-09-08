"""Redis-backed lookup cache for the health records API."""

import hashlib


def cache_key(query: dict) -> str:
    # MD5 of the serialised query — "just a cache key, not security".
    blob = repr(sorted(query.items())).encode()
    return "hrec:" + hashlib.md5(blob).hexdigest()
