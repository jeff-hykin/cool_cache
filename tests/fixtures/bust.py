"""bust=True wipes the persisted pickle on decoration."""
import os
import sys
import cool_cache
from cool_cache import cache

cache_dir = sys.argv[1]
mode = sys.argv[2]  # "first" or "bust"

real_calls = []

def _impl(x):
    real_calls.append(x)
    return x + 1

if mode == "first":
    f = cache(folder=cache_dir)(_impl)
    assert f(10) == 11
    assert f(10) == 11
    assert real_calls == [10], real_calls
    if cool_cache.worker_que is not None:
        cool_cache.worker_que.join()
    pickles = [n for n in os.listdir(cache_dir) if n.endswith(".pickle")]
    assert len(pickles) == 1, pickles
elif mode == "bust":
    f = cache(folder=cache_dir, bust=True)(_impl)
    assert f(10) == 11
    assert real_calls == [10], f"bust did not force recomputation: {real_calls}"
else:
    raise SystemExit(f"unknown mode {mode}")
print(f"OK bust mode={mode}")
