"""
Cross-function worker-queue dedup regression.

First run: heavy interleaved writes for fa + fb. Worker must key its dedup
by cache_file_name, not just 'latest item in queue', or fb's write will
be silently dropped.

Second run (fresh process): both functions must load from disk without
recomputing anything.
"""
import os
import sys
import cool_cache
from cool_cache import cache

cache_dir = sys.argv[1]
mode = sys.argv[2]

a_calls = []
b_calls = []

@cache(folder=cache_dir)
def fa(x):
    a_calls.append(x)
    return f"A{x}"

@cache(folder=cache_dir)
def fb(x):
    b_calls.append(x)
    return f"B{x}"

for i in range(20):
    assert fa(i) == f"A{i}"
    assert fb(i) == f"B{i}"

if cool_cache.worker_que is not None:
    cool_cache.worker_que.join()

pickles = sorted(n for n in os.listdir(cache_dir) if n.endswith(".pickle"))

if mode == "first":
    assert a_calls == list(range(20)), a_calls
    assert b_calls == list(range(20)), b_calls
    assert len(pickles) == 2, pickles
elif mode == "second":
    assert a_calls == [], f"fa did not persist: {a_calls}"
    assert b_calls == [], f"fb did not persist (worker dedup bug?): {b_calls}"
    assert len(pickles) == 2, pickles
else:
    raise SystemExit(f"unknown mode {mode}")
print(f"OK cross_function mode={mode}")
