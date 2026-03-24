from __future__ import annotations

import asyncio
import random
from datetime import datetime
from importlib.resources import files
from pathlib import Path

from .models import Checkpoint, Group, GroupUnavailable, Post

CHECKPOINT_MARKERS = ("/checkpoint/", "/login", "two_step_verification")
EXTRACT_POSTS = files(__package__).joinpath("extract_posts.js").read_text(encoding="utf-8")


def chronological(url: str) -> str:
    joiner = "&" if "?" in url else "?"
    return f"{url.rstrip('/')}{joiner}sorting_setting=CHRONOLOGICAL"


def looks_like_checkpoint(url: str) -> bool:
    return any(marker in url for marker in CHECKPOINT_MARKERS)


class FacebookCollector:
    def __init__(self, profiles: Path, headless: bool = False, scrolls: int = 3) -> None:
        self.profiles = profiles
        self.headless = headless
        self.scrolls = scrolls
        self._playwright = None
        self._contexts: dict = {}

    async def __aenter__(self) -> FacebookCollector:
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        return self

    async def __aexit__(self, *exc) -> None:
        for ctx in self._contexts.values():
            await ctx.close()
        await self._playwright.stop()

    async def _page(self, account: str):
        if account not in self._contexts:
            self._contexts[account] = await self._playwright.chromium.launch_persistent_context(
                str(self.profiles / account),
                headless=self.headless,
                locale="ru-RU",
                viewport={"width": 1280, "height": 900},
            )
        ctx = self._contexts[account]
        return ctx.pages[0] if ctx.pages else await ctx.new_page()

    async def fetch(self, group: Group, account: str) -> list[Post]:
        page = await self._page(account)
        try:
            await page.goto(chronological(group.url), wait_until="domcontentloaded", timeout=45_000)
        except Exception as e:
            raise GroupUnavailable(f"{group.id}: page did not load ({type(e).__name__})") from e
        if looks_like_checkpoint(page.url):
            raise Checkpoint(f"{account}: redirected to {page.url}")
        try:
            await page.wait_for_selector('[role="feed"]', timeout=20_000)
        except Exception as e:
            raise GroupUnavailable(f"{group.id}: feed not found ({type(e).__name__})") from e
        for _ in range(self.scrolls):
            await page.mouse.wheel(0, random.randint(1400, 2200))
            await asyncio.sleep(random.uniform(1.2, 2.5))
        now = datetime.now()
        return [
            Post(
                post_id=raw["postId"],
                group_id=group.id,
                group_name=group.title,
                author=raw["author"],
                text=raw["text"],
                url=raw["url"],
                collected_at=now,
            )
            for raw in await page.evaluate(EXTRACT_POSTS)
        ]


async def login(profiles: Path, account: str) -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(str(profiles / account), headless=False)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto("https://www.facebook.com/")
        closed = asyncio.Event()
        ctx.on("close", lambda *_: closed.set())
        await closed.wait()
