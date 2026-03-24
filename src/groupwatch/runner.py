from __future__ import annotations

import asyncio
from collections import Counter, deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from .accounts import AccountPool
from .models import Checkpoint, ErrorRecord, Group, NoAccountAvailable, Post
from .sinks import Sink
from .store import Store


class Collector(Protocol):
    async def fetch(self, group: Group, account: str) -> list[Post]: ...


@dataclass
class RoundStats:
    total: int
    done: int = 0
    failed: int = 0
    seen: int = 0
    new: int = 0
    retries: int = 0
    errors: Counter[str] = field(default_factory=Counter)
    latest: deque[Post] = field(default_factory=lambda: deque(maxlen=8))
    started: datetime = field(default_factory=datetime.now)


class Runner:
    def __init__(
        self,
        pool: AccountPool,
        collector: Collector,
        store: Store,
        sinks: Sequence[Sink],
        max_attempts: int = 3,
    ) -> None:
        self.pool = pool
        self.collector = collector
        self.store = store
        self.sinks = sinks
        self.max_attempts = max_attempts

    def _error(self, stats: RoundStats, group: Group, account: str, kind: str, detail: str) -> None:
        record = ErrorRecord(datetime.now(), group.id, account, kind, detail)
        stats.errors[kind] += 1
        self.store.log_error(record)
        for sink in self.sinks:
            sink.write_error(record)

    async def _visit(self, queue: asyncio.Queue, stats: RoundStats, group: Group, attempt: int) -> None:
        try:
            account = await self.pool.acquire(group.members)
        except NoAccountAvailable as e:
            stats.failed += 1
            self._error(stats, group, "", "no_account", str(e))
            return
        try:
            posts = await self.collector.fetch(group, account.name)
        except Checkpoint as e:
            await self.pool.release(account, blocked="checkpoint")
            self._error(stats, group, account.name, "checkpoint", str(e))
            queue.put_nowait((group, attempt))
            return
        except Exception as e:
            await self.pool.release(account)
            if attempt < self.max_attempts:
                stats.retries += 1
                queue.put_nowait((group, attempt + 1))
            else:
                stats.failed += 1
                self._error(stats, group, account.name, type(e).__name__, str(e))
            return
        await self.pool.release(account)
        fresh = self.store.remember(posts)
        for sink in self.sinks:
            sink.write_posts(fresh)
        stats.done += 1
        stats.seen += len(posts)
        stats.new += len(fresh)
        stats.latest.extend(fresh)

    async def _worker(self, queue: asyncio.Queue, stats: RoundStats) -> None:
        while True:
            group, attempt = await queue.get()
            try:
                await self._visit(queue, stats, group, attempt)
            finally:
                queue.task_done()

    async def run_round(self, groups: Sequence[Group], stats: RoundStats | None = None) -> RoundStats:
        stats = stats or RoundStats(total=len(groups))
        queue: asyncio.Queue = asyncio.Queue()
        for g in groups:
            queue.put_nowait((g, 1))
        workers = [
            asyncio.create_task(self._worker(queue, stats)) for _ in range(len(self.pool.accounts))
        ]
        try:
            await queue.join()
        finally:
            for w in workers:
                w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
        return stats
