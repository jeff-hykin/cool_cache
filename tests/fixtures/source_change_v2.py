"""Second version of `compute` — different body, so a distinct pickle must be written."""
import os
import sys
import cool_cache
from cool_cache import cache

cache_dir = sys.argv[1]

@cache(folder=cache_dir)
def compute(x):
    return x + 2  # body differs from v1

assert compute(5) == 7
assert compute(5) == 7
if cool_cache.worker_que is not None:
    cool_cache.worker_que.join()

pickles = [n for n in os.listdir(cache_dir) if n.endswith(".pickle")]
assert len(pickles) == 2, f"expected 2 distinct pickles after source change, got {pickles}"
print("OK source_change_v2")
