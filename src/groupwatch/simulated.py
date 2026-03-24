from __future__ import annotations

import asyncio
import random
import zlib
from collections import defaultdict
from datetime import datetime

from .models import Checkpoint, Group, GroupUnavailable, Post

AUTHORS = ["Анна К.", "Игорь П.", "Marta S.", "Олег В.", "Dmitry L.", "Светлана Р.", "Ahmed N.", "Юлия Т."]
TOPICS = [
    "Ищу подрядчика на ремонт квартиры, бюджет обсуждаем",
    "Продаю велосипед, почти новый, самовывоз",
    "Кто может посоветовать бухгалтера для ИП?",
    "Сдаётся студия у метро, без комиссии",
    "Нужен дизайнер на разовый проект, пишите в личку",
    "Отдам даром детские вещи 2-4 года",
    "Подскажите хорошего стоматолога в районе",
    "Ищем менеджера по продажам, удалёнка",
]


def demo_groups(count: int) -> list[Group]:
    return [
        Group(url=f"https://www.facebook.com/groups/demo{n:04d}", name=f"Demo group {n:04d}")
        for n in range(1, count + 1)
    ]


class SimulatedCollector:
    def __init__(
        self,
        seed: int = 7,
        latency: tuple[float, float] = (0.05, 0.25),
        dead_every: int = 37,
        flaky_rate: float = 0.04,
        checkpoint_account: str | None = None,
        checkpoint_after: int = 25,
    ) -> None:
        self._rng = random.Random(seed)
        self._latency = latency
        self._dead_every = dead_every
        self._flaky_rate = flaky_rate
        self._checkpoint_account = checkpoint_account
        self._checkpoint_after = checkpoint_after
        self._calls: defaultdict[str, int] = defaultdict(int)
        self._counter: defaultdict[str, int] = defaultdict(int)
        self._history: defaultdict[str, list[Post]] = defaultdict(list)

    async def fetch(self, group: Group, account: str) -> list[Post]:
        await asyncio.sleep(self._rng.uniform(*self._latency))
        self._calls[account] += 1
        if account == self._checkpoint_account and self._calls[account] > self._checkpoint_after:
            raise Checkpoint(f"{account}: facebook asked to confirm identity")
        number = int("".join(c for c in group.id if c.isdigit()) or 0)
        if self._dead_every and number % self._dead_every == 0:
            raise GroupUnavailable(f"{group.id}: group is private or removed")
        if self._rng.random() < self._flaky_rate:
            raise GroupUnavailable(f"{group.id}: feed did not load")
        fresh = [self._post(group) for _ in range(self._rng.choice([0, 0, 1, 1, 2, 3]))]
        repeats = self._history[group.id][-2:]
        self._history[group.id].extend(fresh)
        return fresh + repeats

    def _post(self, group: Group) -> Post:
        self._counter[group.id] += 1
        post_id = f"{zlib.crc32(group.id.encode())}{self._counter[group.id]:05d}"
        return Post(
            post_id=post_id,
            group_id=group.id,
            group_name=group.title,
            author=self._rng.choice(AUTHORS),
            text=self._rng.choice(TOPICS),
            url=f"{group.url}/posts/{post_id}",
            collected_at=datetime.now(),
        )
