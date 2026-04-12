"""keep_for expiry: entry refreshes after the configured TTL."""
import time
from cool_cache import cache

real_calls = []

@cache(folder=None, keep_for="30ms")
def f(x):
    real_calls.append(x)
    return time.time()

first = f("x")
second = f("x")
assert first == second, "should be cached immediately"

time.sleep(0.08)
third = f("x")
assert third != first, "should have expired"
assert len(real_calls) == 2, real_calls
print("OK keep_for_expiry")
