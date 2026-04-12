"""Cold-storage @cache: caches to disk, pickle appears in folder."""
import os
import sys
import cool_cache
from cool_cache import cache

cache_dir = sys.argv[1]
real_calls = []

@cache(folder=cache_dir)
def add(a, b):
    real_calls.append((a, b))
    return a + b

assert add(1, 2) == 3
assert add(1, 2) == 3  # cache hit
assert add(4, 5) == 9
assert add(4, 5) == 9  # cache hit
assert real_calls == [(1, 2), (4, 5)], real_calls

if cool_cache.worker_que is not None:
    cool_cache.worker_que.join()

files = [name for name in os.listdir(cache_dir) if name.endswith(".pickle")]
assert len(files) == 1, f"expected 1 pickle, found {files}"
print("OK cold_basic")
