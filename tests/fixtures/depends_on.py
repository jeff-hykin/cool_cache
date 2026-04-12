"""depends_on: changes to external state must bust the cache."""
from cool_cache import cache

state = {"v": 0}
calls = []

@cache(folder=None, depends_on=lambda: [state["v"]])
def f(x):
    calls.append((state["v"], x))
    return (state["v"], x)

assert f(1) == (0, 1)
assert f(1) == (0, 1)
state["v"] = 1
assert f(1) == (1, 1)
assert f(1) == (1, 1)
state["v"] = 2
assert f(1) == (2, 1)
assert calls == [(0, 1), (1, 1), (2, 1)], calls
print("OK depends_on")
