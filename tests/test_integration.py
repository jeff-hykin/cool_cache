"""
Integration test harness for cool_cache.

Each test case spawns a fixture script from tests/fixtures/ in its own
subprocess with PYTHONPATH pointed at main/. Fixtures apply @cache at
module scope, exercise a scenario, and self-assert; the harness checks
exit code and looks for an "OK" marker on stdout.

Running fixtures as real scripts (instead of inline closures) is what
gives us:
  * true cross-process persistence testing (`persistence.py`,
    `cross_function.py`, `bust.py`, `corrupt_file.py`, `source_change_*.py`)
  * isolation from the test harness's own imported cool_cache module,
    so global state (worker_que, PerFuncCache class attributes) can't
    leak between cases.

Run via: PYTHONPATH=main python3 tests/test_integration.py
     or: ./run/test_integration
"""

import os
import shutil
import subprocess
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
FIXTURES = os.path.join(HERE, "fixtures")
PACKAGE_PATH = os.path.join(REPO, "main")

_RESULTS = []


def run_fixture(name, *args):
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = PACKAGE_PATH + (os.pathsep + existing if existing else "")
    cmd = [sys.executable, os.path.join(FIXTURES, name), *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO,
    )


def assert_success(proc, expected_marker="OK"):
    if proc.returncode != 0 or expected_marker not in proc.stdout:
        raise AssertionError(
            f"fixture failed (exit {proc.returncode})\n"
            f"cmd: {' '.join(proc.args) if hasattr(proc, 'args') else '?'}\n"
            f"--- stdout ---\n{proc.stdout}"
            f"--- stderr ---\n{proc.stderr}"
        )


def fresh_dir():
    return tempfile.mkdtemp(prefix="cool_cache_test_")


def test(name):
    def deco(fn):
        def run():
            try:
                fn()
                _RESULTS.append((name, True, None))
                print(f"  PASS  {name}")
            except AssertionError as err:
                _RESULTS.append((name, False, str(err)))
                print(f"  FAIL  {name}")
                print(str(err))
            except Exception as err:
                _RESULTS.append((name, False, f"{type(err).__name__}: {err}"))
                print(f"  ERROR {name}: {err}")
                traceback.print_exc()
        run._test_name = name
        return run
    return deco


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

@test("inmem_basic fixture")
def t_inmem_basic():
    assert_success(run_fixture("inmem_basic.py"))


@test("cold_basic fixture writes a pickle and hits cache")
def t_cold_basic():
    d = fresh_dir()
    try:
        assert_success(run_fixture("cold_basic.py", d))
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("folder parameter honored (regression)")
def t_folder_respected():
    d = fresh_dir()
    try:
        assert_success(run_fixture("folder_respected.py", d))
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("cold persistence across two fresh processes")
def t_persistence():
    d = fresh_dir()
    try:
        assert_success(run_fixture("persistence.py", d, "first"))
        assert_success(run_fixture("persistence.py", d, "second"))
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("two decorated functions keep distinct caches (class-attr bug)")
def t_isolation():
    d = fresh_dir()
    try:
        assert_success(run_fixture("isolation.py", d))
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("cross-function writes survive the worker dedup (regression)")
def t_cross_function():
    d = fresh_dir()
    try:
        assert_success(run_fixture("cross_function.py", d, "first"))
        # second, fresh process: both functions must load from disk
        assert_success(run_fixture("cross_function.py", d, "second"))
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("(float, payload) values not misread as timestamps (regression)")
def t_float_tuple():
    d = fresh_dir()
    try:
        assert_success(run_fixture("float_tuple.py", d))
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("keep_for expiry refreshes cached entry")
def t_keep_for_expiry():
    assert_success(run_fixture("keep_for_expiry.py"))


@test("keep_for parse errors + all documented units")
def t_keep_for_errors():
    assert_success(run_fixture("keep_for_errors.py"))


@test("settings.default_keep_for with per-decorator override")
def t_default_keep_for():
    assert_success(run_fixture("default_keep_for.py"))


@test("depends_on busts cache on external change")
def t_depends_on():
    assert_success(run_fixture("depends_on.py"))


@test("watch_filepaths busts on file change")
def t_watch_filepaths():
    d = fresh_dir()
    try:
        assert_success(run_fixture("watch_filepaths.py", d))
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("watch_attributes list + callable forms")
def t_watch_attributes():
    assert_success(run_fixture("watch_attributes.py"))


@test("custom_hasher controls the cache key")
def t_custom_hasher():
    assert_success(run_fixture("custom_hasher.py"))


@test("bust=True clears persisted pickle in a fresh process")
def t_bust():
    d = fresh_dir()
    try:
        assert_success(run_fixture("bust.py", d, "first"))
        assert_success(run_fixture("bust.py", d, "bust"))
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("corrupt pickle file is auto-recovered")
def t_corrupt_file():
    d = fresh_dir()
    try:
        assert_success(run_fixture("corrupt_file.py", d))
        # now clobber every persisted pickle to simulate corruption
        for name in os.listdir(d):
            if name.endswith(".pickle"):
                with open(os.path.join(d, name), "wb") as fh:
                    fh.write(b"not a valid pickle")
        # next run must tolerate the bad file and still produce the right value
        assert_success(run_fixture("corrupt_file.py", d))
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("different function sources produce distinct cache files")
def t_source_change():
    d = fresh_dir()
    try:
        assert_success(run_fixture("source_change_v1.py", d))
        assert_success(run_fixture("source_change_v2.py", d))
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("concurrent in-memory calls stay consistent")
def t_inmem_threaded():
    assert_success(run_fixture("inmem_threaded.py"))


@test("concurrent cold-storage calls don't crash")
def t_cold_threaded():
    d = fresh_dir()
    try:
        assert_success(run_fixture("cold_threaded.py", d))
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    all_tests = [
        t_inmem_basic,
        t_cold_basic,
        t_folder_respected,
        t_persistence,
        t_isolation,
        t_cross_function,
        t_float_tuple,
        t_keep_for_expiry,
        t_keep_for_errors,
        t_default_keep_for,
        t_depends_on,
        t_watch_filepaths,
        t_watch_attributes,
        t_custom_hasher,
        t_bust,
        t_corrupt_file,
        t_source_change,
        t_inmem_threaded,
        t_cold_threaded,
    ]
    print(f"running {len(all_tests)} integration tests (each in a subprocess)")
    for t in all_tests:
        t()
    passed = sum(1 for _, ok, _ in _RESULTS if ok)
    failed = [(n, m) for n, ok, m in _RESULTS if not ok]
    print()
    print(f"passed: {passed}/{len(_RESULTS)}")
    if failed:
        print("failures:")
        for name, msg in failed:
            first_line = (msg or "").splitlines()[0] if msg else ""
            print(f"  - {name}: {first_line}")
        sys.exit(1)
    print("all integration tests passed")


if __name__ == "__main__":
    main()
