import asyncio

import pytest

from groupwatch.accounts import AccountPool
from groupwatch.models import NoAccountAvailable


class FakeTime:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    async def sleep(self, seconds):
        self.t += max(seconds, 0)
        await asyncio.sleep(0)


def pool(names, gap=10.0, hourly=100, clock=None):
    clock = clock or FakeTime()
    return AccountPool(names, gap, hourly, clock=clock.now, sleep=clock.sleep, jitter=lambda: 1.0), clock


async def test_one_account_waits_the_gap_between_visits():
    p, clock = pool(["a"], gap=10)
    a = await p.acquire()
    await p.release(a)
    await p.acquire()
    assert clock.t == 10


async def test_idle_account_is_preferred_over_one_still_in_its_gap():
    p, clock = pool(["a", "b"], gap=10)
    first = await p.acquire()
    await p.release(first)
    second = await p.acquire()
    assert second.name != first.name
    assert clock.t == 0


async def test_hourly_cap_holds_the_account_until_the_window_slides():
    p, clock = pool(["a"], gap=0, hourly=2)
    for _ in range(2):
        await p.release(await p.acquire())
    await p.acquire()
    assert clock.t == 3600


async def test_group_is_only_visited_by_accounts_that_are_its_members():
    p, _ = pool(["a", "b"])
    got = await p.acquire(frozenset({"b"}))
    assert got.name == "b"


async def test_checkpointed_account_is_never_handed_out_again():
    p, _ = pool(["a", "b"])
    a = await p.acquire(frozenset({"a"}))
    await p.release(a, blocked="checkpoint")
    assert (await p.acquire()).name == "b"
    with pytest.raises(NoAccountAvailable):
        await p.acquire(frozenset({"a"}))
