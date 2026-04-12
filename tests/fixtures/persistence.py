"""Cross-process persistence: second fresh process must hit disk cache."""
import sys
import cool_cache
from cool_cache import cache

cache_dir = sys.argv[1]
mode = sys.argv[2]  # "first" or "second"

real_calls = []

@cache(folder=cache_dir)
def slow_sum(a, b):
    real_calls.append((a, b))
    return a + b + 1000

assert slow_sum(3, 4) == 1007
assert slow_sum(3, 4) == 1007
assert slow_sum(5, 6) == 1011

if cool_cache.worker_que is not None:
    cool_cache.worker_que.join()

if mode == "first":
    assert real_calls == [(3, 4), (5, 6)], real_calls
elif mode == "second":
    assert real_calls == [], (
        f"expected persistent cache hit in fresh process, "
        f"but recomputed: {real_calls}"
    )
else:
    raise SystemExit(f"unknown mode {mode}")
print(f"OK persistence mode={mode}")
