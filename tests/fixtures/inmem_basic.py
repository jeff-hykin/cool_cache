"""In-memory @cache: same args should only run the body once."""
from cool_cache import cache

real_calls = []

@cache(folder=None)
def add(a, b):
    real_calls.append((a, b))
    return a + b

assert add(1, 2) == 3
assert add(1, 2) == 3
assert add(2, 3) == 5
assert add(1, 2) == 3
assert real_calls == [(1, 2), (2, 3)], real_calls
print("OK inmem_basic")
