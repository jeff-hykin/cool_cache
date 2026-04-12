"""watch_filepaths: touching a watched file must bust the cache."""
import os
import sys
from cool_cache import cache

cache_dir = sys.argv[1]
target = os.path.join(cache_dir, "watched.txt")
with open(target, "w") as fh:
    fh.write("one")

real_calls = []

@cache(folder=None, watch_filepaths=lambda p: [p])
def read_file(p):
    real_calls.append(p)
    with open(p) as fh:
        return fh.read()

assert read_file(target) == "one"
assert read_file(target) == "one"
assert len(real_calls) == 1

with open(target, "w") as fh:
    fh.write("two")

assert read_file(target) == "two"
assert read_file(target) == "two"
assert len(real_calls) == 2
print("OK watch_filepaths")
