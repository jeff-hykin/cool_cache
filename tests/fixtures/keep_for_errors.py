"""keep_for parse-error paths and full unit table."""
from cool_cache import parse_keep_for_seconds

for bad in [10, "10 fortnights", "abcs", ""]:
    try:
        parse_keep_for_seconds(bad)
    except ValueError:
        continue
    raise AssertionError(f"expected ValueError for keep_for={bad!r}")

cases = {
    "500ms": 0.5,
    "2s": 2,
    "1.5h": 1.5 * 3600,
    "3d": 3 * 86400,
    "1mo": 30 * 86400,
    "2y": 2 * 365 * 86400,
}
for text, expected in cases.items():
    got = parse_keep_for_seconds(text)
    assert abs(got - expected) < 1e-6, f"{text}: got {got}, expected {expected}"

assert parse_keep_for_seconds(None) is None
print("OK keep_for_errors")
