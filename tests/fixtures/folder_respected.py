"""Custom folder must actually be used (regression: it was ignored)."""
import os
import sys
import cool_cache
from cool_cache import cache

cache_dir = sys.argv[1]
legacy = os.path.abspath("cache.ignore")
legacy_pre = set(os.listdir(legacy)) if os.path.isdir(legacy) else set()

@cache(folder=cache_dir)
def f(x):
    return x + 100

f(1); f(2); f(3)
if cool_cache.worker_que is not None:
    cool_cache.worker_que.join()

pickles = [n for n in os.listdir(cache_dir) if n.endswith(".pickle")]
assert len(pickles) == 1, f"custom folder got {pickles}"

legacy_post = set(os.listdir(legacy)) if os.path.isdir(legacy) else set()
leaked = legacy_post - legacy_pre
assert not leaked, f"leaked into legacy cache.ignore/: {leaked}"
print("OK folder_respected")
