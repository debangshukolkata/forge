Create a Python module `cache.py` with a class `TTLCache` that keeps at most `capacity` entries, each valid for `ttl` seconds.

`TTLCache(capacity: int, ttl: float, clock=time.monotonic)`
- `clock` is a function returning the current time in seconds; tests will pass a fake one.
- `capacity < 1` or `ttl <= 0` raises `ValueError`.

Methods:
- `set(key, value)`: stores the value; its lifetime starts now (setting an existing key restarts the lifetime). When the cache is over capacity, first drop expired entries; if it is still over capacity, drop the least recently used live entry.
- `get(key, default=None)`: returns the value if the key is present and not expired, otherwise `default`. A successful `get` counts as a use of the key. An entry is expired when `clock() - stored_at >= ttl`; reading does not extend its lifetime.
- `delete(key)`: removes the key; returns True if it was present and live, False otherwise.
- `__len__`: number of live (non-expired) entries.
- `__contains__(key)`: True for a live key; does not count as a use.

Write tests for it too. Use only the standard library.
