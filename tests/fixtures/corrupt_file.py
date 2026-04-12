"""A corrupt pickle file must be removed and the cache recomputed."""
import sys
import cool_cache
from cool_cache import cache

cache_dir = sys.argv[1]
real_calls = []

def _impl(x):
    real_calls.append(x)
    return x * 3

f = cache(folder=cache_dir)(_impl)
assert f(7) == 21
assert real_calls == [7]
if cool_cache.worker_que is not None:
    cool_cache.worker_que.join()
print("OK corrupt_file")
