"""Concurrent in-memory calls must stay consistent and not raise."""
import threading
from cool_cache import cache

@cache(folder=None)
def f(x):
    return x * x

results = [None] * 200

def worker(i):
    results[i] = f(i % 10)

threads = [threading.Thread(target=worker, args=(i,)) for i in range(200)]
for t in threads: t.start()
for t in threads: t.join()

for i, r in enumerate(results):
    assert r == (i % 10) ** 2, (i, r)
print("OK inmem_threaded")
