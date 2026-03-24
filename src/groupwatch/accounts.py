from __future__ import annotations

import asyncio
import random
import time
from collections import deque
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field

from .models import NoAccountAvailable

HOUR = 3600.0


@dataclass
class Account:
    name: str
    min_gap: float
    hourly_limit: int
    next_free: float = 0.0
    busy: bool = False
    blocked: str | None = None
    requests: int = 0
    recent: deque[float] = field(default_factory=deque)

    def ready_at(self, now: float) -> float:
        while self.recent and now - self.recent[0] >= HOUR:
            self.recent.popleft()
        window = self.recent[0] + HOUR if len(self.recent) >= self.hourly_limit else 0.0
        return max(self.next_free, window)


class AccountPool:
    def __init__(
        self,
        names: Iterable[str],
        min_gap: float,
        hourly_limit: int,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[], float] = lambda: random.uniform(0.7, 1.3),
    ) -> None:
        self.accounts = {n: Account(n, min_gap, hourly_limit) for n in names}
        if not self.accounts:
            raise ValueError("at least one account is required")
        self._clock = clock
        self._sleep = sleep
        self._jitter = jitter
        self._changed = asyncio.Condition()

    def _eligible(self, members: frozenset[str]) -> list[Account]:
        return [
            a
            for a in self.accounts.values()
            if a.blocked is None and (not members or a.name in members)
        ]

    async def acquire(self, members: frozenset[str] = frozenset()) -> Account:
        async with self._changed:
            while True:
                eligible = self._eligible(members)
                if not eligible:
                    raise NoAccountAvailable(", ".join(sorted(members)) or "all accounts blocked")
                idle = [a for a in eligible if not a.busy]
                if idle:
                    now = self._clock()
                    account = min(idle, key=lambda a: a.ready_at(now))
                    account.busy = True
                    break
                await self._changed.wait()
        wait = account.ready_at(self._clock()) - self._clock()
        if wait > 0:
            await self._sleep(wait)
        return account

    async def release(self, account: Account, blocked: str | None = None) -> None:
        now = self._clock()
        account.requests += 1
        account.recent.append(now)
        account.next_free = now + account.min_gap * self._jitter()
        account.busy = False
        if blocked:
            account.blocked = blocked
        async with self._changed:
            self._changed.notify_all()

    def active(self) -> int:
        return sum(1 for a in self.accounts.values() if a.blocked is None)
