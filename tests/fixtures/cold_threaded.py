"""Concurrent cold-storage calls must not crash (regression: deepcopy race)."""
import sys
import threading
import cool_cache
from cool_cache import cache

cache_dir = sys.argv[1]

@cache(folder=cache_dir)
def f(x):
    return x + 1

errors = []
def worker(i):
    try:
        for j in range(50):
            k = (i + j) % 7
            assert f(k) == k + 1
    except Exception as err:
        errors.append(err)

threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
for t in threads: t.start()
for t in threads: t.join()

if cool_cache.worker_que is not None:
    cool_cache.worker_que.join()
assert not errors, errors
print("OK cold_threaded")
