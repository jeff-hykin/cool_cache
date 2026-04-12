"""watch_attributes: both list and callable forms."""
from cool_cache import cache

class ListForm:
    def __init__(self, a, b):
        self.a = a
        self.b = b

    @cache(folder=None, watch_attributes=["a"])
    def work(self, x):
        return (self.a, self.b, x)

t = ListForm(1, 100)
first = t.work(0)
t.b = 999  # untracked -> still a cache hit
assert t.work(0) == first
t.a = 2    # tracked -> recompute
assert t.work(0) != first
assert t.work(0) == (2, 999, 0)

class CallableForm:
    def __init__(self, a, b):
        self.a = a
        self.b = b

    @cache(folder=None, watch_attributes=lambda self: [self.a])
    def work(self, x):
        return (self.a, self.b, x)

u = CallableForm(1, 100)
first_u = u.work(0)
u.b = 42
assert u.work(0) == first_u
u.a = 9
assert u.work(0) != first_u
print("OK watch_attributes")
