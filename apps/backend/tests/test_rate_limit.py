from concurrent.futures import ThreadPoolExecutor

from ago.rate_limit import RateLimiter


def test_fixed_window_limit_and_reset():
    limiter = RateLimiter(limit=2, window_seconds=10)
    assert limiter.allow("user", now=0)
    assert limiter.allow("user", now=1)
    assert not limiter.allow("user", now=2)
    assert limiter.allow("user", now=10)
    assert limiter.allow("other", now=10)


def test_thread_safe_limit():
    limiter = RateLimiter(limit=3)
    with ThreadPoolExecutor(max_workers=10) as pool:
        outcomes = list(pool.map(lambda _: limiter.allow("shared", now=100), range(30)))
    assert sum(outcomes) == 3


def test_bounded_key_cardinality():
    limiter = RateLimiter(limit=1, max_keys=1)
    assert limiter.allow("first", now=1)
    assert not limiter.allow("second", now=1)
    assert limiter.allow("second", now=61)
