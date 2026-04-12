"""First version of `compute` — different body from v2, different function_id."""
import sys
import cool_cache
from cool_cache import cache

cache_dir = sys.argv[1]

@cache(folder=cache_dir)
def compute(x):
    return x + 1

assert compute(5) == 6
assert compute(5) == 6
if cool_cache.worker_que is not None:
    cool_cache.worker_que.join()
print("OK source_change_v1")
