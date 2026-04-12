"""custom_hasher: only the selected components participate in the key."""
from cool_cache import cache

calls = []

@cache(folder=None, custom_hasher=lambda a, b: [a])
def f(a, b):
    calls.append((a, b))
    return (a, b)

f(1, "x")
f(1, "y")  # b ignored by hasher -> cache hit
f(1, "z")
assert len(calls) == 1, calls
f(2, "q")
assert len(calls) == 2, calls
f(2, "different")  # still a=2 -> cache hit
assert len(calls) == 2, calls
print("OK custom_hasher")
