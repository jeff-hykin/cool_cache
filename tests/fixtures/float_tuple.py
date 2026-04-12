"""Regression: cached (float, payload) values must not be misread as timestamps."""
import sys
import cool_cache
from cool_cache import cache

cache_dir = sys.argv[1]

real_calls_mem = []

@cache(folder=None)
def f_mem(x):
    real_calls_mem.append(x)
    return (123.456, {"payload": x})

assert f_mem("k") == (123.456, {"payload": "k"})
assert f_mem("k") == (123.456, {"payload": "k"})
assert f_mem("k") == (123.456, {"payload": "k"})
assert real_calls_mem == ["k"], real_calls_mem

real_calls_cold = []

@cache(folder=cache_dir)
def f_cold(x):
    real_calls_cold.append(x)
    return (9.99, ("nested", x))

assert f_cold(1) == (9.99, ("nested", 1))
assert f_cold(1) == (9.99, ("nested", 1))
assert real_calls_cold == [1], real_calls_cold

if cool_cache.worker_que is not None:
    cool_cache.worker_que.join()
print("OK float_tuple")
