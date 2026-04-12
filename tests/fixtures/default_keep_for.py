"""settings.default_keep_for is honored; per-decorator keep_for overrides."""
import time
from cool_cache import cache, settings

settings.default_keep_for = "30ms"
try:
    f_calls = []

    @cache(folder=None)
    def f():
        f_calls.append(time.time())
        return len(f_calls)

    f(); f()
    time.sleep(0.08)
    f()
    assert len(f_calls) == 2, f_calls

    g_calls = []

    @cache(folder=None, keep_for=None)  # override: never expire
    def g():
        g_calls.append(time.time())
        return "v"

    g()
    time.sleep(0.08)
    g()
    assert len(g_calls) == 1, g_calls
finally:
    settings.default_keep_for = None
print("OK default_keep_for")
