import pytest

from app.core import rate_limit
from app.core.exceptions import TooManyRequestsError
from app.core.rate_limit import RateLimiter


def test_blocks_after_limit_with_retry_after() -> None:
    limiter = RateLimiter("login", limit=3, window_seconds=60)
    for _ in range(3):
        limiter.check("ip-1")
    with pytest.raises(TooManyRequestsError) as error:
        limiter.check("ip-1")
    assert error.value.status_code == 429
    assert int(error.value.headers["Retry-After"]) >= 1  # type: ignore[index]


def test_keys_are_independent() -> None:
    limiter = RateLimiter("login", limit=1, window_seconds=60)
    limiter.check("ip-1")
    limiter.check("ip-2")


def test_window_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [1000.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: now[0])
    limiter = RateLimiter("login", limit=1, window_seconds=60)
    limiter.check("ip-1")
    with pytest.raises(TooManyRequestsError):
        limiter.check("ip-1")
    now[0] += 61
    limiter.check("ip-1")
