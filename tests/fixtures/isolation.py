"""Two decorated functions must not share cache state (class-attr bug)."""
import os
import sys
import cool_cache
from cool_cache import cache

cache_dir = sys.argv[1]

@cache(folder=cache_dir)
def fa(x):
    return ("A", x)

@cache(folder=cache_dir)
def fb(x):
    return ("B", x)

assert fa(1) == ("A", 1)
assert fb(1) == ("B", 1)
assert fa(2) == ("A", 2)
assert fb(2) == ("B", 2)
# repeated calls should all hit the correct function's cache
assert fa(1) == ("A", 1)
assert fb(1) == ("B", 1)
assert fa(2) == ("A", 2)
assert fb(2) == ("B", 2)

if cool_cache.worker_que is not None:
    cool_cache.worker_que.join()
pickles = sorted(n for n in os.listdir(cache_dir) if n.endswith(".pickle"))
assert len(pickles) == 2, f"expected 2 distinct pickles, got {pickles}"
print("OK isolation")
