import asyncio

import pytest

from ago.scheduler import IntervalScheduler


def test_scheduler_intervals_and_duplicates():
    scheduler = IntervalScheduler()
    seen = []

    async def handler():
        seen.append("ran")

    scheduler.add("refresh", 10, handler)
    assert asyncio.run(scheduler.tick(now=0)) == []
    assert asyncio.run(scheduler.tick(now=float("inf"))) == ["refresh"]
    assert seen == ["ran"]
    with pytest.raises(ValueError):
        scheduler.add("refresh", 10, handler)
